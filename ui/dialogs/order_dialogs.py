# -*- coding: utf-8 -*-
"""Diálogos de pedido (simples e com múltiplos produtos)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional, cast

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from core.database import Database
from core.formatting import format_size


class MultiProductOrderDialog(QDialog):
    """
    Diálogo para criação de pedido com MÚLTIPLOS produtos.
    Permite adicionar vários produtos para o mesmo cliente em um único pedido.
    """
    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from core.config import load_config
        
        self.db = db
        self.products_list: list[dict[str, Any]] = []  # Lista de produtos adicionados
        
        self.setWindowTitle("Novo Pedido - Múltiplos Produtos")
        self.resize(800, 600)
        
        
        main_layout = QVBoxLayout(self)
        
        # === SEÇÃO 1: Informações Gerais do Pedido ===
        info_group = QGroupBox("Informações do Pedido")
        info_layout = QFormLayout()
        
        # Cliente
        self.customer = QComboBox()
        self._load_customers()
        info_layout.addRow("Cliente:", self.customer)
        
        # Data de entrega
        self.delivery = QDateEdit()
        self.delivery.setCalendarPopup(True)
        self.delivery.setDisplayFormat("dd/MM/yyyy")
        self.delivery.setDate(QDate.currentDate())
        
        
        info_layout.addRow("Data Entrega:", self.delivery)
        
        # Status
        self.status = QComboBox()
        self.status.addItems(["Aguardando Pagamento", "Pagamento na Retirada", "Pago"])
        info_layout.addRow("Status:", self.status)
        
        # Etiqueta
        self.label = QComboBox()
        self._load_labels()
        info_layout.addRow("Etiqueta:", self.label)
        
        # Observações gerais
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Observações gerais do pedido...")
        self.notes.setMaximumHeight(60)
        info_layout.addRow("Observações:", self.notes)
        
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        # === SEÇÃO 2: Adicionar Produtos ===
        product_group = QGroupBox("Adicionar Produtos")
        product_layout = QHBoxLayout()
        
        product_layout.addWidget(QLabel("Produto:"))
        self.product = QComboBox()
        self._load_products()
        product_layout.addWidget(self.product, 2)
        
        product_layout.addWidget(QLabel("Qtd:"))
        self.quantity = QSpinBox()
        self.quantity.setMinimum(1)
        self.quantity.setMaximum(1000000)
        self.quantity.setValue(1)
        product_layout.addWidget(self.quantity, 1)
        
        self.btn_add_product = QPushButton("➕ Adicionar")
        cast(Any, self.btn_add_product.clicked).connect(self._add_product_to_list)
        product_layout.addWidget(self.btn_add_product)
        
        product_group.setLayout(product_layout)
        main_layout.addWidget(product_group)
        
        # === SEÇÃO 3: Tabela de Produtos Adicionados ===
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Produto", "Tamanho", "Quantidade", "Ação"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.table)
        
        # Informação
        info_label = QLabel("💡 Adicione todos os produtos desejados antes de salvar o pedido")
        info_label.setStyleSheet("color: #6b7280; font-style: italic; padding: 5px;")
        main_layout.addWidget(info_label)
        
        # === BOTÕES FINAIS ===
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        cast(Any, btns.accepted).connect(self._save_order)
        cast(Any, btns.rejected).connect(self.reject)
        main_layout.addWidget(btns)
    
    def _load_customers(self) -> None:
        self.customer.clear()
        rows = self.db.query("SELECT id, name FROM customers ORDER BY name")
        for r in rows:
            self.customer.addItem(r["name"], r["id"])
    
    def _load_products(self) -> None:
        self.product.clear()
        rows = self.db.query("SELECT id, name FROM products ORDER BY name")
        for r in rows:
            self.product.addItem(r["name"], r["id"])
    
    def _load_labels(self) -> None:
        self.label.clear()
        rows = self.db.query("SELECT name FROM labels ORDER BY name")
        for r in rows:
            self.label.addItem(r["name"])
        comum_index = self.label.findText("Comum")
        if comum_index >= 0:
            self.label.setCurrentIndex(comum_index)
    
    def _add_product_to_list(self) -> None:
        """Adiciona o produto selecionado à lista"""
        prod_id = self.product.currentData()
        prod_name = self.product.currentText()
        qty = self.quantity.value()
        
        if not prod_id:
            QMessageBox.warning(self, "Aviso", "Selecione um produto!")
            return
        
        if qty <= 0:
            QMessageBox.warning(self, "Aviso", "Quantidade deve ser maior que 0!")
            return
        
        # Busca informações do produto
        prod_data = self.db.query("SELECT size, stock FROM products WHERE id=?", (prod_id,))
        if not prod_data:
            QMessageBox.warning(self, "Erro", "Produto não encontrado!")
            return
        
        size = prod_data[0]["size"] or ""
        
        # Adiciona à lista (sem validação de estoque - permite estoque negativo)
        self.products_list.append({
            "product_id": prod_id,
            "product_name": prod_name,
            "size": size,
            "quantity": qty
        })
        
        self._refresh_table()
        
        # Reseta quantidade
        self.quantity.setValue(1)
    
    def _refresh_table(self) -> None:
        """Atualiza a tabela com os produtos adicionados"""
        self.table.setRowCount(len(self.products_list))
        
        for row, item in enumerate(self.products_list):
            # Define altura mínima da linha para acomodar o botão
            self.table.setRowHeight(row, 50)
            
            # Produto
            self.table.setItem(row, 0, QTableWidgetItem(item["product_name"]))
            
            # Tamanho
            size_formatted = format_size(item["size"]) if item["size"] else "-"
            self.table.setItem(row, 1, QTableWidgetItem(size_formatted))
            
            # Quantidade
            self.table.setItem(row, 2, QTableWidgetItem(str(item["quantity"])))
            
            # Botão remover - apenas o ícone sem fundo
            btn_remove = QPushButton("🗑️")
            btn_remove.setToolTip("Remover este produto")
            btn_remove.setFixedSize(40, 35)
            btn_remove.setStyleSheet("""
                QPushButton {
                    background-color: transparent !important;
                    background: transparent !important;
                    border: none !important;
                    padding: 6px !important;
                    font-size: 20px !important;
                }
                QPushButton:hover {
                    background-color: rgba(239, 68, 68, 0.1) !important;
                    background: rgba(239, 68, 68, 0.1) !important;
                    border-radius: 6px !important;
                }
                QPushButton:pressed {
                    background-color: rgba(239, 68, 68, 0.2) !important;
                    background: rgba(239, 68, 68, 0.2) !important;
                }
            """)
            btn_remove.setProperty("row", row)
            cast(Any, btn_remove.clicked).connect(lambda checked, r=row: self._remove_product(r))
            
            # Container para centralizar o botão
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.addWidget(btn_remove)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.setContentsMargins(5, 5, 5, 5)
            self.table.setCellWidget(row, 3, container)
    
    def _remove_product(self, row: int) -> None:
        """Remove um produto da lista"""
        if 0 <= row < len(self.products_list):
            del self.products_list[row]
            self._refresh_table()
    
    def _save_order(self) -> None:
        """Salva o pedido com todos os produtos"""
        if not self.products_list:
            QMessageBox.warning(self, "Aviso", "Adicione pelo menos um produto ao pedido!")
            return
        
        customer_id = self.customer.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Aviso", "Selecione um cliente!")
            return
        
        # Aceita e salva
        self.accept()
    
    def get_order_data(self) -> dict[str, Any]:
        """Retorna os dados do pedido completo"""
        return {
            "customer_id": self.customer.currentData(),
            "delivery_date": self.delivery.date().toPyDate().isoformat(),
            "status": self.status.currentText(),
            "label": self.label.currentText(),
            "notes": self.notes.toPlainText().strip() or None,
            "products": self.products_list
        }


class OrderDialog(QDialog):
    """
    Diálogo de criação/edição de pedidos.
    - Permite adicionar MÚLTIPLOS produtos por cliente
    - Carrega clientes e produtos do banco.
    - Valida quantidade > 0.
    - Valida a data (campo com máscara dd/MM/yyyy).
    - Total sempre é 0.0 (não controlamos preços).
    """
    def __init__(self, db: Database, parent: Optional[QWidget] = None, data: Optional[sqlite3.Row] = None) -> None:
        super().__init__(parent)
        from PyQt6.QtCore import QRegularExpression
        from PyQt6.QtGui import QRegularExpressionValidator
        from core.config import load_config
        

        self.db = db
        self.setWindowTitle("Pedido")

        layout = QFormLayout(self)

        # Cliente
        self.customer: QComboBox = QComboBox()
        self._load_customers()

        # Produto
        self.product: QComboBox = QComboBox()
        
        # Label para mostrar o tamanho do produto selecionado (criar ANTES de carregar produtos)
        self.product_size_label: QLabel = QLabel()
        self.product_size_label.setStyleSheet("color: #6b7280; font-style: italic;")
        
        # Agora carrega os produtos (que vai chamar _on_product_changed)
        self._load_products()
        cast(Any, self.product.currentIndexChanged).connect(self._on_product_changed)

        # Quantidade
        self.quantity: QSpinBox = QSpinBox()
        self.quantity.setMaximum(1_000_000)
        self.quantity.setValue(1)

        # Data de entrega
        self.delivery: QDateEdit = QDateEdit()
        self.delivery.setCalendarPopup(True)
        self.delivery.setDisplayFormat("dd/MM/yyyy")
        self.delivery.setReadOnly(False)
        # Validador dd/MM/yyyy
        date_regex = QRegularExpression(r"^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/\d{4}$")
        cast(Any, self.delivery.lineEdit()).setValidator(QRegularExpressionValidator(date_regex))
        # Se for novo pedido, já deixa hoje
        self.delivery.setDate(QDate.currentDate())

        # Status (financeiro)
        self.status: QComboBox = QComboBox()
        self.status.addItems([
            "Aguardando Pagamento",
            "Pagamento na Retirada",
            "Pago"
        ])

        # Etiqueta
        self.label: QComboBox = QComboBox()
        self._load_labels()

        # Observações
        self.notes: QTextEdit = QTextEdit()
        self.notes.setPlaceholderText("Observações do pedido, sabores, decoração, etc.")

        # Adiciona campos no form
        layout.addRow("Cliente:", self.customer)
        layout.addRow("Produto:", self.product)
        layout.addRow("", self.product_size_label)
        layout.addRow("Quantidade:", self.quantity)
        layout.addRow("Entrega:", self.delivery)
        layout.addRow("Status:", self.status)
        layout.addRow("Etiqueta:", self.label)
        layout.addRow("Obs:", self.notes)

        # Botões
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        cast(Any, btns.accepted).connect(self.accept)
        cast(Any, btns.rejected).connect(self.reject)
        layout.addRow(btns)

        # Se veio com registro para edição, pré-carrega
        if data:
            self._select_combobox_by_data(self.customer, data["customer_id"])
            self._select_combobox_by_data(self.product, data["product_id"])
            self._on_product_changed()  # Atualiza o label de tamanho após selecionar o produto
            self.quantity.setValue(int(data["quantity"]))
            # Data
            try:
                d = datetime.strptime(data["delivery_date"], "%Y-%m-%d").date()
                self.delivery.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
            # Status
            if data["status"]:
                existing = [self.status.itemText(i) for i in range(self.status.count())]
                if data["status"] not in existing:
                    self.status.addItem(data["status"])
                self.status.setCurrentText(data["status"])
            # Observações
            self.notes.setPlainText(data["notes"] or "")

    # Helpers
    def _select_combobox_by_data(self, combo: QComboBox, id_value: int) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == id_value:
                combo.setCurrentIndex(i)
                return

    def _load_customers(self) -> None:
        self.customer.clear()
        rows = self.db.query("SELECT id, name FROM customers ORDER BY name")
        for r in rows:
            self.customer.addItem(r["name"], r["id"])

    def _load_products(self) -> None:
        self.product.clear()
        rows = self.db.query("SELECT id, name, size FROM products ORDER BY name")
        for r in rows:
            self.product.addItem(r['name'], r["id"])
        # Atualiza o label de tamanho após carregar
        self._on_product_changed()
    
    def _load_labels(self) -> None:
        """Carrega as etiquetas disponíveis no combobox"""
        self.label.clear()
        rows = self.db.query("SELECT name FROM labels ORDER BY name")
        for r in rows:
            self.label.addItem(r["name"])
        # Define "Comum" como padrão se existir
        comum_index = self.label.findText("Comum")
        if comum_index >= 0:
            self.label.setCurrentIndex(comum_index)
    
    def _on_product_changed(self) -> None:
        """Atualiza o label com o tamanho do produto selecionado"""
        prod_id = self.product.currentData()
        if prod_id:
            try:
                rows = self.db.query("SELECT size FROM products WHERE id=?", (prod_id,))
                if rows:
                    size_value = rows[0]["size"]
                    if size_value:
                        formatted_size = format_size(size_value)
                        self.product_size_label.setText(f"📏 Tamanhos disponíveis: {formatted_size}")
                        self.product_size_label.setVisible(True)
                    else:
                        self.product_size_label.setText("")
                        self.product_size_label.setVisible(False)
                else:
                    self.product_size_label.setText("")
                    self.product_size_label.setVisible(False)
            except Exception as e:
                # Se der erro (coluna não existe ainda), esconde o label
                self.product_size_label.setText("")
                self.product_size_label.setVisible(False)
        else:
            self.product_size_label.setText("")
            self.product_size_label.setVisible(False)

    # Saída do diálogo
    def get_values(self) -> tuple[int, int, int, str, float, str, str, Optional[str]]:
        """
        Retorna: (customer_id, product_id, quantity, delivery_iso, total, status, notes)
        - Faz validação de quantidade
        - Total sempre será 0.0 (não controlamos preços)
        - Checa estoque disponível
        """
        cust_id = self.customer.currentData()
        prod_id = self.product.currentData()
        qty = int(self.quantity.value())
        if qty <= 0:
            raise ValueError("Quantidade deve ser maior que 0")

        # Data no formato ISO (yyyy-MM-dd)
        d_iso = self.delivery.date().toPyDate().isoformat()

        status = self.status.currentText()
        label = self.label.currentText()
        notes = self.notes.toPlainText().strip() or None
        
        # Produtos podem ficar com estoque negativo
        # Os produtos com estoque negativo ou zero aparecerão automaticamente na lista de produção

        total = 0.0  # Não controlamos preços
        return cust_id, prod_id, qty, d_iso, total, status, label, notes
