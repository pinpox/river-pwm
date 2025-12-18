#!/usr/bin/env python3
"""
Example pwm configuration file.

This is the default configuration used when no custom config is provided.
"""

import sys
from pwm import RiverWM, RiverConfig

# Create configuration
config = RiverConfig()

# Create and run window manager
wm = RiverWM(config)
sys.exit(wm.run())
