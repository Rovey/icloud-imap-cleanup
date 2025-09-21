"""Setup script for IMAP Mail Cleanup."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="imap-mail-cleanup",
    version="2.0.0",
    author="Generated with Claude Code",
    description="Threaded email cleanup tool for iCloud IMAP with GUI support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/imap-mail-cleanup",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Email",
        "Topic :: Utilities",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "imap-cleanup=imap_cleanup.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)