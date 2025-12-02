#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Setup configuration for ragstack_common package.

This shared library provides utilities for Lambda functions including:
- Bedrock client and model interactions
- OCR backends (Textract and Bedrock)
- Image processing utilities
- S3 storage operations
- Data models and schemas
"""

from setuptools import find_packages, setup

setup(
    name="ragstack_common",
    version="0.1.0",
    description="Shared utilities for Lambda functions",
    packages=find_packages(),
    python_requires=">=3.12",
    install_requires=[
        "boto3>=1.34.0",
        "PyMuPDF>=1.23.0",
        "Pillow>=10.0.0",
        # Scraping dependencies
        "httpx>=0.27.0",
        "beautifulsoup4>=4.12.0",
        "markdownify>=0.13.0",
        "lxml>=5.0.0",
    ],
    author="Development Team",
    license="MIT-0",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
