from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='django_informixdb_vault',
    version='0.3.0',
    description='A database driver for Django to connect to an Informix db via ODBC, obtaining the credentials from Hashicorp Vault',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/reecetech/django_informixdb_vault',
    author='Reecetech',
    author_email='opensource@reecetech.com.au',
    license='APLv2',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    keywords='django informix vault',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=['django~=2.2.0', 'pyodbc~=4.0.21', 'django_informixdb~=1.10.0', 'hvac~=0.10.4'],
    extras_require={
        'dev': ['check-manifest'],
        'test': ['coverage'],
    },
)
