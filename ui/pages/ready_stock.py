# -*- coding: utf-8 -*-
"""Página de Estoque Pronto."""

from __future__ import annotations

from typing import Any, Callable, Optional, cast

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.database import Database
from core.formatting import format_size
from ui.dialogs.product_dialog import ProductDialog
from ui.pages.base import BasePage


class ReadyStockPage(BasePage):
    """Lista de produtos com estoque disponível (Pronta Entrega)."""
    def __init__(self, db: Database, toast_cb: Optional[Callable[[str], None]] = None) -> None:
        super().__init__("Pronta entrega", "Itens disponíveis no estoque")
        self.db = db
        self.toast_cb = toast_cb
        bl = QVBoxLayout(self.body)
        
        # Botões de ação
        actions = QHBoxLayout()
        self.btn_edit: QPushButton = QPushButton("Editar")
        self.btn_edit.clicked.connect(self.edit_product)
        actions.addWidget(self.btn_edit)
        actions.addStretch(1)
        bl.addLayout(actions)
        
        # Barra de pesquisa simples
        search_box = QHBoxLayout()
        search_box.addWidget(QLabel("Pesquisar:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nome ou descrição…")
        self.search_edit.setClearButtonEnabled(True)
        cast(Any, self.search_edit.textChanged).connect(lambda _t: self.refresh())
        btn_refresh = QPushButton("Atualizar")
        cast(Any, btn_refresh.clicked).connect(self.refresh)
        search_box.addWidget(self.search_edit, 1)
        search_box.addWidget(btn_refresh)
        bl.addLayout(search_box)

        # Tabela
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome", "Descrição", "Tamanho", "Estoque"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.edit_product)
        if header := self.table.horizontalHeader():
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(False)
        bl.addWidget(self.table)
        self.refresh()
        
        # Atualiza a cada 5s enquanto visível (estoque pode mudar pelo painel da cozinha)
        self.start_auto_refresh(self.refresh, 5000)

    def refresh(self) -> None:
        try:
            try:
                term = self.search_edit.text().strip()
            except Exception:
                term = ""
            # Mostra TODOS os produtos (não só os com estoque > 0): itens zerados
            # ficam marcados como "Esgotado" em vez de simplesmente sumir da lista
            # sem aviso - antes era impossível notar que um produto zerou só
            # olhando essa tela, já que ele desaparecia silenciosamente.
            if term:
                like = f"%{term}%"
                rows = self.db.query(
                    """
                    SELECT id, name, description, size, stock, min_stock
                    FROM products
                    WHERE name LIKE ? OR description LIKE ?
                    ORDER BY (stock <= 0), name
                    """,
                    (like, like)
                )
            else:
                rows = self.db.query(
                    "SELECT id, name, description, size, stock, min_stock FROM products ORDER BY (stock <= 0), name"
                )
            if not self.rows_changed("table", rows):
                return  # nada mudou: mantém a tabela (rolagem e seleção)
            self.table.setRowCount(0)
            for r in rows:
                row = self.table.rowCount(); self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(r["name"]))
                self.table.setItem(row, 1, QTableWidgetItem(r["description"] or ""))
                self.table.setItem(row, 2, QTableWidgetItem(format_size(r["size"])))
                stock_val = r["stock"]
                stock_item = QTableWidgetItem("Esgotado" if stock_val <= 0 else str(stock_val))
                if stock_val <= 0:
                    stock_item.setBackground(QColor(255, 102, 102))  # Vermelho claro
                    stock_item.setForeground(QColor(255, 255, 255))  # Texto branco
                    stock_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                self.table.setItem(row, 3, stock_item)
                self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(r["id"])) )
        except Exception as e:
            print(f"Erro no refresh da página Estoque: {e}")
            # Não propaga o erro para não travar o aplicativo

    def edit_product(self) -> None:
        """Edita o produto selecionado"""
        current_row = self.table.currentRow()
        if current_row < 0:
            if self.toast_cb:
                self.toast_cb("Selecione um produto para editar")
            return
        
        # Obter ID do produto
        try:
            product_id = int(self.table.verticalHeaderItem(current_row).text())
        except (ValueError, AttributeError):
            if self.toast_cb:
                self.toast_cb("Erro ao obter ID do produto")
            return
        
        # Buscar dados completos do produto
        product_data = self.db.query("SELECT * FROM products WHERE id = ?", (product_id,))
        if not product_data:
            if self.toast_cb:
                self.toast_cb("Produto não encontrado")
            return
        
        product = product_data[0]
        
        # Abrir diálogo de edição
        dialog = ProductDialog(self, product)
        dialog.setWindowTitle("Editar Produto")
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Atualizar produto no banco
            try:
                name, description, size, stock, min_stock = dialog.get_values()
                
                if not name:
                    if self.toast_cb:
                        self.toast_cb("Nome do produto é obrigatório")
                    return
                
                self.db.execute(
                    """
                    UPDATE products 
                    SET name = ?, description = ?, size = ?, stock = ?, min_stock = ?
                    WHERE id = ?
                    """,
                    (name, description, size, stock, min_stock, product_id)
                )
                
                if self.toast_cb:
                    self.toast_cb("Produto atualizado com sucesso!")
                
                self.refresh()

            except Exception as e:
                if self.toast_cb:
                    self.toast_cb(f"Erro ao atualizar produto: {str(e)}")
