# pwm - pinpox' Window Manager

A tiling window manager for the River Wayland compositor, written in Python.

<img width="1280" height="718" alt="image" src="https://github.com/user-attachments/assets/42eb1085-5b4c-4a63-be5a-8370735ccf30" />

---

<img width="1280" height="718" alt="image" src="https://github.com/user-attachments/assets/da088c94-4e7d-48d6-9010-1b8c414c89c8" />


## Features

- **Multiple Layouts**: Tiling (horizontal/vertical), grid, monocle, centered-master, floating
- **Workspaces**: 9 virtual workspaces per output
- **Key Bindings**: Configurable keyboard shortcuts
- **Multi-Output**: Full support for multiple monitors
- **Borders**: Configurable window borders with focus indication

## Requirements

- River Wayland compositor 0.4.x (with river-window-management-v1 protocol)
- Python 3.8+
- Nix (for building)

## Installation

### With Nix Flakes

```bash
nix run github:pinpox/river-pwm
```

The script automatically detects if you're running inside another compositor:
- **Nested mode** (if `WAYLAND_DISPLAY` or `DISPLAY` is set): Opens River in a window
- **Bare metal** (if not set): Starts River as the main compositor

### Command Line Options

```bash
pwm --help

Options:
  --terminal, -t TEXT       Terminal emulator (default: foot)
  --launcher, -l TEXT       Application launcher (default: fuzzel)
  --gap, -g INTEGER         Gap between windows in pixels (default: 4)
  --border-width, -b INTEGER Border width in pixels (default: 2)
```

## Default Key Bindings

All bindings use **Alt** as the modifier key.

### Window Management

| Binding | Action |
|---------|--------|
| `Alt+Return` | Spawn terminal |
| `Alt+D` | Spawn launcher |
| `Alt+Q` | Close focused window |
| `Alt+Shift+Q` | Quit window manager |

### Navigation

| Binding | Action |
|---------|--------|
| `Alt+J` / `Alt+Down` | Focus next window |
| `Alt+K` / `Alt+Up` | Focus previous window |
| `Alt+Shift+J` | Swap with next window |
| `Alt+Shift+K` | Swap with previous window |
| `Alt+Shift+Return` | Promote focused window to master |

### Layouts

| Binding | Action |
|---------|--------|
| `Alt+Space` | Cycle to next layout |
| `Alt+Shift+Space` | Cycle to previous layout |
| `Alt+F` | Toggle fullscreen |

### Workspaces

| Binding | Action |
|---------|--------|
| `Alt+1-9` | Switch to workspace 1-9 |
| `Alt+Shift+1-9` | Move window to workspace 1-9 |

## Available Layouts

1. **tile-right** (default): Master window(s) on left, stack on right
2. **tile-bottom**: Master window(s) on top, stack on bottom
3. **monocle**: All windows fullscreen and stacked
4. **grid**: Windows arranged in a grid pattern
5. **centered-master**: Master in center, stacks split on left/right sides
6. **floating**: Traditional floating windows

Cycle through layouts with `Alt+Space` / `Alt+Shift+Space`.

## Project Structure

```
river-pwm/
├── flake.nix           # Nix flake for building
├── __init__.py         # Package exports
├── __main__.py         # Entry point
├── protocol.py         # Wayland protocol definitions
├── connection.py       # Wayland socket handling
├── objects.py          # Window, Output, Seat objects
├── manager.py          # Core WindowManager class
├── layout.py           # Layout algorithms
└── riverwm.py          # Complete WM implementation
```

## Programmatic Usage

```python
from pwm import RiverWM, RiverConfig, Modifiers

# Create custom configuration
config = RiverConfig(
    terminal='alacritty',
    launcher='wofi',
    gap=8,
    border_width=3,
    mod=Modifiers.MOD4,  # Use Super instead of Alt
)

# Create and run window manager
wm = RiverWM(config)
wm.run()
```

### Custom Layouts

```python
from pwm import Layout, LayoutGeometry, Area, Window

class MyLayout(Layout):
    @property
    def name(self) -> str:
        return "my-layout"

    def calculate(self, windows: list[Window], area: Area) -> dict[Window, LayoutGeometry]:
        result = {}
        # ... implement layout logic ...
        return result
```

## Protocol Support

This implementation uses the following River protocols:

- `river-window-management-v1`: Core window management
- `river-xkb-bindings-v1`: Keyboard bindings
- `river-layer-shell-v1`: Layer shell integration

## Development

The project uses Nix flakes for reproducible builds. The flake provides:

- `packages.pwm`: The pwm window manager binary
- `packages.river`: River compositor 0.4.x (from upstream)
- `packages.river-pwm`: Smart launcher script (auto-detects nested/bare-metal mode)

Note: The flake includes River 0.4.x for convenience, but River is developed separately by the River project.

## License

ISC License (same as River).

## Credits

**pwm** is created by pinpox as a window manager for the [River Wayland compositor](https://github.com/riverwm/river).

River itself is developed by Isaac Freund and the River contributors.
