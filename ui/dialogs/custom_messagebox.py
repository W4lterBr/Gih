from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

class CustomMessageBox(QDialog):
    def __init__(self, parent=None, title="Mensagem", text="", buttons=("OK",), default=0, qss=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label)
        btn_layout = QHBoxLayout()
        self._result = None
        self._btns = []
        for i, btxt in enumerate(buttons):
            btn = QPushButton(btxt)
            btn.clicked.connect(lambda _, ix=i: self._on_btn(ix))
            btn_layout.addWidget(btn)
            self._btns.append(btn)
        layout.addLayout(btn_layout)
        if qss:
            self.setStyleSheet(qss)
        self._btns[default].setFocus()

    def _on_btn(self, ix):
        self._result = ix
        self.accept()

    @staticmethod
    def show_message(parent, title, text, buttons=("OK",), default=0, qss=None):
        dlg = CustomMessageBox(parent, title, text, buttons, default, qss)
        dlg.exec()
        return dlg._result
