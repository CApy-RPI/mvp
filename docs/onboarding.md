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
## Managing Dependencies

### Dependency Management

- Use a virtual environment to manage dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

### Installing Requirements

- Use `requirements.txt` for production dependencies and `requirements_dev.txt` for development dependencies:

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements_dev.txt
```

### requirements.txt vs requirements_dev.txt

- `requirements.txt`: Contains the dependencies required for the application to run in production.
- `requirements_dev.txt`: Contains additional dependencies required for development, such as testing and linting tools.

Example `requirements.txt`:

```plaintext
discord.py
pymongo
```

Example `requirements_dev.txt`:

```plaintext
pytest
flake8
black
mypy
```
---

# Coding Style Guide for Python Discord Bot with MongoDB

## 1. Code Structure and Organization

### 1.1 Folder Structure

Maintain a clear, modular folder layout:

```plaintext
capy/
├── docs/
├── src/
│   ├── capy_app/  
│   │   ├── backend/  
│   │   │   ├── db/                    # Database models and connection utilities
│   │   │   ├── mods/                  # Additional modules for extended functionalities
│   │   │   ├── res/                   # Static resources like images, JSON files, etc.
│   │   │   ├── utils/                 # Utility/helper functions
│   │   ├── frontend/  
│   │   │   ├── cogs/                  # Separate modules for bot commands/features
│   │   │   ├── bot.py
│   │   ├── config.py                  # Configuration constants
│   │   └── main.py                    # Entry point of the bot
├── tests/                             # Unit and integration tests
│   ├── capy_app/  
│   │   ├── backend/  
│   │   │   ├── db/                   
│   │   │   ├── mods/                 
│   │   │   ├── res/                 
│   │   │   ├── utils/                
│   │   ├── frontend/  
│   │   │   ├── cogs/                 
│   │   │   ├── bot.py
│   │   ├── config.py                  
│   │   └── main.py                    
├── .env                           # Environment variables and secrets
├── requirements.txt               # Python dependencies
├── requirements_dev.txt           # Development dependencies
├── style.md                       # Coding style guide
├── test.md                        # Testing script
└── updater.py                     # Script for updating host
```

### 1.2 Code Structure

- Use a class-based design for modularity:
  - Define a `Cog` for each bot feature (e.g., moderation, profiles).
  - Separate utility methods by category into individual files for clarity.

---

## 2. Python Conventions

### 2.1 Variables and Functions

- Use **snake_case** for variables and functions:

```python
def get_user_profile(user_id: str) -> dict:
    ...
```

### 2.2 Classes

- Use **PascalCase** for class names:

```python
class UserProfile:
    ...
```

### 2.3 Files

- Use **lowercase_with_underscores** for file names (e.g., `user_profiles.py`).

---

## 3. Comments and Documentation

### 3.1 Inline Comments

- Provide concise, meaningful inline comments above complex code:

```python
# Fetch the user profile from the database
user_profile = db.get_user(user_id)
```

### 3.2 Function and Class Docstrings

- Write docstrings for all public functions, methods, and classes. Follow the Google style for docstrings:

```python
def fetch_user_data(user_id: str) -> dict:
    """
    Fetch user data from the database.

    Args:
        user_id (str): The unique ID of the user.

    Returns:
        dict: The user profile data.
    """
```

### 3.3 Module Docstrings

- Include a brief description at the top of each file:

```python
"""
This module handles MongoDB connection and operations
for user profiles.
"""
```

---

## 4. Semantic Guidelines

### 4.1 Code Readability

- Prioritize clarity over brevity:

```python
# Good
for user in user_list:
    if user.is_active():
        active_users.append(user)

# Bad
active_users = [u for u in user_list if u.is_active()]
```

### 4.2 MongoDB Semantics

- Use descriptive collection and field names:
  - Collection names: **snake_case plural** (e.g., `user_profiles`).
  - Field names: **camelCase** (to match MongoDB standards).

```json
{
    "_id": "123456",
    "userName": "johndoe",
    "profileSettings": {
        "theme": "dark",
        "notificationsEnabled": true
    }
}
```

### 4.3 Logging

- Use Python's `logging` module:
  - Log at appropriate levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - Include timestamps and context:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

### 4.4 Guard Clauses

- Use guard clauses to simplify complex conditional logic:

```python
def process_user(user):
    if not user.is_active():
        return
    # Process active user
    ...
```

- As compared to:

```python
def process_user(user):
    if user.is_active():
        # Process active user
        ...
```

### 4.5 Helper Methods

- Use helper methods to break down complex algorithms into smaller, manageable pieces, especially for methods with many tab scopes:

```python
def complex_algorithm(data):
    result = step_one(data)
    result = step_two(result)
    return step_three(result)

def step_one(data):
    # Perform first step
    ...

def step_two(data):
    # Perform second step
    ...

def step_three(data):
    # Perform third step
    ...
```

### 4.6 Error Handling

- Catch specific exceptions, log meaningful messages, and use `raise` to propagate errors:

```python
try:
    db.connect()
except ConnectionError as e:
    logging.error(f"Database connection failed: {e}")
    raise
```

- Example:

```python
def fetch_user_data(user_id: str) -> dict:
    try:
        user_data = db.get_user(user_id)
        if not user_data:
            raise ValueError(f"No user found with ID: {user_id}")
        return user_data
    except Exception as e:
        logging.error(f"Error fetching user data: {e}")
        raise
```

---
## 5. Imports

### 5.1 Minimize Imports

- Minimize the use of `from library import a, b, c, d`. Instead, import the entire module and use it with the module name to avoid namespace conflicts:

```python
# Good
import os
import sys

# Bad
from os import path, mkdir, remove
from sys import argv, exit
```

### 5.2 Import Order

- Follow the standard import order: standard library imports, third-party imports, and local imports. Separate each group with a blank line:

```python
# Standard library imports
import os
import sys

# Third-party imports
import requests

# Local imports
from .utils import helper_function
```

---

## 6. Module Initialization

### 6.1 Creating `__init__.py` Files

- When adding new scripts to a module, ensure that the module's directory contains an `__init__.py` file. This file can be empty or used to initialize the module.

---

# Quality-Driven Development

This development approach emphasizes meeting strict quality gates before considering any task or feature "done." It integrates principles from several established methodologies, ensuring robust, maintainable, and error-free code.

## Key Principles

1. **Test-Driven Development (TDD):**
   - Writing automated tests before implementing the code.
   - Ensures functionality meets requirements from the start.
   - Emphasizes "all tests must pass" as a non-negotiable requirement.

2. **Continuous Integration/Continuous Deployment (CI/CD):**
   - Every change to the codebase passes through automated pipelines for testing, linting, and type checks.
   - Ensures consistent code quality and reduces integration issues.

3. **Static Typing and Code Quality Enforcement:**
   - Tools like `mypy` (type checking), `flake8` or `pylint` (linting), and `black` (code formatting) are enforced.
   - Guarantees code is type-safe, well-formatted, and adheres to coding standards.

4. **Definition of Done (DoD):**
   - Establishes a clear checklist to define when a task or feature is complete.
   - Tasks must:
     - Pass all automated tests.
     - Validate linting rules.
     - Enforce typing with no errors.
   - Prevents incomplete or low-quality code from being merged or deployed.

## Quality-Driven Development Practices

- **Prioritizing Quality Gates:** Quality gates (tests, linting, typing) are prerequisites for task completion.
- **Clean Code Development:** Clean, maintainable, and validated code is enforced in every step of the workflow.
- **Best Practices-Driven Development:** Industry standards like TDD, CI/CD, and static typing are integrated to ensure robustness.

## Benefits of This Approach

- **Error Prevention:** Automated gates catch issues early in the development process.
- **Consistency:** Linting and typing ensure code adheres to a uniform style and standard.
- **Robustness:** Passing tests and type checks reduces bugs and increases confidence in the code.
- **Maintainability:** Clean, well-tested code is easier to understand and extend in the future.

## AI in Quality-Driven Development

The use of AI is not only allowed but also encouraged. AI tools can assist in:

- **Debugging:** Identifying and resolving issues quickly.
- **Code Suggestions:** Accelerating development by generating code snippets and tests.
- **Research Assistance:** Streamlining research into best practices and tools.

However, we maintain high standards for students' ability to debug and research issues independently. All development practices must be met before marking a task as done. If any criteria are unmet, we will work with the developer to review and improve the work.

## Pre-Push Checklist

Before pushing your code to the repository, ensure the following steps are completed:

1. **Code Formatting with Black**

   - Use **black** to automatically format your code files:

   ```bash
   # Install black if not already installed
   pip install black

   # Format your code files
   black path/to/your/code/file.py
   ```

2. **Linting with Flake8**

   - Use **flake8** to check for style guide enforcement and code quality issues in your code files:

   ```bash
   # Install flake8 if not already installed
   pip install flake8

   # Run flake8 on your code files
   flake8 path/to/your/code/file.py
   ```

3. **Type Checking with Mypy**

   - Use **mypy** for static type checking in your code files:

   ```bash
   # Install mypy if not already installed
   pip install mypy

   # Run mypy on your code files
   mypy path/to/your/code/file.py
   ```

4. **Running Tests with Pytest**

   - Use **pytest** for running unit tests:

   ```bash
   # Install pytest if not already installed
   pip install pytest

   # Run all tests
   pytest
   ```

5. **Creating Branch**
    - Ensure that you are checked out of the develop branch
    - On Linear, select which issue you are working on and do:
        - **Command/Ctrl + Shift + "."**
   
      This copies the branch name template that you have to use on your created branch
        ```plaintext
        feature/cap-[ISSUE_NUM]
        ```
    - Run this command, ensuring that you are using the specified branch name template. Make sure that you append an issue title at the end of the name as well:
        ```bash
        git checkout -b feature/cap-[ISSUE_NUM]-["Issue Title"]
        ```
      
6. **Pushing to the Repository**

   - Ensure all tests pass and code is properly formatted and linted before pushing:

   ```bash
   # Add changes to the staging area
   git add .

   # Commit changes with a descriptive message
   git commit -m "[Description of changes]"

   # Push changes to the repository
   git push origin [branch-name]
   ```

   - Use descriptive commit messages:

   ```plaintext
   [Feature] Add user profile creation functionality
   [Refactor] Moving utility method to module
   [Fix] Resolve MongoDB connection issue
   ```

## Pull Request Guidelines

- Include a clear description of changes.
- Link to relevant issues.
- Request at least one reviewer for approval.