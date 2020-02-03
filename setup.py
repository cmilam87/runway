"""Packaging settings."""
from codecs import open as codecs_open
from os.path import abspath, dirname, join

from setuptools import find_packages, setup

from src.runway import __version__


THIS_DIR = abspath(dirname(__file__))
with codecs_open(join(THIS_DIR, 'README.rst'), encoding='utf-8') as readfile:
    LONG_DESCRIPTION = readfile.read()


INSTALL_REQUIRES = [
    'Send2Trash',
    'awacs',  # for embedded hooks
    # awscli included for embedded hooks and aws subcommand
    'awscli>=1.16.308<2.0',
    'botocore>=1.12.111',  # matching awscli/boto3 requirement
    'boto3>=1.9.111<2.0',
    'cfn_flip>=1.2.1',  # 1.2.1+ require PyYAML 4.1+
    'cfn-lint',
    'docopt',
    'requests',
    'future',
    'pyhcl~=0.4',
    'pyOpenSSL',  # For embedded hook & associated script usage
    'PyYAML>=4.1,<5.3',  # match awscli top-end
    'six>=1.13.0',
    'typing;python_version<"3.5"',
    'yamllint',
    'zgitignore',  # for embedded hooks
    'troposphere>=2.4.2',
    # botocore pins its urllib3 dependency like this, so we need to do the
    # same to ensure v1.25+ isn't pulled in by pip
    'urllib3>=1.20,<1.25',
    # dependency of importlib-metadata, dependency of pytest, cfn-lint, & others
    # 2.0.0 drops support for python 3.5
    'zipp~=1.0.0',
    # inherited from stacker 1.7.0 requirements
    'gitpython>=2.0,<3.0',
    'jinja2>=2.7,<3.0',
    'schematics>=2.0.1,<2.1.0',
    'formic2',
    'python-dateutil>=2.0,<3.0',
    'backports.tempfile;python_version<"3.2"'
]


setup(
    name='runway',
    version=__version__,
    description='Simplify infrastructure/app testing/deployment',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/onicagroup/runway',
    author='Onica Group LLC',
    author_email='opensource@onica.com',
    license='Apache License 2.0',
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Utilities',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    python_requires='>=2.6',
    keywords='cli',
    # exclude=['docs', 'tests*'],
    packages=find_packages(where='src'),
    package_dir={"": "src"},
    install_requires=INSTALL_REQUIRES,
    entry_points={
        'console_scripts': [
            'runway=runway.cli:main',
        ],
    },
    scripts=['scripts/stacker-runway', 'scripts/stacker-runway.cmd',
             'scripts/tf-runway', 'scripts/tf-runway.cmd',
             'scripts/tfenv-runway', 'scripts/tfenv-runway.cmd'],
    include_package_data=True  # needed for templates,blueprints,hooks
)
