=========
 CHANGES
=========

5.0 (2023-03-02)
================

- Drop support for Python 2.7, 3.5, 3.6.

- Add support for Python 3.11.


4.5 (2022-08-30)
================

- Add support for Python 3.5, 3.9, 3.10.


4.4.0 (2020-10-16)
==================

- Fix inconsistent resolution order with zope.interface v5.

- Add support for Python 3.8.

- Drop support for Python 3.4 and 3.5.


4.3.0 (2018-10-19)
==================

- Add support for Python 3.7.

- Host documentation at https://zopesession.readthedocs.io


4.2.0 (2017-09-22)
==================

- Add support for Python 3.5 and 3.6.

- Drop support for Python 2.6 and 3.3

- Reach 100% code coverage and maintain it via tox.ini and Travis CI.

4.1.0 (2015-06-02)
==================

- Add support for PyPy and PyPy3.


4.0.0 (2014-12-24)
==================

- Add support for Python 3.4.

- Add support for testing on Travis.


4.0.0a2 (2013-08-27)
====================

- Fix test that fails on any timezone east of GMT


4.0.0a1 (2013-02-21)
====================

- Add support for Python 3.3

- Replace deprecated ``zope.component.adapts`` usage with equivalent
  ``zope.component.adapter`` decorator.

- Replace deprecated ``zope.interface.implements`` usage with equivalent
  ``zope.interface.implementer`` decorator.

- Drop support for Python 2.4 and 2.5.


3.9.5 (2011-08-11)
==================

- LP #824355:  enable support for HttpOnly cookies.

- Fix a bug in ``zope.session.session.Session`` that would trigger an
  infinite loop if either iteration or a containment test were
  attempted on an instance.


3.9.4 (2011-03-07)
==================

- Add an explicit `provides` to the IClientId adapter declaration in
  adapter.zcml.

- Add option to disable implicit sweeps in
  PersistentSessionDataContainer.


3.9.3 (2010-09-25)
==================

- Add test extra to declare test dependency on ``zope.testing``.

- Use Python's ``doctest`` module instead of depreacted
  ``zope.testing.doctest``.


3.9.2 (2009-11-23)
==================

- Fix Python 2.4 hmac compatibility issue by only using hashlib in
  Python versions 2.5 and above.

- Use the CookieClientIdManager's secret as the hmac key instead of the
  message when constructing and verifying client ids.

- Make it possible to construct CookieClientIdManager passing cookie namespace
  and/or secret as constructor's arguments.

- Use zope.schema.fieldproperty.FieldProperty for "namespace" attribute of
  CookieClientIdManager, just like for other attributes in its interface.
  Also, make ICookieClientIdManager's "namespace" field an ASCIILine, so
  it accepts only non-unicode strings for cookie names.


3.9.1 (2009-04-20)
==================

- Restore compatibility with Python 2.4.


3.9.0 (2009-03-19)
==================

- Don't raise deprecation warnings on Python 2.6.

- Drop dependency on ``zope.annotation``. Instead, we make classes implement
  `IAttributeAnnotatable` in ZCML configuration, only if ``zope.annotation``
  is available. If your code relies on annotatable `CookieClientIdManager`
  and `PersistentSessionDataContainer` and you don't include the zcml classes
  configuration of this package, you'll need to use `classImplements` function
  from ``zope.interface`` to make those classes implement `IAttributeAnnotatable`
  again.

- Drop dependency on zope.app.http, use standard date formatting function
  from the ``email.utils`` module.

- Zope 3 application bootstrapping code for session utilities was moved into
  zope.app.appsetup package, thus drop dependency on zope.app.appsetup in this
  package.

- Drop testing dependencies, as we don't need anything behind zope.testing and
  previous dependencies was simply migrated from zope.app.session before.

- Remove zpkg files and zcml slugs.

- Update package's description a bit.


3.8.1 (2009-02-23)
==================

- Add an ability to set cookie effective domain for CookieClientIdManager.
  This is useful for simple cases when you have your application set up on
  one domain and you want your identification cookie be active for subdomains.

- Python 2.6 compatibility change. Encode strings before calling hmac.new()
  as the function no longer accepts the unicode() type.


3.8.0 (2008-12-31)
==================

- Add missing test dependency on ``zope.site`` and
  ``zope.app.publication``.


3.7.1 (2008-12-30)
==================

- Specify i18n_domain for titles in apidoc.zcml

- ZODB 3.9 no longer contains
  ZODB.utils.ConflictResolvingMappingStorage, fixed tests, so they
  work both with ZODB 3.8 and 3.9.


3.7.0 (2008-10-03)
==================

New features:

- Added a 'postOnly' option on CookieClientIdManagers to only allow setting
  the client id cookie on POST requests.  This is to further reduce risk from
  broken caches handing the same client id out to multiple users. (Of
  course, it doesn't help if caches are broken enough to cache POSTs.)


3.6.0 (2008-08-12)
==================

New features:

- Added a 'secure' option on CookieClientIdManagers to cause the secure
  set-cookie option to be used, which tells the browser not to send the
  cookie over http.

  This provides enhanced security for ssl-only applications.

- Only set the client-id cookie if it isn't already set and try to
  prevent the header from being cached.  This is to minimize risk from
  broken caches handing the same client id out to multiple users.


3.5.2 (2008-06-12)
==================

- Remove ConflictErrors caused on SessionData caused by setting
  ``lastAccessTime``.


3.5.1 (2008-04-30)
==================

- Split up the ZCML to make it possible to re-use more reasonably.


3.5.0 (2008-03-11)
==================

- Change the default session "resolution" to a sane value and document/test it.


3.4.1 (2007-09-25)
==================

- Fixed some meta data and switch to tgz release.


3.4.0 (2007-09-25)
==================

- Initial release

- Moved parts from ``zope.app.session`` to this packages
