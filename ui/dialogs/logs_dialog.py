# -*- coding: utf-8 -*-
"""Diálogo de visualização dos logs de ações."""

from __future__ import annotations

from typing import Any, Optional, cast

from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import Database
from core.formatting import format_datetime


class LogsDialog(QDialog):
    """Dialog simples para visualizar audit_logs por entidade/id."""
    def __init__(self, db: Database, entity: str, entity_id: Optional[int], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Aplica estilo escuro apenas se o tema ativo for escuro
        try:
            from core.config import apply_dark_popup_style
            apply_dark_popup_style(self)
        except Exception:
            pass
        self.setWindowTitle(f"Logs - {entity} #{entity_id}")
        self.resize(700, 400)
        self.db = db
        v = QVBoxLayout(self)
        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["Data", "Usuário", "Ação", "Detalhes"])
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        if h := self.tbl.horizontalHeader():
            h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            h.setStretchLastSection(True)
        v.addWidget(self.tbl)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cast(Any, btns.rejected).connect(self.reject)
        cast(Any, btns.accepted).connect(self.accept)
        v.addWidget(btns)

        rows = self.db.query("SELECT created_at, user, action, details FROM audit_logs WHERE entity=? AND entity_id=? ORDER BY created_at DESC", (entity, entity_id))
        if not rows:
            self.tbl.setRowCount(0)
            # mostra mensagem simples
            self.tbl.insertRow(0)
            self.tbl.setItem(0, 0, QTableWidgetItem("—"))
            self.tbl.setItem(0, 1, QTableWidgetItem("—"))
            self.tbl.setItem(0, 2, QTableWidgetItem("—"))
            self.tbl.setItem(0, 3, QTableWidgetItem("Nenhum log encontrado."))
        else:
            for r in rows:
                row = self.tbl.rowCount(); self.tbl.insertRow(row)
                # Formata data/hora no padrão brasileiro (DD/MM/AAAA HH:MM)
                self.tbl.setItem(row, 0, QTableWidgetItem(format_datetime(str(r["created_at"]))))
                self.tbl.setItem(row, 1, QTableWidgetItem(str(r["user"] or "")))
                self.tbl.setItem(row, 2, QTableWidgetItem(str(r["action"])))
                details_raw = str(r["details"] or "")
                # Se for update, esperamos um resumo com '; ' separando mudanças — mostra em linhas separadas
                if str(r["action"]).lower() == "update" and details_raw:
                    details_text = details_raw.replace("; ", "\n")
                else:
                    details_text = details_raw
                item = QTableWidgetItem(details_text)
                item.setToolTip(details_raw)
                self.tbl.setItem(row, 3, item)
        self.tbl.resizeColumnsToContents()
