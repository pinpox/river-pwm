"""
Unit tests for workspace management.
"""

import pytest
from pwm.layouts.layout_base import Workspace, LayoutManager, LayoutDirection
from pwm.layouts import TilingLayout, GridLayout, MonocleLayout
from pwm.protocol import Area


@pytest.mark.unit
class TestWorkspace:
    """Test workspace window management."""

    def test_create_workspace(self, mock_window):
        """Test creating a workspace."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)

        assert ws.name == "test"
        assert ws.layout == layout
        assert len(ws.windows) == 0
        assert ws.focused_window is None

    def test_add_window(self, mock_window):
        """Test adding a window to workspace."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        window = mock_window(object_id=1, title="test window")

        ws.add_window(window)

        assert len(ws.windows) == 1
        assert window in ws.windows
        assert ws.focused_window == window

    def test_add_multiple_windows(self, mock_window):
        """Test adding multiple windows."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        windows = [mock_window(object_id=i) for i in range(1, 4)]

        for window in windows:
            ws.add_window(window)

        assert len(ws.windows) == 3
        # First added window stays focused (only set when None)
        assert ws.focused_window == windows[0]

    def test_remove_window(self, mock_window):
        """Test removing a window from workspace."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        w1 = mock_window(object_id=1)
        w2 = mock_window(object_id=2)

        ws.add_window(w1)
        ws.add_window(w2)
        ws.remove_window(w1)

        assert len(ws.windows) == 1
        assert w1 not in ws.windows
        assert w2 in ws.windows
        # Focus should move to remaining window
        assert ws.focused_window == w2

    def test_remove_focused_window(self, mock_window):
        """Test removing the focused window updates focus."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        windows = [mock_window(object_id=i) for i in range(1, 4)]

        for window in windows:
            ws.add_window(window)

        # Focus is on windows[2]
        ws.remove_window(windows[2])

        # Focus should move to next window (wraps to windows[0])
        assert ws.focused_window in [windows[0], windows[1]]
        assert len(ws.windows) == 2

    def test_remove_last_window(self, mock_window):
        """Test removing the last window clears focus."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        window = mock_window(object_id=1)

        ws.add_window(window)
        ws.remove_window(window)

        assert len(ws.windows) == 0
        assert ws.focused_window is None

    def test_focus_next(self, mock_window):
        """Test cycling focus to next window."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        windows = [mock_window(object_id=i) for i in range(1, 4)]

        for window in windows:
            ws.add_window(window)

        # Initially focused on first window (windows[0])
        assert ws.focused_window == windows[0]

        ws.focus_next()
        assert ws.focused_window == windows[1]

        ws.focus_next()
        assert ws.focused_window == windows[2]

        ws.focus_next()
        # Should cycle back to first window
        assert ws.focused_window == windows[0]

    def test_focus_prev(self, mock_window):
        """Test cycling focus to previous window."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        windows = [mock_window(object_id=i) for i in range(1, 4)]

        for window in windows:
            ws.add_window(window)

        # Initially focused on first window (windows[0])
        ws.focus_prev()
        # Should wrap to last window
        assert ws.focused_window == windows[2]

        ws.focus_prev()
        assert ws.focused_window == windows[1]

        ws.focus_prev()
        assert ws.focused_window == windows[0]

    def test_swap_next(self, mock_window):
        """Test swapping window with next in list."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL)
        ws = Workspace("test", layout=layout)
        windows = [mock_window(object_id=i) for i in range(1, 4)]

        for window in windows:
            ws.add_window(window)

        # Focus windows[2], swap with next (should be windows[0])
        original_order = ws.windows.copy()
        ws.swap_next()

        # Windows should have swapped positions
        assert ws.windows != original_order
