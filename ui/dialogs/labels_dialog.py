# -*- coding: utf-8 -*-
"""Diálogo de etiquetas de pedidos."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, cast

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QColorDialog, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QInputDialog, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.database import Database
from ui.messages import show_message


class LabelsDialog(QDialog):
    """Diálogo para gerenciar etiquetas de pedidos."""
    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from core.config import load_config
        
            
        self.db = db
        self.setWindowTitle("Gerenciar Etiquetas")
        self.resize(500, 400)
        
        v = QVBoxLayout(self)
        
        # Tabela de etiquetas
        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(["Nome", "Cor"])
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        if h := self.tbl.horizontalHeader():
            h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.tbl)
        
        # Botões de ação
        h_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Adicionar")
        self.btn_edit = QPushButton("Editar")
        self.btn_del = QPushButton("Excluir")
        h_layout.addWidget(self.btn_add)
        h_layout.addWidget(self.btn_edit)
        h_layout.addWidget(self.btn_del)
        h_layout.addStretch(1)
        v.addLayout(h_layout)
        
        # Botão fechar
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cast(Any, btns.rejected).connect(self.reject)
        v.addWidget(btns)
        
        cast(Any, self.btn_add.clicked).connect(self.add)
        cast(Any, self.btn_edit.clicked).connect(self.edit)
        cast(Any, self.btn_del.clicked).connect(self.delete)
        
        self.refresh()
    
    def refresh(self) -> None:
        rows = self.db.query("SELECT id, name, color FROM labels ORDER BY name")
        self.tbl.setRowCount(0)
        for r in rows:
            row_idx = self.tbl.rowCount()
            self.tbl.insertRow(row_idx)
            self.tbl.setItem(row_idx, 0, QTableWidgetItem(str(r["name"])))
            
            # Mostra cor com um widget visual
            color_text = str(r["color"] or "#6B7280")
            color_item = QTableWidgetItem(color_text)
            color_item.setBackground(QColor(color_text))
            self.tbl.setItem(row_idx, 1, color_item)
            
            self.tbl.setVerticalHeaderItem(row_idx, QTableWidgetItem(str(r["id"])))
        self.tbl.resizeColumnsToContents()
    
    def current_id(self) -> Optional[int]:
        idx = self.tbl.currentRow()
        if idx < 0:
            return None
        vh = self.tbl.verticalHeaderItem(idx)
        return int(vh.text()) if vh else None
    
    def add(self) -> None:
        from core.config import load_config
        
        # Criar QInputDialog com estilo correto
        input_dialog = QInputDialog(self)
        input_dialog.setWindowTitle("Nova Etiqueta")
        input_dialog.setLabelText("Nome da etiqueta:")
        input_dialog.setTextValue("")
        
        
        ok = input_dialog.exec()
        name = input_dialog.textValue() if ok else ""
        
        if ok and name.strip():
            name = name.strip()
            # Verifica duplicata (case-insensitive)
            existing = self.db.query("SELECT 1 FROM labels WHERE LOWER(name)=LOWER(?)", (name,))
            if existing:
                show_message(self, "Erro", "Já existe uma etiqueta com este nome.", ("OK",))
                return
            
            # Permite escolher cor usando método estático
            initial_color = QColor("#6B7280")
            color = QColorDialog.getColor(initial_color, self, "Escolher cor da etiqueta")
            
            if color.isValid():
                color_hex = color.name()
            else:
                # Se cancelar, usa cor padrão
                color_hex = "#6B7280"
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                self.db.execute("INSERT INTO labels(name, color, created_at) VALUES (?,?,?)", (name, color_hex, now))
                self.refresh()
            except Exception as e:
                show_message(self, "Erro", f"Erro ao adicionar etiqueta: {e}", ("OK",))
    
    def edit(self) -> None:
        lid = self.current_id()
        if not lid:
            show_message(self, "Aviso", "Selecione uma etiqueta.", ("OK",))
            return
        
        row = self.db.query("SELECT * FROM labels WHERE id=?", (lid,))
        if not row:
            return
        
        old_name = str(row[0]["name"])
        old_color = str(row[0]["color"] or "#6B7280")
        
        # Pergunta o que deseja editar
        # Retorna índice: 0=Nome, 1=Cor, 2=Ambos, 3=Cancelar
        choice = show_message(
            self, 
            "Editar Etiqueta", 
            f"Etiqueta: {old_name}\n\nO que deseja editar?", 
            ("Nome", "Cor", "Ambos", "Cancelar")
        )
        
        if choice == 3 or choice is None:  # Cancelar
            return
        
        new_name = old_name
        new_color = old_color
        
        # Edita o nome se solicitado (choice 0=Nome ou 2=Ambos)
        if choice in (0, 2):
            from core.config import load_config
            
            # Criar QInputDialog com estilo correto
            input_dialog = QInputDialog(self)
            input_dialog.setWindowTitle("Editar Nome")
            input_dialog.setLabelText("Nome da etiqueta:")
            input_dialog.setTextValue(old_name)
            
            
            ok = input_dialog.exec()
            name_input = input_dialog.textValue() if ok else ""
            
            if not ok:
                return
            
            new_name = name_input.strip()
            if not new_name:
                show_message(self, "Erro", "O nome não pode estar vazio.", ("OK",))
                return
            
            if new_name != old_name:
                # Verifica duplicata (case-insensitive - "Urgente" e "urgente" não
                # podiam coexistir sem confundir o cascade de UPDATE orders abaixo)
                existing = self.db.query("SELECT 1 FROM labels WHERE LOWER(name)=LOWER(?) AND id!=?", (new_name, lid))
                if existing:
                    show_message(self, "Erro", "Já existe uma etiqueta com este nome.", ("OK",))
                    return
        
        # Edita a cor se solicitado (choice 1=Cor ou 2=Ambos)
        if choice in (1, 2):
            initial_color = QColor(old_color)
            color = QColorDialog.getColor(initial_color, self, "Escolher cor da etiqueta")
            
            if color.isValid():
                new_color = color.name()
            else:
                # Se cancelar o seletor de cor, mantém a cor antiga
                new_color = old_color
        
        try:
            self.db.execute("UPDATE labels SET name=?, color=? WHERE id=?", (new_name, new_color, lid))
            # Atualiza todos os pedidos que usam esta etiqueta (case-insensitive,
            # simétrico com a checagem de duplicata acima)
            if new_name != old_name:
                self.db.execute("UPDATE orders SET label=? WHERE LOWER(label)=LOWER(?)", (new_name, old_name))
            self.refresh()
        except Exception as e:
            show_message(self, "Erro", f"Erro ao editar etiqueta: {e}", ("OK",))
    
    def delete(self) -> None:
        lid = self.current_id()
        if not lid:
            show_message(self, "Aviso", "Selecione uma etiqueta.", ("OK",))
            return
        
        row = self.db.query("SELECT name FROM labels WHERE id=?", (lid,))
        if not row:
            return
        
        label_name = str(row[0]["name"])
        
        # Verifica se há pedidos usando esta etiqueta
        orders_count = self.db.query("SELECT COUNT(*) as c FROM orders WHERE label=?", (label_name,))
        count = int(orders_count[0]["c"]) if orders_count else 0
        
        msg = f"Excluir a etiqueta '{label_name}'?"
        if count > 0:
            msg += f"\n\n{count} pedido(s) usam esta etiqueta e serão alterados para 'Comum'."
        
        res = show_message(self, "Confirmação", msg, ("Não", "Sim"), default=1)
        if res == 1:
            try:
                # Atualiza pedidos para 'Comum'
                if count > 0:
                    self.db.execute("UPDATE orders SET label='Comum' WHERE label=?", (label_name,))
                # Exclui a etiqueta
                self.db.execute("DELETE FROM labels WHERE id=?", (lid,))
                self.refresh()
            except Exception as e:
                show_message(self, "Erro", f"Erro ao excluir: {e}", ("OK",))
