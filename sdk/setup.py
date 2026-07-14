from setuptools import setup, find_packages

setup(
    name="hayat-sdk",
    version="2.0.0",
    description="Official Python SDK for HAYAT — Bangladesh Legal Intelligence Platform",
    author="HAYAT Legal Technologies",
    author_email="dev@hayat.legal",
    url="https://github.com/hayat-legal/hayat-sdk",
    packages=find_packages(),
    install_requires=["httpx>=0.27.0"],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Legal Industry",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
