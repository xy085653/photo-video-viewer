from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPoint
from PySide6.QtGui import QPixmap, QPainter, QWheelEvent, QFont, QImageReader, QColor, QPolygon

from .image_state import ImageState


ZOOM_STEP = 1.15
ZOOM_MIN = 0.05
ZOOM_MAX = 16.0


class _Canvas(QGraphicsView):
    wheel_zoomed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)

        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("QGraphicsView { background: #1a1a1a; border: none; }")

        self._zoom = 1.0
        self._image_path = None
        self._is_video = False

    def set_image(self, path: str):
        self._image_path = path
        pix = QPixmap(path)
        self._item.setPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self._zoom = 1.0
        self.resetTransform()
        self.fitInView(self._item, Qt.KeepAspectRatio)

    def clear_image(self):
        self._image_path = None
        self._is_video = False
        self._item.setPixmap(QPixmap())
        self._scene.setSceneRect(QRectF())

    def set_video_placeholder(self, path: str):
        self._image_path = path
        self._is_video = True
        w, h = 640, 400
        pix = QPixmap(w, h)
        pix.fill(QColor("#1a1a1a"))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#ff9800"))
        painter.setPen(Qt.NoPen)
        cx, cy = w // 2, h // 2 - 20
        sz = 60
        triangle = QPolygon([
            QPoint(int(cx - sz * 0.35), int(cy - sz * 0.5)),
            QPoint(int(cx - sz * 0.35), int(cy + sz * 0.5)),
            QPoint(int(cx + sz * 0.65), int(cy)),
        ])
        painter.drawPolygon(triangle)
        painter.setPen(QColor("#ccc"))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(0, cy + sz, w, 30, Qt.AlignCenter, "Click to play video")
        painter.end()
        self._item.setPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self._zoom = 1.0
        self.resetTransform()
        self.fitInView(self._item, Qt.KeepAspectRatio)

    def apply_zoom(self, zoom: float):
        """外部缩放（工具栏），zoom 相对于 fit 基准"""
        factor = zoom / self._zoom
        self._zoom = zoom
        self.scale(factor, factor)

    def wheelEvent(self, event: QWheelEvent):
        if self._is_video:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            factor = ZOOM_STEP
        elif delta < 0:
            factor = 1 / ZOOM_STEP
        else:
            return
        new_z = self._zoom * factor
        if new_z < ZOOM_MIN or new_z > ZOOM_MAX:
            return
        self._zoom = new_z
        self.scale(factor, factor)
        self.wheel_zoomed.emit(self._zoom)

    @property
    def current_zoom(self):
        return self._zoom


class _InfoOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setObjectName("info_overlay")
        self.setStyleSheet(
            "QFrame#info_overlay {"
            "  background: rgba(18, 18, 18, 180);"
            "  border-radius: 6px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        title_f = QFont()
        title_f.setPointSize(11)
        title_f.setBold(True)

        body_f = QFont()
        body_f.setPointSize(10)

        accent_f = QFont()
        accent_f.setPointSize(10)
        accent_f.setBold(True)

        def make_label(text="", font=body_f, color="#ccc"):
            lbl = QLabel(text)
            lbl.setFont(font)
            lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
            return lbl

        self._name = make_label(font=title_f, color="#f0f0f0")
        self._filesize = make_label()
        self._date = make_label()
        self._dim = make_label()
        self._format = make_label()
        self._ratio = make_label()
        self._zoom_label = make_label(font=accent_f, color="#ff9800")

        layout.addWidget(self._name)
        layout.addWidget(self._filesize)
        layout.addWidget(self._date)
        layout.addWidget(self._dim)
        layout.addWidget(self._format)
        layout.addWidget(self._ratio)
        layout.addWidget(self._zoom_label)

        self.hide()

    def set_image(self, name: str, info: dict, zoom: float, is_video: bool = False):
        self._name.setText(name)
        self._filesize.setText(f"大小：{info.get('filesize', '')}")
        self._date.setText(f"日期：{info.get('date', '')}")
        self._dim.setVisible(not is_video)
        self._format.setVisible(not is_video)
        self._ratio.setVisible(not is_video)
        if not is_video:
            self._dim.setText(f"尺寸：{info.get('dimensions', '')}")
            self._format.setText(f"格式：{info.get('format', '')}")
            self._ratio.setText(f"比例：{info.get('ratio', '')}")
        self._zoom_label.setVisible(not is_video)
        if not is_video:
            self._zoom_label.setText(f"缩放：{zoom:.0%}")
        self.adjustSize()
        self.show()

    def set_zoom(self, zoom: float):
        self._zoom_label.setText(f"缩放：{zoom:.0%}")

    def clear(self):
        self.hide()


class PreviewPanel(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state
        self.setMinimumSize(100, 100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._canvas = _Canvas()
        layout.addWidget(self._canvas)

        self._overlay = _InfoOverlay(self._canvas)
        self._overlay.move(8, 8)

        self._suppress_zoom_sync = False
        self._img_w = 0
        self._img_h = 0

        self._canvas.wheel_zoomed.connect(self._on_wheel_zoomed)
        self._state.current_idx_changed.connect(self._refresh)
        self._state.zoom_changed.connect(self._on_state_zoom_changed)
        self._state.images_changed.connect(self._on_images_changed)

    def _on_wheel_zoomed(self, zoom: float):
        self._overlay.set_zoom(zoom)
        if self._suppress_zoom_sync:
            return
        self._suppress_zoom_sync = True
        self._state.zoom_level = zoom
        self._state.zoom_changed.emit()
        self._suppress_zoom_sync = False

    def _on_state_zoom_changed(self):
        if self._suppress_zoom_sync or self._canvas._is_video:
            return
        path = self._state.current_file
        if path:
            self._canvas.apply_zoom(self._state.zoom_level)
            self._overlay.set_zoom(self._state.zoom_level)

    def _refresh(self):
        path = self._state.current_file
        if not path:
            return
        self._suppress_zoom_sync = True
        self._state.zoom_level = 1.0

        file = Path(path)
        stat = file.stat()

        size_bytes = stat.st_size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"

        mtime = datetime.fromtimestamp(stat.st_mtime)
        date_str = mtime.strftime("%Y-%m-%d %H:%M")

        if ImageState.is_video(path):
            self._canvas.set_video_placeholder(path)
            info = {"filesize": size_str, "date": date_str}
            self._overlay.set_image(file.name, info, 1.0, is_video=True)
        else:
            self._canvas.set_image(path)
            pix = QPixmap(path)
            w, h = pix.width(), pix.height()
            depth = pix.depth()
            reader = QImageReader(path)

            def gcd(a, b):
                while b:
                    a, b = b, a % b
                return a
            g = gcd(w, h)
            ratio_str = f"{w // g}:{h // g}"

            fmt_bytes = reader.format()
            fmt_str = bytes(fmt_bytes).decode().upper() if fmt_bytes else file.suffix.upper()[1:]

            info = {
                "filesize": size_str,
                "date": date_str,
                "dimensions": f"{w} × {h}  ({depth} bit)",
                "format": fmt_str,
                "ratio": ratio_str,
            }
            self._overlay.set_image(file.name, info, 1.0)

        self._suppress_zoom_sync = False

    def _on_images_changed(self):
        if self._state.current_idx < 0:
            self._canvas.clear_image()
            self._overlay.clear()
