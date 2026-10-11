# -*- coding: utf-8 -*-
"""Página de Clientes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional, cast

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import Database
from ui.dialogs.customer_dialog import CustomerDialog
from ui.dialogs.logs_dialog import LogsDialog
from ui.dialogs.order_dialogs import MultiProductOrderDialog
from ui.icons import safe_qta_icon
from ui.messages import show_message
from ui.pages.base import BasePage


class CustomersPage(BasePage):
    def __init__(self, db: Database, toast_cb: Optional[Callable[[str], None]] = None) -> None:
        super().__init__("Clientes", "Gestão de clientes e histórico")
        self.db = db
        self.toast_cb = toast_cb
        self.dashboard_cb: Optional[Callable[[], None]] = None  # <- para Pylance
        bl = QVBoxLayout(self.body)
        actions = QHBoxLayout()
        self.btn_add: QPushButton = QPushButton("+ Novo")
        self.btn_add.setProperty("primary", True)
        self.btn_edit: QPushButton = QPushButton("Editar")
        self.btn_del: QPushButton = QPushButton("Excluir")
        actions.addWidget(self.btn_add); actions.addWidget(self.btn_edit); actions.addWidget(self.btn_del); actions.addStretch(1)
        bl.addLayout(actions)
        # Barra de pesquisa (filtro por nome/telefone/endereço/observação)
        search_box = QHBoxLayout()
        lbl_search = QLabel("Pesquisar:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nome, telefone, endereço ou observação…")
        self.search_edit.setClearButtonEnabled(True)
        cast(Any, self.search_edit.textChanged).connect(lambda _t: self.refresh())
        btn_clear = QPushButton("Limpar")
        cast(Any, btn_clear.clicked).connect(lambda: self.search_edit.clear())
        search_box.addWidget(lbl_search)
        search_box.addWidget(self.search_edit, 1)
        search_box.addWidget(btn_clear)
        bl.addLayout(search_box)
        # Tabela com ação rápida de pedido (antes de Logs)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nome", "Telefone", "Endereço", "Observação", "Pedido", "Logs"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        if header := self.table.horizontalHeader():
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            # não esticar a última coluna; manter Logs compacto
            header.setStretchLastSection(False)
            try:
                logs_col = 5  # Logs agora é a coluna 5 (0-based)
                header.setSectionResizeMode(logs_col, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(logs_col, 96)
                it = self.table.horizontalHeaderItem(logs_col)
                if it:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            except Exception:
                pass
        # Configura header vertical para altura automática das linhas  
        if vh := self.table.verticalHeader():
            vh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            vh.setMinimumSectionSize(36)  # Altura mínima para acomodar ícones de 28px
        bl.addWidget(self.table)
        # se usuário não for admin, esconde a coluna de Logs
        try:
            if getattr(self.db, "current_role", "admin") != "admin":
                self.table.setColumnHidden(5, True)  # esconder Logs para não admin
        except Exception:
            pass
        cast(Any, self.btn_add.clicked).connect(self.add)
        cast(Any, self.btn_edit.clicked).connect(self.edit)
        cast(Any, self.btn_del.clicked).connect(self.delete)
        self.refresh()

    def refresh(self) -> None:
        # Aplica filtro da barra de pesquisa, se houver texto
        try:
            term = self.search_edit.text().strip()
        except Exception:
            term = ""
        if term:
            like = f"%{term}%"
            rows = self.db.query(
                """
                SELECT * FROM customers
                WHERE name LIKE ? OR phone LIKE ? OR address LIKE ? OR observation LIKE ?
                ORDER BY name
                """,
                (like, like, like, like)
            )
        else:
            rows = self.db.query("SELECT * FROM customers ORDER BY name")
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(r["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(r["phone"] or ""))
            self.table.setItem(row, 2, QTableWidgetItem(r["address"] or ""))
            self.table.setItem(row, 3, QTableWidgetItem(r["observation"] or ""))
            self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(r["id"])))
            # botão de novo pedido
            btn_order = QPushButton(); btn_order.setObjectName("IconButton")
            btn_order.setToolTip("Criar pedido para este cliente")
            btn_order.setFlat(True)
            try:
                btn_order.setIcon(safe_qta_icon("ph.notebook", color="#8ab4ff"))
            except Exception:
                pass
            btn_order.setIconSize(QSize(18, 18))
            btn_order.setFixedSize(28, 28)
            cust_id = int(r["id"]) if r["id"] is not None else None
            cast(Any, btn_order.clicked).connect(lambda _c=False, cid=cust_id: self._start_order_for_customer(cid))
            container_order = QWidget(); lo = QHBoxLayout(container_order)
            lo.addWidget(btn_order); lo.setAlignment(Qt.AlignmentFlag.AlignCenter); lo.setContentsMargins(0,0,0,0)
            self.table.setCellWidget(row, 4, container_order)
            # Força altura mínima de 48px para o botão de pedido também
            self.table.setRowHeight(row, 48)
            # botão de logs (ícone) com container centralizado
            btn = QPushButton(); btn.setObjectName("IconButton")
            btn.setToolTip("Ver logs deste cliente")
            btn.setFlat(True)
            try:
                btn.setIcon(safe_qta_icon("ph.magnifying-glass", color="#9aa3b2"))
            except Exception:
                pass
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(28, 28)
            ent_id = int(r["id"]) if r["id"] is not None else None
            cast(Any, btn.clicked).connect(lambda _checked=False, eid=ent_id: self._show_logs("customer", eid))
            # Container para centralizar o botão
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.addWidget(btn)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 5, container)
            # Força altura mínima de 48px para garantir que ícones não sejam cortados
            self.table.setRowHeight(row, 48)
        self.table.resizeColumnsToContents()
        # Reaplica largura fixa da coluna de Logs após autoajuste
        try:
            self.table.setColumnWidth(5, 96)
        except Exception:
            pass

    def _show_logs(self, entity: str, entity_id: Optional[int]) -> None:
        dlg = LogsDialog(self.db, entity, entity_id, self)
        dlg.exec()

    def _start_order_for_customer(self, customer_id: Optional[int]) -> None:
        """Cria novo pedido com múltiplos produtos para o cliente selecionado"""
        if not customer_id:
            return
        
        # Usa o novo diálogo de múltiplos produtos
        d = MultiProductOrderDialog(self.db, self)
        
        # Pré-seleciona o cliente
        try:
            for i in range(d.customer.count()):
                if d.customer.itemData(i) == int(customer_id):
                    d.customer.setCurrentIndex(i)
                    d.customer.setEnabled(False)  # Desabilita mudança de cliente
                    break
        except Exception:
            pass
        
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

                # Cria um pedido para CADA produto (mantém compatibilidade com schema).
                # Agrupado em uma única transação: além de ficar muito mais rápido num
                # lote grande (um só commit em vez de vários por produto - sem isso a
                # janela travava numa seleção/lote grande), a transação já desfaz tudo
                # sozinha se algo falhar no meio. NÃO adicionar reversão manual aqui: já
                # tentamos isso e causava dupla-reversão (a transação desfazia o estoque
                # certo, e o código manual desfazia de novo por cima, duplicando o valor).
                pedidos_criados: list[int] = []
                try:
                    with self.db.transaction():
                        for product in order_data["products"]:
                            prod_id = product["product_id"]
                            qty = product["quantity"]
                            total = 0.0

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

                            if oid:
                                self.db.execute("UPDATE orders SET order_number=? WHERE id=?", (oid, oid))
                                pedidos_criados.append(oid)

                            # Baixa estoque APENAS se data de entrega <= hoje
                            if should_reserve_now:
                                self.db.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, prod_id))
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
                        f"Falha ao criar pedido(s) de {order_data['products'].__len__()} "
                        f"produto(s): {batch_error}\n\n"
                        f"Nenhum pedido deste lote foi salvo - a operação foi revertida.",
                        ("OK",)
                    )
                    return

                if self.dashboard_cb:
                    self.dashboard_cb()
                if self.toast_cb:
                    qtd_produtos = len(pedidos_criados)
                    self.toast_cb(f"✅ {qtd_produtos} pedido(s) criado(s) com sucesso!")

            except Exception as e:
                show_message(self, "Erro ao salvar", str(e), ("OK",))

    def current_id(self) -> Optional[int]:
        idx = self.table.currentRow()
        if idx < 0:
            return None
        vh = self.table.verticalHeaderItem(idx)
        return int(vh.text()) if vh else None

    def add(self) -> None:
        d = CustomerDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                name, phone, address, observation = d.get_values()
                if not name:
                    raise ValueError("Nome é obrigatório.")
                cur = self.db.execute(
                    "INSERT INTO customers(name, phone, address, observation) VALUES (?,?,?,?)",
                    (name, phone, address, observation)
                )
                cid_new = int(cur.lastrowid) if cur and cur.lastrowid is not None else None
                self.refresh()
                if self.toast_cb:
                    self.toast_cb("Cliente criado")
                try:
                    self.db.audit_log("customer", cid_new, "create", details=f"name={name},phone={phone}")
                except Exception:
                    pass
            except Exception as e:
                show_message(self, "Erro ao salvar", str(e), ("OK",))

    def edit(self) -> None:
        cid = self.current_id()
        if not cid:
            return
        row = self.db.query("SELECT * FROM customers WHERE id=?", (cid,))
        if not row:
            return
        d = CustomerDialog(self, row[0])
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                name, phone, address, observation = d.get_values()
                if not name:
                    raise ValueError("Nome é obrigatório.")
                self.db.execute(
                    "UPDATE customers SET name=?, phone=?, address=?, observation=? WHERE id=?",
                    (name, phone, address, observation, cid)
                )
                if self.dashboard_cb:
                    self.dashboard_cb()
                self.refresh()
                if self.toast_cb:
                    self.toast_cb("Cliente atualizado")
                try:
                    old = row[0]
                    changes: list[str] = []
                    if str(old["name"] or "") != str(name or ""):
                        changes.append(f"name: '{old['name']}' -> '{name}'")
                    if str(old["phone"] or "") != str(phone or ""):
                        changes.append(f"phone: '{old['phone'] or ''}' -> '{phone or ''}'")
                    if str(old["address"] or "") != str(address or ""):
                        changes.append(f"address: '{old['address'] or ''}' -> '{address or ''}'")
                    if str(old["observation"] or "") != str(observation or ""):
                        changes.append(f"observation: '{old['observation'] or ''}' -> '{observation or ''}'")
                    details = "; ".join(changes) if changes else None
                    self.db.audit_log("customer", cid, "update", details=details)
                except Exception:
                    pass
            except Exception as e:
                show_message(self, "Erro ao atualizar", str(e), ("OK",))

    def delete(self) -> None:
        # Antes só usava self.table.currentRow() (uma linha); selecionar vários
        # clientes e clicar Excluir apagava só o último focado.
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        cids: list[int] = []
        for index in selected_rows:
            vh = self.table.verticalHeaderItem(index.row())
            if vh:
                try:
                    cids.append(int(vh.text()))
                except (ValueError, AttributeError):
                    pass
        cids = list(dict.fromkeys(cids))
        if not cids:
            return

        count = len(cids)
        msg = "Excluir este cliente?" if count == 1 else f"Excluir {count} clientes selecionados?"
        res = show_message(self, "Confirmação", msg, ("Não", "Sim"), default=1)
        if res != 1:
            return

        deleted = 0
        blocked: list[str] = []
        # Agrupa tudo em uma única transação para não travar a janela numa seleção grande
        with self.db.transaction():
            for cid in cids:
                try:
                    # Pré-checagem: sem isso, excluir um cliente com pedidos vinculados
                    # falhava silenciosamente (IntegrityError da FK, engolido pelo except
                    # genérico abaixo) e o usuário só via "0 clientes excluídos" sem
                    # explicação nenhuma.
                    deps = self.db.query("SELECT COUNT(*) AS c FROM orders WHERE customer_id=?", (cid,))
                    if deps and deps[0]["c"] > 0:
                        name_row = self.db.query("SELECT name FROM customers WHERE id=?", (cid,))
                        blocked.append(name_row[0]["name"] if name_row else str(cid))
                        continue

                    self.db.execute("DELETE FROM customers WHERE id=?", (cid,))
                    deleted += 1
                    try:
                        self.db.audit_log("customer", cid, "delete", details=None)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Erro ao excluir cliente #{cid}: {e}")

        if self.dashboard_cb:
            self.dashboard_cb()
        self.refresh()
        if self.toast_cb:
            if deleted and not blocked:
                self.toast_cb("Cliente excluído" if deleted == 1 else f"{deleted} clientes excluídos")
            elif deleted and blocked:
                self.toast_cb(f"{deleted} excluído(s), {len(blocked)} bloqueado(s) por ter pedidos vinculados")
            elif blocked:
                self.toast_cb("Nenhum cliente excluído (todos têm pedidos vinculados)")
        if blocked:
            show_message(
                self, "Aviso",
                "Cliente(s) com pedidos vinculados não foram excluídos: " + ", ".join(blocked) +
                ". Exclua/ajuste os pedidos primeiro.",
                ("OK",)
            )
