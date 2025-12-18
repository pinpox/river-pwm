"""
Window Layout Management

Provides various layout algorithms for window arrangement.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING

from .protocol import Area, WindowEdges, BorderConfig

if TYPE_CHECKING:
    from .objects import Window, Output


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
    VERTICAL = auto()    # Windows arranged top-to-bottom


class Layout(ABC):
    """Abstract base class for window layouts."""

    @abstractmethod
    def calculate(self, windows: List['Window'], area: Area) -> Dict['Window', LayoutGeometry]:
        """
        Calculate window positions and sizes.

        Args:
            windows: List of windows to layout
            area: Available area for the layout

        Returns:
            Dictionary mapping windows to their calculated geometry
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Layout name for display."""
        pass


class TilingLayout(Layout):
    """
    Master-stack tiling layout.

    One or more master windows on one side, remaining windows stacked on the other.
    """

    def __init__(self,
                 direction: LayoutDirection = LayoutDirection.HORIZONTAL,
                 master_count: int = 1,
                 master_ratio: float = 0.55,
                 gap: int = 4):
        self.direction = direction
        self.master_count = master_count
        self.master_ratio = master_ratio
        self.gap = gap

    @property
    def name(self) -> str:
        if self.direction == LayoutDirection.HORIZONTAL:
            return "tile-right"
        return "tile-bottom"

    def calculate(self, windows: List['Window'], area: Area) -> Dict['Window', LayoutGeometry]:
        if not windows:
            return {}

        result = {}
        n = len(windows)
        master_n = min(self.master_count, n)
        stack_n = n - master_n

        # Apply gap to area
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap
        )

        if n == 1:
            # Single window takes all space
            result[windows[0]] = LayoutGeometry(
                usable.x, usable.y, usable.width, usable.height,
                WindowEdges.TOP | WindowEdges.BOTTOM | WindowEdges.LEFT | WindowEdges.RIGHT
            )
            return result

        # Calculate master and stack areas
        if self.direction == LayoutDirection.HORIZONTAL:
            master_width = int(usable.width * self.master_ratio) if stack_n > 0 else usable.width
            stack_width = usable.width - master_width - self.gap if stack_n > 0 else 0

            # Layout master windows
            master_height = (usable.height - (master_n - 1) * self.gap) // master_n
            for i, win in enumerate(windows[:master_n]):
                y = usable.y + i * (master_height + self.gap)
                edges = WindowEdges.LEFT
                if i == 0:
                    edges |= WindowEdges.TOP
                if i == master_n - 1:
                    edges |= WindowEdges.BOTTOM
                if stack_n == 0:
                    edges |= WindowEdges.RIGHT

                result[win] = LayoutGeometry(
                    usable.x, y, master_width, master_height, edges
                )

            # Layout stack windows
            if stack_n > 0:
                stack_x = usable.x + master_width + self.gap
                stack_height = (usable.height - (stack_n - 1) * self.gap) // stack_n
                for i, win in enumerate(windows[master_n:]):
                    y = usable.y + i * (stack_height + self.gap)
                    edges = WindowEdges.RIGHT
                    if i == 0:
                        edges |= WindowEdges.TOP
                    if i == stack_n - 1:
                        edges |= WindowEdges.BOTTOM

                    result[win] = LayoutGeometry(
                        stack_x, y, stack_width, stack_height, edges
                    )

        else:  # VERTICAL
            master_height = int(usable.height * self.master_ratio) if stack_n > 0 else usable.height
            stack_height = usable.height - master_height - self.gap if stack_n > 0 else 0

            # Layout master windows
            master_width = (usable.width - (master_n - 1) * self.gap) // master_n
            for i, win in enumerate(windows[:master_n]):
                x = usable.x + i * (master_width + self.gap)
                edges = WindowEdges.TOP
                if i == 0:
                    edges |= WindowEdges.LEFT
                if i == master_n - 1:
                    edges |= WindowEdges.RIGHT
                if stack_n == 0:
                    edges |= WindowEdges.BOTTOM

                result[win] = LayoutGeometry(
                    x, usable.y, master_width, master_height, edges
                )

            # Layout stack windows
            if stack_n > 0:
                stack_y = usable.y + master_height + self.gap
                stack_width = (usable.width - (stack_n - 1) * self.gap) // stack_n
                for i, win in enumerate(windows[master_n:]):
                    x = usable.x + i * (stack_width + self.gap)
                    edges = WindowEdges.BOTTOM
                    if i == 0:
                        edges |= WindowEdges.LEFT
                    if i == stack_n - 1:
                        edges |= WindowEdges.RIGHT

                    result[win] = LayoutGeometry(
                        x, stack_y, stack_width, stack_height, edges
                    )

        return result


class MonocleLayout(Layout):
    """
    Monocle layout - all windows full size, stacked.

    Only the focused window is shown.
    """

    def __init__(self, gap: int = 0):
        self.gap = gap

    @property
    def name(self) -> str:
        return "monocle"

    def calculate(self, windows: List['Window'], area: Area) -> Dict['Window', LayoutGeometry]:
        if not windows:
            return {}

        result = {}

        # Apply gap to area
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap
        )

        # All windows get full size
        for win in windows:
            result[win] = LayoutGeometry(
                usable.x, usable.y, usable.width, usable.height,
                WindowEdges.TOP | WindowEdges.BOTTOM | WindowEdges.LEFT | WindowEdges.RIGHT
            )

        return result


class GridLayout(Layout):
    """
    Grid layout - windows arranged in a grid pattern.
    """

    def __init__(self, gap: int = 4):
        self.gap = gap

    @property
    def name(self) -> str:
        return "grid"

    def calculate(self, windows: List['Window'], area: Area) -> Dict['Window', LayoutGeometry]:
        if not windows:
            return {}

        result = {}
        n = len(windows)

        # Calculate grid dimensions
        cols = 1
        while cols * cols < n:
            cols += 1
        rows = (n + cols - 1) // cols

        # Apply gap to area
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap
        )

        cell_width = (usable.width - (cols - 1) * self.gap) // cols
        cell_height = (usable.height - (rows - 1) * self.gap) // rows

        for i, win in enumerate(windows):
            row = i // cols
            col = i % cols
            x = usable.x + col * (cell_width + self.gap)
            y = usable.y + row * (cell_height + self.gap)

            # Calculate tiled edges
            edges = WindowEdges.NONE
            if col == 0:
                edges |= WindowEdges.LEFT
            if col == cols - 1:
                edges |= WindowEdges.RIGHT
            if row == 0:
                edges |= WindowEdges.TOP
            if row == rows - 1:
                edges |= WindowEdges.BOTTOM

            result[win] = LayoutGeometry(x, y, cell_width, cell_height, edges)

        return result


class FloatingLayout(Layout):
    """
    Floating layout - windows keep their current positions.
    """

    def __init__(self, default_width: int = 800, default_height: int = 600):
        self.default_width = default_width
        self.default_height = default_height
        self._positions: Dict[int, Tuple[int, int]] = {}
        self._sizes: Dict[int, Tuple[int, int]] = {}

    @property
    def name(self) -> str:
        return "floating"

    def set_position(self, window: 'Window', x: int, y: int):
        """Set window position."""
        self._positions[window.object_id] = (x, y)

    def set_size(self, window: 'Window', width: int, height: int):
        """Set window size."""
        self._sizes[window.object_id] = (width, height)

    def calculate(self, windows: List['Window'], area: Area) -> Dict['Window', LayoutGeometry]:
        if not windows:
            return {}

        result = {}

        for i, win in enumerate(windows):
            # Get stored or calculate default position
            if win.object_id in self._positions:
                x, y = self._positions[win.object_id]
            else:
                # Cascade new windows
                offset = (i % 10) * 30
                x = area.x + 50 + offset
                y = area.y + 50 + offset
                self._positions[win.object_id] = (x, y)

            # Get stored or calculate default size
            if win.object_id in self._sizes:
                width, height = self._sizes[win.object_id]
            else:
                width = self.default_width
                height = self.default_height
                if win.width > 0 and win.height > 0:
                    width = win.width
                    height = win.height
                self._sizes[win.object_id] = (width, height)

            result[win] = LayoutGeometry(x, y, width, height)

        return result

    def remove_window(self, window: 'Window'):
        """Remove window from tracking."""
        self._positions.pop(window.object_id, None)
        self._sizes.pop(window.object_id, None)


class CenteredMasterLayout(Layout):
    """
    Centered master layout.

    Master window(s) centered, stack windows on both sides.
    """

    def __init__(self,
                 master_count: int = 1,
                 master_ratio: float = 0.5,
                 gap: int = 4):
        self.master_count = master_count
        self.master_ratio = master_ratio
        self.gap = gap

    @property
    def name(self) -> str:
        return "centered-master"

    def calculate(self, windows: List['Window'], area: Area) -> Dict['Window', LayoutGeometry]:
        if not windows:
            return {}

        result = {}
        n = len(windows)
        master_n = min(self.master_count, n)
        stack_n = n - master_n

        # Apply gap
        usable = Area(
            area.x + self.gap,
            area.y + self.gap,
            area.width - 2 * self.gap,
            area.height - 2 * self.gap
        )

        if stack_n == 0:
            # Only master windows - center them
            master_width = int(usable.width * self.master_ratio)
            master_x = usable.x + (usable.width - master_width) // 2
            master_height = (usable.height - (master_n - 1) * self.gap) // master_n

            for i, win in enumerate(windows):
                y = usable.y + i * (master_height + self.gap)
                result[win] = LayoutGeometry(
                    master_x, y, master_width, master_height,
                    WindowEdges.TOP | WindowEdges.BOTTOM | WindowEdges.LEFT | WindowEdges.RIGHT
                )
        else:
            # Master in center, stack split on sides
            master_width = int(usable.width * self.master_ratio)
            side_width = (usable.width - master_width - 2 * self.gap) // 2
            master_x = usable.x + side_width + self.gap

            # Master windows
            master_height = (usable.height - (master_n - 1) * self.gap) // master_n
            for i, win in enumerate(windows[:master_n]):
                y = usable.y + i * (master_height + self.gap)
                result[win] = LayoutGeometry(
                    master_x, y, master_width, master_height,
                    WindowEdges.TOP | WindowEdges.BOTTOM
                )

            # Split stack between left and right
            left_n = stack_n // 2
            right_n = stack_n - left_n

            # Left stack
            if left_n > 0:
                left_height = (usable.height - (left_n - 1) * self.gap) // left_n
                for i, win in enumerate(windows[master_n:master_n + left_n]):
                    y = usable.y + i * (left_height + self.gap)
                    edges = WindowEdges.LEFT
                    if i == 0:
                        edges |= WindowEdges.TOP
                    if i == left_n - 1:
                        edges |= WindowEdges.BOTTOM
                    result[win] = LayoutGeometry(
                        usable.x, y, side_width, left_height, edges
                    )

            # Right stack
            if right_n > 0:
                right_x = master_x + master_width + self.gap
                right_height = (usable.height - (right_n - 1) * self.gap) // right_n
                for i, win in enumerate(windows[master_n + left_n:]):
                    y = usable.y + i * (right_height + self.gap)
                    edges = WindowEdges.RIGHT
                    if i == 0:
                        edges |= WindowEdges.TOP
                    if i == right_n - 1:
                        edges |= WindowEdges.BOTTOM
                    result[win] = LayoutGeometry(
                        right_x, y, side_width, right_height, edges
                    )

        return result


@dataclass
class Workspace:
    """Represents a workspace/tag containing windows."""
    name: str
    windows: List['Window'] = field(default_factory=list)
    layout: Layout = field(default_factory=TilingLayout)
    focused_window: Optional['Window'] = None

    def add_window(self, window: 'Window'):
        """Add a window to the workspace."""
        if window not in self.windows:
            self.windows.append(window)
            if self.focused_window is None:
                self.focused_window = window

    def remove_window(self, window: 'Window'):
        """Remove a window from the workspace."""
        if window in self.windows:
            self.windows.remove(window)
            if self.focused_window == window:
                self.focused_window = self.windows[0] if self.windows else None
            # Clean up floating layout if needed
            if isinstance(self.layout, FloatingLayout):
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
        self.windows[idx], self.windows[next_idx] = self.windows[next_idx], self.windows[idx]

    def swap_prev(self):
        """Swap focused window with previous."""
        if not self.windows or self.focused_window is None:
            return
        idx = self.windows.index(self.focused_window)
        prev_idx = (idx - 1) % len(self.windows)
        self.windows[idx], self.windows[prev_idx] = self.windows[prev_idx], self.windows[idx]

    def promote(self):
        """Promote focused window to master."""
        if not self.windows or self.focused_window is None:
            return
        if self.focused_window != self.windows[0]:
            self.windows.remove(self.focused_window)
            self.windows.insert(0, self.focused_window)


class LayoutManager:
    """
    Manages layouts for multiple outputs and workspaces.
    """

    def __init__(self):
        self.outputs: Dict[int, 'Output'] = {}
        self.workspaces: Dict[int, Dict[int, Workspace]] = {}  # output_id -> workspace_id -> Workspace
        self.active_workspace: Dict[int, int] = {}  # output_id -> active workspace id
        self.window_workspace: Dict[int, Tuple[int, int]] = {}  # window_id -> (output_id, workspace_id)

        # Available layouts
        self.layouts: List[Layout] = [
            TilingLayout(LayoutDirection.HORIZONTAL),
            TilingLayout(LayoutDirection.VERTICAL),
            MonocleLayout(),
            GridLayout(),
            CenteredMasterLayout(),
            FloatingLayout(),
        ]

        # Configuration
        self.num_workspaces = 9
        self.gap = 4
        self.border_width = 2
        self.border_color = BorderConfig(
            edges=WindowEdges.TOP | WindowEdges.BOTTOM | WindowEdges.LEFT | WindowEdges.RIGHT,
            width=2,
            r=0x4c4c4c,
            g=0x4c4c4c,
            b=0x4c4c4c,
            a=0xFFFFFFFF
        )
        self.focused_border_color = BorderConfig(
            edges=WindowEdges.TOP | WindowEdges.BOTTOM | WindowEdges.LEFT | WindowEdges.RIGHT,
            width=2,
            r=0x5294e2,
            g=0x5294e2,
            b=0x5294e2,
            a=0xFFFFFFFF
        )

    def add_output(self, output: 'Output'):
        """Add an output to manage."""
        self.outputs[output.object_id] = output
        self.workspaces[output.object_id] = {}
        for i in range(1, self.num_workspaces + 1):
            self.workspaces[output.object_id][i] = Workspace(
                name=str(i),
                layout=TilingLayout(gap=self.gap)
            )
        self.active_workspace[output.object_id] = 1

    def remove_output(self, output: 'Output'):
        """Remove an output from management."""
        if output.object_id in self.outputs:
            del self.outputs[output.object_id]
            del self.workspaces[output.object_id]
            del self.active_workspace[output.object_id]

    def add_window(self, window: 'Window', output: Optional['Output'] = None):
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

    def remove_window(self, window: 'Window'):
        """Remove a window from the layout."""
        if window.object_id in self.window_workspace:
            output_id, ws_id = self.window_workspace[window.object_id]
            if output_id in self.workspaces and ws_id in self.workspaces[output_id]:
                self.workspaces[output_id][ws_id].remove_window(window)
            del self.window_workspace[window.object_id]

    def get_active_workspace(self, output: 'Output') -> Optional[Workspace]:
        """Get the active workspace for an output."""
        output_id = output.object_id
        if output_id not in self.active_workspace:
            return None
        ws_id = self.active_workspace[output_id]
        return self.workspaces.get(output_id, {}).get(ws_id)

    def switch_workspace(self, output: 'Output', workspace_id: int):
        """Switch to a different workspace."""
        output_id = output.object_id
        if output_id in self.workspaces and workspace_id in self.workspaces[output_id]:
            self.active_workspace[output_id] = workspace_id

    def move_window_to_workspace(self, window: 'Window', workspace_id: int):
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

    def cycle_layout(self, output: 'Output', direction: int = 1):
        """Cycle through available layouts."""
        workspace = self.get_active_workspace(output)
        if workspace is None:
            return

        current_idx = 0
        for i, layout in enumerate(self.layouts):
            if layout.name == workspace.layout.name:
                current_idx = i
                break

        new_idx = (current_idx + direction) % len(self.layouts)
        # Create a new instance of the layout
        layout_class = type(self.layouts[new_idx])
        workspace.layout = layout_class(gap=self.gap)

    def calculate_layout(self, output: 'Output') -> Dict['Window', LayoutGeometry]:
        """Calculate the layout for an output."""
        workspace = self.get_active_workspace(output)
        if workspace is None:
            return {}

        # Get usable area (respecting layer shell exclusive zones)
        area = output.area
        if output.layer_shell_output:
            ls_area = output.layer_shell_output.non_exclusive_area
            if ls_area.width > 0 and ls_area.height > 0:
                area = ls_area

        return workspace.layout.calculate(workspace.windows, area)
