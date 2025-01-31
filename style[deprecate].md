# Coding Style Guide for Python Discord Bot with MongoDB

## 1. Code Structure and Organization

### 1.1 Folder Structure

Maintain a clear, modular folder layout:

```plaintext
capy/
├── src/
│   ├── capy_backend/  
│   │   ├── db/                    # Database models and connection utilities
│   │   ├── mods/                  # Additional modules for extended functionalities
│   │   ├── res/                   # Static resources like images, JSON files, etc.
│   │   ├── utils/                 # Utility/helper functions
│   ├── capy_discord/  
│   │   ├── cogs/                  # Separate modules for bot commands/features
│   │   ├── bot.py
│   ├── config.py                  # Configuration constants
│   └── main.py                    # Entry point of the bot
├── tests/                         # Unit and integration tests
│   ├── capy_backend/  
│   │   ├── db/                    # Database models and connection utilities
│   │   ├── mods/                  # Additional modules for extended functionalities
│   │   ├── res/                   # Static resources like images, JSON files, etc.
│   │   ├── utils/                 # Utility/helper functions
│   ├── capy_discord/  
│   │   ├── cogs/                  # Separate modules for bot commands/features
│   │   ├── bot.py
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

## 5. Managing Dependencies

### 5.1 Dependency Management

- Use a virtual environment to manage dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

### 5.2 Installing Requirements

- Use `requirements.txt` for production dependencies and `requirements_dev.txt` for development dependencies:

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements_dev.txt
```

### 5.3 requirements.txt vs requirements_dev.txt

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

## 6. Imports

### 6.1 Minimize Imports

- Minimize the use of `from library import a, b, c, d`. Instead, import the entire module and use it with the module name to avoid namespace conflicts:

```python
# Good
import os
import sys

# Bad
from os import path, mkdir, remove
from sys import argv, exit
```

### 6.2 Import Order

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

## 7. Module Initialization

### 7.1 Creating `__init__.py` Files

- When adding new scripts to a module, ensure that the module's directory contains an `__init__.py` file. This file can be empty or used to initialize the module.

---

