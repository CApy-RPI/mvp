# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path information --------------------------------------------------------

import sys
from pathlib import Path

# Get the absolute path to the project root
project_root = Path(__file__).parent.parent
src_path = project_root / "src"


# Add paths to Python path
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "CAPY Discord Bot"
copyright = "2024, Jason Zhang, Shamik Karkhanis"
author = "Jason Zhang, Shamik Karkhanis"
release = "0.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration


# Extension configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx.ext.intersphinx",  # Add intersphinx for external docs
]

# Mock external dependencies
autodoc_mock_imports = [
    "discord",
    "discord.ext",
    "motor",
    "motor.motor_asyncio",
    "pymongo",
    "beanie",
    "pydantic",
]

# Intersphinx configuration
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "discord": ("https://discordpy.readthedocs.io/en/stable/", None),
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
