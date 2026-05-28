import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """返回资源文件的绝对路径，兼容开发环境和 PyInstaller 打包环境"""
    try:
        base = Path(sys._MEIPASS)
    except AttributeError:
        base = Path(__file__).parent.parent
    return base / relative_path
