from setuptools import setup, find_packages

setup(
    name="vaultscan",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "vaultscan=vaultscan.cli:main",
        ],
    },
    install_requires=[
        "pydantic>=2.7.0",
        "pydantic-settings>=2.3.0",
        "pyyaml>=6.0",
        "GitPython>=3.1.0",
        "python-dotenv>=1.0.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0"
    ],
)
