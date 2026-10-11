# -*- coding: utf-8 -*-
"""Diálogo de item de produção."""

from __future__ import annotations

from typing import Any, Optional, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from core.database import Database
from core.formatting import format_size


class ProductionItemDialog(QDialog):
    """Diálogo para adicionar item manualmente à lista de produção"""
    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from core.config import load_config
        
            
        self.db = db
        self.setWindowTitle("Adicionar Item à Produção")
        self.resize(450, 280)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título
        title_label = QLabel("➕ Adicionar Item à Lista de Produção")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Form layout para campos
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Produto (ComboBox)
        self.product = QComboBox()
        self.product.setMinimumHeight(35)
        self._load_products()
        cast(Any, self.product.currentIndexChanged).connect(self._on_product_changed)
        form_layout.addRow("Produto:", self.product)
        
        # Quantidade
        self.quantity = QSpinBox()
        self.quantity.setMinimum(1)
        self.quantity.setMaximum(1_000_000)
        self.quantity.setValue(1)
        self.quantity.setMinimumHeight(35)
        self.quantity.setSuffix(" un")
        form_layout.addRow("Quantidade:", self.quantity)
        
        # Tamanho (ComboBox único - mais intuitivo)
        self.size_combo = QComboBox()
        self.size_combo.setMinimumHeight(35)
        self.size_combo.setEditable(True)  # Permite edição manual
        self.size_combo.setPlaceholderText("Selecione ou digite o tamanho...")
        form_layout.addRow("Tamanho:", self.size_combo)
        
        # Observações (QLineEdit para texto livre)
        self.notes_edit = QLineEdit()
        self.notes_edit.setMinimumHeight(35)
        self.notes_edit.setPlaceholderText("Digite uma observação (opcional)...")
        form_layout.addRow("Obs:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # Carrega tamanhos do primeiro produto
        self._on_product_changed()
        
        # Espaçador
        layout.addStretch(1)
        
        # Botões
        btns_layout = QHBoxLayout()
        btns_layout.addStretch(1)
        
        btn_cancel = QPushButton("✖ Cancelar")
        btn_cancel.setMinimumSize(120, 40)
        cast(Any, btn_cancel.clicked).connect(self.reject)
        
        btn_save = QPushButton("✔ Adicionar")
        btn_save.setMinimumSize(120, 40)
        btn_save.setDefault(True)
        cast(Any, btn_save.clicked).connect(self.accept)
        
        btns_layout.addWidget(btn_cancel)
        btns_layout.addWidget(btn_save)
        
        layout.addLayout(btns_layout)
    
    def _load_products(self) -> None:
        """Carrega lista de produtos no combobox"""
        self.product.clear()
        rows = self.db.query("SELECT id, name FROM products ORDER BY name")
        for r in rows:
            self.product.addItem(r["name"], r["id"])
    
    def _on_product_changed(self) -> None:
        """Atualiza lista de tamanhos quando produto muda"""
        self.size_combo.clear()
        
        prod_id = self.product.currentData()
        if not prod_id:
            return
        
        # Busca os tamanhos do produto
        rows = self.db.query("SELECT size FROM products WHERE id=?", (prod_id,))
        if not rows or not rows[0]["size"]:
            self.size_combo.addItem("Tamanho único")
            return
        
        # Separa tamanhos por vírgula e adiciona ao combo
        size_str = rows[0]["size"]
        sizes = [s.strip() for s in size_str.split(",") if s.strip()]
        
        for size in sizes:
            formatted_size = format_size(size)
            self.size_combo.addItem(formatted_size, size)  # Exibe formatado, guarda original
        
        # Seleciona o primeiro por padrão
        if self.size_combo.count() > 0:
            self.size_combo.setCurrentIndex(0)
    
    def get_values(self) -> tuple[int, str, int, str, str]:
        """Retorna (product_id, nome_produto, quantidade, tamanho_selecionado, observações)"""
        product_name = self.product.currentText()
        
        # Busca o ID do produto selecionado
        product_id = 0
        rows = self.db.query("SELECT id FROM products WHERE name = ?", (product_name,))
        if rows:
            product_id = rows[0]["id"]
        
        qty = self.quantity.value()
        
        # Pega o tamanho selecionado ou digitado
        # Tenta pegar o valor original (userData), senão pega o texto exibido
        size = self.size_combo.currentData()
        if size is None or size == "":
            size = self.size_combo.currentText().strip()
        
        # Pega as observações
        notes = self.notes_edit.text().strip()
        
        return product_id, product_name, qty, size, notes
