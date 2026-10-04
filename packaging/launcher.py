"""PyInstaller entry point.

PyInstaller runs the entry script as a top-level module, so the package's
__main__.py (relative import) cannot be used here.
"""
import sys

from school_test_engine.app import main

if __name__ == "__main__":
    sys.exit(main())
