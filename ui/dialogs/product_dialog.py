# -*- coding: utf-8 -*-
"""Diálogo de cadastro/edição de produto."""

from __future__ import annotations

import sqlite3
from typing import Any, Optional, cast

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)


class ProductDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, data: Optional[sqlite3.Row] = None) -> None:
        super().__init__(parent)
        from core.config import load_config
        
            
        self.setWindowTitle("Produto")
        layout = QFormLayout(self)
        self.name: QLineEdit = QLineEdit()
        self.description: QLineEdit = QLineEdit()
        
        # Container para os tamanhos dinâmicos
        self.size_inputs: list[QLineEdit] = []
        self.sizes_container = QWidget()
        self.sizes_layout = QVBoxLayout(self.sizes_container)
        self.sizes_layout.setContentsMargins(0, 0, 0, 0)
        self.sizes_layout.setSpacing(5)
        
        # Adiciona primeiro campo de tamanho
        self._add_size_field()
        
        # Botão para adicionar mais tamanhos
        self.btn_add_size = QPushButton("+ Adicionar outro tamanho")
        self.btn_add_size.setObjectName("AddSizeButton")
        cast(Any, self.btn_add_size.clicked).connect(self._add_size_field)
        self.sizes_layout.addWidget(self.btn_add_size)
        
        self.stock: QSpinBox = QSpinBox(); self.stock.setMaximum(1_000_000)
        self.min_stock: QSpinBox = QSpinBox(); self.min_stock.setMaximum(100_000)
        
        # Campo de preço
        self.price: QDoubleSpinBox = QDoubleSpinBox()
        self.price.setMaximum(999999.99)
        self.price.setDecimals(2)
        self.price.setPrefix("R$ ")
        self.price.setSingleStep(1.0)
        
        layout.addRow("Nome:", self.name)
        layout.addRow("Descrição:", self.description)
        layout.addRow("Tamanhos (cm):", self.sizes_container)
        layout.addRow("Preço:", self.price)
        layout.addRow("Estoque:", self.stock)
        layout.addRow("Estoque mín.:", self.min_stock)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        cast(Any, btns.accepted).connect(self.accept)
        cast(Any, btns.rejected).connect(self.reject)
        layout.addRow(btns)
        if data:
            self.name.setText(data["name"])
            self.description.setText(data["description"] or "")
            # Carrega os tamanhos separados por vírgula
            if data["size"]:
                sizes = [s.strip() for s in data["size"].split(",") if s.strip()]
                # Remove o campo inicial vazio e adiciona os tamanhos salvos
                for widget in self.size_inputs[:]:
                    widget.deleteLater()
                    self.size_inputs.remove(widget)
                for size in sizes:
                    self._add_size_field(size)
            # Carregar preço
            try:
                price_value = float(data["price"]) if data["price"] is not None else 0.0
            except (KeyError, TypeError, ValueError):
                price_value = 0.0
            self.price.setValue(price_value)
            self.stock.setValue(int(data["stock"]))
            self.min_stock.setValue(int(data["min_stock"]))
    
    def _add_size_field(self, initial_value: str = "") -> None:
        """Adiciona um novo campo de tamanho à lista."""
        # Cria um container horizontal para o campo + botão de remover
        field_container = QWidget()
        field_layout = QHBoxLayout(field_container)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(5)
        
        # Cria o campo de texto
        size_field = QLineEdit()
        size_field.setPlaceholderText("Ex: 15 cm" if not self.size_inputs else "Ex: 20 cm")
        if initial_value:
            size_field.setText(initial_value)
        field_layout.addWidget(size_field)
        
        # Adiciona o campo à lista
        self.size_inputs.append(size_field)
        
        # Adiciona botão de remover (exceto para o primeiro campo)
        if len(self.size_inputs) > 1:
            btn_remove = QPushButton("×")
            btn_remove.setFixedWidth(30)
            btn_remove.setStyleSheet("font-size: 18px; font-weight: bold;")
            cast(Any, btn_remove.clicked).connect(lambda: self._remove_size_field(field_container, size_field))
            field_layout.addWidget(btn_remove)
        
        # Insere o container antes do botão "+ Adicionar outro tamanho"
        insert_index = self.sizes_layout.count() - 1  # -1 para ficar antes do botão
        self.sizes_layout.insertWidget(insert_index, field_container)
    
    def _remove_size_field(self, container: QWidget, field: QLineEdit) -> None:
        """Remove um campo de tamanho da lista."""
        if field in self.size_inputs:
            self.size_inputs.remove(field)
        container.deleteLater()

    def get_values(self) -> tuple[str, Optional[str], Optional[str], int, int, float]:
        # Coleta todos os tamanhos não vazios e junta com vírgula
        sizes = [field.text().strip() for field in self.size_inputs if field.text().strip()]
        size_str = ", ".join(sizes) if sizes else None
        
        return (
            self.name.text().strip(),
            self.description.text().strip() or None,
            size_str,
            int(self.stock.value()),
            int(self.min_stock.value()),
            float(self.price.value()),
        )
