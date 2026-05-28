# LuminaView

A desktop image viewer and video player built with PySide6 (Qt6) and VLC.

## Features

- **Image Browsing** — Folder tree navigation with thumbnail grid view
- **Image Preview** — Zoom in/out, fullscreen mode, keyboard navigation
- **Video Playback** — Embedded VLC-based player with play/pause, seek, speed control, volume
- **Network Streaming** — Support for HLS (m3u8) and RTMP streams via URL input dialog
- **Slideshow** — Automatic image slideshow with configurable interval
- **Dark Theme** — Orange-accented dark UI theme

## Requirements

- Python 3.10+
- [PySide6](https://pypi.org/project/PySide6/)
- [python-vlc](https://pypi.org/project/python-vlc/) — VLC media player bindings
- [VLC](https://www.videolan.org/vlc/) installed on the system

## Installation

```bash
pip install PySide6 python-vlc
```

## Usage

```bash
python main.py
```

### Keyboard Shortcuts (Image View)

| Key | Action |
|---|---|
| ← / → | Previous / Next image |
| Space | Toggle fullscreen |
| F | Fullscreen |
| Delete | Delete current file |

### Video Player Shortcuts

| Key | Action |
|---|---|
| Space | Play / Pause |
| ← / → | Rewind / Forward 5s |
| ↑ / ↓ | Volume up / down |
| M | Mute toggle |
| F | Fullscreen toggle |
| [ / ] | Speed down / up |
| Home / End | Previous / Next file |
| Escape | Close player |

## Build (PyInstaller)

```bash
pip install pyinstaller
pyinstaller LuminaView.spec
```

## License

MIT
