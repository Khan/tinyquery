#!/usr/bin/env python

from setuptools import setup

setup(
    name='Tinyquery',
    version='1.2.1',
    description='In-memory test stub for bigquery',
    author='Khan Academy',
    author_email='opensource+pypi@khanacademy.org',
    url='https://github.com/Khan/tinyquery',
    keywords=['bigquery'],
    packages=['tinyquery'],
    install_requires=['arrow==0.12.1', 'ply==3.10', 'six==1.11.0'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 2.7',
    ],
)
