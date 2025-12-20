"""
Application Launcher

Spawns applications in response to command events.
"""

import subprocess
import os


class ApplicationLauncher:
    """Spawns applications in response to command events.

    This component subscribes to CMD_SPAWN_* events and launches
    the configured applications.

    Responsibilities:
    - CMD_SPAWN_TERMINAL: Spawn terminal application
    - CMD_SPAWN_LAUNCHER: Spawn application launcher
    """

    def __init__(self, bus, config):
        """Initialize application launcher.

        Args:
            bus: Event bus instance (Pypubsub)
            config: Configuration object with terminal/launcher paths
        """
        self.bus = bus
        self.config = config
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Subscribe to spawn command events."""
        from pubsub import pub
        from . import topics

        pub.subscribe(self._on_spawn_terminal, topics.CMD_SPAWN_TERMINAL)
        pub.subscribe(self._on_spawn_launcher, topics.CMD_SPAWN_LAUNCHER)

    def _on_spawn_terminal(self):
        """Handle CMD_SPAWN_TERMINAL command."""
        self._spawn(self.config.terminal)

    def _on_spawn_launcher(self):
        """Handle CMD_SPAWN_LAUNCHER command."""
        self._spawn(self.config.launcher)

    def _spawn(self, command: str):
        """Spawn a program.

        Args:
            command: Shell command to execute
        """
        try:
            env = os.environ.copy()
            subprocess.Popen(
                command,
                shell=True,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except Exception as e:
            print(f"Failed to spawn {command}: {e}")
