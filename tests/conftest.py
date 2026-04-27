import sys
import os

# Add src to the python path so tests can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
