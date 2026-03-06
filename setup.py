from setuptools import setup, find_packages

setup(
    name="jira-dependencies-tracking",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "jira-extract=jira_extract:cli",
        ],
    },
    python_requires=">=3.9",
)
