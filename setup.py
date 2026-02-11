"""Setup file for CineMatch AI."""

from setuptools import find_packages, setup

setup(
    name="cinematch-ai",
    version="1.0.0",
    description="Multi-Agent Movie Recommendation System with Explainable AI",
    author="Sagar Darji",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # Will use requirements.txt
    ],
)
