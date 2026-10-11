# -*- coding: utf-8 -*-
"""Página de Produtos: cadastro, preços e alerta de estoque baixo."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional, cast

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import Database
from core.formatting import format_price_br, format_size
from ui.dialogs.logs_dialog import LogsDialog
from ui.dialogs.product_dialog import ProductDialog
from ui.icons import safe_qta_icon
from ui.messages import show_message
from ui.pages.base import BasePage


class ProductsPage(BasePage):
    def __init__(self, db: Database, toast_cb: Optional[Callable[[str], None]] = None) -> None:
        super().__init__("Produtos", "Gerencie o catálogo")
        self.toast_cb = toast_cb
        self.db = db
        bl = QVBoxLayout(self.body)
        
        actions = QHBoxLayout()
        self.btn_add: QPushButton = QPushButton("+ Novo")
        self.btn_add.setProperty("primary", True)
        self.btn_del: QPushButton = QPushButton("Excluir")
        self.btn_edit: QPushButton = QPushButton("Editar")
        actions.addWidget(self.btn_add); actions.addWidget(self.btn_edit); actions.addWidget(self.btn_del); actions.addStretch(1)
        bl.addLayout(actions)
        # Barra de pesquisa (nome/descrição)
        search_box = QHBoxLayout()
        search_box.addWidget(QLabel("Pesquisar:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nome ou descrição…")
        self.search_edit.setClearButtonEnabled(True)
        cast(Any, self.search_edit.textChanged).connect(lambda _t: self.refresh())
        btn_clear = QPushButton("Limpar")
        cast(Any, btn_clear.clicked).connect(lambda: self.search_edit.clear())
        search_box.addWidget(self.search_edit, 1)
        search_box.addWidget(btn_clear)
        bl.addLayout(search_box)
        # adiciona coluna extra para o botão de visualização de logs
        self.table: QTableWidget = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nome", "Descrição", "Tamanho", "Preço", "Estoque", "Logs"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            # não esticar a última coluna; manter Logs compacto
            header.setStretchLastSection(False)
            # fixa largura da coluna Logs para manter alinhamento consistente
            try:
                logs_col = 5
                header.setSectionResizeMode(logs_col, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(logs_col, 96)
                # Centraliza o título
                item = self.table.horizontalHeaderItem(logs_col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
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
                self.table.setColumnHidden(4, True)
        except Exception:
            pass
        cast(Any, self.btn_add.clicked).connect(self.add)
        cast(Any, self.btn_edit.clicked).connect(self.edit)
        cast(Any, self.btn_del.clicked).connect(self.delete)
        self.refresh()
        self._warn_low_stock()
        
        # Atualiza a cada 5s enquanto visível (estoque pode mudar pelo painel da cozinha)
        self.start_auto_refresh(self.refresh, 5000)

    def _warn_low_stock(self) -> None:
        # Avisa sobre produtos com estoque baixo
        rows = self.db.query("SELECT name, stock, min_stock FROM products WHERE stock <= min_stock AND min_stock > 0 ORDER BY name")
        if rows and self.toast_cb:
            names = ", ".join([f"{r['name']}({r['stock']})" for r in rows])
            self.toast_cb(f"⚠️ Estoque baixo: {names}")

    def refresh(self) -> None:
        # Filtro por texto (nome/descrição)
        try:
            term = self.search_edit.text().strip()
        except Exception:
            term = ""
        if term:
            like = f"%{term}%"
            rows = self.db.query(
                "SELECT * FROM products WHERE name LIKE ? OR description LIKE ? ORDER BY name",
                (like, like)
            )
        else:
            rows = self.db.query("SELECT * FROM products ORDER BY name")
        if not self.rows_changed("table", rows):
            return  # nada mudou: mantém a tabela (rolagem e seleção)
        self.table.setRowCount(0)
        
        for r in rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(r["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(r["description"] or ""))
            self.table.setItem(row, 2, QTableWidgetItem(format_size(r["size"])))
            # Preço formatado no padrão brasileiro
            try:
                price_value = float(r["price"]) if r["price"] is not None else 0.0
            except (KeyError, TypeError, ValueError):
                price_value = 0.0
            price_item = QTableWidgetItem(format_price_br(price_value))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, price_item)
            self.table.setItem(row, 4, QTableWidgetItem(str(r["stock"])))
            self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(r["id"])))
            
            # botão de logs (ícone) com container centralizado - coluna 5
            btn = QPushButton(); btn.setObjectName("IconButton")
            btn.setToolTip("Ver logs deste produto")
            btn.setFlat(True)
            try:
                btn.setIcon(safe_qta_icon("ph.magnifying-glass", color="#9aa3b2"))
            except Exception:
                pass
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(28, 28)
            ent_id = int(r["id"]) if r["id"] is not None else None
            cast(Any, btn.clicked).connect(lambda _checked=False, eid=ent_id: self._show_logs("product", eid))
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
        # Reaplica largura fixa da coluna Logs após autoajuste
        try:
            self.table.setColumnWidth(5, 96)
        except Exception:
            pass

    def current_id(self) -> Optional[int]:
        idx = self.table.currentRow()
        if idx < 0:
            return None
        vh = self.table.verticalHeaderItem(idx)
        return int(vh.text()) if vh else None
    
    def _show_logs(self, entity: str, entity_id: Optional[int]) -> None:
        dlg = LogsDialog(self.db, entity, entity_id, self)
        dlg.exec()

    def add(self) -> None:
        d = ProductDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                name, desc, size, stock, min_stock, price = d.get_values()
                if not name:
                    raise ValueError("Nome é obrigatório.")
                
                # Verifica se tem múltiplos tamanhos separados por vírgula
                sizes = [s.strip() for s in size.split(",") if s.strip()] if size else []
                
                if len(sizes) > 1:
                    # Criar um produto para cada tamanho
                    created_count = 0
                    for sz in sizes:
                        product_name = f"{name} {sz}cm"
                        cur = self.db.execute(
                            "INSERT INTO products(name, description, size, stock, min_stock, price) VALUES (?,?,?,?,?,?)",
                            (product_name, desc, sz, stock, min_stock, price)
                        )
                        pid_new = int(cur.lastrowid) if cur and cur.lastrowid is not None else None
                        if pid_new and stock and int(stock) > 0:
                            self.db.execute(
                                "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                                (pid_new, 'entrada', int(stock), 'Cadastro inicial', None, datetime.now().strftime("%Y-%m-%d %H:%M"))
                            )
                        try:
                            self.db.audit_log("product", pid_new, "create", details=f"name={product_name},stock={stock},price={price}")
                        except Exception:
                            pass
                        created_count += 1
                    
                    self.refresh()
                    if self.toast_cb:
                        self.toast_cb(f"{created_count} produtos criados com sucesso")
                    self._warn_low_stock()
                else:
                    # Criar apenas um produto (comportamento normal)
                    cur = self.db.execute(
                        "INSERT INTO products(name, description, size, stock, min_stock, price) VALUES (?,?,?,?,?,?)",
                        (name, desc, size, stock, min_stock, price)
                    )
                    pid_new = int(cur.lastrowid) if cur and cur.lastrowid is not None else None
                    if pid_new and stock and int(stock) > 0:
                        self.db.execute(
                            "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                            (pid_new, 'entrada', int(stock), 'Cadastro inicial', None, datetime.now().strftime("%Y-%m-%d %H:%M"))
                        )
                    self.refresh()
                    if self.toast_cb:
                        self.toast_cb("Produto criado com sucesso")
                    self._warn_low_stock()
                    try:
                        self.db.audit_log("product", pid_new, "create", details=f"name={name},stock={stock}")
                    except Exception:
                        pass
            except Exception as e:
                show_message(self, "Erro ao salvar", str(e), ("OK",))

    def edit(self) -> None:
        pid = self.current_id()
        if not pid:
            return
        row = self.db.query("SELECT * FROM products WHERE id=?", (pid,))
        if not row:
            return
        d = ProductDialog(self, row[0])
        if d.exec() == QDialog.DialogCode.Accepted:
            try:
                name, desc, size, stock, min_stock, price = d.get_values()
                if not name:
                    raise ValueError("Nome é obrigatório.")
                
                # Verifica se tem múltiplos tamanhos separados por vírgula
                sizes = [s.strip() for s in size.split(",") if s.strip()] if size else []
                
                old_stock_before_edit = int(row[0]["stock"] or 0)

                if len(sizes) > 1:
                    # Atualiza o produto atual com o primeiro tamanho
                    first_size = sizes[0]
                    product_name = f"{name} {first_size}cm"
                    self.db.execute(
                        "UPDATE products SET name=?, description=?, size=?, stock=?, min_stock=?, price=? WHERE id=?",
                        (product_name, desc, first_size, stock, min_stock, price, pid)
                    )
                    # Registra o ajuste de estoque deste produto em Movimentação - antes
                    # editar o produto mudava products.stock sem deixar rastro nenhum,
                    # diferente de add()/produção, que sempre registram.
                    stock_delta = int(stock) - old_stock_before_edit
                    if stock_delta != 0:
                        self.db.execute(
                            "INSERT INTO stock_movements(product_id, type, category, quantity, reason, order_id, created_at, created_by) VALUES (?,?,?,?,?,?,?,?)",
                            (pid, 'entrada' if stock_delta > 0 else 'saida', 'Ajuste de Inventário', abs(stock_delta),
                             'Edição de produto', None, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), getattr(self.db, "current_user", None) or "unknown")
                        )

                    # Cria novos produtos para os tamanhos restantes
                    created_count = 0
                    for sz in sizes[1:]:
                        new_product_name = f"{name} {sz}cm"
                        cur = self.db.execute(
                            "INSERT INTO products(name, description, size, stock, min_stock, price) VALUES (?,?,?,?,?,?)",
                            (new_product_name, desc, sz, stock, min_stock, price)
                        )
                        new_pid = int(cur.lastrowid) if cur and cur.lastrowid is not None else None
                        if new_pid and stock and int(stock) > 0:
                            self.db.execute(
                                "INSERT INTO stock_movements(product_id, type, quantity, reason, order_id, created_at) VALUES (?,?,?,?,?,?)",
                                (new_pid, 'entrada', int(stock), 'Cadastro inicial', None, datetime.now().strftime("%Y-%m-%d %H:%M"))
                            )
                        try:
                            self.db.audit_log("product", new_pid, "create", details=f"name={new_product_name},stock={stock},price={price}")
                        except Exception:
                            pass
                        created_count += 1
                    
                    self.refresh()
                    self._warn_low_stock()
                    if self.toast_cb:
                        self.toast_cb(f"Produto atualizado e {created_count} novo(s) produto(s) criado(s)")
                else:
                    # Comportamento normal - apenas atualiza
                    self.db.execute(
                        "UPDATE products SET name=?, description=?, size=?, stock=?, min_stock=?, price=? WHERE id=?",
                        (name, desc, size, stock, min_stock, price, pid)
                    )
                    stock_delta = int(stock) - old_stock_before_edit
                    if stock_delta != 0:
                        self.db.execute(
                            "INSERT INTO stock_movements(product_id, type, category, quantity, reason, order_id, created_at, created_by) VALUES (?,?,?,?,?,?,?,?)",
                            (pid, 'entrada' if stock_delta > 0 else 'saida', 'Ajuste de Inventário', abs(stock_delta),
                             'Edição de produto', None, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), getattr(self.db, "current_user", None) or "unknown")
                        )
                    self.refresh()
                    self._warn_low_stock()
                    if self.toast_cb:
                        self.toast_cb("Produto atualizado")
                try:
                    old = row[0]
                    changes: list[str] = []
                    if str(old["name"] or "") != str(name or ""):
                        changes.append(f"name: '{old['name']}' -> '{name}'")
                    if str(old["description"] or "") != str(desc or ""):
                        changes.append(f"description: '{old['description'] or ''}' -> '{desc or ''}'")
                    try:
                        old_stock = int(old["stock"] or 0)
                    except Exception:
                        old_stock = 0
                    if int(stock) != old_stock:
                        changes.append(f"stock: {old_stock} -> {stock}")
                    try:
                        old_min = int(old["min_stock"] or 0)
                    except Exception:
                        old_min = 0
                    if int(min_stock) != old_min:
                        changes.append(f"min_stock: {old_min} -> {min_stock}")
                    details = "; ".join(changes) if changes else None
                    self.db.audit_log("product", pid, "update", details=details)
                except Exception:
                    pass
            except Exception as e:
                show_message(self, "Erro ao atualizar", str(e), ("OK",))

    def delete(self) -> None:
        # Antes só considerava self.table.currentRow() (uma linha), então selecionar
        # vários produtos e clicar Excluir apagava só o último focado. Agora pega
        # todas as linhas selecionadas via selectionModel().
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        pids: list[int] = []
        for index in selected_rows:
            vh = self.table.verticalHeaderItem(index.row())
            if vh:
                try:
                    pids.append(int(vh.text()))
                except (ValueError, AttributeError):
                    pass
        pids = list(dict.fromkeys(pids))
        if not pids:
            return

        count = len(pids)
        msg = "Excluir este produto?" if count == 1 else f"Excluir {count} produtos selecionados?"
        res = show_message(self, "Confirmação", msg, ("Não", "Sim"), default=1)
        if res != 1:
            return

        deleted = 0
        blocked: list[str] = []
        # Agrupa tudo em uma única transação: sem isso, excluir muitos produtos fazia
        # 3+ commits síncronos por produto (centenas/milhares no total) e travava a
        # janela por vários segundos numa seleção grande.
        with self.db.transaction():
            for pid in pids:
                try:
                    deps = self.db.query("SELECT COUNT(*) AS c FROM orders WHERE product_id=?", (pid,))
                    if deps and deps[0]["c"] > 0:
                        name_row = self.db.query("SELECT name FROM products WHERE id=?", (pid,))
                        blocked.append(name_row[0]["name"] if name_row else str(pid))
                        continue

                    # Deleta registros relacionados antes de deletar o produto
                    self.db.execute("DELETE FROM stock_movements WHERE product_id=?", (pid,))
                    self.db.execute("DELETE FROM production_items WHERE product_id=?", (pid,))
                    self.db.execute("DELETE FROM products WHERE id=?", (pid,))
                    deleted += 1
                    try:
                        self.db.audit_log("product", pid, "delete", details=None)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Erro ao excluir produto #{pid}: {e}")

        self.refresh()
        self._warn_low_stock()
        if self.toast_cb:
            if deleted and not blocked:
                self.toast_cb("Produto excluído" if deleted == 1 else f"{deleted} produtos excluídos")
            elif deleted and blocked:
                self.toast_cb(f"{deleted} excluído(s), {len(blocked)} bloqueado(s) por ter pedidos vinculados")
            elif blocked:
                self.toast_cb("Nenhum produto excluído (todos têm pedidos vinculados)")
        if blocked:
            show_message(
                self, "Aviso",
                "Produto(s) com pedidos vinculados não foram excluídos: " + ", ".join(blocked) +
                ". Exclua/ajuste os pedidos primeiro.",
                ("OK",)
            )
