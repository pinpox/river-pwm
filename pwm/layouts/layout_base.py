"""
Window Layout Base Classes

Provides the Layout interface and shared layout infrastructure.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING

from ..protocol import Area, WindowEdges, BorderConfig

if TYPE_CHECKING:
    from ..objects import Window, Output


@dataclass
class LayoutGeometry:
    """Calculated geometry for a window in a layout."""

    x: int
    y: int
    width: int
    height: int
    tiled_edges: WindowEdges = WindowEdges.NONE


class LayoutDirection(Enum):
    """Split direction for layouts."""

    HORIZONTAL = auto()  # Windows arranged left-to-right
    VERTICAL = auto()  # Windows arranged top-to-bottom


class Layout(ABC):
    """Abstract base class for window layouts."""

    @abstractmethod
    def calculate(
        self,
        windows: List["Window"],
        area: Area,
        focused_window: Optional["Window"] = None,
    ) -> Dict["Window", LayoutGeometry]:
        """
        Calculate window positions and sizes.

        Args:
            windows: List of windows to layout
            area: Available area for the layout
            focused_window: Currently focused window (optional, used for stacking order)

        Returns:
            Dictionary mapping windows to their calculated geometry
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Layout name for display."""
        pass

    # Decoration interface methods (with default implementations)
    def should_render_decorations(self) -> bool:
        """Whether this layout renders custom decorations."""
        return False

    def create_decorations(self, connection, style):
        """Create decoration resources. Called once when layout activated."""
        pass

    def render_decorations(self, windows, focused_window, area):
        """Render decorations. Called every frame."""
        pass

    def cleanup_decorations(self):
        """Clean up decoration resources. Called when layout deactivated."""
        pass


@dataclass
class Workspace:
    """Represents a workspace/tag containing windows."""

    name: str
    windows: List["Window"] = field(default_factory=list)
    layout: Optional[Layout] = None
    focused_window: Optional["Window"] = None

    def add_window(self, window: "Window"):
        """Add a window to the workspace."""
        if window not in self.windows:
            self.windows.append(window)
            if self.focused_window is None:
                self.focused_window = window

    def remove_window(self, window: "Window"):
        """Remove a window from the workspace."""
        if window in self.windows:
            self.windows.remove(window)
            if self.focused_window == window:
                self.focused_window = self.windows[0] if self.windows else None
            # Clean up floating layout if needed
            if self.layout and hasattr(self.layout, "remove_window"):
                self.layout.remove_window(window)

    def focus_next(self):
        """Focus the next window."""
        if not self.windows or self.focused_window is None:
            return
        idx = self.windows.index(self.focused_window)
        self.focused_window = self.windows[(idx + 1) % len(self.windows)]

    def focus_prev(self):
        """Focus the previous window."""
        if not self.windows or self.focused_window is None:
            return
        idx = self.windows.index(self.focused_window)
        self.focused_window = self.windows[(idx - 1) % len(self.windows)]

    def swap_next(self):
        """Swap focused window with next."""
        if not self.windows or self.focused_window is None:
            return
        idx = self.windows.index(self.focused_window)
        next_idx = (idx + 1) % len(self.windows)
        self.windows[idx], self.windows[next_idx] = (
            self.windows[next_idx],
            self.windows[idx],
        )

    def swap_prev(self):
        """Swap focused window with previous."""
        if not self.windows or self.focused_window is None:
            return
        idx = self.windows.index(self.focused_window)
        prev_idx = (idx - 1) % len(self.windows)
        self.windows[idx], self.windows[prev_idx] = (
            self.windows[prev_idx],
            self.windows[idx],
        )

    def promote(self):
        """Promote focused window to master."""
        if not self.windows or self.focused_window is None:
            return
        if self.focused_window != self.windows[0]:
            self.windows.remove(self.focused_window)
            self.windows.insert(0, self.focused_window)

    def cycle_tabs_forward(self):
        """Cycle to next tab (for tabbed layout)."""
        self.focus_next()

    def cycle_tabs_backward(self):
        """Cycle to previous tab (for tabbed layout)."""
        self.focus_prev()


class LayoutManager:
    """
    Manages layouts for multiple outputs and workspaces.

    This component subscribes to window/output lifecycle events and layout command events.
    It publishes WORKSPACE_SWITCHED and LAYOUT_CHANGED events.

    Responsibilities:
    - Manage workspaces and window placement
    - Handle window and output lifecycle
    - CMD_CYCLE_LAYOUT: Cycle through available layouts
    - CMD_CYCLE_LAYOUT_REVERSE: Cycle layouts in reverse
    - CMD_SWAP_NEXT/PREV: Swap windows within workspace
    - CMD_PROMOTE: Promote window to master
    - CMD_SWITCH_WORKSPACE: Switch to workspace
    - CMD_MOVE_TO_WORKSPACE: Move window to workspace
    - CMD_CYCLE_TAB_FORWARD/BACKWARD: Cycle tabs (for tabbed layout)
    """

    def __init__(self, bus, layouts: Optional[List[Layout]] = None):
        self.bus = bus
        self.outputs: Dict[int, "Output"] = {}
        self.workspaces: Dict[int, Dict[int, Workspace]] = (
            {}
        )  # output_id -> workspace_id -> Workspace
        self.active_workspace: Dict[int, int] = {}  # output_id -> active workspace id
        self.window_workspace: Dict[int, Tuple[int, int]] = (
            {}
        )  # window_id -> (output_id, workspace_id)

        # Configuration
        self.num_workspaces = 9
        self.gap = 4
        self.border_width = 2

        # Store provided layouts (will be set properly by RiverWM)
        self.layouts: List[Layout] = layouts if layouts is not None else []

        self.border_color = BorderConfig(
            edges=WindowEdges.TOP
            | WindowEdges.BOTTOM
            | WindowEdges.LEFT
            | WindowEdges.RIGHT,
            width=2,
            r=0x4C4C4C,
            g=0x4C4C4C,
            b=0x4C4C4C,
            a=0xFFFFFFFF,
        )
        self.focused_border_color = BorderConfig(
            edges=WindowEdges.TOP
            | WindowEdges.BOTTOM
            | WindowEdges.LEFT
            | WindowEdges.RIGHT,
            width=2,
            r=0x5294E2,
            g=0x5294E2,
            b=0x5294E2,
            a=0xFFFFFFFF,
        )

        # Track focused output via bus
        self.focused_output: Optional["Output"] = None

        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Subscribe to events LayoutManager cares about."""
        from pubsub import pub
        from .. import topics

        # Notification events
        pub.subscribe(self._on_window_created, topics.WINDOW_CREATED)
        pub.subscribe(self._on_window_closed, topics.WINDOW_CLOSED)
        pub.subscribe(self._on_output_created, topics.OUTPUT_CREATED)
        pub.subscribe(self._on_output_removed, topics.OUTPUT_REMOVED)

        # Focus state (to track focused output)
        pub.subscribe(self._on_focused_output_changed, topics.FOCUSED_OUTPUT_CHANGED)

        # Layout command events
        pub.subscribe(self._on_cycle_layout, topics.CMD_CYCLE_LAYOUT)
        pub.subscribe(self._on_cycle_layout_reverse, topics.CMD_CYCLE_LAYOUT_REVERSE)
        pub.subscribe(self._on_swap_next, topics.CMD_SWAP_NEXT)
        pub.subscribe(self._on_swap_prev, topics.CMD_SWAP_PREV)
        pub.subscribe(self._on_promote, topics.CMD_PROMOTE)
        pub.subscribe(self._on_cycle_tab_forward, topics.CMD_CYCLE_TAB_FORWARD)
        pub.subscribe(self._on_cycle_tab_backward, topics.CMD_CYCLE_TAB_BACKWARD)

        # Workspace command events
        pub.subscribe(self._on_switch_workspace, topics.CMD_SWITCH_WORKSPACE)
        pub.subscribe(self._on_move_to_workspace, topics.CMD_MOVE_TO_WORKSPACE)

    def _on_focused_output_changed(self, output):
        """Track focused output from FocusManager."""
        self.focused_output = output

    def _on_output_created(self, output: "Output"):
        """Handle OUTPUT_CREATED event."""
        self.add_output(output)

    def _on_output_removed(self, output: "Output"):
        """Handle OUTPUT_REMOVED event."""
        self.remove_output(output)

    def _on_window_created(self, window: "Window"):
        """Handle WINDOW_CREATED event."""
        # Add to active workspace on focused output
        output = self.focused_output if self.focused_output else None
        self.add_window(window, output)

    def _on_window_closed(self, window: "Window"):
        """Handle WINDOW_CLOSED event."""
        self.remove_window(window)

    def add_output(self, output: "Output"):
        """Add an output to manage."""
        self.outputs[output.object_id] = output
        self.workspaces[output.object_id] = {}
        # effective_gap ensures visual gap between borders equals configured gap
        effective_gap = self.gap + (self.border_width * 2)
        for i in range(1, self.num_workspaces + 1):
            # Use first layout from self.layouts, or create a default
            if self.layouts:
                layout = self.layouts[0]
            else:
                # Import here to avoid circular dependency
                from .layout_tiling import TilingLayout

                layout = TilingLayout(gap=effective_gap)

            self.workspaces[output.object_id][i] = Workspace(name=str(i), layout=layout)
        self.active_workspace[output.object_id] = 1

    def remove_output(self, output: "Output"):
        """Remove an output from management."""
        if output.object_id in self.outputs:
            del self.outputs[output.object_id]
            del self.workspaces[output.object_id]
            del self.active_workspace[output.object_id]

    def add_window(self, window: "Window", output: Optional["Output"] = None):
        """Add a window to the layout."""
        if output is None:
            # Use first available output
            if not self.outputs:
                return
            output = next(iter(self.outputs.values()))

        output_id = output.object_id
        ws_id = self.active_workspace.get(output_id, 1)

        if output_id in self.workspaces and ws_id in self.workspaces[output_id]:
            self.workspaces[output_id][ws_id].add_window(window)
            self.window_workspace[window.object_id] = (output_id, ws_id)

    def remove_window(self, window: "Window"):
        """Remove a window from the layout."""
        if window.object_id in self.window_workspace:
            output_id, ws_id = self.window_workspace[window.object_id]
            if output_id in self.workspaces and ws_id in self.workspaces[output_id]:
                self.workspaces[output_id][ws_id].remove_window(window)
            del self.window_workspace[window.object_id]

    def get_active_workspace(self, output: "Output") -> Optional[Workspace]:
        """Get the active workspace for an output."""
        output_id = output.object_id
        if output_id not in self.active_workspace:
            return None
        ws_id = self.active_workspace[output_id]
        return self.workspaces.get(output_id, {}).get(ws_id)

    def switch_workspace(self, output: "Output", workspace_id: int):
        """Switch to a different workspace."""
        from pubsub import pub
        from .. import topics

        output_id = output.object_id
        if output_id in self.workspaces and workspace_id in self.workspaces[output_id]:
            old_workspace = self.active_workspace.get(output_id, 1)
            self.active_workspace[output_id] = workspace_id

            # Publish workspace switch event
            pub.sendMessage(
                topics.WORKSPACE_SWITCHED,
                current_workspace=workspace_id,
                old_workspace=old_workspace,
                output_name=output.name if hasattr(output, "name") else str(output_id),
            )

    def move_window_to_workspace(self, window: "Window", workspace_id: int):
        """Move a window to a different workspace."""
        if window.object_id not in self.window_workspace:
            return

        output_id, old_ws_id = self.window_workspace[window.object_id]
        if old_ws_id == workspace_id:
            return

        if output_id in self.workspaces:
            if old_ws_id in self.workspaces[output_id]:
                self.workspaces[output_id][old_ws_id].remove_window(window)
            if workspace_id in self.workspaces[output_id]:
                self.workspaces[output_id][workspace_id].add_window(window)
                self.window_workspace[window.object_id] = (output_id, workspace_id)

    def cycle_layout(self, output: "Output", direction: int = 1):
        """Cycle through available layouts."""
        from pubsub import pub
        from .. import topics

        workspace = self.get_active_workspace(output)
        if workspace is None:
            return

        # Clean up old layout decorations
        if workspace.layout and workspace.layout.should_render_decorations():
            workspace.layout.cleanup_decorations()
            if hasattr(workspace.layout, "_decorations_created"):
                delattr(workspace.layout, "_decorations_created")

        current_idx = 0
        if workspace.layout:
            for i, layout in enumerate(self.layouts):
                if layout.name == workspace.layout.name:
                    current_idx = i
                    break

        new_idx = (current_idx + direction) % len(self.layouts)
        # Use the layout instance from self.layouts
        workspace.layout = self.layouts[new_idx]

        # Publish layout change event
        pub.sendMessage(topics.LAYOUT_CHANGED, layout_name=workspace.layout.name)

    def calculate_layout(self, output: "Output") -> Dict["Window", LayoutGeometry]:
        """Calculate the layout for an output."""
        workspace = self.get_active_workspace(output)
        if workspace is None or workspace.layout is None:
            return {}

        # Get usable area (respecting layer shell exclusive zones)
        area = output.area
        if output.layer_shell_output:
            ls_area = output.layer_shell_output.non_exclusive_area
            if ls_area.width > 0 and ls_area.height > 0:
                area = ls_area

        # All layouts now accept focused_window parameter
        return workspace.layout.calculate(
            workspace.windows, area, workspace.focused_window
        )

    # Command event handlers
    def _on_cycle_layout(self):
        """Handle CMD_CYCLE_LAYOUT command."""
        if self.focused_output:
            self.cycle_layout(self.focused_output, direction=1)

    def _on_cycle_layout_reverse(self):
        """Handle CMD_CYCLE_LAYOUT_REVERSE command."""
        if self.focused_output:
            self.cycle_layout(self.focused_output, direction=-1)

    def _on_swap_next(self):
        """Handle CMD_SWAP_NEXT command."""
        if self.focused_output:
            workspace = self.get_active_workspace(self.focused_output)
            if workspace:
                workspace.swap_next()

    def _on_swap_prev(self):
        """Handle CMD_SWAP_PREV command."""
        if self.focused_output:
            workspace = self.get_active_workspace(self.focused_output)
            if workspace:
                workspace.swap_prev()

    def _on_promote(self):
        """Handle CMD_PROMOTE command."""
        if self.focused_output:
            workspace = self.get_active_workspace(self.focused_output)
            if workspace:
                workspace.promote()

    def _on_cycle_tab_forward(self):
        """Handle CMD_CYCLE_TAB_FORWARD command."""
        if self.focused_output:
            workspace = self.get_active_workspace(self.focused_output)
            if workspace:
                workspace.cycle_tabs_forward()

    def _on_cycle_tab_backward(self):
        """Handle CMD_CYCLE_TAB_BACKWARD command."""
        if self.focused_output:
            workspace = self.get_active_workspace(self.focused_output)
            if workspace:
                workspace.cycle_tabs_backward()

    def _on_switch_workspace(self, workspace_id):
        """Handle CMD_SWITCH_WORKSPACE command."""
        if self.focused_output:
            self.switch_workspace(self.focused_output, workspace_id)

    def _on_move_to_workspace(self, workspace_id):
        """Handle CMD_MOVE_TO_WORKSPACE command.

        Args:
            workspace_id: The workspace to move the focused window to
        """
        from pubsub import pub
        from .. import topics

        # Get focused window from the bus - we'll need it from FocusManager
        # For now, get it from the active workspace
        if self.focused_output:
            workspace = self.get_active_workspace(self.focused_output)
            if workspace and workspace.focused_window:
                self.move_window_to_workspace(workspace.focused_window, workspace_id)
