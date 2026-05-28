from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget, QWidget,
    QLineEdit, QLabel, QPushButton,
)
from PySide6.QtCore import Qt, Signal


class UrlInputDialog(QDialog):
    connection_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("播放网络视频")
        self.resize(520, 220)
        self.setMinimumSize(480, 200)
        self.setStyleSheet("""
            QDialog { background: #1e1e1e; }
            QLabel { color: #ccc; font-size: 12px; }
        """)

        # --- Stacking container (content + loading overlay) ---
        stack = QWidget()
        stack_layout = QGridLayout(stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        # --- Content widget ---
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { background: #121212; border: 1px solid #333; border-radius: 4px; }
            QTabBar::tab {
                background: #2a2a2a; color: #aaa; padding: 8px 24px;
                border: 1px solid #333; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: #121212; color: #ff9800; }
            QTabBar::tab:hover { color: #f0f0f0; }
        """)
        content_layout.addWidget(self._tabs)

        # Tab 1: 网络URL
        self._url_tab = QWidget()
        url_layout = QVBoxLayout(self._url_tab)
        url_layout.setContentsMargins(12, 12, 12, 12)
        url_layout.setSpacing(8)
        url_label = QLabel("输入视频文件的直接链接（支持 mp4、avi、mkv 等格式）:")
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://example.com/video.mp4")
        self._url_input.setStyleSheet(self._input_style())
        url_layout.addWidget(url_label)
        url_layout.addWidget(self._url_input)
        url_layout.addStretch()
        self._tabs.addTab(self._url_tab, "网络URL")

        # Tab 2: 直播URL
        self._live_tab = QWidget()
        live_layout = QVBoxLayout(self._live_tab)
        live_layout.setContentsMargins(12, 12, 12, 12)
        live_layout.setSpacing(8)
        live_label = QLabel("输入直播流地址（支持 m3u8、rtmp、http-flv 等协议）:")
        self._live_input = QLineEdit()
        self._live_input.setPlaceholderText("https://example.com/live/stream.m3u8")
        self._live_input.setStyleSheet(self._input_style())
        live_layout.addWidget(live_label)
        live_layout.addWidget(self._live_input)
        live_layout.addStretch()
        self._tabs.addTab(self._live_tab, "直播URL")

        # Error label (shown between tabs and buttons on failure)
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ff5252; font-size: 12px; background: transparent;")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        content_layout.addWidget(self._error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setStyleSheet(self._btn_style())
        self._cancel_btn.clicked.connect(self.reject)

        self._ok_btn = QPushButton("确定")
        self._ok_btn.setStyleSheet(self._btn_style(accent=True))
        self._ok_btn.clicked.connect(self._on_ok)
        self._ok_btn.setDefault(True)

        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addWidget(self._ok_btn)
        content_layout.addLayout(btn_layout)

        stack_layout.addWidget(content, 0, 0)

        # --- Loading overlay ---
        self._loading_overlay = QLabel("正在连接流媒体服务器...\n请稍候")
        self._loading_overlay.setAlignment(Qt.AlignCenter)
        self._loading_overlay.setStyleSheet(
            "background: rgba(0, 0, 0, 200); color: #ff9800; "
            "font-size: 18px; font-weight: bold; border-radius: 2px;"
        )
        self._loading_overlay.hide()
        stack_layout.addWidget(self._loading_overlay, 0, 0)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(stack)

        # Enter shortcut in both inputs
        self._url_input.returnPressed.connect(self._on_ok)
        self._live_input.returnPressed.connect(self._on_ok)

    # ====================== Public API ======================

    def show_loading(self):
        self._error_label.hide()
        self._loading_overlay.show()
        self._ok_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._url_input.setEnabled(False)
        self._live_input.setEnabled(False)
        self._tabs.setEnabled(False)

    def hide_loading(self):
        self._loading_overlay.hide()
        self._ok_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._url_input.setEnabled(True)
        self._live_input.setEnabled(True)
        self._tabs.setEnabled(True)

    def show_error(self, msg: str):
        self.hide_loading()
        self._error_label.setText(msg)
        self._error_label.show()

    def get_url(self) -> str:
        if self._tabs.currentIndex() == 0:
            return self._url_input.text()
        else:
            return self._live_input.text()

    def get_is_live(self) -> bool:
        return self._tabs.currentIndex() == 1

    # ====================== Internal ======================

    def _on_ok(self):
        if self._loading_overlay.isVisible():
            return
        url = self.get_url().strip()
        if not url:
            return
        self.show_loading()
        self.connection_requested.emit(url)

    @staticmethod
    def _input_style():
        return """
            QLineEdit {
                background: #2a2a2a; color: #f0f0f0; border: 1px solid #444;
                border-radius: 4px; padding: 8px 12px; font-size: 13px;
            }
            QLineEdit:focus { border-color: #ff9800; }
        """

    @staticmethod
    def _btn_style(accent=False):
        if accent:
            return (
                "QPushButton { background: #ff9800; color: #121212; border: none; "
                "border-radius: 4px; padding: 8px 24px; font-size: 13px; font-weight: bold; }"
                "QPushButton:hover { background: #f57c00; }"
                "QPushButton:pressed { background: #e65100; }"
            )
        return (
            "QPushButton { background: #333; color: #ccc; border: 1px solid #555; "
            "border-radius: 4px; padding: 8px 24px; font-size: 13px; }"
            "QPushButton:hover { background: #444; color: #f0f0f0; }"
        )
