import os
import subprocess
from PySide6.QtWidgets import (
    QScrollArea, QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, QMenu, QPushButton,
)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QPixmap, QFontMetrics, QAction, QPainter, QColor, QPolygon

from .thumbnail_loader import ThumbnailLoader
from .image_state import ImageState

CELL_W = 136   # 120 thumb + 8 pad * 2
CELL_H = 170   # 120 thumb + 8 gap + ~22 name + 8 pad * 2
THUMB_S = 120


class ThumbnailCell(QFrame):
    clicked = Signal(int)
    double_clicked = Signal(int)
    show_in_explorer = Signal(int)
    delete_requested = Signal(int)
    play_clicked = Signal(int)

    def __init__(self, idx: int, file_path: str = "", parent=None):
        super().__init__(parent)
        self._idx = idx
        self._file_path = file_path
        self._selected = False
        self.setFixedSize(CELL_W, CELL_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self._apply_border()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignCenter)

        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(THUMB_S, THUMB_S)
        self._thumb_label.setAlignment(Qt.AlignCenter)
        self._thumb_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._thumb_label, alignment=Qt.AlignCenter)

        self._name_label = QLabel()
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setFixedWidth(CELL_W - 16)
        self._name_label.setStyleSheet("color: #ccc; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self._name_label)

        btn_size = 44
        self._play_btn = QPushButton("▶", self._thumb_label)
        self._play_btn.setFixedSize(btn_size, btn_size)
        self._play_btn.setCursor(Qt.PointingHandCursor)
        self._play_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 160);"
            "  color: #ff9800;"
            "  font-size: 22px;"
            "  border: 2px solid #ff9800;"
            "  border-radius: 22px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 152, 0, 60);"
            "  color: #fff;"
            "}"
        )
        self._play_btn.move((THUMB_S - btn_size) // 2, (THUMB_S - btn_size) // 2)
        self._play_btn.clicked.connect(lambda: self.play_clicked.emit(self._idx))
        self._play_btn.hide()

    def _apply_border(self):
        color = "#ff9800" if self._selected else "#444"
        self.setStyleSheet(
            f"background: #1e1e1e; border: 1px solid {color}; border-radius: 6px;"
        )

    def set_thumbnail(self, pixmap: QPixmap):
        scaled = pixmap.scaled(THUMB_S, THUMB_S, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._thumb_label.setPixmap(scaled)

    def set_name(self, name: str):
        fm = QFontMetrics(self._name_label.font())
        elided = fm.elidedText(name, Qt.ElideRight, CELL_W - 20)
        self._name_label.setText(elided)
        self._name_label.setToolTip(name)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_border()

    def set_file_path(self, path: str):
        self._file_path = path

    def set_is_video(self, is_video: bool):
        self._play_btn.setVisible(is_video)
        if is_video:
            self._play_btn.raise_()

    def set_video_placeholder(self):
        pix = QPixmap(THUMB_S, THUMB_S)
        pix.fill(QColor("#2a2a2a"))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#ff9800"))
        painter.setPen(Qt.NoPen)
        cx, cy = THUMB_S // 2, THUMB_S // 2
        sz = 24
        triangle = QPolygon([
            QPoint(cx - sz // 3, cy - sz // 2),
            QPoint(cx - sz // 3, cy + sz // 2),
            QPoint(cx + sz * 2 // 3, cy),
        ])
        painter.drawPolygon(triangle)
        painter.end()
        self._thumb_label.setPixmap(pix)

    @property
    def idx(self):
        return self._idx

    def mousePressEvent(self, event):
        self.clicked.emit(self._idx)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self._idx)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_fullscreen = menu.addAction("全屏查看")
        menu.addSeparator()
        act_explorer = menu.addAction("在资源管理器中显示")
        menu.addSeparator()
        act_delete = menu.addAction("删除")

        action = menu.exec(event.globalPos())
        if action == act_fullscreen:
            self.double_clicked.emit(self._idx)
        elif action == act_explorer:
            self.show_in_explorer.emit(self._idx)
        elif action == act_delete:
            self.delete_requested.emit(self._idx)


class ThumbnailPanel(QScrollArea):
    fullscreen_requested = Signal(str)
    play_video_requested = Signal(str)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumSize(200, 200)
        self.setStyleSheet("QScrollArea { background: #121212; border: none; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(12, 12, 12, 12)
        self._grid.setSpacing(8)
        self.setWidget(self._container)

        self._cells = []
        self._thumbs = {}       # idx → QPixmap cache
        self._columns = 4
        self._selected_idx = -1

        self._state.images_changed.connect(self._reload)
        self._state.image_deleted.connect(self._rebuild)
        self._state.current_idx_changed.connect(self._sync_selection)
        self._loader = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        cols = max(1, (w - 24) // (CELL_W + 8))
        if cols != self._columns:
            self._columns = cols
            self._relayout()
        self._update_container_size()

    def _reload(self):
        self._cells.clear()
        self._thumbs.clear()
        self._selected_idx = -1
        self._rebuild()

    def _add_thumbnail(self, idx: int, pixmap: QPixmap):
        self._thumbs[idx] = pixmap
        if idx < len(self._cells):
            self._cells[idx].set_thumbnail(pixmap)

    def _relayout(self):
        """仅重新排列现有 cells，不销毁"""
        for i, cell in enumerate(self._cells):
            self._grid.removeWidget(cell)
        for i, cell in enumerate(self._cells):
            row = i // self._columns
            col = i % self._columns
            self._grid.addWidget(cell, row, col)
        self._update_container_size()

    def _rebuild(self, *_):
        """重建所有 cells（加载新文件夹 / 删除图片时）"""
        # 清空网格
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells.clear()
        self._thumbs.clear()

        if not self._state.current_images:
            self._update_container_size()
            return

        # 删除后重新加载缩略图（索引已变化，旧缓存失效）
        if self._loader:
            self._loader.stop()
        self._loader = ThumbnailLoader(self._state.current_images)
        self._loader.thumbnail_ready.connect(self._add_thumbnail)
        self._loader.start()

        for i, f in enumerate(self._state.current_images):
            cell = ThumbnailCell(i)
            cell.set_name(f.name)
            cell.set_selected(i == self._selected_idx)
            cell.clicked.connect(self._on_cell_clicked)
            cell.double_clicked.connect(self._on_cell_double_clicked)
            cell.show_in_explorer.connect(self._on_show_in_explorer)
            cell.delete_requested.connect(self._on_cell_delete)
            if ImageState.is_video(str(f)):
                cell.set_is_video(True)
                cell.set_video_placeholder()
                cell.play_clicked.connect(self._on_cell_play_clicked)
            elif i in self._thumbs:
                cell.set_thumbnail(self._thumbs[i])
            self._cells.append(cell)
            row = i // self._columns
            col = i % self._columns
            self._grid.addWidget(cell, row, col)

        self._update_container_size()

    def _update_container_size(self):
        rows = max(1, (len(self._cells) + self._columns - 1) // self._columns) if self._cells else 0
        content_w = self._columns * (CELL_W + 8) - 8 + 24  # cells + spacing + margins(12*2)
        content_h = rows * (CELL_H + 8) - 8 + 24 if rows else 0
        self._container.setMinimumSize(0, 0)
        self._container.resize(content_w, content_h)

    def _on_cell_clicked(self, idx: int):
        self._state.select(idx)

    def _on_cell_double_clicked(self, _idx: int):
        path = self._state.current_file
        if not path:
            return
        if self._state.current_file_is_video:
            self.play_video_requested.emit(path)
        else:
            self.fullscreen_requested.emit(path)

    def _on_cell_play_clicked(self, idx: int):
        if 0 <= idx < len(self._state.current_images):
            self._state.select(idx)
            self.play_video_requested.emit(str(self._state.current_images[idx]))

    def _on_show_in_explorer(self, idx: int):
        if 0 <= idx < len(self._state.current_images):
            file_path = str(self._state.current_images[idx])
            subprocess.Popen(["explorer", "/select,", file_path])

    def _on_cell_delete(self, idx: int):
        self._state.delete_at(idx)

    def _sync_selection(self):
        new_idx = self._state.current_idx
        if self._selected_idx != new_idx:
            if 0 <= self._selected_idx < len(self._cells):
                self._cells[self._selected_idx].set_selected(False)
            self._selected_idx = new_idx
            if 0 <= self._selected_idx < len(self._cells):
                self._cells[self._selected_idx].set_selected(True)
        QTimer.singleShot(0, self._update_container_size)
