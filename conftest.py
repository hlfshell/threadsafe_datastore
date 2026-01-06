"""
Pytest configuration to handle missing optional dependencies gracefully.
"""

import sys
import os

# Add src to Python path so tests can import the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

