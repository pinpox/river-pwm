"""
Unit tests for OperationManager.
"""

import pytest
from pwm.operation_manager import OperationManager, OpType, Operation
from pwm.protocol import WindowEdges, Area


@pytest.mark.unit
class TestOperationManager:
    """Test OperationManager state management."""

    @pytest.fixture
    def mock_seat(self):
        """Mock seat object."""

        class MockSeat:
            def __init__(self):
                self.op_pointer_started = False
                self.op_ended = False

            def op_start_pointer(self):
                self.op_pointer_started = True

            def op_end(self):
                self.op_ended = True

        return MockSeat()

    @pytest.fixture
    def mock_workspace_with_floating(self):
        """Mock workspace with floating layout."""

        class MockWorkspace:
            def __init__(self):
                self.layout = FloatingLayout()

        return MockWorkspace()

    @pytest.fixture
    def get_workspace_fn(self, mock_workspace_with_floating):
        """Mock function that returns workspace."""
        return lambda window: mock_workspace_with_floating

    def test_initial_state(self, get_workspace_fn):
        """Test OperationManager starts with no active operation."""
        manager = OperationManager(get_workspace_fn)

        assert not manager.is_active()
        assert manager.get_operation_type() == OpType.NONE
        assert manager.get_current_window() is None

    def test_start_move_operation(self, mock_window, mock_seat, get_workspace_fn):
        """Test starting a move operation."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1)

        # Add get_node method to mock window
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        success = manager.start_move(mock_seat, window)

        assert success is True
        assert manager.is_active()
        assert manager.get_operation_type() == OpType.MOVE
        assert manager.get_current_window() == window
        assert mock_seat.op_pointer_started

    def test_start_move_blocks_when_operation_active(
        self, mock_window, mock_seat, get_workspace_fn
    ):
        """Test starting move when operation already active."""
        manager = OperationManager(get_workspace_fn)
        window1 = mock_window(object_id=1)
        window2 = mock_window(object_id=2)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window1.get_node = lambda: Node()
        window2.get_node = lambda: Node()

        # Start first operation
        manager.start_move(mock_seat, window1)

        # Try to start second
        success = manager.start_move(mock_seat, window2)

        assert success is False
        assert manager.get_current_window() == window1  # Still first window

    def test_start_resize_operation(
        self, mock_window, mock_seat, mock_workspace_with_floating, get_workspace_fn
    ):
        """Test starting a resize operation."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1, width=800, height=600)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        # Set window size in floating layout
        mock_workspace_with_floating.layout.set_size(window, 800, 600)

        success = manager.start_resize(
            mock_seat, window, WindowEdges.BOTTOM | WindowEdges.RIGHT
        )

        assert success is True
        assert manager.is_active()
        assert manager.get_operation_type() == OpType.RESIZE
        assert manager.get_current_window() == window
        assert mock_seat.op_pointer_started

    def test_start_resize_no_workspace(self, mock_window, mock_seat):
        """Test starting resize when workspace not found."""
        manager = OperationManager(lambda window: None)  # Returns None
        window = mock_window(object_id=1)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        success = manager.start_resize(mock_seat, window, WindowEdges.RIGHT)

        assert success is False
        assert not manager.is_active()

    def test_handle_move_delta(
        self, mock_window, mock_seat, mock_workspace_with_floating, get_workspace_fn
    ):
        """Test handling pointer delta during move."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        # Start move
        manager.start_move(mock_seat, window)

        # Set initial position
        mock_workspace_with_floating.layout.set_position(window, 100, 200)

        # Handle delta (move +50, +30)
        manager.handle_delta(mock_seat, 50, 30)

        # Check position updated
        positions = mock_workspace_with_floating.layout._positions
        assert positions[window.object_id] == (150, 230)

    def test_handle_resize_delta_bottom_right(
        self, mock_window, mock_seat, mock_workspace_with_floating, get_workspace_fn
    ):
        """Test resizing from bottom-right corner."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1, width=800, height=600)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        # Set initial size
        mock_workspace_with_floating.layout.set_position(window, 100, 200)
        mock_workspace_with_floating.layout.set_size(window, 800, 600)

        # Start resize from bottom-right
        edges = WindowEdges.BOTTOM | WindowEdges.RIGHT
        manager.start_resize(mock_seat, window, edges)

        # Drag +100, +50
        manager.handle_delta(mock_seat, 100, 50)

        # Check size increased
        sizes = mock_workspace_with_floating.layout._sizes
        assert sizes[window.object_id] == (900, 650)

        # Position should not change
        positions = mock_workspace_with_floating.layout._positions
        assert positions[window.object_id] == (100, 200)

    def test_handle_resize_delta_top_left(
        self, mock_window, mock_seat, mock_workspace_with_floating, get_workspace_fn
    ):
        """Test resizing from top-left corner."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1, width=800, height=600)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        # Set initial size and position
        mock_workspace_with_floating.layout.set_position(window, 100, 200)
        mock_workspace_with_floating.layout.set_size(window, 800, 600)

        # Start resize from top-left
        edges = WindowEdges.TOP | WindowEdges.LEFT
        manager.start_resize(mock_seat, window, edges)

        # Drag +100, +50 (opposite direction for top-left)
        manager.handle_delta(mock_seat, 100, 50)

        # Size should decrease (dragging inward)
        sizes = mock_workspace_with_floating.layout._sizes
        assert sizes[window.object_id] == (700, 550)

        # Position should shift to maintain bottom-right corner
        positions = mock_workspace_with_floating.layout._positions
        assert positions[window.object_id] == (200, 250)

    def test_resize_minimum_size(
        self, mock_window, mock_seat, mock_workspace_with_floating, get_workspace_fn
    ):
        """Test resize respects minimum window size."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1, width=200, height=200)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        # Set initial small size
        mock_workspace_with_floating.layout.set_position(window, 100, 200)
        mock_workspace_with_floating.layout.set_size(window, 200, 200)

        # Start resize
        manager.start_resize(mock_seat, window, WindowEdges.RIGHT)

        # Try to shrink below minimum (100px)
        manager.handle_delta(mock_seat, -150, 0)

        # Should be clamped to minimum
        sizes = mock_workspace_with_floating.layout._sizes
        assert sizes[window.object_id][0] == 100  # Width clamped
        assert sizes[window.object_id][1] == 200  # Height unchanged

    def test_end_operation(self, mock_window, mock_seat, get_workspace_fn):
        """Test ending an operation."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1)

        # Mock methods
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()
        window.inform_resize_end = lambda: None

        # Start operation
        manager.start_move(mock_seat, window)
        assert manager.is_active()

        # End operation
        manager.end_operation(mock_seat)

        assert not manager.is_active()
        assert manager.get_operation_type() == OpType.NONE
        assert manager.get_current_window() is None
        assert mock_seat.op_ended

    def test_end_operation_wrong_seat(self, mock_window, get_workspace_fn):
        """Test ending operation with wrong seat does nothing."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        # Create two seats
        class MockSeat:
            def __init__(self):
                self.op_pointer_started = False
                self.op_ended = False

            def op_start_pointer(self):
                self.op_pointer_started = True

            def op_end(self):
                self.op_ended = True

        seat1 = MockSeat()
        seat2 = MockSeat()

        # Start with seat1
        manager.start_move(seat1, window)

        # Try to end with seat2
        manager.end_operation(seat2)

        # Should still be active
        assert manager.is_active()
        assert not seat2.op_ended

    def test_handle_delta_wrong_seat(
        self, mock_window, mock_seat, mock_workspace_with_floating, get_workspace_fn
    ):
        """Test handling delta from wrong seat does nothing."""
        manager = OperationManager(get_workspace_fn)
        window = mock_window(object_id=1)

        # Mock get_node
        class Node:
            x = 100
            y = 200

        window.get_node = lambda: Node()

        # Create second seat
        class MockSeat2:
            pass

        seat2 = MockSeat2()

        # Start with first seat
        manager.start_move(mock_seat, window)
        mock_workspace_with_floating.layout.set_position(window, 100, 200)

        # Try delta with different seat
        manager.handle_delta(seat2, 50, 50)

        # Position should not change
        positions = mock_workspace_with_floating.layout._positions
        assert positions[window.object_id] == (100, 200)
