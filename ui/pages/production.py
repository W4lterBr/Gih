# -*- coding: utf-8 -*-
"""Página de Produção: lista do dia e integração com o painel da cozinha."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, Optional, cast

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QDateEdit, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import Database
from core.formatting import format_size
from core.paths import RESOURCE_DIR
from ui.dialogs.production_item_dialog import ProductionItemDialog
from ui.messages import show_message
from ui.pages.base import BasePage


class ProductionPage(BasePage):
    """Página de Produção - Lista de produção editável com atualização automática"""
    def __init__(self, db: Database, toast_cb: Optional[Callable[[str], None]] = None) -> None:
        super().__init__("Produção", "Lista de produção e controle de estoque")
        self.db = db
        self.toast_cb = toast_cb
        
        # Cache para detectar mudanças
        self._last_production_hash = ""
        self._last_stock_hash = ""
        
        # Auto-refresh a cada 2s enquanto a página está visível (refresh completo ao aparecer)
        self.start_auto_refresh(self._auto_refresh, 2000, on_show=self.refresh)

        bl = QVBoxLayout(self.body)
        
        # Barra de ações
        actions_box = QHBoxLayout()
        
        # Botão para adicionar item manualmente
        self.btn_add_item = QPushButton("+ Adicionar Item")
        self.btn_add_item.setProperty("primary", True)
        cast(Any, self.btn_add_item.clicked).connect(self._add_production_item)
        actions_box.addWidget(self.btn_add_item)
        
        # Botão para importar pedidos pendentes
        self.btn_import_orders = QPushButton("📋 Importar de Pedidos")
        cast(Any, self.btn_import_orders.clicked).connect(self._import_from_orders)
        actions_box.addWidget(self.btn_import_orders)
        
        # Botão para limpar lista
        self.btn_clear = QPushButton("🗑️ Limpar Lista")
        cast(Any, self.btn_clear.clicked).connect(self._clear_list)
        actions_box.addWidget(self.btn_clear)
        
        actions_box.addStretch(1)
        
        bl.addLayout(actions_box)

        # Container com duas tabelas lado a lado
        tables_container = QHBoxLayout()
        
        # === LADO ESQUERDO: Lista de Produção ===
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        # Cabeçalho com título, data e botão
        header_box = QHBoxLayout()
        left_title = QLabel("📝 Lista de Produção")
        left_title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 8px;")
        header_box.addWidget(left_title)
        
        # Data picker
        self.production_date = QDateEdit()
        self.production_date.setDate(QDate.currentDate())
        self.production_date.setCalendarPopup(True)
        self.production_date.setDisplayFormat("dd/MM/yyyy")
        
        
        cast(Any, self.production_date.dateChanged).connect(self._on_date_changed)
        header_box.addWidget(self.production_date)
        
        # Botão "Disparar para Cozinha"
        self.btn_dispatch = QPushButton("🔥 Disparar para Cozinha")
        self.btn_dispatch.setStyleSheet("""
            QPushButton {
                background: #16a34a;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #15803d;
            }
        """)
        cast(Any, self.btn_dispatch.clicked).connect(self._dispatch_to_kitchen)
        header_box.addWidget(self.btn_dispatch)
        
        header_box.addStretch(1)
        left_layout.addLayout(header_box)
        
        self.production_table = QTableWidget(0, 4)
        self.production_table.setHorizontalHeaderLabels(["Produto", "Qtd", "Tamanho", "Obs"])
        self.production_table.setAlternatingRowColors(True)
        self.production_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        if header := self.production_table.horizontalHeader():
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Produto estica
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Qtd
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Tamanho
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Obs estica
        
        # Conectar sinal de edição de célula
        cast(Any, self.production_table.itemChanged).connect(self._on_production_item_changed)
        
        left_layout.addWidget(self.production_table)
        
        # Botão para remover item selecionado
        remove_btn_box = QHBoxLayout()
        remove_btn_box.addStretch(1)
        self.btn_remove_item = QPushButton("- Remover Selecionado")
        cast(Any, self.btn_remove_item.clicked).connect(self._remove_selected_item)
        remove_btn_box.addWidget(self.btn_remove_item)
        left_layout.addLayout(remove_btn_box)
        
        tables_container.addWidget(left_container, 1)
        
        # === LADO DIREITO: Estoque Atual ===
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        right_title = QLabel("📦 Estoque Atual")
        right_title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 8px;")
        right_layout.addWidget(right_title)
        
        # Barra de pesquisa para estoque
        search_stock_box = QHBoxLayout()
        search_stock_box.addWidget(QLabel("Pesquisar:"))
        self.search_stock_edit = QLineEdit()
        self.search_stock_edit.setPlaceholderText("Produto...")
        self.search_stock_edit.setClearButtonEnabled(True)
        cast(Any, self.search_stock_edit.textChanged).connect(lambda _t: self._refresh_stock_table())
        search_stock_box.addWidget(self.search_stock_edit, 1)
        right_layout.addLayout(search_stock_box)
        
        self.stock_table = QTableWidget(0, 2)
        self.stock_table.setHorizontalHeaderLabels(["Qtd", "Encomendas"])
        self.stock_table.setAlternatingRowColors(True)
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        if header2 := self.stock_table.horizontalHeader():
            header2.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Adiciona coluna vertical com nome dos produtos
        self.stock_table.verticalHeader().setVisible(True)
        right_layout.addWidget(self.stock_table)
        
        tables_container.addWidget(right_container, 1)
        
        bl.addLayout(tables_container)
        
        # Carrega dados iniciais
        self.refresh()

    def refresh(self) -> None:
        """Atualiza ambas as tabelas (produção e estoque)"""
        self._refresh_production_table()
        self._refresh_stock_table()
    
    def _auto_refresh(self) -> None:
        """Auto-refresh com detecção de mudanças para evitar flickering"""
        # Gera hash do estado atual da produção
        production_rows = self.db.query("""
            SELECT pi.id, p.name, pi.quantity, pi.size
            FROM production_items pi
            JOIN products p ON p.id = pi.product_id
            ORDER BY pi.created_at DESC
        """)
        
        # Gera hash do estado atual do estoque com encomendas da data selecionada
        selected_date = self.production_date.date().toString("yyyy-MM-dd")
        stock_rows = self.db.query("""
            SELECT p.id, p.name, p.stock, 
                   COALESCE(SUM(o.quantity), 0) as total_orders
            FROM products p
            LEFT JOIN orders o ON o.product_id = p.id 
                              AND o.status != 'Entregue' 
                              AND DATE(o.delivery_date) = ?
            GROUP BY p.id, p.name, p.stock
            ORDER BY 
              CASE WHEN p.stock <= 0 THEN 0 WHEN p.stock < 5 THEN 1 ELSE 2 END,
              p.name
        """, (selected_date,))
        
        # Cria hashes simples baseados nos dados
        production_data = str([(r["id"], r["name"], r["quantity"], r["size"]) for r in production_rows])
        stock_data = str([(r["id"], r["name"], r["stock"], r["total_orders"]) for r in stock_rows])
        
        # Só atualiza se houve mudança
        if production_data != self._last_production_hash:
            self._last_production_hash = production_data
            self._refresh_production_table()
        
        if stock_data != self._last_stock_hash:
            self._last_stock_hash = stock_data
            self._refresh_stock_table()
    
    def _refresh_production_table(self) -> None:
        """Atualiza a tabela de produção (lado esquerdo) - carrega do banco"""
        # Desconecta temporariamente o sinal para evitar trigger durante refresh
        try:
            cast(Any, self.production_table.itemChanged).disconnect(self._on_production_item_changed)
        except Exception:
            pass
        
        # Busca todos os itens da lista de produção salvos
        rows = self.db.query("""
            SELECT pi.id, p.id as product_id, p.name, pi.quantity, pi.size, pi.notes
            FROM production_items pi
            JOIN products p ON p.id = pi.product_id
            ORDER BY pi.created_at DESC
        """)
        
        self.production_table.setRowCount(0)
        for r in rows:
            row = self.production_table.rowCount()
            self.production_table.insertRow(row)
            
            # Coluna 0: Nome do produto (não editável)
            name_item = QTableWidgetItem(str(r["name"]))
            name_item.setData(Qt.ItemDataRole.UserRole, r["id"])  # Armazena ID do production_item
            name_item.setData(Qt.ItemDataRole.UserRole + 1, r["product_id"])  # Armazena product_id
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Não editável
            self.production_table.setItem(row, 0, name_item)
            
            # Coluna 1: Quantidade (editável)
            qty_item = QTableWidgetItem(str(r["quantity"]))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.production_table.setItem(row, 1, qty_item)
            
            # Coluna 2: Tamanho (editável)
            size_text = format_size(str(r["size"])) if r["size"] else ""
            size_item = QTableWidgetItem(size_text)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            size_item.setData(Qt.ItemDataRole.UserRole, str(r["size"]))  # Armazena tamanho bruto
            self.production_table.setItem(row, 2, size_item)
            
            # Coluna 3: Observações (editável)
            notes_text = str(r["notes"]) if r["notes"] else ""
            notes_item = QTableWidgetItem(notes_text)
            self.production_table.setItem(row, 3, notes_item)
        
        # Reconecta o sinal
        cast(Any, self.production_table.itemChanged).connect(self._on_production_item_changed)
    
    def _on_production_item_changed(self, item: QTableWidgetItem) -> None:
        """Chamado quando uma célula da tabela de produção é editada"""
        row = item.row()
        col = item.column()
        
        # Ignora edições na coluna de nome (não deveria acontecer)
        if col == 0:
            return
        
        # Pega o ID do item da primeira coluna
        name_item = self.production_table.item(row, 0)
        if not name_item:
            return
        
        item_id = name_item.data(Qt.ItemDataRole.UserRole)
        product_id = name_item.data(Qt.ItemDataRole.UserRole + 1)  # product_id armazenado
        if not item_id:
            return
        
        try:
            if col == 1:  # Quantidade
                new_qty = int(item.text().strip())
                if new_qty <= 0:
                    raise ValueError("Quantidade deve ser maior que zero")
                
                # Busca a quantidade antiga para calcular a diferença
                old_qty_row = self.db.query(
                    "SELECT quantity FROM production_items WHERE id = ?",
                    (item_id,)
                )
                old_qty = int(old_qty_row[0]["quantity"]) if old_qty_row else 0
                
                # Atualiza a quantidade na lista de produção
                self.db.execute(
                    "UPDATE production_items SET quantity = ? WHERE id = ?",
                    (new_qty, item_id)
                )
                
                # Atualiza o estoque do produto com a diferença
                quantity_change = new_qty - old_qty
                if quantity_change != 0 and product_id:
                    self.db.execute(
                        "UPDATE products SET stock = stock + ? WHERE id = ?",
                        (quantity_change, product_id)
                    )
                    # Registra em stock_movements para aparecer na tela de Movimentação
                    # (antes esse ajuste de estoque via Produção não deixava rastro nenhum)
                    try:
                        mov_type = 'entrada' if quantity_change > 0 else 'saida'
                        self.db.execute(
                            "INSERT INTO stock_movements(product_id, type, category, quantity, reason, order_id, created_at, created_by) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (product_id, mov_type, 'Produção', abs(quantity_change), 'Ajuste na lista de produção', None,
                             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), getattr(self.db, "current_user", None) or "unknown")
                        )
                    except Exception:
                        pass

                    if self.toast_cb:
                        self.toast_cb(f"Quantidade atualizada: {new_qty} (estoque {quantity_change:+d})")

                    # Atualiza a tabela de estoque
                    self._refresh_stock_table()
                else:
                    if self.toast_cb:
                        self.toast_cb(f"Quantidade atualizada: {new_qty}")
            
            elif col == 2:  # Tamanho
                new_size = item.text().strip()

                self.db.execute(
                    "UPDATE production_items SET size = ? WHERE id = ?",
                    (new_size, item_id)
                )

                # Atualiza o display com formatação (bloqueando sinais: setText() dispara
                # itemChanged de novo, reentrando neste handler com o texto já formatado
                # - "20" virava "20 cm" e o segundo disparo gravava "20 cm" no banco em
                # vez de "20", corrompendo o valor bruto a cada edição)
                self.production_table.blockSignals(True)
                try:
                    item.setText(format_size(new_size) if new_size else "")
                    item.setData(Qt.ItemDataRole.UserRole, new_size)
                finally:
                    self.production_table.blockSignals(False)

                if self.toast_cb:
                    self.toast_cb(f"Tamanho atualizado: {format_size(new_size) if new_size else 'N/A'}")
            
            elif col == 3:  # Observações
                new_notes = item.text().strip()
                
                self.db.execute(
                    "UPDATE production_items SET notes = ? WHERE id = ?",
                    (new_notes, item_id)
                )
                
                if self.toast_cb:
                    self.toast_cb("Observação atualizada")
        
        except ValueError as e:
            if self.toast_cb:
                self.toast_cb(f"Erro: {str(e)}")
            # Reverte para o valor anterior
            self._refresh_production_table()
        except Exception as e:
            if self.toast_cb:
                self.toast_cb(f"Erro ao atualizar: {str(e)}")
            self._refresh_production_table()
    
    def _refresh_stock_table(self) -> None:
        """Atualiza a tabela de estoque (lado direito) com encomendas da data selecionada"""
        try:
            term = self.search_stock_edit.text().strip()
        except Exception:
            term = ""
        
        # Obtém a data selecionada no calendário de produção
        selected_date = self.production_date.date().toString("yyyy-MM-dd")
        
        # Busca produtos com total de encomendas da data selecionada
        if term:
            like = f"%{term}%"
            rows = self.db.query(
                """SELECT p.id, p.name, p.stock, 
                          COALESCE(SUM(o.quantity), 0) as total_orders
                   FROM products p
                   LEFT JOIN orders o ON o.product_id = p.id 
                                      AND o.status != 'Entregue'
                                      AND DATE(o.delivery_date) = ?
                   WHERE p.name LIKE ?
                   GROUP BY p.id, p.name, p.stock
                   ORDER BY 
                     CASE WHEN p.stock <= 0 THEN 0 WHEN p.stock < 5 THEN 1 ELSE 2 END,
                     p.name""", 
                (selected_date, like)
            )
        else:
            rows = self.db.query(
                """SELECT p.id, p.name, p.stock, 
                          COALESCE(SUM(o.quantity), 0) as total_orders
                   FROM products p
                   LEFT JOIN orders o ON o.product_id = p.id 
                                      AND o.status != 'Entregue'
                                      AND DATE(o.delivery_date) = ?
                   GROUP BY p.id, p.name, p.stock
                   ORDER BY 
                     CASE WHEN p.stock <= 0 THEN 0 WHEN p.stock < 5 THEN 1 ELSE 2 END,
                     p.name""",
                (selected_date,)
            )
        
        self.stock_table.setRowCount(0)
        for r in rows:
            row = self.stock_table.rowCount()
            self.stock_table.insertRow(row)
            
            # Nome do produto no header vertical
            self.stock_table.setVerticalHeaderItem(row, QTableWidgetItem(str(r["name"])))
            
            # Qtd (estoque atual)
            stock_item = QTableWidgetItem(str(r["stock"]))
            stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Destaca em vermelho claro se estoque negativo ou zero
            if r["stock"] <= 0:
                stock_item.setBackground(QColor(255, 102, 102))  # Vermelho claro
                stock_item.setForeground(QColor(255, 255, 255))  # Texto branco
                stock_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            # Destaca em amarelo se estoque baixo (menos de 5)
            elif r["stock"] < 5:
                stock_item.setBackground(QColor(255, 193, 7))  # Amarelo
                stock_item.setForeground(QColor(0, 0, 0))  # Texto preto
            self.stock_table.setItem(row, 0, stock_item)
            
            # Encomendas (total de pedidos não entregues)
            orders_item = QTableWidgetItem(str(int(r["total_orders"])))
            orders_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stock_table.setItem(row, 1, orders_item)
    
    def _add_production_item(self) -> None:
        """Adiciona um item manualmente à lista de produção"""
        dialog = ProductionItemDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            product_id, product_name, quantity, sizes, notes = dialog.get_values()
            
            # Salva no banco de dados
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.db.execute("""
                INSERT INTO production_items (product_id, quantity, size, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (product_id, quantity, sizes, notes, now))
            
            # Atualiza a tabela
            self._refresh_production_table()
            
            if self.toast_cb:
                self.toast_cb(f"Item adicionado: {product_name}")
    
    def _import_from_orders(self) -> None:
        """Importa pedidos pendentes/em produção para a lista baseado na data selecionada"""
        # Usa a data selecionada no campo production_date
        selected_date = self.production_date.date().toString("yyyy-MM-dd")
        
        # Debug: mostra quais pedidos existem na data
        debug_rows = self.db.query(
            """
            SELECT o.id, p.name, o.quantity, o.delivery_date, o.status, o.notes
            FROM orders o
            LEFT JOIN products p ON p.id = o.product_id
            WHERE DATE(o.delivery_date) = ?
            ORDER BY p.name
            """,
            (selected_date,)
        )
        
        if debug_rows:
            print(f"\n📋 Pedidos encontrados para {selected_date}:")
            for dr in debug_rows:
                product_name = dr['name'] if dr['name'] else "Pedidos em lote"
                notes_info = f" (LOTE)" if dr['notes'] and dr['notes'].startswith('LOTE:') else ""
                print(f"  - ID:{dr['id']} | {product_name}{notes_info} | Qtd:{dr['quantity']} | Status:{dr['status']}")
        else:
            print(f"\n📋 Nenhum pedido encontrado para {selected_date}")
        
        rows = self.db.query(
            """
            SELECT 
                o.id as order_id,
                c.name as customer_name,
                CASE 
                    WHEN o.notes LIKE 'LOTE:%' THEN 'Pedidos em lote'
                    ELSE p.name
                END as produto,
                CASE 
                    WHEN o.notes LIKE 'LOTE:%' THEN 'Lote'
                    ELSE p.size
                END as size,
                o.quantity as total,
                o.product_id,
                o.notes
            FROM orders o
            LEFT JOIN products p ON p.id = o.product_id
            LEFT JOIN customers c ON c.id = o.customer_id
            WHERE DATE(o.delivery_date) = ?
            AND o.status IN ('Pendente', 'Em produção', 'Aguardando Pagamento', 'Pago')
            ORDER BY c.name, o.notes
            """,
            (selected_date,)
        )
        
        if not rows:
            if self.toast_cb:
                self.toast_cb(f"Nenhum pedido encontrado para {selected_date}")
            return

        # Confirma antes de apagar a lista atual: isso zera TODA a production_items
        # (inclusive itens de outras datas e adicionados manualmente), não só os da
        # data selecionada - sem aviso, um item manual criado minutos antes era
        # destruído silenciosamente ao importar pedidos de qualquer data.
        existing_count = self.db.query("SELECT COUNT(*) AS c FROM production_items")
        if existing_count and int(existing_count[0]["c"]) > 0:
            res = show_message(
                self, "Confirmação",
                f"Importar pedidos de {selected_date} vai substituir TODA a lista de "
                f"produção atual ({existing_count[0]['c']} item(ns), incluindo os adicionados "
                f"manualmente ou de outras datas). Continuar?",
                ("Não", "Sim"), default=1
            )
            if res != 1:
                return

        # Limpa a lista atual (do banco também)
        self.db.execute("DELETE FROM production_items")
        
        # Adiciona os itens ao banco
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for r in rows:
            # Para pedidos em lote ou normais
            customer_info = r["customer_name"] if r["customer_name"] else "Cliente desconhecido"
            notes = f"{customer_info} - Importado de pedidos"
            
            self.db.execute("""
                INSERT INTO production_items (product_id, quantity, size, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (r["product_id"], r["total"], r["size"], notes, now))
        
        # Atualiza a tabela
        self._refresh_production_table()
        
        if self.toast_cb:
            self.toast_cb(f"Importados {len(rows)} item(ns) de pedidos pendentes")
    
    def _remove_selected_item(self) -> None:
        """Remove o(s) item(ns) selecionado(s) da lista de produção.

        Antes só olhava currentRow() (uma linha), então selecionar vários itens
        e clicar em remover só apagava o último focado.
        """
        selected_rows = self.production_table.selectionModel().selectedRows()
        if not selected_rows:
            if self.toast_cb:
                self.toast_cb("Selecione um ou mais itens para remover")
            return

        # Coleta tudo ANTES de remover linhas - remover no meio do loop invalidaria
        # os índices das linhas seguintes
        to_remove: list[tuple[int, Optional[Any], str]] = []
        for index in selected_rows:
            row = index.row()
            name_item = self.production_table.item(row, 0)
            product_name = name_item.text() if name_item else ""
            item_id = name_item.data(Qt.ItemDataRole.UserRole) if name_item else None
            to_remove.append((row, item_id, product_name))

        removed_names: list[str] = []
        ui_only_rows: list[int] = []
        with self.db.transaction():
            for row, item_id, product_name in to_remove:
                if item_id:
                    self.db.execute("DELETE FROM production_items WHERE id = ?", (item_id,))
                    removed_names.append(product_name)
                else:
                    # Fallback: remove apenas da UI (não deveria acontecer)
                    ui_only_rows.append(row)

        if removed_names:
            self._refresh_production_table()
        for row in sorted(ui_only_rows, reverse=True):
            self.production_table.removeRow(row)

        if self.toast_cb:
            if len(removed_names) == 1:
                self.toast_cb(f"Item removido: {removed_names[0]}")
            elif removed_names:
                self.toast_cb(f"{len(removed_names)} itens removidos")
            elif ui_only_rows:
                self.toast_cb(f"{len(ui_only_rows)} item(ns) removido(s) (apenas da UI)")
    
    def _on_date_changed(self, date: QDate) -> None:
        """Callback quando a data é alterada"""
        # Pode adicionar lógica para filtrar por data no futuro
        pass
    
    def _dispatch_to_kitchen(self) -> None:
        """Dispara a lista de produção para a cozinha (painel web)"""
        selected_date = self.production_date.date().toPyDate().isoformat()
        
        # Salva a lista atual com a data selecionada
        production_rows = self.db.query("""
            SELECT p.name, pi.quantity, pi.size, pi.notes
            FROM production_items pi
            JOIN products p ON p.id = pi.product_id
            ORDER BY pi.created_at DESC
        """)
        
        if not production_rows:
            if self.toast_cb:
                self.toast_cb("⚠️ Lista de produção vazia!")
            return
        
        # Salva no arquivo JSON para o painel web
        try:
            import json
            data = {
                "date": selected_date,
                "items": [
                    {
                        "produto": row["name"],
                        "quantidade": row["quantity"],
                        "tamanho": row["size"] or "N/A",
                        "obs": row["notes"] or ""
                    }
                    for row in production_rows
                ]
            }
            
            # Salva no diretório web
            web_dir = os.path.join(RESOURCE_DIR, "web")
            os.makedirs(web_dir, exist_ok=True)
            
            json_path = os.path.join(web_dir, "production_list.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if self.toast_cb:
                self.toast_cb(f"🔥 Lista disparada para cozinha! ({len(production_rows)} itens)")
        
        except Exception as e:
            show_message(self, "Erro", f"Erro ao disparar lista: {e}", ("OK",))
    
    def _clear_list(self) -> None:
        """Limpa toda a lista de produção"""
        if self.production_table.rowCount() == 0:
            if self.toast_cb:
                self.toast_cb("Lista já está vazia")
            return
        
        reply = show_message(
            self,
            "Limpar Lista",
            f"Tem certeza que deseja limpar todos os {self.production_table.rowCount()} item(ns) da lista de produção?",
            ("Cancelar", "Limpar"),
            default=0
        )
        
        if reply == 1:
            # Remove do banco
            self.db.execute("DELETE FROM production_items")
            
            # Atualiza a tabela
            self._refresh_production_table()
            
            if self.toast_cb:
                self.toast_cb("Lista de produção limpa")
