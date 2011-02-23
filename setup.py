import os
from setuptools import setup, Extension

setup(
    name = 'python-phringes',
    version = '0.0.1',
    author = 'Rurik A. Primiani',
    author_email = 'rprimian@cfa.harvard.edu',
    description = 'Python software for interfacing to the PHRINGES system',
    packages = ['phringes', 'phringes.core', 'phringes.backends', 'phringes.plotting'],
    ext_modules = [Extension('phringes.backends._dds', ['src/dds.c', 'src/dDS_clnt.c', 'src/dDS_xdr.c'])],
    )
