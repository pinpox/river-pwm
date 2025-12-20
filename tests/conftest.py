"""
Shared pytest fixtures for pwm tests.
"""

import pytest
from pwm.protocol import Area


@pytest.fixture
def mock_window():
    """Factory fixture for creating mock window objects."""

    class MockWindow:
        def __init__(self, object_id=1, title="test", width=800, height=600):
            self.object_id = object_id
            self.title = title
            self.width = width
            self.height = height
            self.app_id = "test_app"

        def __hash__(self):
            return hash(self.object_id)

        def __eq__(self, other):
            if not isinstance(other, MockWindow):
                return False
            return self.object_id == other.object_id

    return MockWindow


@pytest.fixture
def standard_area():
    """Standard 1920x1080 area for layout tests."""
    return Area(0, 0, 1920, 1080)


@pytest.fixture
def small_area():
    """Small 800x600 area for layout tests."""
    return Area(0, 0, 800, 600)


@pytest.fixture
def portrait_area():
    """Portrait 1080x1920 area for layout tests."""
    return Area(0, 0, 1080, 1920)
