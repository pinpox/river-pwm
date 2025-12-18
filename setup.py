#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="pwm",
    version="0.1.0",
    description="pinpox' window manager - A Python library for River window management",
    author="pinpox",
    license="ISC",
    packages=find_packages(),
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Desktop Environment :: Window Managers",
    ],
)
