from pathlib import Path
from PySide6.QtCore import QObject, Signal


class ImageState(QObject):
    images_changed = Signal()        # 图片列表变化（新文件夹加载）
    image_deleted = Signal(int)      # 单张删除（旧索引）
    current_idx_changed = Signal()   # 当前索引变化（导航 / 点击 / 删除后）
    zoom_changed = Signal()          # 缩放比变化

    SUPPORTED = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif')
    VIDEO_EXTS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.webm', '.flv')
    ALL_SUPPORTED = SUPPORTED + VIDEO_EXTS

    def __init__(self):
        super().__init__()
        self.current_folder = None
        self.current_images = []
        self.current_idx = -1
        self.zoom_level = 1.0

    @property
    def current_file(self):
        if 0 <= self.current_idx < len(self.current_images):
            return str(self.current_images[self.current_idx])
        return None

    @property
    def current_file_is_video(self):
        return ImageState.is_video(self.current_file or "")

    @staticmethod
    def is_video(path: str) -> bool:
        return Path(path).suffix.lower() in ImageState.VIDEO_EXTS

    def load_folder(self, folder_path: str):
        self.current_folder = Path(folder_path)
        self.current_images = [
            f for f in self.current_folder.iterdir()
            if f.is_file() and f.suffix.lower() in self.ALL_SUPPORTED
        ]
        self.current_idx = -1
        self.zoom_level = 1.0
        self.images_changed.emit()

    def select(self, idx: int):
        self.current_idx = idx
        self.zoom_level = 1.0
        self.current_idx_changed.emit()

    def prev(self):
        if not self.current_images:
            return
        self.current_idx = (self.current_idx - 1) % len(self.current_images)
        self.current_idx_changed.emit()

    def next(self):
        if not self.current_images:
            return
        self.current_idx = (self.current_idx + 1) % len(self.current_images)
        self.current_idx_changed.emit()

    def zoom_in(self):
        if self.zoom_level >= 4.0:
            return
        self.zoom_level *= 1.25
        self.zoom_changed.emit()

    def zoom_out(self):
        if self.zoom_level <= 0.1:
            return
        self.zoom_level /= 1.25
        self.zoom_changed.emit()

    def delete_current(self):
        if self.current_file is None:
            return False
        return self.delete_at(self.current_idx)

    def delete_at(self, idx: int):
        if not (0 <= idx < len(self.current_images)):
            return False
        file = self.current_images.pop(idx)
        try:
            file.unlink()
        except OSError:
            pass
        if self.current_images:
            self.current_idx = min(idx, len(self.current_images) - 1)
        else:
            self.current_idx = -1
        self.image_deleted.emit(idx)
        self.current_idx_changed.emit()
        return True
