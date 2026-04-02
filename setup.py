from setuptools import setup, find_packages

setup(
    name="jira-em-toolkit",  # Renamed from jira-dependencies-tracking
    version="2.0.0",  # Major version bump for restructure
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
        "Jinja2>=3.1.2",
    ],
    entry_points={
        "console_scripts": [
            # New script names (scripts in root directory)
            "jem-extract=extract:cli",
            "jem-validate-planning=validate_planning:main",
            "jem-analyze-workload=analyze_workload:main",
        ],
    },
    python_requires=">=3.9",
)
