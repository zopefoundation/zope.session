========================
 Using ``zope.session``
========================

.. currentmodule:: zope.session.interfaces

Overview
========

.. caution::
    Session data is maintained on the server. This gives a security
    advantage in that we can assume that a client has not tampered with
    the data.  However, this can have major implications for scalability
    as modifying session data too frequently can put a significant load
    on servers and in extreme situations render your site unusable.
    Developers should keep this in mind when writing code or risk
    problems when their application is run in a production environment.

    Applications requiring write-intensive session implementations (such
    as page counters) should consider using cookies or specialized
    session implementations.

Setup
-----

This package provides a ``configure.zcml`` for use with
`zope.configuration.xmlconfig` that provides the default adapters for
`IClientId` (`.ClientId`), `ISession` (`.Session`) and the
`zope.traversing.interfaces.IPathAdapter` named ``session``.

It also provides ``zope.security`` declarations and marks
`.CookieClientIdManager` and `.PersistentSessionDataContainer` as
implementing `zope.annotation.interfaces.IAttributeAnnotatable` if
that package is installed.

This document assumes that configuration has been completed:

    >>> from zope.configuration import xmlconfig
    >>> import zope.session
    >>> _ = xmlconfig.file('configure.zcml', zope.session)

Note that it does **not** install any `ISessionDataContainer`
or `IClientIdManager` utilities. We do that manually:

    >>> from zope.component import provideUtility
    >>> from zope.session.interfaces import IClientIdManager
    >>> from zope.session.interfaces import ISessionDataContainer
    >>> from zope.session.http import CookieClientIdManager
    >>> from zope.session.session import RAMSessionDataContainer
    >>> provideUtility(CookieClientIdManager(), IClientIdManager)
    >>> sdc = RAMSessionDataContainer()
    >>> for product_id in ('', 'products.foo', 'products.bar'):
    ...    provideUtility(sdc, ISessionDataContainer, product_id)

Sessions
--------

Sessions allow us to fake state over a stateless protocol - HTTP. We
do this by having a unique identifier stored across multiple HTTP
requests, be it a cookie or some id mangled into the URL.

The `IClientIdManager` Utility provides this unique id. It is
responsible for propagating this id so that future requests from the
client get the same id (eg. by setting an HTTP cookie). This utility
is used when we adapt the request to the unique client id:

    >>> from zope.session.interfaces import IClientId
    >>> from zope.publisher.http import HTTPRequest
    >>> from io import BytesIO
    >>> request = HTTPRequest(BytesIO(), {}, None)
    >>> client_id = IClientId(request)

The `ISession` adapter gives us a mapping that can be used to store
and retrieve session data. A unique key (the package id) is used to
avoid namespace clashes:

    >>> from zope.session.interfaces import ISession
    >>> pkg_id = 'products.foo'
    >>> session = ISession(request)[pkg_id]
    >>> session['color'] = 'red'

    >>> session2 = ISession(request)['products.bar']
    >>> session2['color'] = 'blue'

    >>> session['color']
    'red'
    >>> session2['color']
    'blue'


Data Storage
============

The actual data is stored in an `ISessionDataContainer` utility.
`ISession` chooses which `ISessionDataContainer` should be used by
looking up as a named utility using the package id. This allows the
site administrator to configure where the session data is actually
stored by adding a registration for desired `ISessionDataContainer`
with the correct name.

    >>> import zope.component
    >>> from zope.session.interfaces import ISessionDataContainer
    >>> sdc = zope.component.getUtility(ISessionDataContainer, pkg_id)
    >>> sdc[client_id][pkg_id] is session
    True
    >>> sdc[client_id][pkg_id]['color']
    'red'

If no `ISessionDataContainer` utility can be located by name using the
package id, then the unnamed `ISessionDataContainer` utility is used
as a fallback.

    >>> ISession(request)['unknown'] \
    ...     is zope.component.getUtility(ISessionDataContainer)[client_id]\
    ...         ['unknown']
    True

The `ISessionDataContainer` contains `ISessionData` objects, and
`ISessionData` objects in turn contain `ISessionPkgData` objects. You
should never need to know this unless you are writing administrative
views for the session machinery.

    >>> from zope.session.interfaces import ISessionData
    >>> from zope.session.interfaces import ISessionPkgData
    >>> ISessionData.providedBy(sdc[client_id])
    True
    >>> ISessionPkgData.providedBy(sdc[client_id][pkg_id])
    True

The `ISessionDataContainer` is responsible for expiring session data.
The expiry time can be configured by settings its ``timeout``
attribute.

    >>> sdc.timeout = 1200 # 1200 seconds or 20 minutes


Restrictions
============

Data stored in the session must be persistent or picklable. (Exactly
which builtin and standard objects can be pickled depends on the
Python version, the Python implementation, and the ZODB version, so we
demonstrate with a custom object.)

    >>> import transaction
    >>> class NoPickle(object):
    ...     def __reduce__(self):
    ...          raise TypeError("I cannot be pickled")
    >>> session['oops'] = NoPickle()
    >>> transaction.commit()
    Traceback (most recent call last):
        [...]
    TypeError: I cannot be pickled


Page Templates
==============

Session data may be accessed in page template documents using TALES
thanks to the ``session`` path adapter:

.. code-block:: xml

    <span tal:content="request/session:products.foo/color | default">
        green
    </span>

or:

.. code-block:: xml

    <div tal:define="session request/session:products.foo">
        <script type="text/server-python">
            try:
                session['count'] += 1
            except KeyError:
                session['count'] = 1
        </script>

        <span tal:content="session/count" />
    </div>


Session Timeout
===============

Sessions have a timeout (defaulting to an hour, in seconds).

    >>> import zope.session.session
    >>> data_container = zope.session.session.PersistentSessionDataContainer()
    >>> data_container.timeout
    3600

We need to keep up with when the session was last used (to know when
it needs to be expired), but it would be too resource-intensive to
write the last access time every, single time the session data is
touched. The session machinery compromises by only recording the last
access time periodically. That period is called the "resolution". That
also means that if the last-access-time + the-resolution < now, then
the session is considered to have timed out.

The default resolution is 10 minutes (600 seconds), meaning that a
user's session will actually time out sometime between 50 and 60
minutes.

    >>> data_container.resolution
    600


.. testcleanup::

    transaction.abort()
    from zope.testing import cleanup
    cleanup.tearDown()
