#!/usr/bin/env bash
# River compositor initialization script
# This runs when River starts, before the window manager connects

# Set environment variables if needed
# export MOZ_ENABLE_WAYLAND=1
# export QT_QT_PLATFORM=wayland

# River will wait for this script to complete, then pywm will connect
# For now, we just exit immediately to let River start
# The actual window management is handled by pywm

exit 0
