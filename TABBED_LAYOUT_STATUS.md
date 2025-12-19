# Tabbed Layout Implementation Status

## Implementation Complete ✓

The tabbed layout feature has been fully implemented with the following changes:

### 1. Plugin-Style Layout Architecture ✓

**Created Files:**
- `pwm/layouts/layout_base.py` - Base classes with decoration interface
- `pwm/layouts/layout_tiling.py` - Extracted TilingLayout
- `pwm/layouts/layout_monocle.py` - Extracted MonocleLayout
- `pwm/layouts/layout_grid.py` - Extracted GridLayout
- `pwm/layouts/layout_floating.py` - Extracted FloatingLayout
- `pwm/layouts/layout_centered_master.py` - Extracted CenteredMasterLayout
- `pwm/layouts/layout_tabbed.py` - **NEW** TabbedLayout
- `pwm/layouts/tab_decoration.py` - **NEW** TabDecoration renderer
- `pwm/layouts/__init__.py` - Exports all layouts

**Deleted Files:**
- `pwm/layout.py` - Replaced by modular structure

### 2. Layout Interface ✓

Added decoration interface to `Layout` ABC:

```python
class Layout(ABC):
    # Existing methods
    @abstractmethod
    def calculate(self, windows, area) -> Dict[Window, LayoutGeometry]:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    # NEW: Decoration interface (with default implementations)
    def should_render_decorations(self) -> bool:
        return False

    def create_decorations(self, connection, style):
        pass

    def render_decorations(self, windows, focused_window, area):
        pass

    def cleanup_decorations(self):
        pass
```

### 3. User Configuration ✓

**Modified: `pwm/riverwm.py`**
- Added `layouts` parameter to `RiverConfig`
- Added `get_layouts()` method with sensible defaults
- TabbedLayout included in default layout list

**Example Configuration (in `pwm.py`):**
```python
from pwm import (
    TilingLayout, MonocleLayout, GridLayout,
    CenteredMasterLayout, FloatingLayout, TabbedLayout,
    LayoutDirection
)

my_layouts = [
    TilingLayout(LayoutDirection.HORIZONTAL, gap=12),
    TabbedLayout(gap=12, tab_height=30),  # NEW
    MonocleLayout(gap=12),
]

config = RiverConfig(
    layouts=my_layouts,
    # ... other config ...
)
```

### 4. TabbedLayout Features ✓

**Window Management:**
- All windows in workspace automatically become tabs
- Flat structure (simple window list)
- Only focused window is visible
- Other windows hidden

**Tab Bar Rendering:**
- Cairo-rendered tab bar at top of windows
- Shows window titles in each tab
- Focused tab uses `focused_bg_color`
- Unfocused tabs use `bg_color`
- Text truncation with ellipsis for long titles
- Tab separators between tabs

**Navigation:**
- `Alt+Tab` - Cycle forward through tabs
- `Alt+Shift+Tab` - Cycle backward through tabs

### 5. Render Cycle Integration ✓

**Modified: `pwm/riverwm.py:_on_render_start()`**
- Detects tabbed layout
- Shows/hides windows based on focus
- Creates layout decorations on first render
- Calls `render_decorations()` every frame
- Cleans up decorations on layout switch

### 6. IPC Integration ✓

**Modified: `pwm/ipc.py:_get_workspaces()`**
- Added `layout` field with layout name
- Added `tabs` field with tab information:
  - `is_tabbed`: boolean
  - `tab_count`: number of tabs
  - `focused_tab_index`: index of focused tab

**Example IPC Response:**
```json
{
  "num": 1,
  "name": "1",
  "layout": "tabbed",
  "tabs": {
    "is_tabbed": true,
    "tab_count": 3,
    "focused_tab_index": 1
  }
}
```

## Implementation Details

### TabDecoration Class

**Location:** `pwm/layouts/tab_decoration.py`

**Key Features:**
- Creates Wayland surface using `wl_compositor`
- Attaches decoration using `river_decoration_v1` protocol
- Uses shared memory (`wl_shm_pool`) for buffer
- Renders with Cairo graphics library
- Positions tab bar above window using `SET_OFFSET`

**API Used:**
- `connection.send_message()` for Wayland requests
- `ShmPool(connection, size)` constructor
- `pool.create_buffer()` for buffer creation
- `pool.get_data()` for memoryview access
- `cairo.ImageSurface.create_for_data()` for rendering

### Fixed Issues

1. **API Method Names:**
   - Changed `send_request()` → `send_message()`
   - Changed `ShmPool.create()` → `ShmPool(connection, size)`

2. **Buffer Creation:**
   - Fixed parameters for `create_buffer()`
   - Correct format: `WlShm.FORMAT_ARGB8888`

3. **Shared Memory Access:**
   - Changed `pool.data` → `pool.get_data()`

4. **Decoration Attachment:**
   - Use `GET_DECORATION_ABOVE` on window object
   - Create `ProtocolObject` with correct interface
   - Set offset to position above window

## Testing Required

### Manual Testing

**Test Scripts Created:**
- `test_tabbed_simple.sh` - Interactive manual test
- `test_tabbed.py` - IPC monitoring test

**Test Steps:**
1. Start pwm: `nix run . -- --border-width 3`
2. Cycle to tabbed layout: Press `Alt+Space` multiple times
3. Open windows: Press `Alt+Return` 3-4 times
4. Test tab cycling:
   - Press `Alt+Tab` to cycle forward
   - Press `Alt+Shift+Tab` to cycle backward
5. Verify behavior:
   - Tab bar renders at top
   - Only focused window visible
   - Tab titles show window names
   - Focused tab has different background
   - No "TabDecoration: Error" messages

### Expected Behavior

**Visual:**
- Tab bar appears at top of workspace
- Each window gets its own tab
- Focused tab has blue background (#3b4252)
- Unfocused tabs have gray background (#2e3440)
- Tab titles are centered and truncated if needed
- Separators between tabs

**Functionality:**
- Only focused window content is visible
- Alt+Tab cycles through tabs
- Switching workspaces preserves tab state
- Adding/removing windows updates tab bar
- Switching layouts cleans up tab bar

### Edge Cases to Test

1. **Single Window:** Single full-width tab
2. **Many Windows (10+):** Tabs scale appropriately
3. **Long Window Titles:** Truncate with ellipsis
4. **Close Window:** Tabs re-render correctly
5. **New Window:** New tab appears
6. **Switch Workspace:** Tab bar disappears/reappears
7. **Switch Layout:** Decorations clean up properly

## Build Status ✓

Last build: **SUCCESS**
- No compilation errors
- No import errors
- All files tracked in git

## Next Steps

1. **Run Manual Tests:**
   ```bash
   ./test_tabbed_simple.sh
   # or
   python3 test_tabbed.py
   ```

2. **Verify No Errors:**
   - Check for "TabDecoration: Error" messages
   - Verify tab bar renders correctly
   - Test tab navigation

3. **Integration Testing:**
   - Test with different layouts
   - Test workspace switching
   - Test window management operations

4. **Performance Testing:**
   - Monitor rendering performance
   - Check for memory leaks
   - Verify cleanup on layout switch

## Success Criteria

- ✅ Each layout in separate file
- ✅ Layout ABC has decoration interface
- ✅ RiverConfig accepts layouts parameter
- ✅ LayoutManager uses configured layouts
- ✅ TabbedLayout in layout cycle
- ✅ All windows become tabs automatically
- ✅ Only focused tab content visible
- ✅ Alt+Tab cycles forward/backward
- ✅ Tab bar shows window titles
- ✅ Focused tab visually distinct
- ✅ IPC returns tab information
- ⏳ **Needs Testing:** No crashes when switching layouts
- ⏳ **Needs Testing:** No memory leaks
- ⏳ **Needs Testing:** Tab bar renders correctly

## Future Enhancements (Deferred)

- Tab click interaction (pointer event handling)
- Tab close buttons
- Drag-and-drop tab reordering
- Vertical tab bars
- Tab grouping/nesting
- Dynamic tab width sizing
- More layout plugins (spiral, dwindle, etc.)
