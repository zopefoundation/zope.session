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
"""Session tests
"""
from cStringIO import StringIO
from zope.testing import cleanup
import doctest
import os
import os.path
import transaction
import unittest
import zope.component

from zope.component import provideHandler, getGlobalSiteManager
from zope.session.interfaces import IClientId, IClientIdManager, ISession
from zope.session.interfaces import ISessionDataContainer
from zope.session.interfaces import ISessionPkgData, ISessionData
from zope.session.session import ClientId, Session
from zope.session.session import PersistentSessionDataContainer
from zope.session.session import RAMSessionDataContainer
from zope.session.http import CookieClientIdManager

from zope.publisher.interfaces import IRequest
from zope.publisher.http import HTTPRequest

def setUp(session_data_container_class=PersistentSessionDataContainer):
    cleanup.setUp()
    zope.component.provideAdapter(ClientId, (IRequest,), IClientId)
    zope.component.provideAdapter(Session, (IRequest,), ISession)
    zope.component.provideUtility(CookieClientIdManager(), IClientIdManager)
    sdc = session_data_container_class()
    for product_id in ('', 'products.foo', 'products.bar', 'products.baz'):
        zope.component.provideUtility(sdc, ISessionDataContainer, product_id)
    request = HTTPRequest(StringIO(), {}, None)
    return request

def tearDown():
    cleanup.tearDown()

# Test the code in our API documentation is correct
def test_documentation():
    pass
test_documentation.__doc__ = '''
    >>> request = setUp(RAMSessionDataContainer)

    %s

    >>> tearDown()

    ''' % (open(os.path.join(os.path.dirname(__file__), 'api.txt')).read(),)


def tearDownTransaction(test):
    transaction.abort()


def testConflicts():
    """The SessionData objects have been plagued with unnecessary
    ConflictErrors.  The current implementation makes the most common source
    of ConflictErrors in the past, setting the lastAccessTime, no longer a
    problem in this regard.

    To illustrate this, we will do a bit of an integration test.  We'll begin
    by getting a connection and putting a session data container in the root,
    within transaction manager "A".

    >>> try:
    ...     # ZODB 3.8
    ...     from ZODB.DB import DB
    ...     from ZODB.tests.util import ConflictResolvingMappingStorage
    ...     db = DB(ConflictResolvingMappingStorage())
    ... except ImportError:
    ...     # ZODB 3.9 (ConflictResolvingMappingStorage no longer exists)
    ...     import ZODB.DB
    ...     db = ZODB.DB('Data.fs')
    >>> from zope.session.session import (
    ...     PersistentSessionDataContainer, SessionData)
    >>> import transaction
    >>> tm_A = transaction.TransactionManager()
    >>> conn_A = db.open(transaction_manager=tm_A)
    >>> root_A = conn_A.root()
    >>> sdc_A = root_A['sdc'] = PersistentSessionDataContainer()
    >>> sdc_A.resolution = 3
    >>> sd_A = sdc_A['clientid'] = SessionData()
    >>> then = sd_A.getLastAccessTime() - 4
    >>> sd_A.setLastAccessTime(then)
    >>> tm_A.commit()

    Now we have a session data container with a session data lastAccessTime
    that is set to four seconds ago.  Since we set the resolution to three
    seconds, the next time the session is accessed, the lastAccessTime should
    be updated.

    We will access the session simultaneously in two transactions, which will
    set the updated lastAccessTime on both objects, and then commit.  Because
    of the conflict resolution code in zope.minmax, both commits will succeed,
    which is what we wanted to demonstrate.

    >>> tm_B = transaction.TransactionManager()
    >>> conn_B = db.open(transaction_manager=tm_B)
    >>> root_B = conn_B.root()
    >>> sdc_B = root_B['sdc']

    >>> sd_B = sdc_B['clientid'] # has side effect of updating lastAccessTime
    >>> sd_B.getLastAccessTime() > then
    True

    >>> sd_A is sdc_A['clientid'] # has side effect of updating lastAccessTime
    True
    >>> sd_A.getLastAccessTime() > then
    True

    >>> tm_A.commit()
    >>> tm_B.commit()

    Q.E.D.
    """

def testSessionIterationBug():
    """

    The zope.session.session.Session ISession implementation defines
    an `__iter__` method that raises NotImplementedError in order to
    avoid an infinite loop if iteration or a test for containment is
    attempted on an instance.

    >>> import zope.session.session
    >>> request = setUp()
    >>> session = zope.session.session.Session(request)
    >>> try:
    ...     "blah" in session
    ... except TypeError:
    ...     pass
    ... else:
    ...     raise Exception("Should have raised TypeError")

    >>> for i in session:
    ...     raise Exception("Should have raised NotImplementedError")
    Traceback (most recent call last):
    ...
    NotImplementedError

    >>> tearDown()
    """


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite())
    suite.addTest(doctest.DocTestSuite('zope.session.session',
        tearDown=tearDownTransaction))
    suite.addTest(doctest.DocTestSuite('zope.session.http',
        optionflags=doctest.NORMALIZE_WHITESPACE|doctest.ELLIPSIS,)
        )
    return suite


if __name__ == '__main__':
    unittest.main()
