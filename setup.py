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
            # Mission Control script names (scripts in root directory)
            "jem-scan=scan:cli",
            "jem-check-planning=check_planning:main",
            "jem-check-quality=check_quality:main",
            "jem-check-priorities=check_priorities:main",
            "jem-assess-workload=assess_workload:main",
        ],
    },
    python_requires=">=3.9",
)
