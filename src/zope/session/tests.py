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
import unittest
from zope.testing import cleanup

# Test the code in our API documentation is correct
def tearDownTransaction(test):
    import transaction
    transaction.abort()


class TestSessions(cleanup.CleanUp, unittest.TestCase):

    def test_conflicts(self):
        # The SessionData objects have been plagued with unnecessary
        # ConflictErrors.  The current implementation makes the most common source
        # of ConflictErrors in the past, setting the lastAccessTime, no longer a
        # problem in this regard.

        # To illustrate this, we will do a bit of an integration test.  We'll begin
        # by getting a connection and putting a session data container in the root,
        # within transaction manager "A".

        import os
        import shutil
        import tempfile
        import ZODB.DB
        tmpdir = tempfile.mkdtemp(prefix='zope.session-', suffix='-test')
        self.addCleanup(shutil.rmtree, tmpdir)
        db = ZODB.DB(os.path.join(tmpdir, 'testConflicts-Data.fs'))
        self.addCleanup(db.close)
        from zope.session.session import PersistentSessionDataContainer, SessionData
        import transaction
        tm_A = transaction.TransactionManager()
        conn_A = db.open(transaction_manager=tm_A)
        self.addCleanup(conn_A.close)
        root_A = conn_A.root()
        sdc_A = root_A['sdc'] = PersistentSessionDataContainer()
        sdc_A.resolution = 3
        sd_A = sdc_A['clientid'] = SessionData()
        then = sd_A.getLastAccessTime() - 4
        sd_A.setLastAccessTime(then)
        tm_A.commit()

        # Now we have a session data container with a session data lastAccessTime
        # that is set to four seconds ago.  Since we set the resolution to three
        # seconds, the next time the session is accessed, the lastAccessTime should
        # be updated.

        # We will access the session simultaneously in two transactions, which will
        # set the updated lastAccessTime on both objects, and then commit.  Because
        # of the conflict resolution code in zope.minmax, both commits will succeed,
        # which is what we wanted to demonstrate.

        tm_B = transaction.TransactionManager()
        conn_B = db.open(transaction_manager=tm_B)
        self.addCleanup(conn_B.close)
        root_B = conn_B.root()
        sdc_B = root_B['sdc']

        sd_B = sdc_B['clientid'] # has side effect of updating lastAccessTime
        self.assertGreater(sd_B.getLastAccessTime(), then)


        self.assertIs(sd_A, sdc_A['clientid']) # has side effect of updating lastAccessTime
        self.assertGreater(sd_A.getLastAccessTime(), then)

        tm_A.commit()
        tm_B.commit()

    def testSessionIterationBug(self):
        # The zope.session.session.Session ISession implementation defines
        # `__iter__` and `__contains__` methods that raise
        # NotImplementedError and TypeError, respectively, in order to avoid
        # an infinite loop if iteration or a test for containment is
        # attempted on an instance.
        from io import BytesIO
        from zope.publisher.http import HTTPRequest
        from zope.publisher.interfaces import IRequest
        from zope.component import provideAdapter
        from zope.component import provideUtility
        from zope.session.interfaces import IClientId
        from zope.session.interfaces import IClientIdManager
        from zope.session.http import CookieClientIdManager
        import zope.session.session

        provideUtility(CookieClientIdManager(), IClientIdManager)
        provideAdapter(zope.session.session.ClientId, (IRequest,), IClientId)

        request = HTTPRequest(BytesIO(), {}, None)
        session = zope.session.session.Session(request)
        with self.assertRaises(TypeError):
            'blah' in session

        with self.assertRaises(NotImplementedError):
            list(iter(session))


def test_suite():
    import doctest
    import re
    from zope.testing import renormalizing

    checker = renormalizing.RENormalizing([
        # Python 3 strings remove the "u".
        (re.compile("u('.*?')"),
         r"\1"),
        (re.compile('u(".*?")'),
         r"\1"),
        # Python 3 bytes add a "b".
        (re.compile("b('.*?')"),
         r"\1"),
        (re.compile('b(".*?")'),
         r"\1"),
        # Python 3 adds module name to exceptions.
        (re.compile("zope.session.http.MissingClientIdException"),
         r"MissingClientIdException"),
        ])
    flags = doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
    suite = unittest.defaultTestLoader.loadTestsFromName(__name__)

    suite.addTest(doctest.DocTestSuite(
        'zope.session.session',
        checker=checker,
        tearDown=tearDownTransaction))
    suite.addTest(doctest.DocTestSuite(
        'zope.session.http',
        checker=checker,
        optionflags=flags))
    return suite


if __name__ == '__main__':
    unittest.main()
