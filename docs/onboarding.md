# Getting Started:

## Installing Python:
Ensure that you have Python 3.12 installed on your system by running the following command:
```bash
python3 --version
```
If Python is not installed, or you need a different version, follow the installation instructions for
your operating system from the official Python documentation: https://www.python.org/downloads/.

## Project Setup:
You'll need to clone the repository containing the project. Open your terminal and execute the following command:
```bash 
    git clone https://github.com/CApy-RPI/mvp
``` 
## Managing Dependecies:
Use a virtual environment to manage dependecies
```bash
    python -m venv venv
    source venv/bin/activate
```

Use requirements.txt for production dependencies and requirements_dev.txt for development dependencies:
```bash
    # Install production dependencies
    pip install -r requirements.txt

    # Install development dependencies
    pip install -r requirements_dev.txt
```
