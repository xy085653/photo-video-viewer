import os
from PySide6.QtWidgets import QTreeView, QFileSystemModel, QMenu
from PySide6.QtCore import Qt, Signal, QDir, QModelIndex
from PySide6.QtGui import QAction


class FolderTree(QTreeView):
    folder_selected = Signal(str)
    open_in_explorer_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QFileSystemModel()
        self._model.setRootPath("C:/")
        self._model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.setModel(self._model)
        self.setRootIndex(self._model.index("C:/"))
        self.setHeaderHidden(True)
        self.setColumnWidth(0, 260)
        for col in (1, 2, 3):
            self.setColumnHidden(col, True)
        self.clicked.connect(self._on_clicked)
        self._context_path = None

    def _on_clicked(self, index: QModelIndex):
        path = self._model.filePath(index)
        self.folder_selected.emit(path)

    def set_root(self, folder_path: str):
        self.setRootIndex(self._model.index(folder_path))

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            idx = self.indexAt(self.viewport().mapFromGlobal(event.globalPos()))
            if idx.isValid():
                self._context_path = self._model.filePath(idx)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        path = self._context_path
        self._context_path = None
        if not path:
            return
        menu = QMenu(self)

        act_open = menu.addAction("打开")
        menu.addSeparator()
        act_explorer = menu.addAction("在资源管理器中打开")

        action = menu.exec(event.globalPos())
        if action == act_open:
            self.folder_selected.emit(path)
        elif action == act_explorer:
            self.open_in_explorer_requested.emit(path)
