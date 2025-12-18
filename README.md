# pywm - Python Window Manager for River

A tiling window manager for the River Wayland compositor, written in Python.

## Features

- **Tiling Layouts**: Master-stack, grid, monocle, centered-master
- **Floating Layout**: Traditional floating windows with mouse move/resize
- **Workspaces**: 9 virtual workspaces per output
- **Key Bindings**: Configurable keyboard shortcuts
- **Pointer Bindings**: Mouse actions with modifier keys
- **Multi-Output**: Full support for multiple monitors
- **Focus-Follows-Mouse**: Optional sloppy focus mode
- **Borders**: Configurable window borders with focus indication

## Requirements

- River Wayland compositor (with river-window-management-v1 protocol)
- Python 3.8+
- No external Python dependencies (uses only standard library)

## Installation

The pywm package is included in the River source tree. To use it:

```bash
# From the river directory
python -m pywm
```

Or install it system-wide:

```bash
pip install -e pywm/
```

## Usage

### Running

```bash
# Basic usage
python -m pywm

# With options
python -m pywm --terminal alacritty --launcher wofi --gap 8

# As a module
python -c "from pywm import RiverWM; RiverWM().run()"
```

### Configuration

Add to your River init script (`~/.config/river/init`):

```bash
#!/bin/sh
# Start the Python window manager
python -m pywm &
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--terminal`, `-t` | `foot` | Terminal emulator command |
| `--launcher`, `-l` | `fuzzel` | Application launcher command |
| `--gap`, `-g` | `4` | Gap between windows (pixels) |
| `--border-width`, `-b` | `2` | Border width (pixels) |

## Default Key Bindings

All bindings use **Super** (Windows/Logo key) as the modifier.

### Window Management

| Binding | Action |
|---------|--------|
| `Super+Return` | Spawn terminal |
| `Super+D` | Spawn launcher |
| `Super+Q` | Close focused window |
| `Super+Shift+Q` | Quit window manager |

### Navigation

| Binding | Action |
|---------|--------|
| `Super+J` / `Super+Down` | Focus next window |
| `Super+K` / `Super+Up` | Focus previous window |
| `Super+Shift+J` | Swap with next window |
| `Super+Shift+K` | Swap with previous window |
| `Super+Shift+Return` | Promote to master |

### Layout

| Binding | Action |
|---------|--------|
| `Super+Space` | Cycle to next layout |
| `Super+Shift+Space` | Cycle to previous layout |
| `Super+F` | Toggle fullscreen |

### Workspaces

| Binding | Action |
|---------|--------|
| `Super+1-9` | Switch to workspace 1-9 |
| `Super+Shift+1-9` | Move window to workspace 1-9 |

### Mouse Bindings

| Binding | Action |
|---------|--------|
| `Super+Left Click` | Move window (enables floating) |
| `Super+Right Click` | Resize window (enables floating) |

## Available Layouts

1. **tile-right** (default): Master-stack with master on left
2. **tile-bottom**: Master-stack with master on top
3. **monocle**: Fullscreen stacked windows
4. **grid**: Windows in a grid pattern
5. **centered-master**: Master in center, stacks on sides
6. **floating**: Traditional floating windows

## Programmatic Usage

```python
from pywm import RiverWM, RiverConfig, TilingLayout

# Create custom configuration
config = RiverConfig(
    terminal='alacritty',
    launcher='wofi',
    gap=8,
    border_width=3,
    focus_follows_mouse=True,
)

# Create and run window manager
wm = RiverWM(config)
wm.run()
```

### Custom Layouts

```python
from pywm import Layout, LayoutGeometry, Area, Window

class MyLayout(Layout):
    @property
    def name(self) -> str:
        return "my-layout"

    def calculate(self, windows: list[Window], area: Area) -> dict[Window, LayoutGeometry]:
        result = {}
        # ... implement layout logic ...
        return result
```

## Architecture

```
pywm/
├── __init__.py      # Package exports
├── __main__.py      # Entry point
├── protocol.py      # Wayland protocol definitions
├── connection.py    # Wayland socket handling
├── objects.py       # Window, Output, Seat objects
├── manager.py       # Core WindowManager class
├── layout.py        # Layout algorithms
└── riverwm.py       # Complete WM implementation
```

### Protocol Support

- `river-window-management-v1`: Core window management
- `river-xkb-bindings-v1`: Keyboard bindings
- `river-layer-shell-v1`: Layer shell integration

## License

Same license as River (ISC License).
