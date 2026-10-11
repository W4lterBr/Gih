# -*- coding: utf-8 -*-
"""Página de Pedidos: CRUD, baixa/ajuste de estoque e etiquetas."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, Callable, Optional, cast

from PyQt6.QtCore import QDate, QSize, QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMenu, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from core.database import Database
from core.formatting import format_date, format_size
from core.paths import APP_DIR
from ui.dialogs.labels_dialog import LabelsDialog
from ui.dialogs.logs_dialog import LogsDialog
from ui.dialogs.order_dialogs import MultiProductOrderDialog, OrderDialog
from ui.icons import safe_qta_icon
from ui.messages import show_message
from ui.pages.base import BasePage


class OrdersPage(BasePage):
    """Página de Pedidos com CRUD básico e baixa/ajuste de estoque."""
    def __init__(self, db: Database, toast_cb: Optional[Callable[[str], None]] = None,
                 dashboard_cb: Optional[Callable[[], None]] = None) -> None:
        super().__init__("Pedidos", "Controle de pedidos")
        self.db = db
        self.toast_cb = toast_cb
        self.dashboard_cb = dashboard_cb

        bl = QVBoxLayout(self.body)
        actions = QHBoxLayout()
        self.btn_add: QPushButton = QPushButton("+ Novo")
        self.btn_add.setProperty("primary", True)
        self.btn_edit: QPushButton = QPushButton("Editar")
        self.btn_del: QPushButton = QPushButton("Excluir")
        self.btn_label: QPushButton = QPushButton("Etiqueta")
        self.btn_report: QPushButton = QPushButton("Relatório")
        actions.addWidget(self.btn_add); actions.addWidget(self.btn_edit); actions.addWidget(self.btn_del); actions.addWidget(self.btn_label); actions.addWidget(self.btn_report); actions.addStretch(1)
        bl.addLayout(actions)

        # Filtros de data
        filters_box = QHBoxLayout()
        filters_box.addWidget(QLabel("Filtro por data:"))
        
        # Data inicial
        filters_box.addWidget(QLabel("De:"))
        self.date_start = QDateEdit()
        self.date_start.setDate(QDate.currentDate())  # Data de hoje por padrão
        self.date_start.setCalendarPopup(True)
        # Debounce: navegar no calendário dispara vários dateChanged; atualiza só uma vez após 300ms
        self._date_refresh_timer = QTimer(self)
        self._date_refresh_timer.setSingleShot(True)
        self._date_refresh_timer.setInterval(300)
        cast(Any, self._date_refresh_timer.timeout).connect(self.refresh)
        self.date_start.dateChanged.connect(lambda: self._date_refresh_timer.start())
        filters_box.addWidget(self.date_start)
        
        # Data final
        filters_box.addWidget(QLabel("Até:"))
        self.date_end = QDateEdit()
        self.date_end.setDate(QDate.currentDate())  # Data de hoje por padrão
        self.date_end.setCalendarPopup(True)
        self.date_end.dateChanged.connect(lambda: self._date_refresh_timer.start())
        filters_box.addWidget(self.date_end)
        
        # Botão para hoje
        btn_today = QPushButton("Hoje")
        btn_today.clicked.connect(self._set_today_filter)
        filters_box.addWidget(btn_today)
        
        # Botão para limpar filtro
        btn_clear_filter = QPushButton("Todos")
        btn_clear_filter.clicked.connect(self._clear_date_filter)
        filters_box.addWidget(btn_clear_filter)
        
        filters_box.addStretch(1)
        bl.addLayout(filters_box)

        # Barra de pesquisa (cliente/produto/status/observação/etiqueta)
        search_box = QHBoxLayout()
        search_box.addWidget(QLabel("Pesquisar:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Cliente, produto, status ou observação…")
        self.search_edit.setClearButtonEnabled(True)
        cast(Any, self.search_edit.textChanged).connect(lambda _t: self.refresh())
        btn_clear = QPushButton("Limpar")
        cast(Any, btn_clear.clicked).connect(lambda: self.search_edit.clear())
        search_box.addWidget(self.search_edit, 1)
        search_box.addWidget(btn_clear)
        bl.addLayout(search_box)

        # adiciona coluna de logs
        self.table: QTableWidget = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Cliente", "Produto", "Tamanho", "Qtd", "Entrega", "Status", "Etiqueta", "Obs", "Logs"])
        self.table.setAlternatingRowColors(True)
        if header := self.table.horizontalHeader():
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            # não esticar a última coluna (Logs)
            header.setStretchLastSection(False)
            try:
                # deixa a coluna Observação (7) esticável
                header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
                # fixa a coluna Logs (8) compacta
                header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(8, 96)
                # centraliza o título 'Logs'
                it = self.table.horizontalHeaderItem(8)
                if it:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            except Exception:
                pass
        # Configura header vertical para altura automática das linhas
        if vh := self.table.verticalHeader():
            vh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            vh.setMinimumSectionSize(36)  # Altura mínima para acomodar ícones de 28px
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)
        bl.addWidget(self.table)

        cast(Any, self.btn_add.clicked).connect(self.add)
        cast(Any, self.btn_edit.clicked).connect(self.edit)
        cast(Any, self.btn_del.clicked).connect(self.delete)
        cast(Any, self.btn_label.clicked).connect(self.open_label_manager)
        cast(Any, self.btn_report.clicked).connect(self.generate_report)

        self.refresh()
        # se usuário não for admin, esconde a coluna de Logs
        try:
            if getattr(self.db, "current_role", "admin") != "admin":
                # Esconde a coluna de Logs para não-admins
                self.table.setColumnHidden(8, True)
        except Exception:
            pass

    def refresh(self) -> None:
        # Aplica filtro da barra de pesquisa, se houver
        try:
            term = self.search_edit.text().strip()
        except Exception:
            term = ""
            
        # Obtém datas do filtro
        try:
            date_start = self.date_start.date().toString("yyyy-MM-dd")
            date_end = self.date_end.date().toString("yyyy-MM-dd")
        except Exception:
            # Se não há filtro de data definido, usa data de hoje
            today = QDate.currentDate().toString("yyyy-MM-dd")
            date_start = today
            date_end = today
        
        # Constroi a query base com agregação para pedidos em lote
        base_query = """
            SELECT 
                CASE WHEN o.notes LIKE 'LOTE:%' THEN MIN(o.id) ELSE o.id END AS id,
                CASE WHEN o.notes LIKE 'LOTE:%' THEN MIN(o.order_number) ELSE o.order_number END AS order_number,
                c.name AS cliente,
                CASE WHEN o.notes LIKE 'LOTE:%' THEN 'Pedidos em lote' ELSE p.name END AS produto,
                CASE WHEN o.notes LIKE 'LOTE:%' THEN 'Lote' ELSE p.size END AS produto_size,
                CASE WHEN o.notes LIKE 'LOTE:%' THEN SUM(o.quantity) ELSE o.quantity END AS quantity,
                o.delivery_date,
                CASE WHEN o.notes LIKE 'LOTE:%' THEN SUM(o.total) ELSE o.total END AS total,
                o.status,
                COALESCE(o.label, 'Comum') AS label,
                l.color AS label_color,
                o.notes
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = o.product_id
            LEFT JOIN labels l ON l.name = o.label
            WHERE DATE(o.delivery_date) BETWEEN ? AND ?
        """
        
        params = [date_start, date_end]
        
        if term:
            like = f"%{term}%"
            base_query += " AND (c.name LIKE ? OR p.name LIKE ? OR o.status LIKE ? OR COALESCE(o.notes,'') LIKE ?)"
            params.extend([like, like, like, like])
        
        # GROUP BY para agregar pedidos em lote
        base_query += """
            GROUP BY 
                o.customer_id,
                o.delivery_date,
                o.status,
                CASE WHEN o.notes LIKE 'LOTE:%' THEN SUBSTR(o.notes, 1, INSTR(o.notes, '|')) ELSE o.id END
            ORDER BY o.delivery_date DESC, MIN(o.created_at) DESC
        """
        
        rows = self.db.query(base_query, tuple(params))
        # Pausa o redesenho durante o preenchimento (evita travar com muitos pedidos)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r["cliente"])))
            self.table.setItem(row, 1, QTableWidgetItem(str(r["produto"])))
            self.table.setItem(row, 2, QTableWidgetItem(format_size(r["produto_size"])))
            self.table.setItem(row, 3, QTableWidgetItem(str(r["quantity"])))
            self.table.setItem(row, 4, QTableWidgetItem(format_date(str(r["delivery_date"]))))
            self.table.setItem(row, 5, QTableWidgetItem(str(r["status"])))
            
            # Etiqueta com cor
            label_text = str(r["label"] if "label" in r.keys() else "Comum")
            label_item = QTableWidgetItem(label_text)
            
            # Aplica cor de fundo se houver
            if "label_color" in r.keys() and r["label_color"]:
                try:
                    from PyQt6.QtGui import QColor, QBrush
                    bg_color = QColor(r["label_color"])
                    label_item.setBackground(QBrush(bg_color))
                    
                    # Calcula cor do texto baseado na luminância do fundo
                    # Fórmula: (R*299 + G*587 + B*114) / 1000
                    luminance = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
                    text_color = QColor("#000000") if luminance > 128 else QColor("#ffffff")
                    label_item.setForeground(QBrush(text_color))
                except Exception:
                    pass
            
            self.table.setItem(row, 6, label_item)
            self.table.setItem(row, 7, QTableWidgetItem(str(r["notes"] or "")))
            self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(r["id"])))
            
            # Botão de logs (ícone) com container centralizado
            btn = QPushButton(); btn.setObjectName("IconButton")
            btn.setToolTip("Ver logs deste pedido")
            btn.setFlat(True)
            try:
                btn.setIcon(safe_qta_icon("ph.magnifying-glass", color="#9aa3b2"))
            except Exception:
                pass
                pass
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(28, 28)
            ent_id = int(r["id"]) if r["id"] is not None else None
            cast(Any, btn.clicked).connect(lambda _checked=False, eid=ent_id: self._show_logs("order", eid))
            # Container para centralizar o botão
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.addWidget(btn)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 8, container)
            # Força altura mínima de 48px para garantir que ícones não sejam cortados
            self.table.setRowHeight(row, 48)
        self.table.setUpdatesEnabled(True)
        self.table.resizeColumnsToContents()
        # Reaplica largura fixa da coluna de Logs após autoajuste
        try:
            self.table.setColumnWidth(8, 96)
        except Exception:
            pass

    def open_label_manager(self) -> None:
        dlg = LabelsDialog(self.db, self)
        dlg.exec()
        # Atualiza a tabela após fechar o diálogo
        self.refresh()

    def _table_context_menu(self, pos):
        """Menu de contexto da tabela de pedidos"""
        idx = self.table.indexAt(pos)
        if idx.row() < 0:
            return
        
        menu = QMenu(self)
        action_label = menu.addAction("Alterar Etiqueta")
        
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == action_label:
            self._change_order_label()
    
    def _change_order_label(self) -> None:
        """Altera a etiqueta do pedido selecionado"""
        order_id = self.current_id()
        if not order_id:
            return
        
        # Busca etiqueta atual do pedido
        orders = self.db.query("SELECT label FROM orders WHERE id = ?", (order_id,))
        if not orders:
            return
        
        current_label = orders[0]["label"] or "Comum"
        
        # Busca todas as etiquetas disponíveis
        labels = self.db.query("SELECT name FROM labels ORDER BY name")
        label_names = ["Comum"] + [l["name"] for l in labels]
        
        # Diálogo para escolher nova etiqueta
        from PyQt6.QtWidgets import QInputDialog
        from core.config import load_config
        
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Alterar Etiqueta")
        dlg.setLabelText("Escolha a nova etiqueta:")
        dlg.setComboBoxItems(label_names)
        dlg.setTextValue(current_label if current_label in label_names else "Comum")
        
        
        ok = dlg.exec()
        new_label = dlg.textValue()
        
        if ok and new_label:
            try:
                self.db.execute(
                    "UPDATE orders SET label = ? WHERE id = ?",
                    (new_label, order_id)
                )
                self.db.commit()
                if self.toast_cb:
                    self.toast_cb(f"✓ Etiqueta alterada para '{new_label}'")
                self.refresh()
            except Exception as e:
                if self.toast_cb:
                    self.toast_cb(f"✗ Erro ao alterar etiqueta: {e}")

    def _show_logs(self, entity: str, entity_id: Optional[int]) -> None:
        dlg = LogsDialog(self.db, entity, entity_id, self)
        dlg.exec()

    def current_id(self) -> Optional[int]:
        idx = self.table.currentRow()
        if idx < 0:
            return None
        vh = self.table.verticalHeaderItem(idx)
        return int(vh.text()) if vh else None

    def add(self) -> None:
        """Cria novo pedido com suporte a múltiplos produtos"""
        # Usa o novo diálogo de múltiplos produtos
        d = MultiProductOrderDialog(self.db, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                order_data = d.get_order_data()
                
                if not order_data["products"]:
                    show_message(self, "Aviso", "Nenhum produto foi adicionado ao pedido.", ("OK",))
                    return
                
                cust_id = order_data["customer_id"]
                d_iso = order_data["delivery_date"]
                status = order_data["status"]
                label = order_data["label"]
                notes = order_data["notes"]
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # Verifica se a data de entrega é uma segunda-feira (weekday() == 0)
                delivery_date_obj = datetime.strptime(d_iso, "%Y-%m-%d")
                if delivery_date_obj.weekday() == 0:
                    show_message(self, "Pedido Negado", "Segunda não há expediente, pedido negado.", ("OK",))
                    return
                
                # Verifica se deve reservar estoque agora ou depois
                today_obj = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                should_reserve_now = delivery_date_obj <= today_obj

                # Marcador de lote com ID único (não só a contagem de itens) - sem isso,
                # dois lotes do mesmo cliente/data/status com o mesmo número de itens
                # ficavam indistinguíveis para o agrupamento na lista e para a exclusão
                # em lote, podendo apagar pedidos de um lote diferente do selecionado.
                import uuid
                batch_id = uuid.uuid4().hex[:8] if len(order_data["products"]) > 1 else None

                # Cria um pedido para CADA produto. Agrupado em uma única transação:
                # além de muito mais rápido num lote grande (um só commit em vez de
                # vários por produto - sem isso a janela travava por vários segundos
                # numa seleção grande), a transação já desfaz tudo sozinha se algo
                # falhar no meio. NÃO adicionar reversão manual aqui: já tentamos isso
                # e causava dupla-reversão (a transação desfazia o estoque certo, e o
                # código manual desfazia de novo por cima, duplicando o valor).
                pedidos_criados: list[int] = []
                try:
                    with self.db.transaction():
                        for product in order_data["products"]:
                            prod_id = product["product_id"]
                            qty = product["quantity"]
                            total = 0.0  # Não controlamos preços

                            notes_with_marker = notes
                            if batch_id:
                                notes_with_marker = f"LOTE:{batch_id}:{len(order_data['products'])} itens | {notes or ''}".strip()

                            # Cria pedido
                            cur = self.db.execute("""
                                INSERT INTO orders(order_number, customer_id, product_id, quantity,
                                                   delivery_date, total, status, label, notes, stock_reserved, created_at)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                            """, (None, cust_id, prod_id, qty, d_iso, total, status, label, notes_with_marker, 1 if should_reserve_now else 0, now))
                            oid = int(cur.lastrowid) if cur and cur.lastrowid is not None else None

                            # Define order_number sequencial
                            if oid:
                                self.db.execute("UPDATE orders SET order_number=? WHERE id=?", (oid, oid))
                                pedidos_criados.append(oid)

                            # Baixa estoque APENAS se data de entrega <= hoje
                            if should_reserve_now:
                                self.db.execute(
                                    "UPDATE products SET stock = stock - ? WHERE id=?",
                                    (qty, prod_id)
                                )
                                self.db.execute(
                                    "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                                    (prod_id, 'saida', qty, 'Pedido', oid, now)
                                )

                            # Auditoria
                            try:
                                self.db.audit_log("order", oid, "create", details=f"cust={cust_id},prod={prod_id},qty={qty},total={total},reserved={should_reserve_now}")
                            except Exception:
                                pass
                except Exception as batch_error:
                    # A transação já reverteu tudo no banco (nenhum pedido/estoque/
                    # movimentação deste lote ficou persistido) - só falta avisar o usuário.
                    show_message(
                        self, "Erro ao salvar",
                        f"Falha ao criar pedido(s) de {len(order_data['products'])} "
                        f"produto(s): {batch_error}\n\n"
                        f"Nenhum pedido deste lote foi salvo - a operação foi revertida.",
                        ("OK",)
                    )
                    return

                self.refresh()
                if self.dashboard_cb:
                    self.dashboard_cb()
                if self.toast_cb:
                    qtd_produtos = len(pedidos_criados)
                    self.toast_cb(f"✅ {qtd_produtos} pedido(s) criado(s) com sucesso!")

            except Exception as e:
                show_message(self, "Erro ao salvar", str(e), ("OK",))

    def edit(self) -> None:
        oid = self.current_id()
        if not oid:
            return
        row = self.db.query("SELECT * FROM orders WHERE id=?", (oid,))
        if not row:
            return
        data = row[0]
        d = OrderDialog(self.db, self, data)
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                cust_id, prod_id, qty_new, d_iso, total, status, label, notes = d.get_values()
                # Mesma regra aplicada na criação: sem expediente às segundas.
                # Sem esta checagem aqui, dava para criar um pedido válido e depois
                # editar a data de entrega para uma segunda, contornando a regra.
                delivery_date_obj = datetime.strptime(d_iso, "%Y-%m-%d")
                if delivery_date_obj.weekday() == 0:
                    show_message(self, "Pedido Negado", "Segunda não há expediente, pedido negado.", ("OK",))
                    return
                # Só ajusta estoque se este pedido já teve estoque reservado (baixado).
                # Pedidos futuros (stock_reserved=0) nunca tiraram estoque, então editar
                # sua quantidade/produto aqui não deve tocar em products.stock - quem vai
                # baixar é o check_and_reserve_stock() quando a data de entrega chegar.
                was_reserved = int(data["stock_reserved"] or 0) == 1
                # Se o pedido ainda não tinha reservado estoque e a nova data de entrega
                # já é hoje ou passada, reserva agora - sem isso o pedido ficava com
                # stock_reserved=0 e o estoque só era baixado até 1h depois, quando o
                # timer check_and_reserve_stock() rodasse de novo (relatórios de estoque
                # ficavam errados nesse meio-tempo). Não trata o caso inverso (editar um
                # pedido já reservado para uma data futura) - isso reverteria a baixa e
                # não foi reportado como problema.
                today_obj = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                should_reserve_now = (not was_reserved) and delivery_date_obj <= today_obj

                if was_reserved:
                    old_qty = int(data["quantity"])
                    old_pid = int(data["product_id"])
                    if old_pid == prod_id:
                        delta = qty_new - old_qty
                        # se delta > 0, baixa; se delta < 0, devolve
                        if delta != 0:
                            mov_type = 'saida' if delta > 0 else 'entrada'
                            self.db.execute("UPDATE products SET stock = stock - ? WHERE id=?", (delta, prod_id))
                            self.db.execute(
                                "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                                (prod_id, mov_type, abs(delta), 'Ajuste pedido', oid, datetime.now().strftime("%Y-%m-%d %H:%M"))
                            )
                    else:
                        # devolve antigo
                        self.db.execute("UPDATE products SET stock = stock + ? WHERE id=?", (old_qty, old_pid))
                        self.db.execute(
                            "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                            (old_pid, 'entrada', old_qty, 'Ajuste pedido', oid, datetime.now().strftime("%Y-%m-%d %H:%M"))
                        )
                        # baixa novo
                        self.db.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty_new, prod_id))
                        self.db.execute(
                            "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                            (prod_id, 'saida', qty_new, 'Ajuste pedido', oid, datetime.now().strftime("%Y-%m-%d %H:%M"))
                        )
                elif should_reserve_now:
                    self.db.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty_new, prod_id))
                    self.db.execute(
                        "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                        (prod_id, 'saida', qty_new, 'Pedido (reservado ao editar data)', oid, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )

                new_stock_reserved = 1 if (was_reserved or should_reserve_now) else 0
                self.db.execute("""
                    UPDATE orders SET customer_id=?, product_id=?, quantity=?, delivery_date=?, total=?, status=?, label=?, notes=?, stock_reserved=?
                    WHERE id=?
                """, (cust_id, prod_id, qty_new, d_iso, total, status, label, notes, new_stock_reserved, oid))
                # auditoria: atualização do pedido (somente campos alterados)
                try:
                    changes: list[str] = []
                    # cliente
                    try:
                        old_cust_id = int(data["customer_id"])
                    except Exception:
                        old_cust_id = None
                    if old_cust_id != cust_id:
                        old_name = None
                        new_name = None
                        r = self.db.query("SELECT name FROM customers WHERE id=?", (old_cust_id,)) if old_cust_id else []
                        if r:
                            old_name = r[0]["name"]
                        r2 = self.db.query("SELECT name FROM customers WHERE id=?", (cust_id,))
                        if r2:
                            new_name = r2[0]["name"]
                        changes.append(f"customer: '{old_name or old_cust_id}' -> '{new_name or cust_id}'")
                    # produto
                    try:
                        old_prod_id = int(data["product_id"])
                    except Exception:
                        old_prod_id = None
                    if old_prod_id != prod_id:
                        old_p = self.db.query("SELECT name FROM products WHERE id=?", (old_prod_id,)) if old_prod_id else []
                        new_p = self.db.query("SELECT name FROM products WHERE id=?", (prod_id,))
                        old_pn = old_p[0]["name"] if old_p else old_prod_id
                        new_pn = new_p[0]["name"] if new_p else prod_id
                        changes.append(f"product: '{old_pn}' -> '{new_pn}'")
                    # quantidade
                    try:
                        old_qty = int(data["quantity"])
                    except Exception:
                        old_qty = None
                    if old_qty != qty_new:
                        changes.append(f"quantity: {old_qty} -> {qty_new}")
                    # entrega
                    if str(data["delivery_date"] or "") != str(d_iso or ""):
                        changes.append(f"delivery_date: '{data['delivery_date']}' -> '{d_iso}'")
                    # total
                    try:
                        old_total = float(data["total"])
                    except Exception:
                        old_total = None
                    if old_total is None or float(total) != old_total:
                        changes.append(f"total: {old_total} -> {total}")
                    # status
                    if str(data["status"] or "") != str(status or ""):
                        changes.append(f"status: '{data['status'] or ''}' -> '{status or ''}'")
                    # notes
                    if str(data["notes"] or "") != str(notes or ""):
                        changes.append(f"notes: '{data['notes'] or ''}' -> '{notes or ''}'")
                    details = "; ".join(changes) if changes else None
                    self.db.audit_log("order", oid, "update", details=details)
                except Exception:
                    pass
                self.refresh()
                if self.dashboard_cb:
                    self.dashboard_cb()
                if self.toast_cb:
                    self.toast_cb("Pedido atualizado")
            except Exception as e:
                show_message(self, "Erro ao atualizar", str(e), ("OK",))

    def delete(self) -> None:
        """Exclui o(s) pedido(s) selecionado(s)"""
        # Obtém todos os IDs selecionados
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        # Coleta os IDs de todos os pedidos selecionados
        order_ids = []
        for index in selected_rows:
            row = index.row()
            if row < self.table.rowCount():
                # Pega o ID do cabeçalho vertical (onde está armazenado)
                vh_item = self.table.verticalHeaderItem(row)
                if vh_item:
                    try:
                        oid = int(vh_item.text())
                        
                        # Verifica se é um pedido em lote checando as notas
                        lote_check = self.db.query("SELECT notes, customer_id, delivery_date, status, label FROM orders WHERE id=?", (oid,))
                        if lote_check and lote_check[0]["notes"] and lote_check[0]["notes"].startswith("LOTE:"):
                            # É um pedido em lote - precisa excluir TODOS os pedidos do mesmo lote
                            # Identifica todos os pedidos com o mesmo marcador LOTE, cliente, data e status
                            notes_prefix = lote_check[0]["notes"].split("|")[0].strip()  # Pega "LOTE:N itens"
                            cust_id = lote_check[0]["customer_id"]
                            delivery = lote_check[0]["delivery_date"]
                            status = lote_check[0]["status"]
                            label = lote_check[0]["label"]
                            
                            # Busca todos os IDs do lote
                            lote_ids_query = """
                                SELECT id FROM orders 
                                WHERE customer_id=? AND delivery_date=? AND status=? 
                                AND COALESCE(label, 'Comum')=COALESCE(?, 'Comum')
                                AND notes LIKE ?
                            """
                            lote_rows = self.db.query(lote_ids_query, (cust_id, delivery, status, label, f"{notes_prefix}%"))
                            for lote_row in lote_rows:
                                order_ids.append(int(lote_row["id"]))
                        else:
                            # Pedido normal - adiciona apenas este ID
                            order_ids.append(oid)
                    except (ValueError, AttributeError):
                        pass
        
        if not order_ids:
            return
        
        # Remove duplicatas mantendo ordem
        order_ids = list(dict.fromkeys(order_ids))
        
        # Mensagem de confirmação diferente para múltiplos pedidos
        count = len(order_ids)
        if count == 1:
            msg = "Excluir este pedido?"
        else:
            msg = f"Excluir {count} pedidos selecionados?"
        
        res = show_message(self, "Confirmação", msg, ("Não", "Sim"), default=1)
        if res == 1:
            try:
                deleted_count = 0
                # Agrupa tudo em uma única transação: sem isso, cada pedido fazia até 3
                # commits síncronos (estoque + movimentação + o próprio pedido), e excluir
                # uma seleção grande (ou vários lotes) travava a janela por vários segundos.
                with self.db.transaction():
                    for oid in order_ids:
                        try:
                            # Busca informações do pedido para devolver estoque
                            row = self.db.query("SELECT product_id, quantity, stock_reserved FROM orders WHERE id=?", (oid,))
                            if row:
                                pid_value = row[0]["product_id"]
                                qty = int(row[0]["quantity"])
                                was_reserved = int(row[0]["stock_reserved"] or 0) == 1

                                # Só devolve estoque se tiver product_id (pedidos normais) E se o
                                # estoque desse pedido já tinha sido reservado/baixado de fato -
                                # senão soma estoque fantasma que nunca havia sido subtraído
                                if pid_value is not None and was_reserved:
                                    pid = int(pid_value)
                                    self.db.execute("UPDATE products SET stock = stock + ? WHERE id=?", (qty, pid))

                            # Remove dependências antes de excluir o pedido
                            # 1. Remove movimentações de estoque relacionadas
                            self.db.execute("DELETE FROM stock_movements WHERE order_id=?", (oid,))

                            # Não apaga audit_logs deste pedido (não há FK exigindo isso -
                            # apagar aqui só destruía o histórico de criação/edição do pedido
                            # bem antes de registrar a própria exclusão logo abaixo)

                            # 2. Exclui o pedido
                            self.db.execute("DELETE FROM orders WHERE id=?", (oid,))

                            # Registra a exclusão no log
                            try:
                                self.db.audit_log("order", oid, "delete", details=None)
                            except Exception:
                                pass

                            deleted_count += 1
                        except Exception as e:
                            print(f"Erro ao excluir pedido #{oid}: {e}")
                            continue

                self.refresh()
                if self.dashboard_cb:
                    self.dashboard_cb()
                if self.toast_cb:
                    if deleted_count == 1:
                        self.toast_cb("Pedido excluído")
                    else:
                        self.toast_cb(f"{deleted_count} pedidos excluídos")
            except Exception as e:
                show_message(self, "Erro ao excluir", str(e), ("OK",))

    # ------------------------------------------------------------------
    # Relatório de pedidos (PDF / Excel)
    # ------------------------------------------------------------------
    ALL_CUSTOMERS = "Todos os Clientes"
    ALL_LABELS = "Todas as Etiquetas"

    def _company_info(self) -> tuple[str, Optional[str]]:
        """Retorna (nome, caminho do logo) da empresa cadastrada, com fallback para o logo padrão."""
        name, logo = "Confeitaria", None
        try:
            rows = self.db.query("SELECT name, logo_path FROM company WHERE id=1")
            if rows:
                name = rows[0]["name"] or name
                logo = rows[0]["logo_path"]
        except Exception:
            pass
        if not logo or not os.path.exists(logo):
            logo = next((p for p in (
                os.path.join(APP_DIR, "assets", "icons", "logo.png"),
                os.path.join(APP_DIR, "web", "logo.png"),
            ) if os.path.exists(p)), None)
        return name, logo

    def generate_report(self) -> None:
        """Gera relatório em PDF ou Excel dos pedidos do período, filtrados por cliente e etiqueta."""
        customers = self.db.query("""
            SELECT DISTINCT c.name FROM orders o
            JOIN customers c ON c.id = o.customer_id
            WHERE c.name IS NOT NULL AND c.name != ''
            ORDER BY c.name
        """)
        labels = self.db.query("SELECT DISTINCT name FROM labels WHERE name IS NOT NULL AND name != '' ORDER BY name")
        label_names = [self.ALL_LABELS, "Comum"] + [l["name"] for l in labels if l["name"] != "Comum"]

        dlg = QDialog(self)
        dlg.setWindowTitle("Gerar Relatório")
        form = QFormLayout(dlg)
        cb_customer = QComboBox(); cb_customer.addItems([self.ALL_CUSTOMERS] + [c["name"] for c in customers])
        cb_label = QComboBox(); cb_label.addItems(label_names)
        cb_format = QComboBox(); cb_format.addItems(["PDF", "Excel"])
        period = f"{self.date_start.date().toString('dd/MM/yyyy')} a {self.date_end.date().toString('dd/MM/yyyy')}"
        form.addRow("Período:", QLabel(period))
        form.addRow("Cliente:", cb_customer)
        form.addRow("Etiqueta:", cb_label)
        form.addRow("Formato:", cb_format)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        cast(Any, buttons.accepted).connect(dlg.accept)
        cast(Any, buttons.rejected).connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        customer = cb_customer.currentText()
        label = cb_label.currentText()
        report_format = cb_format.currentText()
        date_start = self.date_start.date().toString("yyyy-MM-dd")
        date_end = self.date_end.date().toString("yyyy-MM-dd")

        query = """
            SELECT c.name AS cliente, p.name AS produto, p.size AS produto_size,
                   o.quantity, o.delivery_date, o.status,
                   COALESCE(o.label, 'Comum') AS label, o.notes
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = o.product_id
            WHERE DATE(o.delivery_date) BETWEEN ? AND ?
        """
        params: list[Any] = [date_start, date_end]
        if customer != self.ALL_CUSTOMERS:
            query += " AND c.name = ?"
            params.append(customer)
        if label == "Comum":
            query += " AND (o.label IS NULL OR o.label = 'Comum')"
        elif label != self.ALL_LABELS:
            query += " AND o.label = ?"
            params.append(label)
        query += " ORDER BY o.delivery_date ASC, o.created_at ASC"

        rows = self.db.query(query, tuple(params))
        if not rows:
            show_message(self, "Aviso", "Nenhum pedido encontrado com os filtros selecionados.", ("OK",))
            return

        default_dir = os.path.join(os.path.expanduser("~"), "Documents")
        if not os.path.isdir(default_dir):
            default_dir = os.path.expanduser("~")
        customer_suffix = customer.replace(" ", "_") if customer != self.ALL_CUSTOMERS else "Todos"
        ext, file_filter = (".pdf", "PDF (*.pdf)") if report_format == "PDF" else (".xlsx", "Excel (*.xlsx)")
        default_name = os.path.join(default_dir, f"relatorio_{customer_suffix}_{label.replace(' ', '_')}_{date_start}_{date_end}{ext}")
        filepath, _ = QFileDialog.getSaveFileName(self, f"Salvar Relatório {report_format}", default_name, file_filter)
        if not filepath:
            return

        subtitle = f"Período: {format_date(date_start)} a {format_date(date_end)}"
        if customer != self.ALL_CUSTOMERS:
            subtitle += f" | Cliente: {customer}"
        if label != self.ALL_LABELS:
            subtitle += f" | Etiqueta: {label}"

        try:
            if report_format == "PDF":
                self._generate_pdf_report(filepath, rows, subtitle)
            else:
                self._generate_excel_report(filepath, rows, subtitle)
        except ImportError as e:
            show_message(self, "Erro", f"Biblioteca necessária não instalada: {e.name}", ("OK",))
            return
        except Exception as e:
            show_message(self, "Erro", f"Erro ao gerar relatório {report_format}:\n{e}", ("OK",))
            return

        if self.toast_cb:
            self.toast_cb(f"Relatório {report_format} gerado: {os.path.basename(filepath)}")
        if show_message(self, "Sucesso", f"Relatório {report_format} gerado com sucesso!\n\nDeseja abrir o arquivo?", ("Não", "Sim"), default=1) == 1:
            try:
                os.startfile(filepath)  # type: ignore[attr-defined]
            except Exception:
                import subprocess
                subprocess.call(["open" if sys.platform == "darwin" else "xdg-open", filepath])

    REPORT_HEADERS = ["#", "Cliente", "Produto", "Tamanho", "Qtd", "Entrega", "Status", "Etiqueta", "Observações"]

    def _report_row(self, idx: int, r: Any) -> list[Any]:
        return [idx, str(r["cliente"]), str(r["produto"]), format_size(r["produto_size"]),
                int(r["quantity"]), format_date(str(r["delivery_date"])), str(r["status"]),
                str(r["label"] or "Comum"), str(r["notes"] or "")]

    def _generate_pdf_report(self, filepath: str, rows: list, subtitle: str) -> None:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from xml.sax.saxutils import escape

        company_name, logo = self._company_info()
        doc = SimpleDocTemplate(filepath, pagesize=landscape(A4), topMargin=1.5*cm, bottomMargin=1.5*cm,
                                leftMargin=2*cm, rightMargin=2*cm, title="Relatório de Pedidos")
        elements: list[Any] = []
        if logo:
            try:
                img = Image(logo, width=3*cm, height=3*cm, kind="proportional")
                img.hAlign = "LEFT"
                elements += [img, Spacer(1, 0.3*cm)]
            except Exception:
                pass

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("T", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#1f2937"), alignment=TA_CENTER, spaceAfter=6)
        sub_style = ParagraphStyle("S", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER, spaceAfter=20)
        cell_style = ParagraphStyle("C", parent=styles["Normal"], fontSize=9, leading=11, textColor=colors.HexColor("#374151"))
        total_style = ParagraphStyle("Tot", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#1f2937"))
        footer_style = ParagraphStyle("F", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)

        elements.append(Paragraph(escape(company_name), title_style))
        elements.append(Paragraph("Relatório de Pedidos", sub_style))
        elements.append(Paragraph(escape(subtitle), sub_style))

        data: list[list[Any]] = [self.REPORT_HEADERS]
        total_qty = 0
        for idx, r in enumerate(rows, 1):
            row = self._report_row(idx, r)
            total_qty += row[4]
            data.append([Paragraph(escape(str(v)), cell_style) for v in row])
        data.append([""] * 3 + [Paragraph("TOTAL:", total_style), Paragraph(str(total_qty), total_style)] + [""] * 4)

        table = Table(data, colWidths=[1.2*cm, 3.5*cm, 3.5*cm, 2*cm, 1.2*cm, 2.2*cm, 3*cm, 2.5*cm, 4*cm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e5e7eb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
            ("BOX", (0, -1), (-1, -1), 1, colors.HexColor("#1f2937")),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph(f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", footer_style))
        doc.build(elements)

    def _generate_excel_report(self, filepath: str, rows: list, subtitle: str) -> None:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.drawing.image import Image as XLImage

        company_name, logo = self._company_info()
        wb = Workbook()
        ws = wb.active
        ws.title = "Relatório de Pedidos"

        first_row = 1
        if logo:
            try:
                img = XLImage(logo)
                ratio = 100 / max(img.width, img.height)
                img.width, img.height = int(img.width * ratio), int(img.height * ratio)
                ws.add_image(img, "A1")
                first_row = 6
            except Exception:
                pass

        for offset, (text, font) in enumerate([
            (company_name, Font(size=18, bold=True, color="1f2937")),
            ("Relatório de Pedidos", Font(size=13, bold=True, color="374151")),
            (subtitle, Font(size=11, color="6b7280")),
        ]):
            r = first_row + offset
            ws.cell(row=r, column=1, value=text).font = font
            ws.cell(row=r, column=1).alignment = Alignment(horizontal="center")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)

        thin = Side(style="thin", color="e5e7eb")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_row = first_row + 4
        for col, header in enumerate(self.REPORT_HEADERS, start=1):
            cell = ws.cell(row=header_row, column=col, value=header)
            cell.fill = PatternFill("solid", start_color="1f2937")
            cell.font = Font(bold=True, color="FFFFFF", size=11)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        fills = [PatternFill("solid", start_color="FFFFFF"), PatternFill("solid", start_color="f9fafb")]
        total_qty = 0
        row_num = header_row
        for idx, r in enumerate(rows, 1):
            row_num += 1
            values = self._report_row(idx, r)
            total_qty += values[4]
            for col, value in enumerate(values, start=1):
                cell = ws.cell(row=row_num, column=col, value=value)
                cell.border = border
                cell.fill = fills[(idx + 1) % 2]
                cell.alignment = Alignment(horizontal="center", vertical="center") if col in (1, 5, 6) \
                    else Alignment(horizontal="left", vertical="top", wrap_text=True)

        row_num += 1
        bold = Side(style="medium", color="1f2937")
        for col in range(1, 10):
            cell = ws.cell(row=row_num, column=col)
            cell.fill = PatternFill("solid", start_color="f3f4f6")
            cell.border = Border(left=bold, right=bold, top=bold, bottom=bold)
            cell.font = Font(bold=True, size=11, color="1f2937")
            cell.alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=4, value="TOTAL:")
        ws.cell(row=row_num, column=5, value=total_qty)

        for letter, width in zip("ABCDEFGHI", (8, 25, 25, 12, 8, 15, 20, 15, 35)):
            ws.column_dimensions[letter].width = width
        ws.cell(row=row_num + 2, column=1, value=f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}").font = Font(size=9, italic=True, color="9ca3af")
        wb.save(filepath)

    def _set_today_filter(self) -> None:
        """Define o filtro para a data de hoje"""
        today = QDate.currentDate()
        self.date_start.setDate(today)
        self.date_end.setDate(today)
        self.refresh()

    def _clear_date_filter(self) -> None:
        """Remove o filtro de data mostrando todos os pedidos"""
        # Define uma data muito antiga e uma muito futura para mostrar todos
        self.date_start.setDate(QDate(2020, 1, 1))
        self.date_end.setDate(QDate(2030, 12, 31))
        self.refresh()
