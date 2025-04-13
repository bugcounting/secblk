# Context file to import project modules from test directory.
# This is automatically loaded by pytest.
# https://docs.pytest.org/en/stable/goodpractices.html#tests-outside-application-code

# pylint: disable=missing-module-docstring
import sys
import os

# Set up the application path for relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

this_dir = os.path.abspath(os.path.dirname(__file__))

def file_path_in_testdir(file_name: str) -> str:
    """Return the full path to a file in the test directory."""
    return os.path.join(this_dir, file_name)
