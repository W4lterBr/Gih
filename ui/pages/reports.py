# -*- coding: utf-8 -*-
"""Página de Relatórios: métricas e exportação PDF/Excel."""

from __future__ import annotations

import os
from datetime import date
from typing import Any, cast

from PyQt6.QtCore import QDate, QSize
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import Database
from core.formatting import format_date, money
from core.paths import RESOURCE_DIR
from ui.dialogs.custom_filedialog import CustomFileDialog
from ui.dialogs.user_dialogs import UsersDialog
from ui.icons import safe_qta_icon
from ui.messages import show_message
from ui.pages.base import BasePage


class ReportsPage(BasePage):
    def __init__(self, db: Database) -> None:
        super().__init__("Relatórios", "Visão geral e métricas")
        self.db = db
        bl = QVBoxLayout(self.body)

        self.lbl_sales_month: QLabel = QLabel("Vendas (mês atual): —")
        self.lbl_orders_month: QLabel = QLabel("Pedidos (mês atual): —")
        self.lbl_top_products: QLabel = QLabel("Top produtos: —")
        bl.addWidget(self.lbl_sales_month)
        bl.addWidget(self.lbl_orders_month)
        bl.addWidget(self.lbl_top_products)

        # Removidos os botões de Usuários e Exportações conforme solicitado
        
        # Inicializar abas de relatórios
        self.__init_tabs__()
    
    def showEvent(self, event) -> None:
        """Recarrega os dados quando a página é exibida"""
        super().showEvent(event)
        # Recarrega os dados sempre que a página é exibida
        try:
            self.refresh()
            self.refresh_entregas()
            self.refresh_producao()
            self.refresh_fechamento()
        except Exception:
            pass  # Ignora erros caso os widgets ainda não estejam completamente inicializados
    

    def __init_tabs__(self) -> None:
        """Inicializa as abas de relatórios"""
        # Abas de Relatórios: Entregas, Produção e Fechamento
        bl = self.body.layout() or QVBoxLayout(self.body)
        self.tabs: QTabWidget = QTabWidget()
        bl.addWidget(self.tabs)

        # Relatório de Entregas (por dia, somente 'Pago')
        self.tab_entregas = QWidget(); v1 = QVBoxLayout(self.tab_entregas)
        f1 = QHBoxLayout(); v1.addLayout(f1)
        f1.addWidget(QLabel("Dia:"))
        self.entregas_date: QDateEdit = QDateEdit(); self.entregas_date.setCalendarPopup(True)
        self.entregas_date.setDisplayFormat("dd/MM/yyyy"); self.entregas_date.setDate(QDate.currentDate())
        f1.addWidget(self.entregas_date); f1.addStretch(1)
        # Export buttons for Entregas
        self.btn_ent_pdf: QPushButton = QPushButton(); self.btn_ent_pdf.setFlat(True)
        self.btn_ent_pdf.setToolTip("Exportar Entregas (PDF)")
        try:
            self.btn_ent_pdf.setIcon(safe_qta_icon("ph.file-pdf", color="#dc2626"))
        except Exception:
            self.btn_ent_pdf.setText("PDF")
        self.btn_ent_pdf.setIconSize(QSize(18,18)); self.btn_ent_pdf.setFixedHeight(28)
        f1.addWidget(self.btn_ent_pdf)

        self.btn_ent_xlsx: QPushButton = QPushButton(); self.btn_ent_xlsx.setFlat(True)
        self.btn_ent_xlsx.setToolTip("Exportar Entregas (Excel)")
        icon = safe_qta_icon("ph.file", color="#16a34a")
        if icon and not icon.isNull():
            self.btn_ent_xlsx.setIcon(icon)
        else:
            self.btn_ent_xlsx.setText("XLSX")
        self.btn_ent_xlsx.setIconSize(QSize(18,18)); self.btn_ent_xlsx.setFixedHeight(28)
        f1.addWidget(self.btn_ent_xlsx)
        self.tbl_entregas: QTableWidget = QTableWidget(0, 5)
        self.tbl_entregas.setHorizontalHeaderLabels(["Cliente", "Quantidade", "Produto", "Endereço", "Observação"])
        self.tbl_entregas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_entregas.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        cast(Any, self.tbl_entregas.verticalHeader()).setVisible(False)
        if header := self.tbl_entregas.horizontalHeader():
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
        v1.addWidget(self.tbl_entregas)
        self.lbl_entregas_tot: QLabel = QLabel("")
        v1.addWidget(self.lbl_entregas_tot)
        cast(Any, self.entregas_date.dateChanged).connect(self.refresh_entregas)
        self.tabs.addTab(self.tab_entregas, "Relatório de Entregas")

        # Relatório de Produção (entradas e saídas)
        self.tab_prod = QWidget(); v2 = QVBoxLayout(self.tab_prod)
        f2 = QHBoxLayout(); v2.addLayout(f2)
        f2.addWidget(QLabel("Período:"))
        self.prod_from: QDateEdit = QDateEdit(); self.prod_from.setCalendarPopup(True); self.prod_from.setDisplayFormat("dd/MM/yyyy")
        today = QDate.currentDate(); first = QDate(today.year(), today.month(), 1)
        self.prod_from.setDate(first)
        f2.addWidget(self.prod_from)
        f2.addWidget(QLabel("até"))
        self.prod_to: QDateEdit = QDateEdit(); self.prod_to.setCalendarPopup(True); self.prod_to.setDisplayFormat("dd/MM/yyyy"); self.prod_to.setDate(today)
        f2.addWidget(self.prod_to); f2.addStretch(1)
        # Export buttons for Produção
        self.btn_prod_pdf: QPushButton = QPushButton(); self.btn_prod_pdf.setFlat(True)
        self.btn_prod_pdf.setToolTip("Exportar Produção (PDF)")
        icon = safe_qta_icon("ph.file-pdf", color="#dc2626")
        if icon and not icon.isNull():
            self.btn_prod_pdf.setIcon(icon)
        else:
            self.btn_prod_pdf.setText("PDF")
        self.btn_prod_pdf.setIconSize(QSize(18,18)); self.btn_prod_pdf.setFixedHeight(28)
        f2.addWidget(self.btn_prod_pdf)

        self.btn_prod_xlsx: QPushButton = QPushButton(); self.btn_prod_xlsx.setFlat(True)
        self.btn_prod_xlsx.setToolTip("Exportar Produção (Excel)")
        icon = safe_qta_icon("ph.file", color="#16a34a")
        if icon and not icon.isNull():
            self.btn_prod_xlsx.setIcon(icon)
        else:
            self.btn_prod_xlsx.setText("XLSX")
        self.btn_prod_xlsx.setIconSize(QSize(18,18)); self.btn_prod_xlsx.setFixedHeight(28)
        f2.addWidget(self.btn_prod_xlsx)
        self.tbl_prod: QTableWidget = QTableWidget(0, 5)
        self.tbl_prod.setHorizontalHeaderLabels(["Data", "Produto", "Tipo", "Quantidade", "Motivo"])
        self.tbl_prod.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_prod.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        cast(Any, self.tbl_prod.verticalHeader()).setVisible(False)
        if header2 := self.tbl_prod.horizontalHeader():
            header2.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header2.setStretchLastSection(True)
        v2.addWidget(self.tbl_prod)
        self.lbl_prod_tot: QLabel = QLabel("")
        v2.addWidget(self.lbl_prod_tot)
        cast(Any, self.prod_from.dateChanged).connect(self.refresh_producao)
        cast(Any, self.prod_to.dateChanged).connect(self.refresh_producao)
        # Wire export buttons
        cast(Any, self.btn_ent_pdf.clicked).connect(self.export_pdf)
        cast(Any, self.btn_ent_xlsx.clicked).connect(self.export_xlsx)
        cast(Any, self.btn_prod_pdf.clicked).connect(self.export_pdf)
        cast(Any, self.btn_prod_xlsx.clicked).connect(self.export_xlsx)
        self.tabs.addTab(self.tab_prod, "Relatório de Produção")

        # Relatório de Fechamento
        self.tab_fech = QWidget(); v3 = QVBoxLayout(self.tab_fech)
        f3 = QHBoxLayout(); v3.addLayout(f3)
        f3.addWidget(QLabel("Período:"))
        self.fech_from: QDateEdit = QDateEdit(); self.fech_from.setCalendarPopup(True); self.fech_from.setDisplayFormat("dd/MM/yyyy")
        self.fech_from.setDate(first)
        f3.addWidget(self.fech_from)
        f3.addWidget(QLabel("até"))
        self.fech_to: QDateEdit = QDateEdit(); self.fech_to.setCalendarPopup(True); self.fech_to.setDisplayFormat("dd/MM/yyyy"); self.fech_to.setDate(today)
        f3.addWidget(self.fech_to)
        f3.addWidget(QLabel("Etiqueta:"))
        self.fech_label_filter: QComboBox = QComboBox(); self._reload_labels_into_combo()
        f3.addWidget(self.fech_label_filter); f3.addStretch(1)
        # Botões discretos de exportação apenas nesta aba
        self.btn_fech_pdf: QPushButton = QPushButton()
        self.btn_fech_pdf.setToolTip("Exportar relatório de fechamento (PDF)")
        self.btn_fech_pdf.setFlat(True)
        icon = safe_qta_icon("ph.file-pdf", color="#dc2626")
        if icon and not icon.isNull():
            self.btn_fech_pdf.setIcon(icon)
        else:
            self.btn_fech_pdf.setText("PDF")
        self.btn_fech_pdf.setIconSize(QSize(18, 18))
        self.btn_fech_pdf.setFixedHeight(28)
        f3.addWidget(self.btn_fech_pdf)

        self.btn_fech_xlsx: QPushButton = QPushButton()
        self.btn_fech_xlsx.setToolTip("Exportar relatório de fechamento (Excel)")
        self.btn_fech_xlsx.setFlat(True)
        # Não há ícone XLSX padrão garantido; usar ícone de arquivo e cor verde
        icon = safe_qta_icon("ph.file", color="#16a34a")
        if icon and not icon.isNull():
            self.btn_fech_xlsx.setIcon(icon)
        else:
            self.btn_fech_xlsx.setText("XLSX")
        self.btn_fech_xlsx.setIconSize(QSize(18, 18))
        self.btn_fech_xlsx.setFixedHeight(28)
        f3.addWidget(self.btn_fech_xlsx)
        self.tbl_fech: QTableWidget = QTableWidget(0, 6)
        self.tbl_fech.setHorizontalHeaderLabels(["Cliente", "Etiqueta", "Produto", "Data", "Quantidade", "Valor"])
        self.tbl_fech.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_fech.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        cast(Any, self.tbl_fech.verticalHeader()).setVisible(False)
        if header3 := self.tbl_fech.horizontalHeader():
            header3.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header3.setStretchLastSection(True)
        v3.addWidget(self.tbl_fech)
        self.lbl_fech_tot: QLabel = QLabel("")
        v3.addWidget(self.lbl_fech_tot)
        cast(Any, self.fech_from.dateChanged).connect(self.refresh_fechamento)
        cast(Any, self.fech_to.dateChanged).connect(self.refresh_fechamento)
        cast(Any, self.fech_label_filter.currentIndexChanged).connect(self.refresh_fechamento)
        cast(Any, self.btn_fech_pdf.clicked).connect(self.export_pdf)
        cast(Any, self.btn_fech_xlsx.clicked).connect(self.export_xlsx)
        self.tabs.addTab(self.tab_fech, "Relatório de Fechamento")

        self.refresh()
        self.refresh_entregas()
        self.refresh_producao()
        self.refresh_fechamento()

    def _reload_labels_into_combo(self) -> None:
        self.fech_label_filter.clear()
        self.fech_label_filter.addItem("Todas")
        try:
            rows = self.db.query("SELECT name FROM labels ORDER BY name")
            for r in rows:
                self.fech_label_filter.addItem(str(r["name"]))
        except Exception:
            pass

    # ---- Exportações ----
    def export_xlsx(self) -> None:
        try:
            import openpyxl
            from openpyxl.utils import get_column_letter
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.drawing.image import Image as XLImage
        except ImportError:
            show_message(self, "Erro", "A biblioteca openpyxl não está instalada. Instale com: pip install openpyxl", ("OK",))
            return

        dlg = CustomFileDialog(self, caption="Salvar Excel", directory="", filter="Excel (*.xlsx)", save_mode=True)
        if not dlg.exec():
            return
        path = dlg.get_selected_file()
        if not path:
            return
        # Garante extensão .xlsx
        if not path.lower().endswith(".xlsx"):
            path = path + ".xlsx"

        # Coleta dataset conforme aba ativa
        title, headers, data, meta, summary = self._current_report_dataset()

        wb = openpyxl.Workbook(); ws = wb.active
        ws.title = title[:31] if title else "Relatório"

        # Logo
        try:
            logo_path = os.path.join(RESOURCE_DIR, "assets", "icons", "logo.png")
            if os.path.exists(logo_path):
                img = XLImage(logo_path)
                img.width = 120; img.height = 60
                ws.add_image(img, "A1")
        except Exception:
            pass

        # Título e meta
        start_row = 5
        ws.cell(row=start_row, column=1, value=title).font = Font(size=14, bold=True)
        ws.cell(row=start_row+1, column=1, value=meta or "").font = Font(size=10, italic=True)

        # Cabeçalho
        header_row = start_row + 3
        for c, h in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=c, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2563EB")  # azul
            cell.alignment = Alignment(horizontal="center")
            cell.border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

        # Dados
        for r_idx, rowdata in enumerate(data, start=header_row+1):
            for c, val in enumerate(rowdata, start=1):
                cell = ws.cell(row=r_idx, column=c, value=val)
                cell.alignment = Alignment(horizontal="center")
                cell.border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

        # Auto largura
        for i in range(1, len(headers)+1):
            max_length = 0
            col_letter = get_column_letter(i)
            for cell in ws[col_letter]:
                try:
                    v = "" if cell.value is None else str(cell.value)
                    if len(v) > max_length:
                        max_length = len(v)
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

        # Summary (para Fechamento)
        if summary:
            sr = ws.max_row + 2
            ws.cell(row=sr, column=1, value="Resumo por Cliente/Etiqueta").font = Font(size=12, bold=True)
            headers_s = ["Cliente", "Etiqueta", "Pedidos", "Quantidade", "Valor"]
            for c, h in enumerate(headers_s, start=1):
                cell = ws.cell(row=sr+1, column=c, value=h)
                cell.font = Font(bold=True)
            for i, s in enumerate(summary, start=sr+2):
                for c, val in enumerate(s, start=1):
                    ws.cell(row=i, column=c, value=val)

        wb.save(path)
        show_message(self, "Exportado", f"Excel salvo em:\n{path}", ("OK",))

    def export_pdf(self) -> None:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            show_message(self, "Erro", "A biblioteca reportlab não está instalada. Instale com: pip install reportlab", ("OK",))
            return

        dlg = CustomFileDialog(self, caption="Salvar PDF", directory="", filter="PDF (*.pdf)", save_mode=True)
        if not dlg.exec():
            return
        path = dlg.get_selected_file()
        if not path:
            return
        # Garante extensão .pdf
        if not path.lower().endswith(".pdf"):
            path = path + ".pdf"

        # Coleta dataset conforme aba ativa
        title, headers, data, meta, summary = self._current_report_dataset()

        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=60, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        # Logo e Título
        try:
            logo_path = os.path.join(RESOURCE_DIR, "assets", "icons", "logo.png")
            if os.path.exists(logo_path):
                im = Image(logo_path, width=80, height=40)
                story.append(im)
        except Exception:
            pass
        story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
        if meta:
            story.append(Paragraph(meta, styles["Italic"]))
        story.append(Spacer(1, 12))

        # Tabela principal
        table = Table([headers] + data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2563EB")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,0), 8),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        story.append(table)

        # Resumo para Fechamento
        if summary:
            story.append(Spacer(1, 18))
            story.append(Paragraph("<b>Resumo por Cliente/Etiqueta</b>", styles["Heading3"]))
            headers_s = ["Cliente", "Etiqueta", "Pedidos", "Quantidade", "Valor"]
            table_s = Table([headers_s] + summary, repeatRows=1)
            table_s.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F2937")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ]))
            story.append(table_s)

        doc.build(story)
        show_message(self, "Exportado", f"PDF salvo em:\n{path}", ("OK",))

    def export_csv(self) -> None:
        import csv
        dlg = CustomFileDialog(self, caption="Salvar CSV", directory="", filter="CSV (*.csv)", save_mode=True)
        if not dlg.exec():
            return
        path = dlg.get_selected_file()
        if not path:
            return
        rows = self.db.query("""
            SELECT o.id, c.name AS cliente, p.name AS produto, o.quantity, o.delivery_date, o.total, o.status, o.created_at
            FROM orders o JOIN customers c ON c.id=o.customer_id JOIN products p ON p.id=o.product_id
            ORDER BY o.created_at DESC
        """)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["ID","Cliente","Produto","Quantidade","Entrega","Total","Status","Criado em"])
            for r in rows:
                w.writerow([
                    r["id"], r["cliente"], r["produto"], r["quantity"], 
                    format_date(str(r["delivery_date"])), 
                    f"{float(r['total']):.2f}", 
                    r["status"], 
                    format_date(str(r["created_at"]).split()[0]) if r["created_at"] else ""
                ])
        show_message(self, "Exportado", f"Arquivo salvo em:\n{path}", ("OK",))

    # ---- Métricas ----
    def refresh(self) -> None:
        today = date.today()
        ym = today.strftime("%Y-%m")
        sales = self.db.query("SELECT SUM(total) AS s FROM orders WHERE substr(created_at,1,7)=?", (ym,))
        sales_val = sales[0]["s"] or 0
        self.lbl_sales_month.setText(f"Vendas (mês atual): {money(float(sales_val))}")
        orders_count = self.db.query("SELECT COUNT(*) AS c FROM orders WHERE substr(created_at,1,7)=?", (ym,))
        self.lbl_orders_month.setText(f"Pedidos (mês atual): {orders_count[0]['c']}")
        tops = self.db.query("""
            SELECT p.name, SUM(o.quantity) AS q
            FROM orders o JOIN products p ON p.id=o.product_id
            GROUP BY p.id ORDER BY q DESC LIMIT 3
        """)
        if tops:
            self.lbl_top_products.setText("Top produtos: " + ", ".join([f"{r['name']} ({r['q']})" for r in tops]))
        else:
            self.lbl_top_products.setText("Top produtos: —")

    def refresh_entregas(self) -> None:
        d = self.entregas_date.date().toString("yyyy-MM-dd")
        rows = self.db.query("""
            SELECT c.name AS cliente, o.quantity AS quantidade, p.name AS produto, c.address AS endereco, o.notes AS obs
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products  p ON p.id = o.product_id
            WHERE o.status = 'Pago' AND o.delivery_date = ?
            ORDER BY c.name
        """, (d,))
        self.tbl_entregas.setRowCount(0)
        for r in rows:
            row = self.tbl_entregas.rowCount(); self.tbl_entregas.insertRow(row)
            self.tbl_entregas.setItem(row, 0, QTableWidgetItem(str(r["cliente"])))
            self.tbl_entregas.setItem(row, 1, QTableWidgetItem(str(r["quantidade"])))
            self.tbl_entregas.setItem(row, 2, QTableWidgetItem(str(r["produto"])))
            self.tbl_entregas.setItem(row, 3, QTableWidgetItem(str(r["endereco"]) if r["endereco"] else ""))
            self.tbl_entregas.setItem(row, 4, QTableWidgetItem(str(r["obs"]) if r["obs"] else ""))
        self.tbl_entregas.resizeColumnsToContents()
        total_itens = sum(int(r["quantidade"]) for r in rows) if rows else 0
        total_pedidos = len(rows)
        self.lbl_entregas_tot.setText(f"Total itens: {total_itens} | Pedidos: {total_pedidos}")

    def refresh_producao(self) -> None:
        start = self.prod_from.date().toString("yyyy-MM-dd")
        end = self.prod_to.date().toString("yyyy-MM-dd")
        rows = self.db.query("""
            SELECT sm.created_at AS data, p.name AS produto, sm.type AS tipo, sm.quantity AS quantidade, sm.reason AS motivo
            FROM stock_movements sm
            JOIN products p ON p.id = sm.product_id
            WHERE date(sm.created_at) BETWEEN ? AND ?
            ORDER BY sm.created_at DESC
        """, (start, end))
        self.tbl_prod.setRowCount(0)
        for r in rows:
            row = self.tbl_prod.rowCount(); self.tbl_prod.insertRow(row)
            # Formata data no padrão dd/MM/yyyy
            try:
                d_iso = str(r["data"]) if r["data"] is not None else ""
                d_only = d_iso.split(" ")[0]
                d_fmt = format_date(d_only) if d_only else ""
            except Exception:
                d_fmt = str(r["data"]) if "data" in r.keys() else ""
            self.tbl_prod.setItem(row, 0, QTableWidgetItem(d_fmt))
            self.tbl_prod.setItem(row, 1, QTableWidgetItem(str(r["produto"])))
            self.tbl_prod.setItem(row, 2, QTableWidgetItem(str(r["tipo"])))
            self.tbl_prod.setItem(row, 3, QTableWidgetItem(str(r["quantidade"])))
            self.tbl_prod.setItem(row, 4, QTableWidgetItem(str(r["motivo"]) if r["motivo"] else ""))
        self.tbl_prod.resizeColumnsToContents()
        entradas = sum(int(r["quantidade"]) for r in rows if str(r["tipo"]).lower() == 'entrada')
        saidas = sum(int(r["quantidade"]) for r in rows if str(r["tipo"]).lower() == 'saida')
        saldo = entradas - saidas
        self.lbl_prod_tot.setText(f"Entradas: {entradas} | Saídas: {saidas} | Saldo: {saldo}")

    def refresh_fechamento(self) -> None:
        start = self.fech_from.date().toString("yyyy-MM-dd")
        end = self.fech_to.date().toString("yyyy-MM-dd")
        params: list[Any] = [start, end]
        sql = (
            "SELECT c.name AS cliente, 'Comum' AS etiqueta, "
            "p.name AS produto, date(o.created_at) AS data, o.quantity AS quantidade, o.total AS valor "
            "FROM orders o JOIN customers c ON c.id=o.customer_id JOIN products p ON p.id=o.product_id "
            "WHERE date(o.created_at) BETWEEN ? AND ?"
        )
        sql += " ORDER BY c.name, etiqueta, data"
        rows = self.db.query(sql, tuple(params))
        
        # Agrupa pedidos: se mesmo cliente, mesma etiqueta e mesmo produto, soma quantidade e valor
        from collections import defaultdict
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}  # (cliente, etiqueta, produto) -> dados agregados
        
        for r in rows:
            cliente = str(r["cliente"])
            etiqueta = str(r["etiqueta"])
            produto = str(r["produto"])
            key = (cliente, etiqueta, produto)
            
            if key not in grouped:
                grouped[key] = {
                    "cliente": cliente,
                    "etiqueta": etiqueta,
                    "produto": produto,
                    "data": str(r["data"]) if r["data"] is not None else "",
                    "quantidade": 0,
                    "valor": 0.0
                }
            
            grouped[key]["quantidade"] += int(r["quantidade"] or 0)
            grouped[key]["valor"] += float(r["valor"] or 0.0)
        
        # Popula a tabela com dados agrupados
        self.tbl_fech.setRowCount(0)
        total_pedidos = 0; total_qtd = 0; total_val = 0.0
        
        for key in sorted(grouped.keys()):  # Ordena por (cliente, etiqueta, produto)
            item = grouped[key]
            row = self.tbl_fech.rowCount(); self.tbl_fech.insertRow(row)
            self.tbl_fech.setItem(row, 0, QTableWidgetItem(item["cliente"]))
            self.tbl_fech.setItem(row, 1, QTableWidgetItem(item["etiqueta"]))
            self.tbl_fech.setItem(row, 2, QTableWidgetItem(item["produto"]))
            
            # Formata data
            try:
                d_iso = item["data"]
                d_fmt = format_date(d_iso) if d_iso else ""
            except Exception:
                d_fmt = item["data"]
            self.tbl_fech.setItem(row, 3, QTableWidgetItem(d_fmt))
            self.tbl_fech.setItem(row, 4, QTableWidgetItem(str(item["quantidade"])))
            self.tbl_fech.setItem(row, 5, QTableWidgetItem(money(item["valor"])))
            
            total_pedidos += 1
            total_qtd += item["quantidade"]
            total_val += item["valor"]
            
        self.tbl_fech.resizeColumnsToContents()
        
        # Conta clientes únicos
        unique_clients = len({item["cliente"] for item in grouped.values()})
        
        self.lbl_fech_tot.setText(
            f"Clientes: {unique_clients} | Pedidos: {total_pedidos} | "
            f"Quantidade: {total_qtd} | Valor: {money(total_val)}"
        )

    def _current_report_dataset(self) -> tuple[str, list[str], list[list[Any]], str, list[list[Any]] | None]:
        """Retorna (title, headers, data, meta, summary) para a aba ativa."""
        idx = self.tabs.currentIndex()
        # Entregas
        if idx == self.tabs.indexOf(self.tab_entregas):
            d = self.entregas_date.date().toString("yyyy-MM-dd")
            title = "Relatório de Entregas"
            headers = ["Cliente", "Quantidade", "Produto", "Endereço", "Observação"]
            data: list[list[Any]] = []
            for i in range(self.tbl_entregas.rowCount()):
                data.append([
                    self.tbl_entregas.item(i,0).text() if self.tbl_entregas.item(i,0) else "",
                    self.tbl_entregas.item(i,1).text() if self.tbl_entregas.item(i,1) else "",
                    self.tbl_entregas.item(i,2).text() if self.tbl_entregas.item(i,2) else "",
                    self.tbl_entregas.item(i,3).text() if self.tbl_entregas.item(i,3) else "",
                    self.tbl_entregas.item(i,4).text() if self.tbl_entregas.item(i,4) else "",
                ])
            meta = f"Dia: {format_date(d)} | Status: Pago"
            return (title, headers, data, meta, None)
        # Produção
        if idx == self.tabs.indexOf(self.tab_prod):
            title = "Relatório de Produção"
            headers = ["Data", "Produto", "Tipo", "Quantidade", "Motivo"]
            data: list[list[Any]] = []
            for i in range(self.tbl_prod.rowCount()):
                data.append([
                    self.tbl_prod.item(i,0).text() if self.tbl_prod.item(i,0) else "",
                    self.tbl_prod.item(i,1).text() if self.tbl_prod.item(i,1) else "",
                    self.tbl_prod.item(i,2).text() if self.tbl_prod.item(i,2) else "",
                    self.tbl_prod.item(i,3).text() if self.tbl_prod.item(i,3) else "",
                    self.tbl_prod.item(i,4).text() if self.tbl_prod.item(i,4) else "",
                ])
            meta = f"Período: {self.prod_from.date().toString('dd/MM/yyyy')} a {self.prod_to.date().toString('dd/MM/yyyy')}"
            return (title, headers, data, meta, None)
        # Fechamento
        title = "Relatório de Fechamento"
        headers = ["Cliente", "Etiqueta", "Produto", "Data", "Quantidade", "Valor"]
        data: list[list[Any]] = []
        for i in range(self.tbl_fech.rowCount()):
            data.append([
                self.tbl_fech.item(i,0).text() if self.tbl_fech.item(i,0) else "",
                self.tbl_fech.item(i,1).text() if self.tbl_fech.item(i,1) else "",
                self.tbl_fech.item(i,2).text() if self.tbl_fech.item(i,2) else "",
                self.tbl_fech.item(i,3).text() if self.tbl_fech.item(i,3) else "",
                self.tbl_fech.item(i,4).text() if self.tbl_fech.item(i,4) else "",
                self.tbl_fech.item(i,5).text() if self.tbl_fech.item(i,5) else "",
            ])
        meta = (
            f"Período: {self.fech_from.date().toString('dd/MM/yyyy')} a {self.fech_to.date().toString('dd/MM/yyyy')}" 
            f" | Etiqueta: {self.fech_label_filter.currentText()}"
        )
        # Summary group by cliente/etiqueta
        summary: dict[tuple[str,str], dict[str, Any]] = {}
        for row in data:
            cliente, etiqueta, _, _, qtd, val = row
            key = (cliente, etiqueta)
            if key not in summary:
                summary[key] = {"pedidos": 0, "qtd": 0, "valor": 0.0}
            summary[key]["pedidos"] += 1
            try:
                summary[key]["qtd"] += int(str(qtd).split()[0]) if str(qtd).strip() else 0
            except Exception:
                pass
            try:
                # valor vem formatado (R$ xx,xx) -> normaliza
                v = str(val).replace("R$", "").strip().replace(".", "").replace(",", ".")
                summary[key]["valor"] += float(v) if v else 0.0
            except Exception:
                pass
        summary_rows: list[list[Any]] = []
        for (cli, eti), agg in sorted(summary.items()):
            summary_rows.append([cli, eti, agg["pedidos"], agg["qtd"], f"R$ {agg['valor']:.2f}".replace('.',',')])
        return (title, headers, data, meta, summary_rows)

    def show_users(self) -> None:
        """Abre o diálogo de gerenciamento de usuários (visibilidade já controlada externamente)."""
        try:
            dlg = UsersDialog(self.db, self)
            dlg.exec()
        except Exception:
            pass
