"""
Unit tests for layout algorithms.
"""

import pytest
from pwm.layouts import TilingLayout, GridLayout, MonocleLayout
from pwm.layouts.layout_base import LayoutDirection
from pwm.protocol import Area, WindowEdges


@pytest.mark.unit
class TestTilingLayout:
    """Test tiling layout calculations."""

    def test_single_window_fills_area(self, mock_window, standard_area):
        """Single window should fill entire area minus gaps."""
        layout = TilingLayout(
            direction=LayoutDirection.HORIZONTAL, master_count=1, gap=10
        )
        window = mock_window(object_id=1)

        result = layout.calculate([window], standard_area)

        assert len(result) == 1
        geom = result[window]
        # Area minus gaps on all sides: 1920 - 2*10 = 1900, 1080 - 2*10 = 1060
        assert geom.x == 10
        assert geom.y == 10
        assert geom.width == 1900
        assert geom.height == 1060
        # All edges should be tiled
        assert geom.tiled_edges & WindowEdges.TOP
        assert geom.tiled_edges & WindowEdges.BOTTOM
        assert geom.tiled_edges & WindowEdges.LEFT
        assert geom.tiled_edges & WindowEdges.RIGHT

    def test_two_windows_horizontal_split(self, mock_window, standard_area):
        """Two windows split horizontally with master on left."""
        layout = TilingLayout(
            direction=LayoutDirection.HORIZONTAL,
            master_count=1,
            master_ratio=0.55,
            gap=4,
        )
        w1 = mock_window(object_id=1, title="master")
        w2 = mock_window(object_id=2, title="stack")

        result = layout.calculate([w1, w2], standard_area)

        assert len(result) == 2

        # Master window (left side)
        master_geom = result[w1]
        assert master_geom.x == 4  # gap
        assert master_geom.y == 4  # gap
        # Width should be ~55% of usable area
        usable_width = 1920 - 2 * 4  # 1912
        expected_master_width = int(usable_width * 0.55)  # 1051
        assert master_geom.width == expected_master_width
        assert master_geom.tiled_edges & WindowEdges.LEFT
        assert master_geom.tiled_edges & WindowEdges.TOP
        assert master_geom.tiled_edges & WindowEdges.BOTTOM
        assert not (master_geom.tiled_edges & WindowEdges.RIGHT)

        # Stack window (right side)
        stack_geom = result[w2]
        assert stack_geom.x == 4 + expected_master_width + 4  # gap + master + gap
        assert stack_geom.y == 4
        # Stack takes remaining width
        expected_stack_width = usable_width - expected_master_width - 4  # minus gap
        assert stack_geom.width == expected_stack_width
        assert stack_geom.tiled_edges & WindowEdges.RIGHT
        assert stack_geom.tiled_edges & WindowEdges.TOP
        assert stack_geom.tiled_edges & WindowEdges.BOTTOM
        assert not (stack_geom.tiled_edges & WindowEdges.LEFT)

    def test_empty_window_list(self, standard_area):
        """Empty window list should return empty result."""
        layout = TilingLayout(direction=LayoutDirection.HORIZONTAL, gap=10)
        result = layout.calculate([], standard_area)
        assert result == {}

    def test_three_windows_one_master_two_stack(self, mock_window, standard_area):
        """Three windows: one master, two stacked."""
        layout = TilingLayout(
            direction=LayoutDirection.HORIZONTAL,
            master_count=1,
            master_ratio=0.5,
            gap=10,
        )
        windows = [mock_window(object_id=i) for i in range(1, 4)]

        result = layout.calculate(windows, standard_area)

        assert len(result) == 3

        # Master window takes left half
        master_geom = result[windows[0]]
        usable_width = 1920 - 2 * 10  # 1900
        usable_height = 1080 - 2 * 10  # 1060
        expected_master_width = int(usable_width * 0.5)  # 950

        assert master_geom.width == expected_master_width
        assert master_geom.height == usable_height

        # Two stack windows split vertically on right
        stack1_geom = result[windows[1]]
        stack2_geom = result[windows[2]]

        # Stack windows should have same width (right half)
        stack_width = usable_width - expected_master_width - 10  # minus gap
        assert stack1_geom.width == stack_width
        assert stack2_geom.width == stack_width

        # Stack windows split height
        expected_stack_height = (usable_height - 10) // 2  # minus gap, divided by 2
        assert stack1_geom.height == expected_stack_height
        assert stack2_geom.height == expected_stack_height

        # Stack windows positioned vertically
        assert stack1_geom.y == 10
        assert stack2_geom.y == 10 + expected_stack_height + 10  # below first + gap


@pytest.mark.unit
class TestGridLayout:
    """Test grid layout calculations."""

    def test_single_window(self, mock_window, standard_area):
        """Single window fills entire area."""
        layout = GridLayout(gap=10)
        window = mock_window(object_id=1)

        result = layout.calculate([window], standard_area)

        assert len(result) == 1
        geom = result[window]
        assert geom.width == 1900  # 1920 - 2*10
        assert geom.height == 1060  # 1080 - 2*10

    def test_four_windows_2x2_grid(self, mock_window, standard_area):
        """Four windows arranged in 2x2 grid."""
        layout = GridLayout(gap=10)
        windows = [mock_window(object_id=i) for i in range(1, 5)]

        result = layout.calculate(windows, standard_area)

        assert len(result) == 4

        # Calculate expected dimensions
        usable_width = 1920 - 2 * 10  # 1900
        usable_height = 1080 - 2 * 10  # 1060
        cols = 2
        rows = 2
        cell_width = (usable_width - (cols - 1) * 10) // cols  # (1900 - 10) / 2 = 945
        cell_height = (usable_height - (rows - 1) * 10) // rows  # (1060 - 10) / 2 = 525

        # Check all windows have correct dimensions
        for window in windows:
            geom = result[window]
            assert geom.width == cell_width
            assert geom.height == cell_height

        # Check positions form grid
        assert result[windows[0]].x == 10  # top-left
        assert result[windows[0]].y == 10
        assert result[windows[1]].x == 10 + cell_width + 10  # top-right
        assert result[windows[1]].y == 10
        assert result[windows[2]].x == 10  # bottom-left
        assert result[windows[2]].y == 10 + cell_height + 10
        assert result[windows[3]].x == 10 + cell_width + 10  # bottom-right
        assert result[windows[3]].y == 10 + cell_height + 10

    def test_nine_windows_3x3_grid(self, mock_window, standard_area):
        """Nine windows arranged in 3x3 grid."""
        layout = GridLayout(gap=5)
        windows = [mock_window(object_id=i) for i in range(1, 10)]

        result = layout.calculate(windows, standard_area)

        assert len(result) == 9

        # All windows should have same dimensions
        first_geom = result[windows[0]]
        for window in windows[1:]:
            geom = result[window]
            assert geom.width == first_geom.width
            assert geom.height == first_geom.height


@pytest.mark.unit
class TestMonocleLayout:
    """Test monocle layout calculations."""

    def test_single_window_fullscreen(self, mock_window, standard_area):
        """Single window takes full area minus gaps."""
        layout = MonocleLayout(gap=10)
        window = mock_window(object_id=1)

        result = layout.calculate([window], standard_area)

        assert len(result) == 1
        geom = result[window]
        assert geom.x == 10
        assert geom.y == 10
        assert geom.width == 1900
        assert geom.height == 1060
        # All edges tiled
        assert geom.tiled_edges & WindowEdges.TOP
        assert geom.tiled_edges & WindowEdges.BOTTOM
        assert geom.tiled_edges & WindowEdges.LEFT
        assert geom.tiled_edges & WindowEdges.RIGHT

    def test_multiple_windows_same_geometry(self, mock_window, standard_area):
        """All windows get same fullscreen geometry."""
        layout = MonocleLayout(gap=10)
        windows = [mock_window(object_id=i) for i in range(1, 4)]

        result = layout.calculate(windows, standard_area)

        assert len(result) == 3

        # All windows should have identical geometry
        first_geom = result[windows[0]]
        for window in windows[1:]:
            geom = result[window]
            assert geom.x == first_geom.x
            assert geom.y == first_geom.y
            assert geom.width == first_geom.width
            assert geom.height == first_geom.height
            assert geom.tiled_edges == first_geom.tiled_edges
