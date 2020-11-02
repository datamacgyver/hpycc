from setuptools import setup, find_packages

with open("README.rst", "r") as fh:
    long_description = fh.read()

setup(
    name='hpycc',
    version='0.2.2',
    description='Download THOR files, run ECL scripts and download their results.',
    long_description=long_description,
    url='https://github.com/OdinProAgrica/hpycc',
    author='Rob Mansfield',
    author_email='rob.mansfield@proagrica.com',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Distributed Computing',
        'Topic :: Utilities'
    ],
    keywords='HPCC ECL data access distributed ROXIE THOR',
    license='GNU GPLv3',
    packages=find_packages(),
    zip_safe=False,
    install_requires=[
        'pandas',
        'requests>=2.18.4',
        'docker',
        'numpy',
        "passlib",
        "simplejson==3.16.0"
    ],
    project_urls={
        'Bug Reports': 'https://github.com/OdinProAgrica/hpycc/issues',
        'Source': 'https://github.com/OdinProAgrica/hpycc',
        'ReadTheDocs': 'http://hpycc.readthedocs.io'
    }
)
