##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
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
# This package is developed by the Zope Toolkit project, documented here:
# https://zopetoolkit.readthedocs.io/
# When developing and releasing this package, please follow the documented
# Zope Toolkit policies as described by this documentation.
##############################################################################
"""Setup for zope.session package
"""
import os

from setuptools import find_packages
from setuptools import setup


def read(*rnames):
    with open(os.path.join(os.path.dirname(__file__), *rnames)) as f:
        return f.read()


TESTS_REQUIRE = [
    'zope.configuration',
    'zope.testing',
    'zope.testrunner',
]

setup(name='zope.session',
      version='5.3.dev0',
      author='Zope Foundation and Contributors',
      author_email='zope-dev@zope.dev',
      description='Client identification and sessions for Zope',
      long_description=(
          read('README.rst')
          + '\n\n' +
          read('CHANGES.rst')
      ),
      license='ZPL-2.1',
      keywords="zope3 session",
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Zope Public License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Programming Language :: Python :: 3.11',
          'Programming Language :: Python :: 3.12',
          'Programming Language :: Python :: 3.13',
          'Programming Language :: Python :: Implementation :: CPython',
          'Programming Language :: Python :: Implementation :: PyPy',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Topic :: Internet :: WWW/HTTP',
          'Framework :: Zope :: 3',
      ],
      url='https://github.com/zopefoundation/zope.session',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      namespace_packages=['zope', ],
      python_requires='>=3.9',
      install_requires=[
          'setuptools',
          'ZODB >= 4.2.0.b1',
          'zope.component',
          'zope.i18nmessageid >= 4.0.3',
          'zope.interface',
          'zope.location',
          'zope.publisher >= 4.1.0',
          'zope.minmax',
          'zope.traversing',
      ],
      extras_require={
          'test': TESTS_REQUIRE,
          'docs': [
              'Sphinx',
              'repoze.sphinx.autointerface',
          ],
      },
      include_package_data=True,
      zip_safe=False,
      )
