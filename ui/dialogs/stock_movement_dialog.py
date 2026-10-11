# -*- coding: utf-8 -*-
"""Diálogo de nova movimentação de estoque."""

from __future__ import annotations

from typing import Any, Optional, cast

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QWidget,
)

from core.database import Database
from core.stock_categories import MOVEMENT_CATEGORIES
from ui.messages import show_message


class StockMovementDialog(QDialog):
    """Diálogo para registrar manualmente uma movimentação de estoque
    (entrada, saída, perda/quebra, vencimento, ajuste, produção, etc)."""

    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        from core.config import load_config

        self.setWindowTitle("Nova Movimentação de Estoque")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)

        self.tipo: QComboBox = QComboBox()
        self.tipo.addItems(["Entrada", "Saída"])
        cast(Any, self.tipo.currentTextChanged).connect(self._on_tipo_changed)
        layout.addRow("Tipo:", self.tipo)

        self.categoria: QComboBox = QComboBox()
        layout.addRow("Categoria:", self.categoria)

        self.produto: QComboBox = QComboBox()
        self._load_products()
        cast(Any, self.produto.currentIndexChanged).connect(self._on_produto_changed)
        layout.addRow("Produto:", self.produto)

        self.estoque_atual_label = QLabel("—")
        self.estoque_atual_label.setStyleSheet("color: #6b7280; font-style: italic;")
        layout.addRow("Estoque atual:", self.estoque_atual_label)

        self.quantidade: QSpinBox = QSpinBox()
        self.quantidade.setMinimum(1)
        self.quantidade.setMaximum(999999)
        layout.addRow("Quantidade:", self.quantidade)

        self.data: QDateEdit = QDateEdit()
        self.data.setDate(QDate.currentDate())
        self.data.setMaximumDate(QDate.currentDate())
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        layout.addRow("Data:", self.data)

        self.observacoes: QLineEdit = QLineEdit()
        self.observacoes.setPlaceholderText("Opcional - detalhes adicionais")
        layout.addRow("Observações:", self.observacoes)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        cast(Any, btns.accepted).connect(self._validate_and_accept)
        cast(Any, btns.rejected).connect(self.reject)
        layout.addRow(btns)

        self._on_tipo_changed("Entrada")
        self._on_produto_changed(self.produto.currentIndex())

    def _on_tipo_changed(self, tipo: str) -> None:
        self.categoria.clear()
        self.categoria.addItems(MOVEMENT_CATEGORIES.get(tipo, []))

    def _load_products(self) -> None:
        rows = self.db.query("SELECT id, name, stock FROM products ORDER BY name")
        for r in rows:
            self.produto.addItem(r["name"], (int(r["id"]), int(r["stock"])))

    def _on_produto_changed(self, _index: int) -> None:
        data = self.produto.currentData()
        if data:
            _, stock = data
            self.estoque_atual_label.setText(f"{stock} un")
        else:
            self.estoque_atual_label.setText("—")

    def _validate_and_accept(self) -> None:
        if self.produto.currentData() is None:
            show_message(self, "Aviso", "Cadastre um produto antes de registrar uma movimentação.", ("OK",))
            return
        if self.tipo.currentText() == "Saída":
            _, stock = self.produto.currentData()
            if self.quantidade.value() > stock:
                show_message(
                    self, "Estoque insuficiente",
                    f"Estoque disponível: {stock} un. Não é possível dar saída de {self.quantidade.value()} un.",
                    ("OK",)
                )
                return
        self.accept()

    def get_values(self) -> dict[str, Any]:
        prod_id, _ = self.produto.currentData()
        return {
            "type": "entrada" if self.tipo.currentText() == "Entrada" else "saida",
            "category": self.categoria.currentText(),
            "product_id": prod_id,
            "product_name": self.produto.currentText(),
            "quantity": self.quantidade.value(),
            "date": self.data.date().toString("yyyy-MM-dd"),
            "notes": self.observacoes.text().strip() or None,
        }
