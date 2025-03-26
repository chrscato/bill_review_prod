from setuptools import setup, find_packages

setup(
    name="brsystem",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "flask==3.0.2",
        "python-dotenv==1.0.1"
    ],
) 