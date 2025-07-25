#!/bin/bash

set -e  # Exit on any error

echo "Setting up development environment..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install development requirements
echo "Installing development requirements..."
pip install -r requirements_dev.txt

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install
pre-commit install --hook-type pre-push

echo "Setup complete!"
echo "To activate the virtual environment, run: source .venv/bin/activate"
echo "To run pre-commit on all files: pre-commit run --all-files"
