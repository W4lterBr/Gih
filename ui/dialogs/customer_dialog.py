# -*- coding: utf-8 -*-
"""Diálogo de cadastro/edição de cliente."""

from __future__ import annotations

import sqlite3
from typing import Any, Optional, cast

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit, QWidget


# -----------------------------
# Dialogs (CRUD)
# -----------------------------
class CustomerDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, data: Optional[sqlite3.Row] = None) -> None:
        super().__init__(parent)
        from core.config import load_config
        
            
        self.setWindowTitle("Cliente")
        layout = QFormLayout(self)
        self.name: QLineEdit = QLineEdit()
        self.phone: QLineEdit = QLineEdit()
        self.address: QLineEdit = QLineEdit()
        self.observation: QTextEdit = QTextEdit()
        self.observation.setPlaceholderText("Observações sobre o cliente, preferências, etc.")
        layout.addRow("Nome:", self.name)
        layout.addRow("Telefone:", self.phone)
        layout.addRow("Endereço:", self.address)
        layout.addRow("Observação:", self.observation)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        cast(Any, btns.accepted).connect(self.accept)
        cast(Any, btns.rejected).connect(self.reject)
        layout.addRow(btns)
        if data:
            self.name.setText(data["name"])
            self.phone.setText(data["phone"] or "")
            self.address.setText(data["address"] or "")
            self.observation.setPlainText(data["observation"] or "")

    def get_values(self) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        return (
            self.name.text().strip(),
            self.phone.text().strip() or None,
            self.address.text().strip() or None,
            self.observation.toPlainText().strip() or None,
        )
