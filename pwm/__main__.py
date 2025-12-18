"""
Main entry point for running pwm as a module.

Usage:
    python -m pwm [options]
"""

from .riverwm import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
