#!/usr/bin/env python3
"""
pwm configuration file.

Customize your window manager settings here.
"""

import sys
import os
from pwm import RiverWM, RiverConfig, DecorationPosition

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

    # Server-side decorations (titlebars)
    use_ssd=True,                                    # Enable window decorations
    ssd_position=DecorationPosition.BOTTOM,          # Position: TOP or BOTTOM
    ssd_height=24,                                   # Titlebar height in pixels
    ssd_background_color="#2e3440",                  # Background color (unfocused)
    ssd_focused_background_color="#3b4252",          # Background color (focused)
    ssd_text_color="#d8dee9",                        # Window title text color
    ssd_button_color="#5e81ac",                      # Control button color

    # Number of workspaces
    num_workspaces=9,

    # Focus follows mouse
    focus_follows_mouse=True,
)

# Create and run window manager
wm = RiverWM(config)
sys.exit(wm.run())
