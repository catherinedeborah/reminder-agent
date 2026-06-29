import sys
import os

# Add backend directory to path so that tests can import the 'app' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
