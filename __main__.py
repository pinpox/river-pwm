"""
Main entry point for running pywm as a module.

Usage:
    python -m pywm [options]
"""

from .riverwm import main

if __name__ == '__main__':
    import sys
    sys.exit(main())
