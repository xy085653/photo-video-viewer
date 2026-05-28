from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QFileDialog
from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QIcon

from . import resource_path
from .url_input_dialog import UrlInputDialog


class Toolbar(QFrame):
    folder_opened = Signal(str)

    fullscreen_requested = Signal()
    slideshow_toggled = Signal()
    delete_requested = Signal()
    network_video_requested = Signal(str)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedHeight(48)
        self.setObjectName("toolbar_frame")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        def add_sep():
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setFixedHeight(24)
            sep.setStyleSheet("color: #444;")
            layout.addWidget(sep, alignment=Qt.AlignVCenter)

        def add_btn(icon_path, tooltip, slot):
            btn = QPushButton()
            btn.setFixedSize(30, 30)
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        # 文件操作
        add_btn(str(resource_path("svg/open_folder.svg")), "打开文件夹", self._open_folder)
        add_sep()
        # 导航
        add_btn(str(resource_path("svg/prev.svg")), "上一张", self._state.prev)
        add_btn(str(resource_path("svg/next.svg")), "下一张", self._state.next)
        add_sep()
        # 视图
        add_btn(str(resource_path("svg/zoom_out.svg")), "缩小", self._state.zoom_out)
        add_btn(str(resource_path("svg/zoom_in.svg")), "放大", self._state.zoom_in)
        add_btn(str(resource_path("svg/fullscreen.svg")), "全屏", self.fullscreen_requested)
        add_sep()
        # 工具
        add_btn(str(resource_path("svg/slideshow.svg")), "幻灯片", self.slideshow_toggled)
        add_btn(str(resource_path("svg/delete.svg")), "删除", self.delete_requested)
        add_sep()
        add_btn(str(resource_path("svg/network.svg")), "播放网络视频", self._open_network_video)
        layout.addStretch()

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if folder:
            self.folder_opened.emit(folder)

    def _open_network_video(self):
        dialog = UrlInputDialog(self)
        if dialog.exec() == UrlInputDialog.Accepted:
            url = dialog.get_url().strip()
            if url:
                self.network_video_requested.emit(url)
