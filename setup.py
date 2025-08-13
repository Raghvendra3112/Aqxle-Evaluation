from setuptools import setup, find_packages

setup(
    name="Aqxle_evaluation",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "anthropic>=0.25.0"
    ],
    description="Likert, Elo, and LLM utilities for internal evaluation",
    author="Raghvendra Misra",
    url="https://github.com/Raghvendra3112/Aqxle-evaluation",
)
