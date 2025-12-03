# dashboard.py
# Dashboard com gráficos e KPIs

from typing import Any, List, cast
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import Qt
from core.database import Database

class Dashboard(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db: Database = db
        self.db = db
        layout = QVBoxLayout(self)

        # KPIs
        kpi_layout = QHBoxLayout()
        self.lbl_kpi_sales = QLabel("Vendas do mês: —")
        self.lbl_kpi_orders = QLabel("Pedidos do mês: —")
        self.lbl_kpi_alert = QLabel("<span style='color:#fbbf24'>Estoque baixo: —</span>")
        kpi_layout.addWidget(self.lbl_kpi_sales)
        kpi_layout.addWidget(self.lbl_kpi_orders)
        kpi_layout.addWidget(self.lbl_kpi_alert)
        layout.addLayout(kpi_layout)

        # Gráfico de vendas por produto
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.chart_view)

        self.refresh()

    def refresh(self):
        from datetime import date
        today = date.today()
        ym = today.strftime("%Y-%m")
        sales = cast(List[Any], self.db.query(
            "SELECT SUM(total) AS s FROM orders WHERE substr(created_at,1,7)=? AND status = ?",
            (ym, "Pago")
        ))
        sales_val = cast(float, sales[0]["s"]) if sales[0]["s"] is not None else 0
        self.lbl_kpi_sales.setText(f"Vendas do mês: R$ {sales_val:,.2f}".replace(",","X").replace(".",",").replace("X","."))
        orders_count = cast(List[Any], self.db.query(
            "SELECT COUNT(*) AS c FROM orders WHERE substr(created_at,1,7)=? AND status = ?",
            (ym, "Pago")
        ))
        self.lbl_kpi_orders.setText(f"Pedidos do mês: {orders_count[0]['c']}")
        # Alerta de estoque baixo
        low = cast(List[Any], self.db.query("SELECT name, stock FROM products WHERE stock <= min_stock AND min_stock > 0 ORDER BY name"))
        if low:
            names = ", ".join([f"{r['name']}({r['stock']})" for r in low])
            self.lbl_kpi_alert.setText(f"<span style='color:#fbbf24'>Estoque baixo: {names}</span>")
        else:
            self.lbl_kpi_alert.setText("<span style='color:#22c55e'>Estoque OK</span>")
        # Gr�fico de vendas por produto (Top 5 por faturamento, apenas "Pago" no m�s atual)
        tops = cast(List[Any], self.db.query(
            """
            SELECT p.name, SUM(o.total) AS v
            FROM orders o JOIN products p ON p.id=o.product_id
            WHERE substr(o.created_at,1,7)=? AND o.status = ?
            GROUP BY p.id ORDER BY v DESC LIMIT 5
            """,
            (ym, "Pago")
        ))
        barset = QBarSet("Vendas")
        categories: List[str] = []
        for r in tops:
            _ = barset << float(r["v"])  # Faturamento por produto
            categories.append(str(r["name"]))
        series = QBarSeries()
        cast(Any, series).append(barset)
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Produtos com maior faturamento (R$)")
        axisX = QBarCategoryAxis()
        cast(Any, axisX).append(categories)
        axisY = QValueAxis()
        axisY.setLabelFormat("R$ %.0f")
        chart.addAxis(axisX, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axisY, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axisX)
        series.attachAxis(axisY)
        self.chart_view.setChart(chart)

