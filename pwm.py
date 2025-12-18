#!/usr/bin/env python3
"""
pwm configuration file.

Customize your window manager settings here.
"""

import sys
import os
from pwm import RiverWM, RiverConfig

# Create configuration
config = RiverConfig(

    # Programs
    terminal=os.getenv("PWM_TERMINAL", "foot"),
    launcher=os.getenv("PWM_LAUNCHER", "fuzzel"),

    # Layout settings
    gap=4,
    border_width=2,

    # Colors (hex format: #RRGGBB or #RRGGBBAA)
    border_color="#4c4c4c",           # Gray
    focused_border_color="#5294e2",   # Blue

    # Number of workspaces
    num_workspaces=9,

    # Focus follows mouse
    focus_follows_mouse=True,
)

# Create and run window manager
wm = RiverWM(config)
sys.exit(wm.run())
