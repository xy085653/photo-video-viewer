import sys
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QSplitter, QStatusBar,
    QMessageBox, QProgressBar, QWidget, QVBoxLayout, QLabel,
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap, QIcon

from widgets import resource_path
from widgets.image_state import ImageState
from widgets.toolbar import Toolbar
from widgets.folder_tree import FolderTree
from widgets.thumbnail_panel import ThumbnailPanel
from widgets.preview_panel import PreviewPanel
from widgets.video_player import VideoPlayer


class FastStoneImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LuminaView")
        self.setWindowIcon(QIcon(str(resource_path("svg/luminaview_icon.svg"))))
        self.resize(1280, 720)

        self._load_qss()
        self._state = ImageState()
        self._setup_ui()
        self._connect_signals()

        self._slideshow_timer = None

    # ====================== UI 构建 ======================

    def _load_qss(self):
        try:
            with open(resource_path("qss/style.qss"), "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
            print("✅ 已成功加载独立 style.qss 文件")
        except Exception as e:
            print(f"⚠️ QSS 加载失败: {e}")

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.toolbar = Toolbar(self._state)
        main_layout.addWidget(self.toolbar)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        self.folder_tree = FolderTree()
        self.folder_tree.setMinimumSize(100, 100)
        splitter.addWidget(self.folder_tree)

        self.thumb_panel = ThumbnailPanel(self._state)
        self.thumb_panel.setMinimumSize(200, 200)
        splitter.addWidget(self.thumb_panel)

        self.preview_panel = PreviewPanel(self._state)
        self.preview_panel.setMinimumSize(100, 100)
        splitter.addWidget(self.preview_panel)

        splitter.setSizes([260, 640, 380])
        splitter.setMinimumSize(0, 0)
        central.setMinimumSize(0, 0)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("image_progress")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.hide()
        self.statusBar.addPermanentWidget(self.progress_bar)

    # ====================== 跨组件信号连接 ======================

    def _connect_signals(self):
        self._state.images_changed.connect(self._on_images_changed)

        self.folder_tree.folder_selected.connect(self._open_folder_no_re_root)
        self.folder_tree.open_in_explorer_requested.connect(self._open_in_explorer)
        self.toolbar.folder_opened.connect(self._open_folder_and_re_root)

        self.thumb_panel.fullscreen_requested.connect(self._show_fullscreen)
        self.thumb_panel.play_video_requested.connect(self._open_video_player)
        self.toolbar.fullscreen_requested.connect(
            lambda: self._show_fullscreen(self._state.current_file))
        self.toolbar.slideshow_toggled.connect(self._toggle_slideshow)
        self.toolbar.delete_requested.connect(self._delete_current)
        self.toolbar.network_video_requested.connect(lambda url: self._open_network_video())

    # ====================== 文件夹操作（跨组件协调） ======================

    def _open_folder_and_re_root(self, path: str):
        self.folder_tree.set_root(path)
        self._state.load_folder(path)

    def _open_folder_no_re_root(self, path: str):
        self._state.load_folder(path)

    def _open_in_explorer(self, path: str):
        subprocess.Popen(["explorer", path])

    def _open_video_player(self, path: str):
        file_list = [str(f) for f in self._state.current_images]
        player = VideoPlayer(path, file_list, parent=self)
        player.exec()

    def _open_network_video(self):
        from widgets.url_input_dialog import UrlInputDialog

        dialog = UrlInputDialog(self)
        ctx = {"active": True, "timer": None, "tester": None, "reply": None}

        def cleanup_test():
            ctx["active"] = False
            if ctx["timer"] and ctx["timer"].isActive():
                ctx["timer"].stop()
            if ctx["tester"]:
                try:
                    ctx["tester"].stop()
                    ctx["tester"].release()
                except Exception:
                    pass
            if ctx["reply"]:
                try:
                    ctx["reply"].abort()
                except Exception:
                    pass

        dialog.finished.connect(lambda: cleanup_test())

        def on_connection_requested(url: str):
            if not ctx["active"]:
                return
            dialog.show_loading()

            if url.startswith("rtmp://"):
                _test_rtmp(url)
            else:
                _test_http(url)

        # ---- HTTP/HTTPS: QNetworkAccessManager (非阻塞) ----
        def _test_http(url: str):
            from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

            manager = QNetworkAccessManager(dialog)
            request = QNetworkRequest(QUrl(url))
            request.setTransferTimeout(10000)
            request.setRawHeader(b"User-Agent", b"LuminaView/1.0")

            def _try_get():
                if not ctx["active"]:
                    return
                req2 = QNetworkRequest(QUrl(url))
                req2.setTransferTimeout(10000)
                req2.setRawHeader(b"User-Agent", b"LuminaView/1.0")
                reply2 = manager.get(req2)
                ctx["reply"] = reply2

                def on_get_done():
                    if not ctx["active"]:
                        return
                    ctx["reply"] = None
                    if reply2.error() == 0:  # NoError
                        reply2.deleteLater()
                        ctx["active"] = False
                        dialog.accept()
                    else:
                        err = reply2.errorString()
                        reply2.deleteLater()
                        dialog.hide_loading()
                        dialog.show_error(f"无法连接到服务器 ({err})")

                reply2.finished.connect(on_get_done)

            reply = manager.head(request)
            ctx["reply"] = reply

            def on_head_done():
                if not ctx["active"]:
                    return
                ctx["reply"] = None
                if reply.error() == 0:  # NoError
                    reply.deleteLater()
                    ctx["active"] = False
                    dialog.accept()
                else:
                    reply.deleteLater()
                    _try_get()

            reply.finished.connect(on_head_done)

        # ---- RTMP: VLC --vout=none (避免 HWND 阻塞主线程) ----
        def _test_rtmp(url: str):
            import vlc

            inst = vlc.Instance(
                "--vout=none", "--quiet",
                "--network-caching=300", "--live-caching=300",
                "--no-video-title-show",
            )
            tester = inst.media_player_new()
            tester.set_media(inst.media_new(url))
            tester.play()
            ctx["tester"] = tester

            count = [0]
            timer = QTimer(dialog)
            timer.setInterval(500)
            ctx["timer"] = timer

            def poll():
                if not ctx["active"]:
                    return
                count[0] += 1
                if tester.is_playing():
                    timer.stop()
                    try:
                        tester.stop()
                        tester.release()
                    except Exception:
                        pass
                    ctx["active"] = False
                    dialog.accept()
                elif count[0] >= 40:
                    timer.stop()
                    try:
                        tester.stop()
                        tester.release()
                    except Exception:
                        pass
                    dialog.hide_loading()
                    dialog.show_error("无法连接到流媒体服务器，请检查URL后重试")

            timer.timeout.connect(poll)
            timer.start()

        dialog.connection_requested.connect(on_connection_requested)

        if dialog.exec() == QDialog.Accepted:
            url = dialog.get_url()
            player = VideoPlayer(url, parent=self)
            player.exec()

    def _on_images_changed(self):
        imgs = [f for f in self._state.current_images if not ImageState.is_video(str(f))]
        vids = [f for f in self._state.current_images if ImageState.is_video(str(f))]
        parts = []
        if imgs:
            parts.append(f"{len(imgs)} 张图片")
        if vids:
            parts.append(f"{len(vids)} 个视频")
        if parts:
            self.statusBar.showMessage(f"已加载 {'，'.join(parts)}")
        else:
            self.statusBar.showMessage("文件夹中没有支持的图片或视频")

    # ====================== 跨组件 UI 操作 ======================

    def _show_fullscreen(self, file_path: str):
        if not file_path:
            return
        if ImageState.is_video(file_path):
            self._open_video_player(file_path)
            return
        full_win = QLabel()
        full_win.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        full_win.setStyleSheet("background: black;")
        pix = QPixmap(file_path).scaled(
            full_win.screen().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        full_win.setPixmap(pix)
        full_win.setAlignment(Qt.AlignCenter)
        full_win.showFullScreen()

        def exit_fs(e):
            if e.key() == Qt.Key_Escape:
                full_win.close()
        full_win.keyPressEvent = exit_fs
        full_win.show()

    def _toggle_slideshow(self):
        if self._slideshow_timer is not None:
            self._slideshow_timer.stop()
            self._slideshow_timer = None
            self.statusBar.showMessage("幻灯片已停止")
            return
        if not self._state.current_images:
            self.statusBar.showMessage("没有图片可播放")
            return

        def advance():
            self._state.next()
            # 跳过视频，最多尝试一轮
            for _ in range(len(self._state.current_images)):
                if self._state.current_file_is_video:
                    self._state.next()
                else:
                    break
            else:
                # 全是视频，停止幻灯片
                self._slideshow_timer.stop()
                self._slideshow_timer = None
                self.statusBar.showMessage("没有图片可播放（全是视频）")
                return

        self._slideshow_timer = QTimer()
        self._slideshow_timer.timeout.connect(advance)
        self._slideshow_timer.start(3000)
        self.statusBar.showMessage("幻灯片播放中（3秒/张）...")

    def _delete_current(self):
        if self._state.current_file is None:
            return
        name = Path(self._state.current_file).name
        reply = QMessageBox.question(self, "确认删除", f"确定要删除 {name} 吗？")
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._state.delete_current()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = FastStoneImageViewer()
    viewer.show()
    print("🚀 LuminaView 已启动")
    sys.exit(app.exec())
