from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QSlider,
    QLabel, QWidget, QSizePolicy, QMenu, QMessageBox,
)
from PySide6.QtCore import Qt, QSize, QEvent, QTimer
from PySide6.QtGui import QIcon, QKeyEvent
import vlc

from .image_state import ImageState
from . import resource_path


SPEEDS = [("0.5x", 0.5), ("0.75x", 0.75), ("1.0x", 1.0), ("1.25x", 1.25), ("1.5x", 1.5), ("2.0x", 2.0)]
SEEK_STEP = 5000
SEEK_JUMP = 10000
BTN_SIZE = QSize(30, 30)
ICON_SIZE = QSize(18, 18)


def _icon(name: str) -> QIcon:
    return QIcon(str(resource_path(f"svg/{name}.svg")))


def _fmt_time(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


class VideoPlayer(QDialog):
    def __init__(self, file_path: str, file_list: list = None, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._file_list = file_list or []
        self._current_idx = self._find_index(file_path)
        self._last_volume = 70
        self._play_started = False

        self.setWindowTitle(Path(file_path).name)
        self.resize(960, 660)
        self.setMinimumSize(520, 360)
        self.setStyleSheet(
            "QDialog { background: #0a0a0a; }"
            "QToolTip { color: #f0f0f0; background: #333; border: 1px solid #555; padding: 4px; }"
        )

        # --- VLC 后端 ---
        self._vlc = vlc.Instance(
            "--no-video-title-show",
            "--quiet",
            "--network-caching=300",
            "--live-caching=300",
        )
        self._player = self._vlc.media_player_new()

        # --- 视频容器（纯 QWidget，VLC 渲染到其 HWND） ---
        self._video_widget = QWidget()
        self._video_widget.setStyleSheet("background: black;")
        self._video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._video_widget.setFocusPolicy(Qt.StrongFocus)
        self._player.set_hwnd(int(self._video_widget.winId()))

        # --- 视频容器（用于叠加 loading 蒙版） ---
        self._video_container = QWidget()
        container_layout = QGridLayout(self._video_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self._video_widget, 0, 0)

        self._loading_overlay = QLabel("正在加载...")
        self._loading_overlay.setAlignment(Qt.AlignCenter)
        self._loading_overlay.setStyleSheet(
            "background: rgba(0, 0, 0, 200); color: #ff9800; "
            "font-size: 20px; font-weight: bold;"
        )
        container_layout.addWidget(self._loading_overlay, 0, 0)
        self._loading_overlay.hide()

        # --- 设置媒体源 ---
        self._set_media(file_path)

        # --- 整体布局 ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._video_container)
        layout.addWidget(self._make_control_bar())

        # --- VLC 事件 ---
        mgr = self._player.event_manager()
        mgr.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_vlc_playing)
        mgr.event_attach(vlc.EventType.MediaPlayerPaused, self._on_vlc_paused)
        mgr.event_attach(vlc.EventType.MediaPlayerStopped, self._on_vlc_stopped)
        mgr.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)
        mgr.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end_reached)

        # --- 连接超时（防止 VLC 无限等待网络） ---
        self._loading_timer = QTimer(self)
        self._loading_timer.setSingleShot(True)
        self._loading_timer.setInterval(20000)
        self._loading_timer.timeout.connect(self._on_loading_timeout)

        # --- 位置轮询（播放开始后才启动） ---
        self._pos_timer = QTimer(self)
        self._pos_timer.setInterval(200)
        self._pos_timer.timeout.connect(self._poll_position)
        # 不在这里 start()，等 _on_vlc_playing 再启动

        # --- 事件过滤器（键盘） ---
        self._video_widget.installEventFilter(self)
        self.installEventFilter(self)

        # --- 播放延后到 showEvent（对话框显示 + 事件循环就绪后才启动） ---
        self._show_loading()

    # ====================== VLC 媒体控制 ======================

    def _set_media(self, path: str):
        media = self._vlc.media_new(path)
        self._player.set_media(media)

    def _on_vlc_playing(self, event):
        self._play_pause_btn.setIcon(_icon("pause"))
        self._play_pause_btn.setToolTip("暂停")
        self._loading_timer.stop()
        self._hide_loading()
        if not self._pos_timer.isActive():
            self._pos_timer.start()

    def _on_vlc_paused(self, event):
        self._play_pause_btn.setIcon(_icon("play"))
        self._play_pause_btn.setToolTip("播放")

    def _on_vlc_stopped(self, event):
        self._play_pause_btn.setIcon(_icon("play"))
        self._play_pause_btn.setToolTip("播放")

    def _on_loading_timeout(self):
        self._hide_loading()
        self._loading_overlay.setText("连接超时")
        msg = "连接超时，无法连接到流媒体服务器"
        if self.isVisible():
            QMessageBox.warning(self, "连接超时", msg)
        self.close()

    def _on_vlc_error(self, event):
        self._loading_timer.stop()
        self._hide_loading()
        msg = "无法播放此文件或网络流"
        print(msg)
        if self.isVisible():
            QMessageBox.warning(self, "播放错误", msg)

    def _on_vlc_end_reached(self, event):
        """播完自动回到开头（不重复）"""
        self._player.stop()

    def _poll_position(self):
        """定期更新进度条和时间显示"""
        if not self._player.get_media():
            return
        # 时长（文件打开后才能获取）
        duration = self._player.get_length()
        if duration > 0 and self._seek_slider.maximum() != duration:
            self._seek_slider.setRange(0, duration)
            self._total_time.setText(_fmt_time(duration))
        # 当前进度
        pos = self._player.get_time()
        if pos >= 0 and not self._seek_slider.isSliderDown():
            self._seek_slider.setValue(pos)
        self._current_time.setText(_fmt_time(max(0, pos)))

    def _show_loading(self):
        self._loading_overlay.show()

    def _hide_loading(self):
        self._loading_overlay.hide()

    # ====================== 控件构建 ======================

    def _make_control_bar(self):
        self._control_bar = QWidget()
        bar = self._control_bar
        bar.setStyleSheet("background: #1e1e1e;")
        bar.setFixedHeight(52)
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)

        def btn(name, tooltip, slot):
            b = QPushButton()
            b.setFixedSize(BTN_SIZE)
            b.setIcon(_icon(name))
            b.setIconSize(ICON_SIZE)
            b.setToolTip(tooltip)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: #333; border-radius: 4px; }")
            b.clicked.connect(slot)
            return b

        row.addWidget(btn("prev",        "上一个",    self._prev))
        row.addWidget(btn("rewind",      "快退 5秒",  self._rewind))
        self._play_pause_btn = btn("pause", "暂停",   self._toggle_play_pause)
        row.addWidget(self._play_pause_btn)
        row.addWidget(btn("stop",        "停止",      self._stop))
        row.addWidget(btn("forward",     "快进 5秒",  self._forward))
        row.addWidget(btn("next",        "下一个",    self._next))

        sep = QLabel()
        sep.setFixedWidth(1)
        sep.setFixedHeight(24)
        sep.setStyleSheet("background: #444;")
        row.addWidget(sep)

        self._current_time = QLabel("00:00")
        self._current_time.setStyleSheet("color: #ccc; font-size: 12px; background: transparent; min-width: 38px;")
        row.addWidget(self._current_time)

        self._seek_slider = QSlider(Qt.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._seek_slider.setFixedHeight(20)
        self._seek_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #ff9800; width: 12px; margin: -4px 0; border-radius: 6px; }"
            "QSlider::handle:horizontal:hover { background: #f57c00; }"
            "QSlider::sub-page:horizontal { background: #ff9800; border-radius: 2px; }"
        )
        self._seek_slider.sliderMoved.connect(self._on_seek)
        self._seek_slider.sliderPressed.connect(
            lambda: self._player.set_time(self._seek_slider.sliderPosition()))
        row.addWidget(self._seek_slider)

        self._total_time = QLabel("00:00")
        self._total_time.setStyleSheet("color: #ccc; font-size: 12px; background: transparent; min-width: 38px;")
        row.addWidget(self._total_time)

        sep2 = QLabel()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(24)
        sep2.setStyleSheet("background: #444;")
        row.addWidget(sep2)

        self._speed_btn = QPushButton("1.0x")
        self._speed_btn.setFixedSize(56, 30)
        self._speed_btn.setCursor(Qt.PointingHandCursor)
        self._speed_btn.setToolTip("播放速度")
        self._speed_btn.setStyleSheet(
            "QPushButton { color: #ccc; font-size: 12px; background: transparent; border: 1px solid #444; border-radius: 4px; }"
            "QPushButton:hover { color: #ff9800; border-color: #ff9800; }"
        )
        self._speed_btn.clicked.connect(self._show_speed_menu)
        row.addWidget(self._speed_btn)

        self._mute_btn = btn("volume", "静音", self._toggle_mute)
        row.addWidget(self._mute_btn)

        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.setFixedWidth(80)
        self._volume_slider.setFixedHeight(20)
        self._volume_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #fff; width: 10px; margin: -3px 0; border-radius: 5px; }"
            "QSlider::sub-page:horizontal { background: #fff; border-radius: 2px; }"
        )
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        row.addWidget(self._volume_slider)

        row.addWidget(btn("fullscreen", "全屏", self._toggle_fullscreen))

        return bar

    # ====================== 传输控制 ======================

    def _toggle_vlc_volume_mute_icon(self):
        vol = self._player.audio_get_volume()
        if vol == 0:
            self._mute_btn.setIcon(_icon("mute"))
            self._mute_btn.setToolTip("取消静音")
        else:
            self._mute_btn.setIcon(_icon("volume"))
            self._mute_btn.setToolTip("静音")

    def _find_index(self, path: str) -> int:
        try:
            return self._file_list.index(path)
        except ValueError:
            return -1

    def _toggle_play_pause(self):
        if self._player.is_playing():
            self._player.pause()
        else:
            self._player.play()

    def _stop(self):
        self._player.stop()

    def _rewind(self):
        self._player.set_time(max(0, self._player.get_time() - SEEK_STEP))

    def _forward(self):
        dur = self._player.get_length()
        self._player.set_time(min(dur, self._player.get_time() + SEEK_STEP))

    def _prev(self):
        self._navigate(-1)

    def _next(self):
        self._navigate(1)

    def _navigate(self, direction: int):
        if not self._file_list or self._current_idx < 0:
            return
        n = len(self._file_list)
        for _ in range(n):
            self._current_idx = (self._current_idx + direction) % n
            candidate = self._file_list[self._current_idx]
            if ImageState.is_video(candidate):
                self._load_file(str(candidate))
                return

    def _load_file(self, path: str):
        self._file_path = path
        self.setWindowTitle(Path(path).name)
        self._pos_timer.stop()
        self._player.stop()
        self._set_media(path)
        self._show_loading()
        self._loading_timer.start()
        QTimer.singleShot(200, self._player.play)

    # ====================== 倍速 ======================

    def _show_speed_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1e1e; border: 1px solid #444; border-radius: 4px; padding: 4px 0; color: #f0f0f0; }"
            "QMenu::item { padding: 6px 24px; border-radius: 2px; }"
            "QMenu::item:selected { background: #ff9800; color: #121212; }"
        )
        current_rate = self._player.get_rate()
        for label, rate in SPEEDS:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(abs(current_rate - rate) < 0.01)
            action.triggered.connect(lambda _, r=rate: self._set_speed(r))
        menu.exec(self._speed_btn.mapToGlobal(self._speed_btn.rect().bottomLeft()))

    def _set_speed(self, rate: float):
        self._player.set_rate(rate)
        for label, r in SPEEDS:
            if abs(r - rate) < 0.01:
                self._speed_btn.setText(label)
                break

    # ====================== 音量 / 静音 ======================

    def _toggle_mute(self):
        vol = self._player.audio_get_volume()
        if vol == 0:
            self._player.audio_set_volume(max(1, self._last_volume))
            self._volume_slider.blockSignals(True)
            self._volume_slider.setValue(max(1, self._last_volume))
            self._volume_slider.blockSignals(False)
        else:
            self._last_volume = vol
            self._player.audio_set_volume(0)
            self._volume_slider.blockSignals(True)
            self._volume_slider.setValue(0)
            self._volume_slider.blockSignals(False)
        self._toggle_vlc_volume_mute_icon()

    def _on_volume_changed(self, val):
        self._player.audio_set_volume(val)
        if val == 0:
            self._mute_btn.setIcon(_icon("mute"))
            self._mute_btn.setToolTip("取消静音")
        else:
            self._last_volume = val
            self._mute_btn.setIcon(_icon("volume"))
            self._mute_btn.setToolTip("静音")

    def _volume_up(self):
        self._volume_slider.setValue(min(100, self._volume_slider.value() + 10))

    def _volume_down(self):
        self._volume_slider.setValue(max(0, self._volume_slider.value() - 10))

    # ====================== 事件过滤 & 快捷键 ======================

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if self._handle_key(event.key()):
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent):
        if not self._handle_key(event.key()):
            super().keyPressEvent(event)

    def _handle_key(self, key) -> bool:
        actions = {
            Qt.Key_Space: self._toggle_play_pause,
            Qt.Key_Escape: self.close,
            Qt.Key_Left: self._rewind,
            Qt.Key_Right: self._forward,
            Qt.Key_Up: self._volume_up,
            Qt.Key_Down: self._volume_down,
            Qt.Key_M: self._toggle_mute,
            Qt.Key_F: self._toggle_fullscreen,
            Qt.Key_Home: self._prev,
            Qt.Key_End: self._next,
            Qt.Key_BracketLeft: self._speed_down,
            Qt.Key_BracketRight: self._speed_up,
        }
        handler = actions.get(key)
        if handler:
            handler()
            return True
        return False

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_seek(self, pos_ms):
        self._player.set_time(pos_ms)

    def _speed_up(self):
        current = self._player.get_rate()
        for _, rate in SPEEDS:
            if rate > current + 0.01:
                self._set_speed(rate)
                return

    def _speed_down(self):
        current = self._player.get_rate()
        for _, rate in reversed(SPEEDS):
            if rate < current - 0.01:
                self._set_speed(rate)
                return

    def showEvent(self, event):
        super().showEvent(event)
        if not self._play_started:
            self._play_started = True
            self._loading_timer.start()
            QTimer.singleShot(200, self._player.play)

    def closeEvent(self, event):
        self._pos_timer.stop()
        self._loading_timer.stop()
        self._hide_loading()
        try:
            self._player.release()
        except Exception:
            pass
        super().closeEvent(event)
