# -*- coding: utf-8 -*-
"""Gráficos do Dashboard (QtCharts), com cores que acompanham o tema."""

from __future__ import annotations

from typing import Optional, Sequence

from PyQt6.QtCharts import (
    QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QPieSeries, QValueAxis,
)
from PyQt6.QtCore import QMargins, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QLabel, QStackedLayout, QWidget

from ui.theme.qss import Palette


class _ChartCard(QWidget):
    """Área do gráfico com mensagem de "sem dados" quando não há o que mostrar."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.chart = QChart()
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(0, 0, 0, 0))
        self.chart.layout().setContentsMargins(0, 0, 0, 0)
        self.chart.legend().setVisible(False)
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.view = QChartView(self.chart)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setStyleSheet("background: transparent; border: none;")
        self.empty = QLabel()
        self.empty.setObjectName("subtitle")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack = QStackedLayout(self)
        self.stack.addWidget(self.view)
        self.stack.addWidget(self.empty)

    def show_empty(self, text: str) -> None:
        self.empty.setText(text)
        self.stack.setCurrentWidget(self.empty)

    def _show_chart(self) -> None:
        self.stack.setCurrentWidget(self.view)


class BarChart(_ChartCard):
    """Barras verticais (ex.: vendas por mês)."""

    def set_data(self, labels: Sequence[str], values: Sequence[float], pal: Palette,
                 value_fmt=lambda v: f"{v:,.0f}") -> None:
        self.chart.removeAllSeries()
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        if not values:
            self.show_empty("Sem dados de vendas no período")
            return

        bar_set = QBarSet("Vendas")
        bar_set.append([float(round(v)) for v in values])
        bar_set.setColor(QColor(pal.accent))
        bar_set.setBorderColor(QColor(pal.accent))
        series = QBarSeries()
        series.setBarWidth(0.55)
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)
        series.setLabelsFormat("@value")
        bar_set.setLabelColor(QColor(pal.muted))
        bar_set.setLabelFont(QFont("Segoe UI", 8))
        self.chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(list(labels))
        axis_y = QValueAxis()
        axis_y.setRange(0, max(values) * 1.2 or 1)
        axis_y.setLabelFormat("%.0f")
        axis_y.setTickCount(4)
        font = QFont("Segoe UI", 9)
        for axis in (axis_x, axis_y):
            axis.setLabelsColor(QColor(pal.muted))
            axis.setLabelsFont(font)
            axis.setLinePenColor(QColor(pal.border))
            axis.setGridLineColor(QColor(pal.border))
        axis_x.setGridLineVisible(False)
        axis_y.setLineVisible(False)
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        self._show_chart()


class DonutChart(_ChartCard):
    """Rosca com legenda à direita (ex.: pedidos por status)."""

    def set_data(self, items: Sequence[tuple[str, float, str]], pal: Palette) -> None:
        """items: (rótulo, valor, cor)."""
        self.chart.removeAllSeries()
        total = sum(v for _, v, _ in items)
        if not items or total <= 0:
            self.show_empty("Sem pedidos cadastrados")
            return
        series = QPieSeries()
        series.setHoleSize(0.58)
        series.setPieSize(0.88)
        for label, value, color in items:
            pct = value / total * 100
            sl = series.append(f"{label}  {int(value)} ({pct:.0f}%)", float(value))
            sl.setColor(QColor(color))
            sl.setBorderColor(QColor(pal.surface))
            sl.setBorderWidth(2)
        self.chart.addSeries(series)
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignRight)
        legend.setLabelColor(QColor(pal.text))
        legend.setFont(QFont("Segoe UI", 9))
        self._show_chart()
