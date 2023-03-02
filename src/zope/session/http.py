##############################################################################
#
# Copyright (c) 2004 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Session implementation using cookies
"""
import hmac
import logging
import random
import re
import time
from email.utils import formatdate
from hashlib import sha1
from time import process_time

import zope.location
from persistent import Persistent
from zope.i18nmessageid import ZopeMessageFactory as _
from zope.interface import implementer
from zope.publisher.interfaces.http import IHTTPApplicationRequest
from zope.publisher.interfaces.http import IHTTPRequest
from zope.schema.fieldproperty import FieldProperty

from zope import component
from zope import schema
from zope.session.interfaces import IClientIdManager
from zope.session.session import digestEncode


logger = logging.getLogger(__name__)


class MissingClientIdException(Exception):
    """No ClientId found in Request"""


class ICookieClientIdManager(IClientIdManager):
    """
    Manages client identification using a cookie.

    .. seealso:: `CookieClientIdManager`
    """

    namespace = schema.ASCIILine(
        title=_('Cookie Name'),
        description=_(
            "Name of cookie used to maintain state. "
            "Must be unique to the site domain name, and only contain "
            "ASCII letters, digits and '_'"
        ),
        required=True,
        min_length=1,
        max_length=30,
        constraint=re.compile(r"^[\d\w_]+$").search,
    )

    cookieLifetime = schema.Int(
        title=_('Cookie Lifetime'),
        description=_(
            "Number of seconds until the browser expires the cookie. "
            "Leave blank expire the cookie when the browser is quit. "
            "Set to 0 to never expire. "
        ),
        min=0,
        required=False,
        default=None,
        missing_value=None,
    )

    thirdparty = schema.Bool(
        title=_('Third party cookie'),
        description=_(
            "Is a third party issuing the identification cookie? "
            "Servers like Apache or Nginx have capabilities to issue "
            "identification cookies too. If Third party cookies are "
            "beeing used, Zope will never send a cookie back, just check "
            "for them."
        ),
        required=False,
        default=False,
    )

    domain = schema.TextLine(
        title=_('Effective domain'),
        description=_(
            "An identification cookie can be restricted to a specific domain "
            "using this option. This option sets the ``domain`` attribute "
            "for the cookie header. It is useful for setting one "
            "identification cookie for multiple subdomains. So if this "
            "option is set to ``.example.org``, the cookie will be available "
            "for subdomains like ``yourname.example.org``. "
            "Note that if you set this option to some domain, the "
            "identification cookie won't be available for other domains, so, "
            "for example you won't be able to login using the "
            "SessionCredentials plugin via another domain."),
        required=False,
    )

    secure = schema.Bool(
        title=_('Request Secure communication'),
        required=False,
        default=False,
    )

    postOnly = schema.Bool(
        title=_('Only set cookie on POST requests'),
        required=False,
        default=False,
    )

    httpOnly = schema.Bool(
        title=_('The cookie cannot be accessed through client side scripts'),
        required=False,
        default=False,
    )


@implementer(ICookieClientIdManager)
class CookieClientIdManager(zope.location.Location, Persistent):
    """
    Default implementation of `ICookieClientIdManager`.
    """

    thirdparty = FieldProperty(ICookieClientIdManager['thirdparty'])
    cookieLifetime = FieldProperty(ICookieClientIdManager['cookieLifetime'])
    secure = FieldProperty(ICookieClientIdManager['secure'])
    postOnly = FieldProperty(ICookieClientIdManager['postOnly'])
    domain = FieldProperty(ICookieClientIdManager['domain'])
    namespace = FieldProperty(ICookieClientIdManager['namespace'])
    httpOnly = FieldProperty(ICookieClientIdManager['httpOnly'])

    def __init__(self, namespace=None, secret=None):
        """Create the cookie-based client id manager

        We can pass namespace (cookie name) and/or secret string
        for generating client unique ids.

        If we don't pass either of them, they will be generated
        automatically, this is very handy when storing id manager
        in the persistent database, so they are saved between
        application restarts.

          >>> manager1 = CookieClientIdManager()
          >>> len(manager1.namespace) > 0
          True
          >>> len(manager1.secret) > 0
          True

        We can specify cookie name by hand.

          >>> manager2 = CookieClientIdManager('service_cookie')
          >>> manager2.namespace
          'service_cookie'

        If we want to use `CookieClientIdManager` object as a non-persistent
        utility, we need to specify some constant secret, so it won't be
        recreated on each application restart.

          >>> manager3 = CookieClientIdManager(secret='some_secret')
          >>> manager3.secret
          'some_secret'

        Of course, we can specify both cookie name and secret.

          >>> manager4 = CookieClientIdManager('service_cookie', 'some_secret')
          >>> manager4.namespace
          'service_cookie'
          >>> manager4.secret
          'some_secret'

        """
        if namespace is None:
            namespace = "zope3_cs_%x" % (int(time.time()) - 1000000000)
        if secret is None:
            secret = '%.20f' % random.random()
        self.namespace = namespace
        self.secret = secret

    def getClientId(self, request):
        """Get the client id

        This creates one if necessary:

          >>> from io import BytesIO
          >>> from zope.publisher.http import HTTPRequest
          >>> request = HTTPRequest(BytesIO(), {})
          >>> bim = CookieClientIdManager()
          >>> id = bim.getClientId(request)
          >>> id == bim.getClientId(request)
          True

        The id is retained accross requests:

          >>> request2 = HTTPRequest(BytesIO(), {})
          >>> request2._cookies = dict(
          ...   [(name, cookie['value'])
          ...    for (name, cookie) in request.response._cookies.items()
          ...   ])
          >>> id == bim.getClientId(request2)
          True
          >>> bool(id)
          True

        Note that the return value of this function is a string, not
        an `.IClientId`. This is because this method is used to implement
        the `.IClientId` Adapter.

          >>> type(id) == str
          True

        We don't set the client id unless we need to, so, for example,
        the second response doesn't have cookies set:

          >>> request2.response._cookies
          {}

        An exception to this is if the ``cookieLifetime`` is set to a
        non-zero integer value, in which case we do set it on every
        request, regardless of when it was last set:

          >>> bim.cookieLifetime = 3600 # one hour
          >>> id == bim.getClientId(request2)
          True

          >>> bool(request2.response._cookies)
          True

        If the ``postOnly`` attribute is set to a true value, then cookies
        will only be set on POST requests.

          >>> bim.postOnly = True
          >>> request = HTTPRequest(BytesIO(), {})
          >>> bim.getClientId(request)
          Traceback (most recent call last):
          ...
          zope.session.http.MissingClientIdException

          >>> print(request.response.getCookie(bim.namespace))
          None

          >>> request = HTTPRequest(BytesIO(), {'REQUEST_METHOD': 'POST'})
          >>> id = bim.getClientId(request)
          >>> id == bim.getClientId(request)
          True

          >>> request.response.getCookie(bim.namespace) is not None
          True

          >>> bim.postOnly = False

        It's also possible to use third-party cookies. E.g. Apache ``mod_uid``
        or Nginx ``ngx_http_userid_module`` are able to issue user tracking
        cookies in front of Zope. In case ``thirdparty`` is activated Zope may
        not set a cookie.

          >>> bim.thirdparty = True
          >>> request = HTTPRequest(BytesIO(), {})
          >>> bim.getClientId(request)
          Traceback (most recent call last):
          ...
          zope.session.http.MissingClientIdException

          >>> print(request.response.getCookie(bim.namespace))
          None

        """
        sid = self.getRequestId(request)
        if sid is None:
            if (self.thirdparty
                    or (self.postOnly and request.method != 'POST')):
                raise MissingClientIdException

            sid = self.generateUniqueId()
            self.setRequestId(request, sid)
        elif (not self.thirdparty) and self.cookieLifetime:
            # If we have a finite cookie lifetime, then set the cookie
            # on each request to avoid losing it.
            self.setRequestId(request, sid)

        return sid

    def generateUniqueId(self):
        """Generate a new, random, unique id.

          >>> bim = CookieClientIdManager()
          >>> id1 = bim.generateUniqueId()
          >>> id2 = bim.generateUniqueId()
          >>> id1 != id2
          True

        """
        data = "{:.20f}{:.20f}{:.20f}".format(
            random.random(), time.time(), process_time())
        digest = sha1(data.encode()).digest()
        s = digestEncode(digest)
        # we store a HMAC of the random value together with it, which makes
        # our session ids unforgeable.
        mac = hmac.new(self.secret.encode(), s, digestmod=sha1).digest()
        return (s + digestEncode(mac)).decode()

    def getRequestId(self, request):
        """Return the browser id encoded in request as a string

        Return `None` if an id is not set.

        For example:

          >>> from io import BytesIO
          >>> from zope.publisher.http import HTTPRequest
          >>> request = HTTPRequest(BytesIO(), {}, None)
          >>> bim = CookieClientIdManager()

        Because no cookie has been set, we get no id:

          >>> bim.getRequestId(request) is None
          True

        We can set an id:

          >>> id1 = bim.generateUniqueId()
          >>> bim.setRequestId(request, id1)

        And get it back:

          >>> bim.getRequestId(request) == id1
          True

        When we set the request id, we also set a response cookie.  We
        can simulate getting this cookie back in a subsequent request:

          >>> request2 = HTTPRequest(BytesIO(), {}, None)
          >>> request2._cookies = dict(
          ...   [(name, cookie['value'])
          ...    for (name, cookie) in request.response._cookies.items()
          ...   ])

        And we get the same id back from the new request:

          >>> bim.getRequestId(request) == bim.getRequestId(request2)
          True

        We allow unicode values as input, even though we work in the
        byte-based realm of HMAC:

          >>> id_uni = bim.generateUniqueId()
          >>> bim.setRequestId(request, id_uni)
          >>> bim.getRequestId(request) == id_uni
          True

        If the cookie data has been tampered with (doesn't correspond to our
        secret), we will refuse to return an id:

          >>> cookie = request.response.getCookie(bim.namespace)
          >>> cookie['value'] = 'x' * len(cookie['value'])
          >>> bim.getRequestId(request) is None
          True

        If another server is managing the ClientId cookies (Apache, Nginx)
        we're returning their value without checking:

          >>> bim.namespace = 'uid'
          >>> bim.thirdparty = True
          >>> request3 = HTTPRequest(BytesIO(), {}, None)
          >>> request3._cookies = {'uid': 'AQAAf0Y4gjgAAAQ3AwMEAg=='}
          >>> bim.getRequestId(request3)
          'AQAAf0Y4gjgAAAQ3AwMEAg=='

        """
        response_cookie = request.response.getCookie(self.namespace)
        if response_cookie:
            sid = response_cookie['value']
        else:
            request = IHTTPApplicationRequest(request)
            sid = request.getCookies().get(self.namespace, None)

        if self.thirdparty:
            return sid

        # If there is an id set on the response, use that but
        # don't trust it.  We need to check the response in case
        # there has already been a new session created during the
        # course of this request.

        if sid is None or len(sid) != 54:
            return None
        s, mac = sid[:27], sid[27:]

        # HMAC is specified to work on byte strings only so make
        # sure to feed it that by encoding
        mac_with_my_secret = hmac.new(self.secret.encode(), s.encode(),
                                      digestmod=sha1).digest()
        mac_with_my_secret = digestEncode(mac_with_my_secret).decode()

        if mac_with_my_secret != mac:
            return None

        return sid

    def setRequestId(self, request, id):
        """Set cookie with id on request.

        This sets the response cookie:

        See the examples in `getRequestId`.

        Note that the id is checked for validity. Setting an
        invalid value is silently ignored:

            >>> from io import BytesIO
            >>> from zope.publisher.http import HTTPRequest
            >>> request = HTTPRequest(BytesIO(), {}, None)
            >>> bim = CookieClientIdManager()
            >>> bim.getRequestId(request)
            >>> bim.setRequestId(request, 'invalid id')
            >>> bim.getRequestId(request)

        For now, the cookie path is the application URL:

            >>> cookie = request.response.getCookie(bim.namespace)
            >>> cookie['path'] == request.getApplicationURL(path_only=True)
            True

        By default, session cookies don't expire:

            >>> 'expires' in cookie
            False

        Expiry time of 0 means never (well - close enough)

            >>> bim.cookieLifetime = 0
            >>> request = HTTPRequest(BytesIO(), {}, None)
            >>> bid = bim.getClientId(request)
            >>> cookie = request.response.getCookie(bim.namespace)
            >>> cookie['expires']
            'Tue, 19 Jan 2038 00:00:00 GMT'

        A non-zero value means to expire after than number of seconds:

            >>> bim.cookieLifetime = 3600
            >>> request = HTTPRequest(BytesIO(), {}, None)
            >>> bid = bim.getClientId(request)
            >>> cookie = request.response.getCookie(bim.namespace)
            >>> import email.utils
            >>> c_expires = email.utils.parsedate(cookie['expires'])
            >>> from datetime import datetime, timedelta
            >>> expires = datetime(*c_expires[:7])
            >>> now = datetime.utcnow()
            >>> expires > now + timedelta(minutes=55)
            True

        If another server in front of Zope (Apache, Nginx) is managing the
        cookies we won't set any ClientId cookies:

          >>> request = HTTPRequest(BytesIO(), {}, None)
          >>> bim.thirdparty = True
          >>> from zope.testing.loggingsupport import InstalledHandler
          >>> handler = InstalledHandler('zope.session.http')
          >>> bim.setRequestId(request, '2345')
          >>> handler.uninstall()
          >>> len(handler.records)
          1
          >>> cookie = request.response.getCookie(bim.namespace)
          >>> cookie

        If the secure attribute is set to a true value, then the
        secure cookie option is included.

          >>> bim.thirdparty = False
          >>> bim.cookieLifetime = None
          >>> request = HTTPRequest(BytesIO(), {}, None)
          >>> bim.secure = True
          >>> bim.setRequestId(request, '1234')
          >>> from pprint import pprint
          >>> pprint(request.response.getCookie(bim.namespace))
          {'path': '/', 'secure': True, 'value': '1234'}

        If the domain is specified, it will be set as a cookie attribute.

          >>> bim.domain = '.example.org'
          >>> bim.setRequestId(request, '1234')
          >>> cookie = request.response.getCookie(bim.namespace)
          >>> print(cookie['domain'])
          .example.org

        When the cookie is set, cache headers are added to the
        response to try to prevent the cookie header from being cached:

          >>> request.response.getHeader('Cache-Control')
          'no-cache="Set-Cookie,Set-Cookie2"'
          >>> request.response.getHeader('Pragma')
          'no-cache'
          >>> request.response.getHeader('Expires')
          'Mon, 26 Jul 1997 05:00:00 GMT'

        If the httpOnly attribute is set to a true value, then the
        HttpOnly cookie option is included.

          >>> request = HTTPRequest(BytesIO(), {}, None)
          >>> bim.secure = False
          >>> bim.httpOnly = True
          >>> bim.setRequestId(request, '1234')
          >>> cookie = request.response.getCookie(bim.namespace)
          >>> print(cookie['httponly'])
          True

        """
        # TODO: Currently, the path is the ApplicationURL. This is reasonable,
        #     and will be adequate for most purposes.
        #     A better path to use would be that of the folder that contains
        #     the site manager this service is registered within. However,
        #     that would be expensive to look up on each request, and would
        #     have to be altered to take virtual hosting into account.
        #     Seeing as this utility instance has a unique namespace for its
        #     cookie, using ApplicationURL shouldn't be a problem.

        if self.thirdparty:
            logger.warning('ClientIdManager is using thirdparty cookies, '
                           'ignoring setIdRequest call')
            return

        response = request.response
        options = {}
        if self.cookieLifetime is not None:
            if self.cookieLifetime:
                expires = formatdate(time.time() + self.cookieLifetime,
                                     localtime=False, usegmt=True)
            else:
                expires = 'Tue, 19 Jan 2038 00:00:00 GMT'

            options['expires'] = expires

        if self.secure:
            options['secure'] = True

        if self.domain:
            options['domain'] = self.domain

        if self.httpOnly:
            options['HttpOnly'] = True

        response.setCookie(
            self.namespace, id,
            path=request.getApplicationURL(path_only=True),
            **options)

        response.setHeader(
            'Cache-Control',
            'no-cache="Set-Cookie,Set-Cookie2"')
        response.setHeader('Pragma', 'no-cache')
        response.setHeader('Expires', 'Mon, 26 Jul 1997 05:00:00 GMT')


def notifyVirtualHostChanged(event):
    """
    Adjust cookie paths when
    `zope.publisher.interfaces.http.IVirtualHostRequest` information
    changes.

    Given an event, this method should call a `CookieClientIdManager`'s
    setRequestId if a cookie is present in the response for that manager. To
    demonstrate we create a dummy manager object and event:

        >>> from io import BytesIO
        >>> @implementer(ICookieClientIdManager)
        ... class DummyManager(object):
        ...     namespace = 'foo'
        ...     thirdparty = False
        ...     request_id = None
        ...     def setRequestId(self, request, id):
        ...         self.request_id = id
        ...
        >>> manager = DummyManager()
        >>> component.provideUtility(manager, IClientIdManager)
        >>> from zope.publisher.http import HTTPRequest
        >>> class DummyEvent (object):
        ...     request = HTTPRequest(BytesIO(), {}, None)
        >>> event = DummyEvent()

    With no cookies present, the manager should not be called:

        >>> notifyVirtualHostChanged(event)
        >>> manager.request_id is None
        True

    However, when a cookie *has* been set, the manager is called so it can
    update the cookie if need be:

        >>> event.request.response.setCookie('foo', 'bar')
        >>> notifyVirtualHostChanged(event)
        >>> manager.request_id
        'bar'

    If a server in front of Zope manages the ClientIds (Apache, Nginx), we
    don't need to take care about the cookies:

        >>> manager2 = DummyManager()
        >>> manager2.thirdparty = True
        >>> event2 = DummyEvent()

    However, when a cookie *has* been set, the manager is called so it can
    update the cookie if need be:

        >>> event2.request.response.setCookie('foo2', 'bar2')
        >>> notifyVirtualHostChanged(event2)
        >>> id = manager2.request_id
        >>> id is None
        True

    Of course, if there is no request associated with the event,
    nothing happens:

        >>> event2.request = None
        >>> notifyVirtualHostChanged(event2)

    .. doctest::
        :hide:

        >>> import zope.component.testing
        >>> zope.component.testing.tearDown()
    """
    # the event sends us a IHTTPApplicationRequest, but we need a
    # IHTTPRequest for the response attribute, and so does the cookie-
    # manager.
    request = IHTTPRequest(event.request, None)
    if event.request is None:
        return
    for _name, manager in component.getUtilitiesFor(IClientIdManager):
        if manager and ICookieClientIdManager.providedBy(manager):
            # Third party ClientId Managers need no modification at all
            if not manager.thirdparty:
                cookie = request.response.getCookie(manager.namespace)
                if cookie:
                    manager.setRequestId(request, cookie['value'])
