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
"""Session implementation
"""
from cStringIO import StringIO
import time, string, random, thread
from UserDict import IterableUserDict
from heapq import heapify, heappop

import ZODB
import ZODB.MappingStorage
import zope.location
import zope.minmax
import persistent
from BTrees.OOBTree import OOBTree

import zope.component
import zope.interface
from zope.component.interfaces import ComponentLookupError
from zope.publisher.interfaces import IRequest

from zope.session.interfaces import \
        IClientIdManager, IClientId, ISession, ISessionDataContainer, \
        ISessionPkgData, ISessionData

__docformat__ = 'restructuredtext'

cookieSafeTrans = string.maketrans("+/", "-.")

def digestEncode(s):
    """Encode SHA digest for cookie."""
    return s.encode("base64")[:-2].translate(cookieSafeTrans)


@zope.interface.implementer(IClientId)
@zope.component.adapter(IRequest)
class ClientId(str):
    """See zope.session.interfaces.IClientId

        >>> import tests
        >>> request = tests.setUp()

        >>> id1 = ClientId(request)
        >>> id2 = ClientId(request)
        >>> id1 == id2
        True

        >>> tests.tearDown()

    """

    def __new__(cls, request):
        return str.__new__(cls,
            zope.component.getUtility(IClientIdManager).getClientId(request)
            )


@zope.interface.implementer(ISessionDataContainer)
class PersistentSessionDataContainer(zope.location.Location,
    persistent.Persistent,
    IterableUserDict):
    """A SessionDataContainer that stores data in the ZODB"""


    _v_last_sweep = 0 # Epoch time sweep last run
    disable_implicit_sweeps = False

    def __init__(self):
        self.data = OOBTree()
        self.timeout = 1 * 60 * 60
        # The "resolution" should be a small fraction of the timeout.
        self.resolution = 10 * 60

    def __getitem__(self, pkg_id):
        """Retrieve an ISessionData

            >>> sdc = PersistentSessionDataContainer()

            >>> sdc.timeout = 60
            >>> sdc.resolution = 3
            >>> sdc['clientid'] = sd = SessionData()

        To ensure stale data is removed, we can wind
        back the clock using undocumented means...

            >>> sd.setLastAccessTime(sd.getLastAccessTime() - 64)
            >>> sdc._v_last_sweep = sdc._v_last_sweep - 4

        Now the data should be garbage collected

            >>> sdc['clientid']
            Traceback (most recent call last):
                [...]
            KeyError: 'clientid'

        Can you disable the automatic removal of stale data.

            >>> sdc.disable_implicit_sweeps = True
            >>> sdc['stale'] = stale = SessionData()

        Now we try the same method of winding back the clock.

            >>> stale.setLastAccessTime(sd.getLastAccessTime() - 64)
            >>> sdc._v_last_sweep = sdc._v_last_sweep - 4

        But the data is not automatically removed.

            >>> sdc['stale'] #doctest: +ELLIPSIS
            <zope.session.session.SessionData object at ...>

        We can manually remove stale data by calling sweep() if stale
        data isn't being automatically removed.

            >>> stale.setLastAccessTime(sd.getLastAccessTime() - 64)
            >>> sdc.sweep()
            >>> sdc['stale']
            Traceback (most recent call last):
                [...]
            KeyError: 'stale'

        Now we turn automatic removal back on.

            >>> sdc.disable_implicit_sweeps = False

        Ensure the lastAccessTime on the ISessionData is being updated
        occasionally. The ISessionDataContainer maintains this whenever
        the ISessionData is set or retrieved.

        lastAccessTime on the ISessionData is set when it is added
        to the ISessionDataContainer

            >>> sdc['client_id'] = sd = SessionData()
            >>> sd.getLastAccessTime() > 0
            True

        The lastAccessTime is also updated whenever the ISessionData
        is retrieved through the ISessionDataContainer, at most
        once every 'resolution' seconds.

            >>> then = sd.getLastAccessTime() - 4
            >>> sd.setLastAccessTime(then)
            >>> now = sdc['client_id'].getLastAccessTime()
            >>> now > then
            True
            >>> time.sleep(1)
            >>> now == sdc['client_id'].getLastAccessTime()
            True

        Ensure the lastAccessTime is not modified and no garbage collection
        occurs when timeout == 0. We test this by faking a stale
        ISessionData object.

            >>> sdc.timeout = 0
            >>> sd.setLastAccessTime(sd.getLastAccessTime() - 5000)
            >>> lastAccessTime = sd.getLastAccessTime()
            >>> sdc['client_id'].getLastAccessTime() == lastAccessTime
            True

        Next, we test session expiration functionality beyond transactions.

            >>> import transaction
            >>> from ZODB.DB import DB
            >>> from ZODB.DemoStorage import DemoStorage
            >>> sdc = PersistentSessionDataContainer()
            >>> sdc.timeout = 60
            >>> sdc.resolution = 3
            >>> db = DB(DemoStorage('test_storage'))
            >>> c = db.open()
            >>> c.root()['sdc'] = sdc
            >>> sdc['pkg_id'] = sd = SessionData()
            >>> sd['name'] = 'bob'
            >>> transaction.commit()

        Access immediately. the data should be accessible.

            >>> c.root()['sdc']['pkg_id']['name']
            'bob'

        Change the clock time and stale the session data.

            >>> sdc = c.root()['sdc']
            >>> sd = sdc['pkg_id']
            >>> sd.setLastAccessTime(sd.getLastAccessTime() - 64)
            >>> sdc._v_last_sweep = sdc._v_last_sweep - 4
            >>> transaction.commit()

        The data should be garbage collected.

            >>> c.root()['sdc']['pkg_id']['name']
            Traceback (most recent call last):
                [...]
            KeyError: 'pkg_id'

        Then abort transaction and access the same data again.
        The previous GC was cancelled, but deadline is over.
        The data should be garbage collected again.

            >>> transaction.abort()
            >>> c.root()['sdc']['pkg_id']['name']
            Traceback (most recent call last):
                [...]
            KeyError: 'pkg_id'

        """
        if self.timeout == 0:
            return IterableUserDict.__getitem__(self, pkg_id)

        now = time.time()

        # TODO: When scheduler exists, sweeping should be done by
        # a scheduled job since we are currently busy handling a
        # request and may end up doing simultaneous sweeps

        # If transaction is aborted after sweep. _v_last_sweep keep
        # incorrect sweep time. So when self.data is ghost, revert the time
        # to the previous _v_last_sweep time(_v_old_sweep).
        if self.data._p_state < 0:
            try:
                self._v_last_sweep = self._v_old_sweep
                del self._v_old_sweep
            except AttributeError:
                pass

        if (self._v_last_sweep + self.resolution < now and
            not self.disable_implicit_sweeps):
            self.sweep()
            if getattr(self, '_v_old_sweep', None) is None:
                self._v_old_sweep = self._v_last_sweep
            self._v_last_sweep = now

        rv = IterableUserDict.__getitem__(self, pkg_id)
        # Only update the lastAccessTime once every few minutes, rather than
        # every hit, to avoid ZODB bloat and conflicts
        if rv.getLastAccessTime() + self.resolution < now:
            rv.setLastAccessTime(int(now))
        return rv

    def __setitem__(self, pkg_id, session_data):
        """Set an ISessionPkgData

            >>> sdc = PersistentSessionDataContainer()
            >>> sad = SessionData()

        __setitem__ sets the ISessionData's lastAccessTime

            >>> sad.getLastAccessTime()
            0
            >>> sdc['1'] = sad
            >>> 0 < sad.getLastAccessTime() <= time.time()
            True

        We can retrieve the same object we put in

            >>> sdc['1'] is sad
            True

        """
        session_data.setLastAccessTime(int(time.time()))
        return IterableUserDict.__setitem__(self, pkg_id, session_data)

    def sweep(self):
        """Clean out stale data

            >>> sdc = PersistentSessionDataContainer()
            >>> sdc['1'] = SessionData()
            >>> sdc['2'] = SessionData()

        Wind back the clock on one of the ISessionData's
        so it gets garbage collected

            >>> sdc['2'].setLastAccessTime(
            ...     sdc['2'].getLastAccessTime() - sdc.timeout * 2)

        Sweep should leave '1' and remove '2'

            >>> sdc.sweep()
            >>> sd1 = sdc['1']
            >>> sd2 = sdc['2']
            Traceback (most recent call last):
                [...]
            KeyError: '2'

        """
        # We only update the lastAccessTime every 'resolution' seconds.
        # To compensate for this, we factor in the resolution when
        # calculating the expiry time to ensure that we never remove
        # data that has been accessed within timeout seconds.
        expire_time = time.time() - self.timeout - self.resolution
        heap = [(v.getLastAccessTime(), k) for k,v in self.data.items()]
        heapify(heap)
        while heap:
            lastAccessTime, key = heappop(heap)
            if lastAccessTime < expire_time:
                del self.data[key]
            else:
                return


class RAMSessionDataContainer(PersistentSessionDataContainer):
    """A SessionDataContainer that stores data in RAM.

    Currently session data is not shared between Zope clients, so
    server affinity will need to be maintained to use this in a ZEO cluster.

        >>> sdc = RAMSessionDataContainer()
        >>> sdc['1'] = SessionData()
        >>> sdc['1'] is sdc['1']
        True
        >>> ISessionData.providedBy(sdc['1'])
        True

    """
    def __init__(self):
        self.resolution = 5*60
        self.timeout = 1 * 60 * 60
        # Something unique
        self.key = '%s.%s.%s' % (time.time(), random.random(), id(self))

    _ram_storage = ZODB.MappingStorage.MappingStorage()
    _ram_db = ZODB.DB(_ram_storage)
    _conns = {}

    def _getData(self):

        # Open a connection to _ram_storage per thread
        tid = thread.get_ident()
        if not self._conns.has_key(tid):
            self._conns[tid] = self._ram_db.open()

        root = self._conns[tid].root()
        if not root.has_key(self.key):
            root[self.key] = OOBTree()
        return root[self.key]

    data = property(_getData, None)

    def sweep(self):
        super(RAMSessionDataContainer, self).sweep()
        self._ram_db.pack(time.time())


@zope.interface.implementer(ISession)
@zope.component.adapter(IRequest)
class Session(object):
    """See zope.session.interfaces.ISession"""

    def __init__(self, request):
        self.client_id = str(IClientId(request))

    def _sdc(self, pkg_id):
        # Locate the ISessionDataContainer by looking up the named
        # Utility, and falling back to the unnamed one.
        try:
            return zope.component.getUtility(ISessionDataContainer, pkg_id)
        except ComponentLookupError:
            return zope.component.getUtility(ISessionDataContainer)

    def get(self, pkg_id, default=None):

        """See zope.session.interfaces.ISession

            >>> import tests
            >>> request = tests.setUp(PersistentSessionDataContainer)

           If we use get we get None or default returned if the pkg_id
           is not there.

            >>> session = Session(request).get('not.there', 'default')
            >>> session
            'default'

           This method is lazy and does not create the session data.
            >>> session = Session(request).get('not.there')
            >>> session is None
            True

           The __getitem__ method instead creates the data.
            >>> session = Session(request)['not.there']
            >>> session is None
            False
            >>> session = Session(request).get('not.there')
            >>> session is None
            False
            >>> tests.tearDown()

        """


        # The ISessionDataContainer contains two levels:
        # ISessionDataContainer[client_id] == ISessionData
        # ISessionDataContainer[client_id][pkg_id] == ISessionPkgData
        sdc = self._sdc(pkg_id)
        try:
            sd = sdc[self.client_id]
        except KeyError:
            return default
        try:
            return sd[pkg_id]
        except KeyError:
            return default


    def __getitem__(self, pkg_id):
        """See zope.session.interfaces.ISession

            >>> import tests
            >>> request = tests.setUp(PersistentSessionDataContainer)
            >>> request2 = tests.HTTPRequest(StringIO(''), {}, None)

            >>> ISession.providedBy(Session(request))
            True

        Setup some sessions, each with a distinct namespace

            >>> session1 = Session(request)['products.foo']
            >>> session2 = Session(request)['products.bar']
            >>> session3 = Session(request2)['products.bar']

        If we use the same parameters, we should retrieve the
        same object

            >>> session1 is Session(request)['products.foo']
            True

        Make sure it returned sane values

            >>> ISessionPkgData.providedBy(session1)
            True

        Make sure that pkg_ids don't share a namespace.

            >>> session1['color'] = 'red'
            >>> session2['color'] = 'blue'
            >>> session3['color'] = 'vomit'
            >>> session1['color']
            'red'
            >>> session2['color']
            'blue'
            >>> session3['color']
            'vomit'

            >>> tests.tearDown()

        """
        sdc = self._sdc(pkg_id)

        # The ISessionDataContainer contains two levels:
        # ISessionDataContainer[client_id] == ISessionData
        # ISessionDataContainer[client_id][pkg_id] == ISessionPkgData
        try:
            sd = sdc[self.client_id]
        except KeyError:
            sd = sdc[self.client_id] = SessionData()

        try:
            return sd[pkg_id]
        except KeyError:
            spd = sd[pkg_id] = SessionPkgData()
            return spd


    def __iter__(self):
        raise NotImplementedError


@zope.interface.implementer(ISessionData)
class SessionData(persistent.Persistent, IterableUserDict):
    """See zope.session.interfaces.ISessionData

        >>> session = SessionData()
        >>> ISessionData.providedBy(session)
        True
        >>> session.getLastAccessTime()
        0

    Before the zope.minmax package this class used to have an attribute
    lastAccessTime initialized in the class itself to zero.
    To avoid changing the interface, that attribute has been turned into a
    property.  This part tests the behavior of a legacy session which would
    have the lastAccessTime attribute loaded from the database.
    The implementation should work for that case as well as with the new
    session where lastAccessTime is a property.  These tests will
    be removed in a later release (see the comments in the code below).

    First, create an instance of SessionData and remove a protected attribute
    _lastAccessTime from it to make it more like the legacy SessionData.  The
    subsequent attempt to get lastAccessTime will return a 0, because the
    lastAccessTime is not there and the dictionary returns the default value
    zero supplied to its get() method.

        >>> legacy_session = SessionData()
        >>> del legacy_session._lastAccessTime
        >>> legacy_session.getLastAccessTime()
        0

    Now, artificially add lastAccessTime to the instance's dictionary.
    This should make it exactly like the legacy SessionData().

        >>> legacy_session.__dict__['lastAccessTime'] = 42
        >>> legacy_session.getLastAccessTime()
        42

    Finally, assign to lastAccessTime.  Since the instance now looks like a
    legacy instance, this will trigger, through the property mechanism, a
    creation of a zope.minmax.Maximum() object which will take over the
    handling of this value and its conflict resolution from now on.

        >>> legacy_session.setLastAccessTime(13)
        >>> legacy_session._lastAccessTime.value
        13

    """

    # this is for support of legacy sessions; this comment and
    # the next line will be removed in a later release
    _lastAccessTime = None

    def __init__(self):
        self.data = OOBTree()
        self._lastAccessTime = zope.minmax.Maximum(0)

    # we include this for parallelism with setLastAccessTime
    def getLastAccessTime(self):
        # this conditional is for legacy sessions; this comment and
        # the next two lines will be removed in a later release
        if self._lastAccessTime is None:
            return self.__dict__.get('lastAccessTime', 0)
        return self._lastAccessTime.value

    # we need to set this value with setters in order to get optimal conflict
    # resolution behavior
    def setLastAccessTime(self, value):
        # this conditional is for legacy sessions; this comment and
        # the next two lines will be removed in a later release
        if self._lastAccessTime is None:
            self._lastAccessTime = zope.minmax.Maximum(0)
        self._lastAccessTime.value = value

    lastAccessTime = property(fget=getLastAccessTime,
                              fset=setLastAccessTime, # consider deprecating
                              doc='integer value of the last access time')


@zope.interface.implementer(ISessionPkgData)
class SessionPkgData(persistent.Persistent, IterableUserDict):
    """See zope.session.interfaces.ISessionPkgData

        >>> session = SessionPkgData()
        >>> ISessionPkgData.providedBy(session)
        True
    """
    def __init__(self):
        self.data = OOBTree()
