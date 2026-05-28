from pathlib import Path
from PySide6.QtCore import QThread, Signal, QSize
from PySide6.QtGui import QImageReader, QPixmap

from .image_state import ImageState


class ThumbnailLoader(QThread):
    thumbnail_ready = Signal(int, QPixmap)

    def __init__(self, file_list, size=160):
        super().__init__()
        self.file_list = file_list
        self.thumb_size = size
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True
        self.wait(3000)

    def run(self):
        for idx, file_path in enumerate(self.file_list):
            if self._stop_flag:
                return
            if ImageState.is_video(str(file_path)):
                continue
            reader = QImageReader(str(file_path))
            reader.setScaledSize(QSize(self.thumb_size, self.thumb_size))
            img = reader.read()
            if img.isNull():
                continue
            if self._stop_flag:
                return
            pix = QPixmap.fromImage(img)
            self.thumbnail_ready.emit(idx, pix)
            self.msleep(10)
