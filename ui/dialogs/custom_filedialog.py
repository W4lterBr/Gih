from typing import Optional, Any, cast
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
    QLineEdit, QPushButton, QLabel, QFileIconProvider, QListWidgetItem
)
from PyQt6.QtCore import Qt
import os

class CustomFileDialog(QDialog):
    def __init__(
        self, 
        parent: Optional[QWidget] = None,
        caption: str = "Selecionar Arquivo",
        directory: str = "",
        filter: str = "Todos os Arquivos (*.*)",
        save_mode: bool = False
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(caption)
        self.setModal(True)
        self.resize(600, 400)
        self.save_mode: bool = save_mode
        self.selected_file: Optional[str] = None
        self.current_dir: str = directory or os.path.expanduser("~")
        self.filter: str = filter
        self._setup_ui()
        self._populate_files()
        self._apply_dark_style()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.path_label = QLabel(self.current_dir)
        layout.addWidget(self.path_label)
        self.file_list = QListWidget()
        cast(Any, self.file_list.itemDoubleClicked).connect(self._on_item_double_clicked)
        layout.addWidget(self.file_list)
        self.filename_edit = QLineEdit()
        if self.save_mode:
            layout.addWidget(self.filename_edit)
        btn_layout = QHBoxLayout()
        self.open_btn = QPushButton("Abrir" if not self.save_mode else "Salvar")
        cast(Any, self.open_btn.clicked).connect(self._on_open)
        self.cancel_btn = QPushButton("Cancelar")
        cast(Any, self.cancel_btn.clicked).connect(self.reject)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _populate_files(self) -> None:
        self.file_list.clear()
        self.path_label.setText(self.current_dir)
        icon_provider = QFileIconProvider()
        # Add parent dir
        if os.path.dirname(self.current_dir) != self.current_dir:
            parent_item = QListWidgetItem(".. (pasta anterior)")
            parent_item.setIcon(icon_provider.icon(QFileIconProvider.IconType.Folder))
            parent_item.setData(Qt.ItemDataRole.UserRole, os.path.dirname(self.current_dir))
            self.file_list.addItem(parent_item)
        # List dirs and files
        try:
            for entry in sorted(os.listdir(self.current_dir)):
                full_path = os.path.join(self.current_dir, entry)
                item = QListWidgetItem(entry)
                if os.path.isdir(full_path):
                    item.setIcon(icon_provider.icon(QFileIconProvider.IconType.Folder))
                else:
                    item.setIcon(icon_provider.icon(QFileIconProvider.IconType.File))
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                self.file_list.addItem(item)
        except Exception:  # Ignora erros de permissão ou acesso
            pass

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path: str = cast(str, item.data(Qt.ItemDataRole.UserRole))
        if os.path.isdir(path):
            self.current_dir = path
            self._populate_files()
        else:
            self.selected_file = path
            self.accept()

    def _on_open(self) -> None:
        if self.save_mode:
            filename = self.filename_edit.text().strip()
            if filename:
                self.selected_file = os.path.join(self.current_dir, filename)
                self.accept()
        else:
            item = self.file_list.currentItem()
            if item:
                path: str = cast(str, item.data(Qt.ItemDataRole.UserRole))
                if os.path.isdir(path):
                    self.current_dir = path
                    self._populate_files()
                else:
                    self.selected_file = path
                    self.accept()

    def get_selected_file(self) -> Optional[str]:
        return self.selected_file

    def _apply_dark_style(self) -> None:
        self.setStyleSheet('''
            QDialog {
                background-color: #232629;
                color: #f0f0f0;
            }
            QLabel, QLineEdit, QListWidget, QPushButton {
                color: #f0f0f0;
                background-color: #232629;
                border: none;
            }
            QListWidget::item:selected {
                background: #44475a;
                color: #ffffff;
            }
            QPushButton {
                background-color: #44475a;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #6272a4;
            }
            QLineEdit {
                background-color: #282a36;
                border: 1px solid #44475a;
                border-radius: 4px;
                padding: 4px;
            }
        ''')
