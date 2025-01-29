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
## Managing Dependencies:
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

## Contributing:
Before contributing, ensure the following steps are completed
- Use black to automatically format your code files
```bash
    pip install black
    black path/to/your/file.py
```
- Use flake8 to check for style guide enforcement and code quality issues in your code files:
```bash
    # Install flake8 if not already installed
    pip install flake8

    # Run flake8 on your code files
    flake8 path/to/your/code/file.py
```
- Use mypy for static type checking in your code files:
```bash
    # Install mypy if not already installed
    pip install mypy

    # Run mypy on your code files
    mypy path/to/your/code/file.py
```
- Use pytest for running unit tests:
```bash
    # Install pytest if not already installed
    pip install pytest

    # Run all tests
    pytest
```
To contribute to the project, make sure you:
- Create your feature branch using the command:
```bash
    git checkout -b feature/YourFeature
```
- Adding your changes to the staging area
```bash
    git add .
```
- Commit changes with a descriptive message
```bash
    git commit -m "[Description of changes]"
```
- Push changes to the directory
```bash
    git push origin [feature/YourFeature]
```
- Use descriptive commit messages:
```bash
    [Feature] Add user profile creation functionality
    [Fix] Resolve MongoDB connection issue
```
- Open a pull request
