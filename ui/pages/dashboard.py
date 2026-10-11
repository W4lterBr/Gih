# -*- coding: utf-8 -*-
"""Dashboard: indicadores e gráficos de vendas."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QHeaderView, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.database import Database
from core.formatting import format_price_br
from ui.pages.base import BasePage
from ui.theme.qss import current_theme, on_theme_changed, palette
from ui.widgets.charts import BarChart, DonutChart
from ui.widgets.stat_card import StatCard


class DashboardPage(BasePage):
    """Dashboard com gráficos de vendas e produção"""
    def __init__(self, db: Database, toast_cb: Optional[Callable[[str], None]] = None) -> None:
        super().__init__("Dashboard", "Visão geral de vendas e produção")
        self.db = db
        self.toast_cb = toast_cb
        
        # Layout principal
        # Conteúdo rolável: em telas baixas (notebooks 1366x768) nada fica cortado
        outer = QVBoxLayout(self.body)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(4, 4, 8, 4)
        
        # === Cards com resumo de estatísticas ===
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)
        
        # Card: Total de Vendas
        self.card_vendas = StatCard("Total de vendas", "R$ 0,00", "#8b5cf6", "ph.currency-circle-dollar")
        cards_layout.addWidget(self.card_vendas)
        
        # Card: Pedidos em Produção
        self.card_producao = StatCard("Em produção", "0", "#f59e0b", "ph.cooking-pot")
        cards_layout.addWidget(self.card_producao)
        
        # Card: Pedidos Prontos
        self.card_prontos = StatCard("Prontos", "0", "#10b981", "ph.check-circle")
        cards_layout.addWidget(self.card_prontos)
        
        # Card: Total de Clientes
        self.card_clientes = StatCard("Clientes", "0", "#3b82f6", "ph.users-three")
        cards_layout.addWidget(self.card_clientes)
        
        main_layout.addLayout(cards_layout)
        
        # === Gráficos ===
        graficos_layout = QHBoxLayout()
        graficos_layout.setSpacing(12)
        
        # Gráfico 1: Vendas por Mês (Barras)
        vendas_group = QGroupBox("Vendas dos Últimos 6 Meses")
        vendas_layout = QVBoxLayout(vendas_group)
        self.chart_vendas = BarChart()
        vendas_layout.addWidget(self.chart_vendas)
        graficos_layout.addWidget(vendas_group, 3)
        
        # Gráfico 2: Status dos Pedidos (Pizza)
        status_group = QGroupBox("Status dos Pedidos")
        status_layout = QVBoxLayout(status_group)
        self.chart_status = DonutChart()
        status_layout.addWidget(self.chart_status)
        graficos_layout.addWidget(status_group, 2)
        
        main_layout.addLayout(graficos_layout)
        
        # === Tabela: Produtos Mais Vendidos ===
        produtos_group = QGroupBox("Top 10 Produtos Mais Vendidos")
        produtos_layout = QVBoxLayout(produtos_group)
        
        self.table_top_produtos = QTableWidget()
        self.table_top_produtos.setColumnCount(4)
        self.table_top_produtos.setHorizontalHeaderLabels(["Produto", "Quantidade Vendida", "Receita Total", "Preço Médio"])
        
        # Configurar header para auto-ajustar e quebrar texto
        header = self.table_top_produtos.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(80)
        
        # Configurar comportamento da tabela
        self.table_top_produtos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_top_produtos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_top_produtos.setMinimumHeight(250)
        self.table_top_produtos.verticalHeader().setVisible(False)
        self.table_top_produtos.setAlternatingRowColors(True)
        self.table_top_produtos.setShowGrid(False)
        self.table_top_produtos.setWordWrap(True)
        
        produtos_layout.addWidget(self.table_top_produtos)
        main_layout.addWidget(produtos_group)
        
        main_layout.addStretch()
        
        # Carregar dados iniciais (e redesenhar gráficos quando o tema mudar)
        self.refresh()
        on_theme_changed(lambda _theme: self.refresh())
    
    def refresh(self) -> None:
        """Atualiza todos os dados do dashboard"""
        try:
            # === Atualizar Cards ===
            
            # Total de vendas (soma dos totais dos pedidos)
            vendas_result = self.db.query("""
                SELECT SUM(total) as total
                FROM orders
                WHERE status != 'Cancelado'
            """)
            total_vendas = float(vendas_result[0]["total"]) if vendas_result and vendas_result[0]["total"] else 0.0
            self.card_vendas.value_label.setText(format_price_br(total_vendas))
            
            # Pedidos em produção
            producao_result = self.db.query("SELECT COUNT(*) as c FROM orders WHERE status='Produção'")
            total_producao = int(producao_result[0]["c"]) if producao_result else 0
            self.card_producao.value_label.setText(str(total_producao))
            
            # Pedidos prontos
            prontos_result = self.db.query("SELECT COUNT(*) as c FROM orders WHERE status='Pronto'")
            total_prontos = int(prontos_result[0]["c"]) if prontos_result else 0
            self.card_prontos.value_label.setText(str(total_prontos))
            
            # Total de clientes
            clientes_result = self.db.query("SELECT COUNT(*) as c FROM customers")
            total_clientes = int(clientes_result[0]["c"]) if clientes_result else 0
            self.card_clientes.value_label.setText(str(total_clientes))
            
            # === Atualizar Gráfico de Vendas por Mês ===
            self._update_vendas_chart()
            
            # === Atualizar Gráfico de Status ===
            self._update_status_chart()
            
            # === Atualizar Top Produtos ===
            self._update_top_produtos()
            
        except Exception as e:
            print(f"Erro ao atualizar dashboard: {e}")
    
    def _update_vendas_chart(self) -> None:
        """Atualiza gráfico de vendas dos últimos 6 meses"""
        try:
            # Buscar vendas por mês
            vendas_por_mes = self.db.query("""
                SELECT 
                    strftime('%Y-%m', created_at) as mes,
                    SUM(total) as total
                FROM orders
                WHERE status != 'Cancelado'
                    AND created_at >= date('now', '-6 months')
                GROUP BY mes
                ORDER BY mes
            """)
            
            if not vendas_por_mes:
                self.chart_vendas.show_empty("Sem vendas nos últimos 6 meses")
                return
            
            # Processar dados
            meses = []
            valores = []
            
            # Mapeamento de meses em português
            meses_pt = {
                'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr',
                'May': 'Mai', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
                'Sep': 'Set', 'Oct': 'Out', 'Nov': 'Nov', 'Dec': 'Dez'
            }
            
            for row in vendas_por_mes:
                mes_str = row["mes"]
                valor = float(row["total"]) if row["total"] else 0.0
                
                # Converter mes (YYYY-MM) para nome abreviado em português
                try:
                    mes_date = datetime.strptime(mes_str, "%Y-%m")
                    mes_eng = mes_date.strftime("%b")
                    mes_pt_nome = meses_pt.get(mes_eng, mes_eng)
                    ano = mes_date.strftime("%y")
                    mes_nome = f"{mes_pt_nome}/{ano}"
                except:
                    mes_nome = mes_str
                
                meses.append(mes_nome)
                valores.append(valor)
            
            self.chart_vendas.set_data(meses, valores, palette(current_theme()))

        except Exception as e:
            self.chart_vendas.show_empty(f"Erro ao carregar gráfico: {e}")
    
    def _update_status_chart(self) -> None:
        """Atualiza gráfico de status dos pedidos"""
        try:
            # Buscar contagem por status
            status_counts = self.db.query("""
                SELECT status, COUNT(*) as count
                FROM orders
                GROUP BY status
                ORDER BY count DESC
            """)
            
            if not status_counts:
                self.chart_status.show_empty("Sem pedidos cadastrados")
                return
            
            status_colors = {
                "Produção": "#f59e0b",
                "Pronto": "#10b981",
                "Entregue": "#3b82f6",
                "Cancelado": "#ef4444",
                "Pendente": "#6b7280"
            }
            items = [(row["status"], int(row["count"]), status_colors.get(row["status"], "#8b5cf6"))
                     for row in status_counts]
            self.chart_status.set_data(items, palette(current_theme()))

        except Exception as e:
            self.chart_status.show_empty(f"Erro ao carregar gráfico: {e}")
    
    def _update_top_produtos(self) -> None:
        """Atualiza tabela de produtos mais vendidos"""
        try:
            top_produtos = self.db.query("""
                SELECT 
                    p.name,
                    SUM(o.quantity) as total_quantidade,
                    SUM(o.total) as receita_total,
                    p.price as preco
                FROM orders o
                JOIN products p ON o.product_id = p.id
                WHERE o.status != 'Cancelado'
                GROUP BY p.id
                ORDER BY total_quantidade DESC
                LIMIT 10
            """)
            
            self.table_top_produtos.setRowCount(0)
            
            if not top_produtos:
                return
            
            for row_data in top_produtos:
                row = self.table_top_produtos.rowCount()
                self.table_top_produtos.insertRow(row)
                
                # Nome do produto
                self.table_top_produtos.setItem(row, 0, QTableWidgetItem(row_data["name"]))
                
                # Quantidade vendida
                qtd_item = QTableWidgetItem(str(int(row_data["total_quantidade"])))
                qtd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_top_produtos.setItem(row, 1, qtd_item)
                
                # Receita total
                receita = float(row_data["receita_total"]) if row_data["receita_total"] else 0.0
                receita_item = QTableWidgetItem(format_price_br(receita))
                receita_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_top_produtos.setItem(row, 2, receita_item)
                
                # Preço médio
                preco = float(row_data["preco"]) if row_data["preco"] else 0.0
                preco_item = QTableWidgetItem(format_price_br(preco))
                preco_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_top_produtos.setItem(row, 3, preco_item)
            
        except Exception as e:
            print(f"Erro ao atualizar top produtos: {e}")
