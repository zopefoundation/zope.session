##############################################################################
#
# Copyright (c) 2004 Zope Corporation and Contributors.
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

$Id$
"""
from cStringIO import StringIO
import unittest, os, os.path

import zope.component
from zope.testing import doctest
from zope.app.testing import placelesssetup
import transaction

from zope.session.interfaces import IClientId, IClientIdManager, ISession
from zope.session.interfaces import ISessionDataContainer
from zope.session.interfaces import ISessionPkgData, ISessionData
from zope.session.session import ClientId, Session
from zope.session.session import PersistentSessionDataContainer
from zope.session.session import RAMSessionDataContainer
from zope.session.http import CookieClientIdManager
from zope.session.bootstrap import bootStrapSubscriber as \
     sessionBootstrapSubscriber
from zope.session.testing import SessionLayer

from zope.publisher.interfaces import IRequest
from zope.publisher.http import HTTPRequest

from zope.app.appsetup.tests import TestBootstrapSubscriber, EventStub
from zope.app.appsetup.bootstrap import bootStrapSubscriber

from zope.component import provideHandler, getGlobalSiteManager
from zope.app.folder import Folder
from zope.app.folder.interfaces import IRootFolder
from zope.app.publication.interfaces import IBeforeTraverseEvent
from zope.app.testing.functional import BrowserTestCase
from zope.app.zptpage.zptpage import ZPTPage


def setUp(session_data_container_class=PersistentSessionDataContainer):
    placelesssetup.setUp()
    zope.component.provideAdapter(ClientId, (IRequest,), IClientId)
    zope.component.provideAdapter(Session, (IRequest,), ISession)
    zope.component.provideUtility(CookieClientIdManager(), IClientIdManager)
    sdc = session_data_container_class()
    for product_id in ('', 'products.foo', 'products.bar', 'products.baz'):
        zope.component.provideUtility(sdc, ISessionDataContainer, product_id)
    request = HTTPRequest(StringIO(), {}, None)
    return request

def tearDown():
    placelesssetup.tearDown()

class TestBootstrap(TestBootstrapSubscriber):

    def test_bootstrapSusbcriber(self):
        bootStrapSubscriber(EventStub(self.db))

        sessionBootstrapSubscriber(EventStub(self.db))

        import zope.component
        from zope.app.publication.zopepublication import ZopePublication
        from zope.app.component.hooks import setSite

        cx = self.db.open()
        root = cx.root()
        root_folder = root[ZopePublication.root_name]
        setSite(root_folder)

        zope.component.getUtility(IClientIdManager)
        zope.component.getUtility(ISessionDataContainer)

        cx.close()

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




from interfaces import ISession

class ZPTSessionTest(BrowserTestCase):
    content = u'''
        <div tal:define="
                 session request/session:products.foo;
                 dummy python:session.__setitem__(
                        'count',
                        session.get('count', 0) + 1)
                 " tal:omit-tag="">
            <span tal:replace="session/count" />
        </div>
        '''

    def setUp(self):
        BrowserTestCase.setUp(self)
        page = ZPTPage()
        page.source = self.content
        page.evaluateInlineCode = True
        root = self.getRootFolder()
        root['page'] = page
        self.commit()

    def tearDown(self):
        root = self.getRootFolder()
        del root['page']
        BrowserTestCase.tearDown(self)

    def fetch(self, page='/page'):
        response = self.publish(page)
        self.failUnlessEqual(response.getStatus(), 200)
        return response.getBody().strip()

    def test(self):
        response1 = self.fetch()
        self.failUnlessEqual(response1, u'1')
        response2 = self.fetch()
        self.failUnlessEqual(response2, u'2')
        response3 = self.fetch()
        self.failUnlessEqual(response3, u'3')

class VirtualHostSessionTest(BrowserTestCase):
    def setUp(self):
        super(VirtualHostSessionTest, self).setUp()
        page = ZPTPage()
        page.source = u'<div>Foo</div>'
        page.evaluateInlineCode = True
        root = self.getRootFolder()
        root['folder'] = Folder()
        root['folder']['page'] = page
        self.commit()
        
        provideHandler(self.accessSessionOnRootTraverse, 
                       (IBeforeTraverseEvent,))
        
    def tearDown(self):
        getGlobalSiteManager().unregisterHandler(
            self.accessSessionOnRootTraverse, (IBeforeTraverseEvent,))
        
    def accessSessionOnRootTraverse(self, event):
        if IRootFolder.providedBy(event.object):
            session = ISession(event.request)
        
    def assertCookiePath(self, path):
        cookie = self.cookies.values()[0]
        self.assertEqual(cookie['path'], path)
    
    def testShortendPath(self):
        self.publish(
            '/++skin++Rotterdam/folder/++vh++http:localhost:80/++/page')
        self.assertCookiePath('/')
        
    def testLongerPath(self):
        self.publish(
            '/folder/++vh++http:localhost:80/foo/bar/++/page')
        self.assertCookiePath('/foo/bar')
        
    def testDifferentHostname(self):
        self.publish(
            '/folder/++vh++http:foo.bar:80/++/page')
        self.assertCookiePath('/')


def test_suite():
    ZPTSessionTest.layer = SessionLayer
    VirtualHostSessionTest.layer = SessionLayer
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBootstrap))
    suite.addTest(doctest.DocTestSuite())
    suite.addTest(doctest.DocTestSuite('zope.session.session',
        tearDown=tearDownTransaction))
    suite.addTest(doctest.DocTestSuite('zope.session.http',
        optionflags=doctest.NORMALIZE_WHITESPACE|doctest.ELLIPSIS,)
        )
    suite.addTest(unittest.makeSuite(ZPTSessionTest))
    suite.addTest(unittest.makeSuite(VirtualHostSessionTest))
    return suite


if __name__ == '__main__':
    unittest.main()
