# -*- coding: utf-8 -*-
"""Janela principal: sidebar, header e páginas."""

from __future__ import annotations

import ctypes
import os
import sqlite3
import sys
import threading
from datetime import datetime
from typing import Any, Callable, Optional, cast

from PyQt6.QtCore import QPoint, QPropertyAnimation, QSize, QTimer, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

from core.database import Database
from core.extended_database import ExtendedDatabase, check_and_reserve_stock
from core.paths import APP_DIR, BACKUP_DIR, DB_PATH, RESOURCE_DIR, base_dir
from ui.dialogs.custom_filedialog import CustomFileDialog
from ui.dialogs.database_dialog import DatabaseDialog
from ui.dialogs.user_dialogs import UsersDialog
from ui.icons import safe_qta_icon, safe_qta_icon_states
from ui.messages import show_message
from ui.pages.customers import CustomersPage
from ui.pages.dashboard import DashboardPage
from ui.pages.orders import OrdersPage
from ui.pages.production import ProductionPage
from ui.pages.products import ProductsPage
from ui.pages.ready_stock import ReadyStockPage
from ui.pages.reports import ReportsPage
from ui.pages.settings import SettingsPage
from ui.pages.stock_movements import StockMovementsPage
from ui.theme.qss import current_theme, on_theme_changed, palette
from ui.widgets.toast import Toast


class MainWindow(QMainWindow):
    user: Any

    def animate_page_change(self, index: int) -> None:
        old_index = self.pages.currentIndex()
        if old_index == index:
            return
        old_widget = cast(QWidget, self.pages.currentWidget())
        new_widget = cast(QWidget, self.pages.widget(index))
        w = self.pages.width()
        direction = 1 if index > old_index else -1
        cast(Any, new_widget).setGeometry(direction * w, 0, w, self.pages.height())
        cast(Any, new_widget).show()
        anim_old = QPropertyAnimation(old_widget, b"pos", self)
        anim_old.setDuration(250)
        anim_old.setStartValue(cast(Any, old_widget).pos())
        anim_old.setEndValue(cast(Any, old_widget).pos() - QPoint(direction * w, 0))
        anim_new = QPropertyAnimation(new_widget, b"pos", self)
        anim_new.setDuration(250)
        anim_new.setStartValue(cast(Any, new_widget).pos())
        anim_new.setEndValue(cast(Any, old_widget).pos())
        def on_anim_finished() -> None:
            self.pages.setCurrentIndex(index)
            old_widget.move(0, 0)
            new_widget.move(0, 0)
        cast(Any, anim_new.finished).connect(on_anim_finished)
        anim_old.start()
        anim_new.start()

    def __init__(self, user: Any):
        super().__init__()
        
        # Configuração do ícone da janela principal
        self._setup_window_icon()
        
        self.user = user
        
        # Buscar nome da empresa do banco
        self._update_window_title()
        
        # Tamanho automático baseado na tela disponível
        from PyQt6.QtGui import QGuiApplication, QCursor
        # Usa a tela onde o cursor está (onde o usuário realmente está olhando),
        # não sempre a "tela primária" do Windows - em setups com múltiplos
        # monitores, a primária configurada no Windows pode não ser a que o
        # usuário está usando, fazendo a janela abrir com tamanho calculado
        # para um monitor mas aparecer (ou ser movida) para outro.
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            # Define tamanho como 70%/75% da tela, mas dentro de limites absolutos
            # razoáveis. Sem isso, em monitores muito grandes a janela ficava
            # enorme com elementos de tamanho fixo (sidebar de 220px, botões,
            # fontes) parecendo minúsculos e desproporcionais dentro dela; em
            # monitores pequenos ficava espremida demais.
            width = max(1000, min(int(screen_geometry.width() * 0.7), 1600))
            height = max(650, min(int(screen_geometry.height() * 0.75), 950))
            self.resize(width, height)
            # Tamanho mínimo é 60% da tela ou 800x600 (o que for menor)
            min_width = min(int(screen_geometry.width() * 0.6), 800)
            min_height = min(int(screen_geometry.height() * 0.65), 600)
            self.setMinimumSize(min_width, min_height)
            # Centraliza explicitamente na tela onde a janela vai aparecer
            x = screen_geometry.x() + (screen_geometry.width() - width) // 2
            y = screen_geometry.y() + (screen_geometry.height() - height) // 2
            self.move(x, y)
        else:
            # Fallback caso não consiga detectar a tela
            self.resize(1100, 700)
            self.setMinimumSize(800, 600)
        
        # Sempre usar o banco configurado pelo usuário
        from core.config import get_database_path
        current_db_path = get_database_path()
        
        # Garante que o diretório existe
        db_dir = os.path.dirname(current_db_path)
        os.makedirs(db_dir, exist_ok=True)
        
        # LOG IMPORTANTE: Mostrar qual banco está sendo usado
        if current_db_path.startswith('\\\\'):
            print("=" * 80)
            print("⚠️  ATENÇÃO: USANDO BANCO DE DADOS EM REDE")
            print(f"📂 Caminho: {current_db_path}")
            print("=" * 80)
        else:
            print(f"📂 Usando banco de dados: {current_db_path}")
        
        try:
            self.db = ExtendedDatabase(current_db_path)
        except Exception as e:
            print(f"❌ Erro ao abrir banco de dados: {e}")
            print(f"🔧 Tentando reparar ou criar novo banco...")
            
            # Se o banco está corrompido, tenta reparar
            if os.path.exists(current_db_path):
                try:
                    from core.database import Database
                    temp_db = Database(current_db_path)
                    success, msg = temp_db.repair_database()
                    if success:
                        print(f"✅ Banco reparado: {msg}")
                        self.db = ExtendedDatabase(current_db_path)
                    else:
                        raise Exception(f"Falha no reparo: {msg}")
                except Exception as repair_error:
                    print(f"❌ Não foi possível reparar: {repair_error}")
                    # Remove o banco corrompido e cria um novo
                    backup_path = current_db_path + f".corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    try:
                        os.rename(current_db_path, backup_path)
                        print(f"💾 Banco corrompido salvo em: {backup_path}")
                    except:
                        pass
                    print(f"🆕 Criando novo banco de dados...")
                    self.db = ExtendedDatabase(current_db_path)
            else:
                # Banco não existe, cria novo
                print(f"🆕 Criando novo banco de dados...")
                self.db = ExtendedDatabase(current_db_path)
        # Adicionar atributos para controle de visibilidade 
        setattr(self.db, 'current_role', 'common')  # valor padrão
        setattr(self.db, 'current_user', 'unknown')  # valor padrão
        # define usuário corrente para fins de auditoria (usar username/role ou 'unknown')
        try:
            setattr(self.db, 'current_user', getattr(user, "username", None) or getattr(user, "role", None) or "unknown")
        except Exception:
            setattr(self.db, 'current_user', "unknown")
        # define role separadamente para controle de visibilidade (admin | common)
        try:
            self.user_role = getattr(user, "role", None) or ("admin" if getattr(user, "username", None) == "admin" else "common")
        except Exception:
            self.user_role = "admin"
        try:
            setattr(self.db, 'current_role', self.user_role)
        except Exception:
            pass

        # Seed inicial + backup automático (após 1 hora)
        self._seed()
        self._setup_auto_backup_hourly()
        self._setup_stock_reservation_check()

        # Iniciar servidor web em thread separada
        self._start_web_server()

        root = QWidget(); root.setObjectName("Root"); self.setCentralWidget(root)
        hl = QHBoxLayout(root)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        # Sidebar (painel com marca do sistema + menu)
        sidebar_panel = QFrame(); sidebar_panel.setObjectName("SidebarPanel")
        sidebar_panel.setFixedWidth(232)
        side_v = QVBoxLayout(sidebar_panel)
        side_v.setContentsMargins(14, 18, 14, 14)
        side_v.setSpacing(12)

        brand = QHBoxLayout(); brand.setSpacing(10)
        self.brand_icon = QLabel(); self.brand_icon.setFixedSize(36, 36)
        self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(self.brand_icon)
        brand_texts = QVBoxLayout(); brand_texts.setSpacing(0)
        brand_name = QLabel("Confeitaria"); brand_name.setObjectName("BrandName")
        brand_caption = QLabel("Gestão de pedidos"); brand_caption.setObjectName("BrandCaption")
        brand_texts.addWidget(brand_name); brand_texts.addWidget(brand_caption)
        brand.addLayout(brand_texts, 1)
        side_v.addLayout(brand)
        side_v.addSpacing(6)

        self.sidebar: QListWidget = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setIconSize(QSize(20, 20))
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Ordem do menu: Dashboard, Clientes, Pronta entrega, Produção, Movimentação, Pedidos, Produtos, Configurações
        self._sidebar_icons = [
            ("Dashboard", "ph.squares-four"),
            ("Clientes", "ph.users"),
            ("Pronta entrega", "ph.package"),
            ("Produção", "ph.cooking-pot"),
            ("Movimentação", "ph.arrows-left-right"),
            ("Pedidos", "ph.receipt"),
            ("Produtos", "ph.cake"),
            ("Configurações", "ph.gear-six"),
        ]
        for name, _icon in self._sidebar_icons:
            self.sidebar.addItem(QListWidgetItem(name))
        side_v.addWidget(self.sidebar, 1)
        self._apply_sidebar_theme(current_theme())
        on_theme_changed(self._apply_sidebar_theme)
        hl.addWidget(sidebar_panel)

        # Right area (Header + Pages)
        right = QWidget(); right.setObjectName("RightArea"); right_v = QVBoxLayout(right)
        right_v.setContentsMargins(20, 6, 20, 8)
        right_v.setSpacing(4)
        # Header
        self.header = QWidget(); self.header.setObjectName("Header")
        header_l = QHBoxLayout(self.header)
        header_l.setContentsMargins(8, 10, 8, 12)  # Margens para dar espa\u00e7o \u00e0 logo
        header_l.setSpacing(12)  # Espa\u00e7amento entre elementos
        
        # Logo da empresa (se configurada)
        self.header_logo_label = None  # Referência para atualização dinâmica
        try:
            company_data = self.db.query("SELECT name, logo_path FROM company WHERE id=1")
            if company_data and company_data[0]["logo_path"]:
                logo_path = company_data[0]["logo_path"]
                if os.path.exists(logo_path):
                    from PyQt6.QtGui import QPixmap
                    self.header_logo_label = QLabel()
                    pixmap = QPixmap(logo_path)
                    if not pixmap.isNull():
                        # Escala mantendo proporção com altura máxima de 64px
                        scaled_pixmap = pixmap.scaled(180, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.header_logo_label.setPixmap(scaled_pixmap)
                        # Define tamanho máximo mas permite que a imagem defina o tamanho real
                        self.header_logo_label.setMaximumSize(180, 48)
                        self.header_logo_label.setScaledContents(False)  # Não estica a imagem
                        self.header_logo_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                        header_l.addWidget(self.header_logo_label)
                    else:
                        self.header_logo_label = None
                else:
                    self.header_logo_label = None
            else:
                self.header_logo_label = None
        except Exception as e:
            print(f"Erro ao carregar logo da empresa: {e}")
            self.header_logo_label = None
        
        # Título (usar nome da empresa se configurado)
        try:
            company_data = self.db.query("SELECT name FROM company WHERE id=1")
            company_name = company_data[0]["name"] if company_data else "Confeitaria"
        except Exception:
            company_name = "Confeitaria"
        
        self.title_label = QLabel(company_name)
        self.title_label.setObjectName("AppTitle")
        header_l.addWidget(self.title_label)
        header_l.addStretch(1)
        
        # Inicializa header_logo_label como None se ainda não existe
        if not hasattr(self, 'header_logo_label') or self.header_logo_label is None:
            self.header_logo_label = None
        
        # Banner de acesso ao painel web
        self.web_access_label = QLabel()
        self.web_access_label.setObjectName("WebAccessBanner")
        self.web_access_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.web_access_label.setWordWrap(False)
        self.web_access_label.setCursor(Qt.CursorShape.PointingHandCursor)
        # Obter IP real imediatamente
        local_ip = self._get_local_ip()
        port = 5000
        url_rede = f"http://{local_ip}:{port}"
        url_local = f"http://localhost:{port}"
        # Salvar URLs
        self._web_url_local = url_local
        self._web_url_rede = url_rede
        # Mostrar apenas o endereço de rede (formato do celular)
        banner_text = f"📱  Painel da cozinha  ·  {url_rede}"
        self.web_access_label.setText(banner_text)
        try:
            from core.config import get_web_panel_token
            panel_pin = get_web_panel_token()
        except Exception:
            panel_pin = None
        self._web_panel_token = panel_pin
        pin_line = f"\n🔑 PIN de acesso: {panel_pin}" if panel_pin else ""
        self.web_access_label.setToolTip(
            f"🌐 Acesso pela rede (celular): {url_rede}\n"
            f"💻 Acesso local (este PC): {url_local}"
            f"{pin_line}\n\n"
            f"Clique para copiar o endereço e o PIN\n"
            f"Clique 2x para abrir no navegador"
        )
        # Conectar clique simples para copiar e duplo clique para abrir
        self.web_access_label.mousePressEvent = lambda ev: self._copy_web_address()
        self.web_access_label.mouseDoubleClickEvent = lambda a0: self._open_web_browser()
        header_l.addWidget(self.web_access_label)
        
        right_v.addWidget(self.header)

        # Pages
        self.pages: QStackedWidget = QStackedWidget()
        
        # Dashboard com gráficos
        self.page_dashboard: DashboardPage = DashboardPage(self.db, toast_cb=self.show_toast)
        dashboard_refresh_cb: Optional[Callable[[], None]] = self.page_dashboard.refresh
        
        self.page_orders: OrdersPage = OrdersPage(self.db, toast_cb=self.show_toast, dashboard_cb=dashboard_refresh_cb)
        self.page_products: ProductsPage = ProductsPage(self.db, toast_cb=self.show_toast)
        self.page_customers: CustomersPage = CustomersPage(self.db, toast_cb=self.show_toast)
        # conectar dashboard_cb dos clientes
        self.page_customers.dashboard_cb = dashboard_refresh_cb
        # Nova página: Produção
        self.page_production: ProductionPage = ProductionPage(self.db, toast_cb=self.show_toast)
        # Nova página: Pronta entrega (estoque disponível)
        self.page_ready: ReadyStockPage = ReadyStockPage(self.db, toast_cb=self.show_toast)
        # Nova página: Movimentação (entradas, saídas, produção e perdas de estoque)
        self.page_movements: StockMovementsPage = StockMovementsPage(self.db, toast_cb=self.show_toast)
        self.page_reports: ReportsPage = ReportsPage(self.db)
        self.page_settings: SettingsPage = SettingsPage(self.db, cast(QApplication, QApplication.instance()), self, toast_cb=self.show_toast)

        # Ordem deve bater com 'labels' da sidebar: Dashboard, Clientes, Pronta entrega, Produção, Movimentação, Pedidos, Produtos, Configurações
        self.pages.addWidget(self.page_dashboard)
        self.pages.addWidget(self.page_customers)
        self.pages.addWidget(self.page_ready)
        self.pages.addWidget(self.page_production)
        self.pages.addWidget(self.page_movements)
        self.pages.addWidget(self.page_orders)
        self.pages.addWidget(self.page_products)
        self.pages.addWidget(self.page_settings)

        right_v.addWidget(self.pages)
        # Rodapé
        self.footer = QLabel("© 2025 DWM System Developer. Todos os direitos reservados.")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setObjectName("Footer")
        right_v.addWidget(self.footer)
        
        hl.addWidget(right, 1)

        cast(Any, self.sidebar.currentRowChanged).connect(self.animate_page_change)
        self.sidebar.setCurrentRow(0)
        self._setup_menu()
        

    # ------------ Helpers ------------
    def _update_window_title(self) -> None:
        """Atualiza o título da janela com o nome da empresa do banco"""
        try:
            company_data = self.db.query("SELECT name FROM company WHERE id=1")
            if company_data:
                company_name = company_data[0]["name"]
                self.setWindowTitle(company_name)
                # Atualizar também o título no cabeçalho
                if hasattr(self, 'title_label'):
                    self.title_label.setText(company_name)
            else:
                self.setWindowTitle("Confeitaria")
        except Exception:
            self.setWindowTitle("Confeitaria")
    
    def _update_header_logo(self, logo_path: str | None = None) -> None:
        """Atualiza o logo no cabeçalho da janela"""
        try:
            from PyQt6.QtGui import QPixmap
            
            # Se logo_path não foi fornecido, buscar do banco
            if logo_path is None:
                company_data = self.db.query("SELECT logo_path FROM company WHERE id=1")
                if company_data:
                    logo_path = company_data[0]["logo_path"]
            
            # Se tem logo e arquivo existe
            if logo_path and os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    # Escala mantendo proporção com altura máxima de 64px
                    scaled_pixmap = pixmap.scaled(180, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    # Se já existe o label, apenas atualizar a imagem
                    if self.header_logo_label:
                        self.header_logo_label.setPixmap(scaled_pixmap)
                        self.header_logo_label.show()
                    else:
                        # Criar novo label
                        self.header_logo_label = QLabel()
                        self.header_logo_label.setPixmap(scaled_pixmap)
                        # Define tamanho máximo mas permite que a imagem defina o tamanho real
                        self.header_logo_label.setMaximumSize(180, 48)
                        self.header_logo_label.setScaledContents(False)  # Não estica a imagem
                        self.header_logo_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                        # Inserir no início do header
                        self.header.layout().insertWidget(0, self.header_logo_label)
            else:
                # Sem logo - esconder se existir
                if self.header_logo_label:
                    self.header_logo_label.hide()
        except Exception as e:
            print(f"Erro ao atualizar logo do cabeçalho: {e}")
    
    def _setup_window_icon(self) -> None:
        """Configura o ícone da janela principal do aplicativo."""
        try:
            # Primeiro, tenta usar a logo customizada do banco de dados
            try:
                company_data = self.db.query("SELECT logo_path FROM company WHERE id=1")
                if company_data and company_data[0]["logo_path"]:
                    custom_logo = company_data[0]["logo_path"]
                    if os.path.exists(custom_logo):
                        icon = QIcon(custom_logo)
                        if not icon.isNull():
                            self.setWindowIcon(icon)
                            # Também define o ícone da aplicação para toda a sessão
                            app = QApplication.instance()
                            if app and hasattr(app, 'setWindowIcon'):
                                app.setWindowIcon(icon)
                            print(f"Ícone customizado carregado: {custom_logo}")
                            return
            except Exception as e:
                print(f"Aviso: Não foi possível carregar logo customizada: {e}")
            
            # Fallback: tenta diferentes caminhos para o ícone padrão
            icon_paths = [
                os.path.join(RESOURCE_DIR, 'assets', 'icons', 'logo.ico'),
                os.path.join(base_dir, 'assets', 'icons', 'logo.ico'),
                os.path.join(os.getcwd(), 'assets', 'icons', 'logo.ico'),
                'assets/icons/logo.ico',
                'logo.ico'
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    icon = QIcon(icon_path)
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        # Também define o ícone da aplicação para toda a sessão
                        app = QApplication.instance()
                        if app and hasattr(app, 'setWindowIcon'):
                            app.setWindowIcon(icon)
                        print(f"Ícone padrão carregado: {icon_path}")
                        return
            
            print("Aviso: Nenhum arquivo de ícone encontrado nos caminhos esperados")
        except Exception as e:
            print(f"Erro ao configurar ícone da janela: {e}")

    def show_toast(self, text: str) -> None:
        t = Toast(self, text)
        t.show_near_bottom_right()

    def _seed(self) -> None:
        # Insere alguns dados de exemplo se estiver vazio
        if not self.db.query("SELECT 1 FROM products LIMIT 1"):
            self.db.execute("INSERT INTO products(name, description, stock, min_stock, price) VALUES (?,?,?,?,?)",
                            ("Bolo de Chocolate", "Com cobertura de ganache", 20, 3, 85.00))
            self.db.execute("INSERT INTO products(name, description, stock, min_stock, price) VALUES (?,?,?,?,?)",
                            ("Cheesecake", "Frutas vermelhas", 10, 2, 65.00))
        if not self.db.query("SELECT 1 FROM customers LIMIT 1"):
            self.db.execute("INSERT INTO customers(name, phone, address) VALUES (?,?,?)",
                            ("Maria Oliveira", "(11) 99999-1111", "Rua A, 123"))
            self.db.execute("INSERT INTO customers(name, phone, address) VALUES (?,?,?)",
                            ("João Silva", "(11) 98888-2222", "Rua B, 45"))

    def _apply_sidebar_theme(self, theme: str) -> None:
        """Recolore os ícones do menu e da marca conforme o tema (ícones não seguem o QSS)."""
        pal = palette(theme)
        for i, (_name, icon) in enumerate(self._sidebar_icons):
            item = self.sidebar.item(i)
            if item is not None:
                item.setIcon(safe_qta_icon_states(icon, pal.muted, pal.accent))
        self.brand_icon.setPixmap(safe_qta_icon("ph.cake-fill", color=pal.accent_text).pixmap(QSize(20, 20)))
        self.brand_icon.setStyleSheet(f"background: {pal.accent}; border-radius: 10px;")

    def _setup_menu(self) -> None:
        menu_bar = cast(Any, self.menuBar())
        menu = menu_bar.addMenu("Arquivo")
        
        # Add Users menu item (only for admin)
        act_users = QAction("Usuários", self)
        cast(Any, act_users.triggered).connect(lambda: UsersDialog(self.db, self).exec())
        menu.addAction(act_users)
        try:
            if getattr(self.db, "current_role", "admin") != "admin":
                act_users.setEnabled(False)
                act_users.setToolTip("Apenas administradores podem gerenciar usuários.")
        except Exception:
            pass

        # Add Network Sharing Configuration (only for admin)
        act_network = QAction("Configurar Rede Local", self)
        cast(Any, act_network.triggered).connect(self.configure_network_sharing)
        menu.addAction(act_network)
        try:
            if getattr(self.db, "current_role", "admin") != "admin":
                act_network.setEnabled(False)
                act_network.setToolTip("Apenas administradores podem configurar rede.")
        except Exception:
            pass

        # Add Database menu item (only for admin)
        act_database = QAction("Banco de Dados", self)
        cast(Any, act_database.triggered).connect(self.open_database_settings)
        menu.addAction(act_database)
        try:
            if getattr(self.db, "current_role", "admin") != "admin":
                act_database.setEnabled(False)
                act_database.setToolTip("Apenas administradores podem gerenciar banco de dados.")
        except Exception:
            pass

        act_quit = QAction("Sair", self)
        cast(Any, act_quit.triggered).connect(cast(Any, QApplication.instance()).quit)
        menu.addAction(act_quit)

    def configure_network_sharing(self) -> None:
        """Configura compartilhamento de rede para uso em múltiplos PCs"""
        import subprocess
        import platform
        import ctypes
        
        if platform.system() != "Windows":
            show_message(self, "Não Suportado", "Configuração automática de rede só está disponível para Windows.", ("OK",))
            return
        
        # Verifica se está executando como administrador
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
        
        if not is_admin:
            # Pergunta se quer reiniciar como admin
            restart_msg = (
                "⚠️ Privilégios de Administrador Necessários\n\n"
                "Para configurar o compartilhamento de rede, o aplicativo precisa ser executado como administrador.\n\n"
                "Deseja reiniciar o aplicativo como administrador agora?"
            )
            restart_choice = show_message(self, "Administrador Necessário", restart_msg, ("Cancelar", "Reiniciar como Admin"), 1)
            
            if restart_choice == 1:
                # Reinicia como administrador
                try:
                    if getattr(sys, 'frozen', False):
                        # Executável PyInstaller
                        exe_path = sys.executable
                    else:
                        # Modo desenvolvimento - executa o Python como admin
                        exe_path = sys.executable
                        params = f'"{os.path.abspath(sys.argv[0])}"'
                        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, params, None, 1)
                        QApplication.instance().quit()
                        return
                    
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, None, None, 1)
                    QApplication.instance().quit()
                    return
                except Exception as e:
                    show_message(
                        self,
                        "Erro",
                        f"Não foi possível reiniciar como administrador:\n\n{e}\n\n"
                        f"Por favor, feche o aplicativo e execute-o manualmente como administrador\n"
                        f"(botão direito → Executar como administrador)",
                        ("OK",)
                    )
            return
        
        msg = "🌐 Configuração de Rede Local\n\nEsta opção irá configurar seu PC para compartilhar o banco de dados.\n\nDeseja continuar?"
        result = show_message(self, "Configurar Rede Local", msg, ("Sim", "Cancelar"), 0)
        if result != 0:
            return
        
        try:
            import tempfile
            from core.config import get_database_path
            import shutil
            
            # Obtém o caminho do banco atual
            try:
                current_db = get_database_path()
            except Exception:
                current_db = DB_PATH
            
            # Cria a pasta compartilhada
            share_dir = r"C:\Confeitaria_DB"
            os.makedirs(share_dir, exist_ok=True)
            
            # Copia o banco de dados atual para a pasta compartilhada
            dest_db = os.path.join(share_dir, "confeitaria.db")
            if os.path.exists(current_db) and current_db != dest_db:
                shutil.copy2(current_db, dest_db)
            elif not os.path.exists(dest_db):
                # Se não existe banco, cria um vazio
                import sqlite3
                conn = sqlite3.connect(dest_db)
                conn.close()
            
            # Executa comandos diretamente (já está como admin neste ponto)
            show_message(self, "Aguarde", "⏳ Configurando compartilhamento...\n\nIsso pode levar alguns segundos.", ("OK",))
            
            commands = [
                # Habilita descoberta de rede
                'netsh advfirewall firewall set rule group="Network Discovery" new enable=Yes',
                'netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=Yes',
                # Remove compartilhamento antigo
                'net share Confeitaria_DB /DELETE /Y',
                # Cria compartilhamento com acesso guest
                f'net share Confeitaria_DB=C:\\Confeitaria_DB /GRANT:Todos,FULL /GRANT:Convidado,FULL',
                # Permissões NTFS
                'icacls C:\\Confeitaria_DB /grant "Todos:(OI)(CI)F" /T',
                'icacls C:\\Confeitaria_DB /grant "Convidado:(OI)(CI)F" /T',
                # Desabilita senha para compartilhamento
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa" /v "LimitBlankPasswordUse" /t REG_DWORD /d 0 /f',
                # Habilita acesso anônimo (crítico para sem senha)
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanmanWorkstation\\Parameters" /v "AllowInsecureGuestAuth" /t REG_DWORD /d 1 /f',
                # Desabilita compartilhamento protegido por senha
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa" /v "EveryoneIncludesAnonymous" /t REG_DWORD /d 1 /f',
                # Permite acesso nulo (sem credenciais)
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Parameters" /v "RestrictNullSessAccess" /t REG_DWORD /d 0 /f',
                # Ativa conta guest
                'net user guest /active:yes',
                'net user guest ""'
            ]
            
            errors = []
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    # Ignora alguns erros esperados
                    if result.returncode != 0:
                        error_text = result.stderr.strip()
                        # Ignora erros de "não encontrado" (compartilhamento que não existia)
                        if "2310" not in error_text and "não foi encontrado" not in error_text.lower():
                            errors.append(f"Comando: {cmd[:50]}...\nErro: {error_text[:100]}")
                except Exception as e:
                    errors.append(f"Comando: {cmd[:50]}...\nExceção: {str(e)[:100]}")
            
            # Se teve muitos erros, mostra
            if len(errors) > 3:
                show_message(
                    self,
                    "Aviso",
                    f"⚠️ Alguns comandos falharam:\n\n{errors[0]}\n\n"
                    f"Total de erros: {len(errors)}\n\n"
                    f"Continuando verificação...",
                    ("OK",)
                )
            
            # Aguarda um pouco para garantir que o compartilhamento foi criado
            import time
            time.sleep(2)
            
            # Verifica se o compartilhamento foi realmente criado
            check_share = subprocess.run(
                ["net", "share"],
                capture_output=True,
                text=True
            )
            
            if "Confeitaria_DB" not in check_share.stdout:
                show_message(
                    self,
                    "Erro de Configuração",
                    f"❌ O compartilhamento não foi criado!\n\n"
                    f"Possíveis causas:\n"
                    f"1. Você cancelou a solicitação de administrador\n"
                    f"2. O aplicativo não tem permissões suficientes\n\n"
                    f"💡 SOLUÇÃO:\n"
                    f"1. Feche o aplicativo\n"
                    f"2. Clique com botão DIREITO no ícone\n"
                    f"3. Escolha 'Executar como administrador'\n"
                    f"4. Tente novamente",
                    ("OK",)
                )
                return
            
            computer_name = os.environ.get('COMPUTERNAME', 'ESTE-PC')
            network_path = f"\\\\{computer_name}\\Confeitaria_DB\\confeitaria.db"
            
            # Tenta obter o IP local
            try:
                import socket
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
            except:
                ip_address = "N/A"
            
            # Testa se o compartilhamento está acessível
            test_path = f"\\\\{computer_name}\\Confeitaria_DB"
            if not os.path.exists(test_path):
                show_message(
                    self,
                    "Aviso",
                    f"⚠️ Compartilhamento criado mas não acessível localmente!\n\n"
                    f"Isso pode ser normal. Teste no outro PC.\n\n"
                    f"📁 Pasta local: {share_dir}\n"
                    f"🌐 Caminho: {network_path}\n"
                    f"🔢 IP: {ip_address}",
                    ("OK",)
                )
            else:
                show_message(
                    self, 
                    "Sucesso", 
                    f"✅ Rede configurada com ACESSO SEM SENHA!\n\n"
                    f"📁 Pasta local: {share_dir}\n"
                    f"🌐 Caminho de rede: {network_path}\n"
                    f"🔢 IP deste PC: {ip_address}\n\n"
                    f"💡 No outro PC (cliente):\n"
                    f"   1. Configurações → Conectar a Rede\n"
                    f"   2. Digite: {computer_name} ou {ip_address}\n\n"
                    f"⚠️ SE PEDIR CREDENCIAIS no cliente:\n"
                    f"   • Usuário: guest\n"
                    f"   • Senha: (deixe vazio)\n"
                    f"   • Ou clique 'Conectar como convidado'\n\n"
                    f"✅ Acesso anônimo habilitado!", 
                    ("OK",)
                )
            
            self.show_toast("✅ Rede configurada!")
            
        except Exception as e:
            show_message(self, "Erro", f"Erro: {str(e)}", ("OK",))

    def open_database_settings(self) -> None:
        """Abre o diálogo de gerenciamento de banco de dados"""
        try:
            # Abre o diálogo modal
            dialog = DatabaseDialog(self, toast_cb=self.show_toast, backup_cb=self.backup_db)
            dialog.exec()
            
        except Exception as e:
            show_message(self, "Erro", f"Erro ao abrir gerenciamento de banco:\n{str(e)}", ("OK",))

    def backup_db(self) -> None:
        """Cria backup do banco de dados atualmente em uso"""
        try:
            # Obtém o caminho do banco atualmente em uso
            try:
                from core.config import get_database_path
                current_db_path = get_database_path()
            except Exception:
                current_db_path = DB_PATH  # fallback
            
            # Verifica se o banco existe
            if not os.path.isfile(current_db_path):
                show_message(self, "Erro", f"Banco de dados não encontrado:\n{current_db_path}", ("OK",))
                return
            
            os.makedirs(BACKUP_DIR, exist_ok=True)
            
            # Sugere nome baseado no banco atual
            db_name = os.path.splitext(os.path.basename(current_db_path))[0]
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
            suggested_name = f"backup_{db_name}_{timestamp}.zip"
            suggested_path = os.path.join(BACKUP_DIR, suggested_name)
            
            dlg = CustomFileDialog(self, caption="Salvar backup", directory=BACKUP_DIR, filter="ZIP (*.zip)", save_mode=True)
            if not dlg.exec():
                return
            path = dlg.get_selected_file()
            if not path:
                return
                
            import zipfile
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                # Adiciona o banco de dados principal
                z.write(current_db_path, arcname=os.path.basename(current_db_path))
                
                # Adiciona arquivos WAL e SHM (se existirem)
                wal_path = current_db_path + "-wal"
                shm_path = current_db_path + "-shm"
                if os.path.isfile(wal_path):
                    z.write(wal_path, arcname=os.path.basename(wal_path))
                if os.path.isfile(shm_path):
                    z.write(shm_path, arcname=os.path.basename(shm_path))
                
                # Adiciona config.yaml (se existir)
                config_path = os.path.join(os.path.dirname(current_db_path), "config.yaml")
                if os.path.isfile(config_path):
                    z.write(config_path, arcname="config.yaml")
            
            show_message(self, "Backup", f"Backup criado com sucesso!\n\n📁 Origem: {current_db_path}\n💾 Backup: {path}", ("OK",))
            self.show_toast("Backup concluído ✅")
        except Exception as e:
            show_message(self, "Erro no backup", f"Erro ao criar backup:\n\n{e}", ("OK",))

    def _perform_auto_backup(self) -> None:
        """Executa backup automático de hora em hora.
        
        Cria backup silencioso sem interromper o trabalho do usuário.
        Apenas mostra notificação toast discreta.
        
        IMPORTANTE: Se o banco está em rede, faz backup DO banco da rede.
        """
        print("\n" + "="*60)
        print(f"[Backup] 🕒 Iniciando backup automático - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("="*60)
        
        try:
            # SEMPRE obtém o caminho do banco configurado (local ou rede)
            try:
                from core.config import get_database_path
                current_db_path = get_database_path()
                
                # Verifica se é caminho de rede
                if current_db_path.startswith('\\\\') or (len(current_db_path) > 1 and current_db_path[1] == ':' and ord(current_db_path[0].upper()) > ord('C')):
                    print(f"[Backup] 🌐 Banco de dados em REDE detectado: {current_db_path}")
                else:
                    print(f"[Backup] 💻 Banco de dados LOCAL: {current_db_path}")
                    
            except Exception as e:
                print(f"[Backup] ⚠️ Erro ao obter caminho do banco: {e}")
                current_db_path = DB_PATH  # fallback
                print(f"[Backup] Usando caminho padrão: {current_db_path}")
            
            # Verifica se o banco existe e está acessível
            if not os.path.isfile(current_db_path):
                print(f"[Backup] ❌ Arquivo não encontrado ou inacessível: {current_db_path}")
                self.show_toast("⚠️ Backup não realizado - Banco inacessível")
                return
            
            # Verifica tamanho do arquivo (se muito pequeno, pode estar corrompido)
            file_size = os.path.getsize(current_db_path)
            if file_size < 1024:  # Menos de 1KB
                print(f"[Backup] ⚠️ Arquivo muito pequeno ({file_size} bytes) - possível corrupção")
            
            import zipfile
            os.makedirs(BACKUP_DIR, exist_ok=True)
            
            # Nome do arquivo: (NOME_PC)_[nome_banco]_dd-mm-aaaa_hh-mm.zip
            db_name = os.path.splitext(os.path.basename(current_db_path))[0]
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
            computer_name = os.environ.get('COMPUTERNAME', 'PC').replace(' ', '_')  # Nome do computador
            auto_path = os.path.join(BACKUP_DIR, f"{computer_name}_{db_name}_{timestamp}.zip")
            
            print(f"[Backup] 📦 Criando arquivo ZIP: {auto_path}")
            print(f"[Backup] 📄 Copiando de: {current_db_path}")
            
            # Cria o backup ZIP do banco (da rede ou local)
            with zipfile.ZipFile(auto_path, 'w', zipfile.ZIP_DEFLATED) as z:
                # Adiciona o banco de dados principal
                z.write(current_db_path, arcname=os.path.basename(current_db_path))
                
                # Adiciona arquivos WAL e SHM (se existirem)
                wal_path = current_db_path + "-wal"
                shm_path = current_db_path + "-shm"
                if os.path.isfile(wal_path):
                    z.write(wal_path, arcname=os.path.basename(wal_path))
                if os.path.isfile(shm_path):
                    z.write(shm_path, arcname=os.path.basename(shm_path))
                
                # Adiciona config.yaml (se existir)
                config_path = os.path.join(os.path.dirname(current_db_path), "config.yaml")
                if os.path.isfile(config_path):
                    z.write(config_path, arcname="config.yaml")
            
            backup_size = os.path.getsize(auto_path) / 1024  # KB
            print(f"[Backup] ✅ Backup local criado com sucesso ({backup_size:.2f} KB)")
            
            # Apenas mostra toast discreto - SEM popup que interrompe o trabalho
            self.show_toast(f"💾 Backup automático concluído ({timestamp})")
            
            # Envia para GitHub (tanto o ZIP quanto o .db original)
            print(f"[Backup] ☁️ Iniciando envio para GitHub...")
            self._backup_to_github(auto_path, current_db_path)
            
        except Exception as e:
            # Silenciosamente registra erro sem interromper o usuário
            print(f"[Backup] ❌ Erro ao fazer backup automático: {e}")
            import traceback
            traceback.print_exc()
            # Mostra toast de erro discreto
            try:
                self.show_toast("⚠️ Erro ao fazer backup automático")
            except Exception:
                pass

    def _backup_to_github(self, backup_file: str, source_db_path: str) -> None:
        """Envia o backup para o repositório GitHub de forma assíncrona.
        
        Args:
            backup_file: Caminho completo do arquivo de backup ZIP
            source_db_path: Caminho do banco de dados original (pode ser rede ou local)
        """
        import subprocess
        import threading
        
        def upload_backup():
            try:
                # Verifica se Git está instalado
                try:
                    git_check = subprocess.run(
                        ["git", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                    if git_check.returncode != 0:
                        print("[GitHub] ❌ Git não está instalado no sistema")
                        print("[GitHub] ℹ️ Instale o Git para habilitar backup em nuvem")
                        print("[GitHub] 📥 Download: https://git-scm.com/download/win")
                        return
                    print(f"[GitHub] ✅ Git detectado: {git_check.stdout.strip()}")
                except FileNotFoundError:
                    print("[GitHub] ❌ Git não encontrado no PATH do sistema")
                    print("[GitHub] ℹ️ Backup local salvo em:", BACKUP_DIR)
                    return
                except subprocess.TimeoutExpired:
                    print("[GitHub] ⏱️ Timeout ao verificar Git")
                    return
                
                # Diretório do repositório de backup
                backup_repo_dir = os.path.join(base_dir, "Backup_Clientes")
                
                # Clone o repositório se não existir
                if not os.path.exists(backup_repo_dir):
                    print("[GitHub] 📥 Clonando repositório de backup...")
                    print("[GitHub] ℹ️ Isso pode levar alguns minutos na primeira vez...")
                    result = subprocess.run(
                        ["git", "clone", "git@github.com:W4lterBr/Backup_Clientes.git", backup_repo_dir],
                        capture_output=True,
                        text=True,
                        timeout=60,  # Aumentado para 60 segundos
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                    if result.returncode != 0:
                        print(f"[GitHub] ❌ Erro ao clonar repositório")
                        print(f"[GitHub] Detalhes: {result.stderr}")
                        print("[GitHub] ℹ️ Possíveis causas:")
                        print("[GitHub]    - Chave SSH não configurada")
                        print("[GitHub]    - Repositório não existe ou sem permissão")
                        print("[GitHub]    - Sem conexão com internet")
                        print("[GitHub] 💡 Configure o Git SSH ou execute o backup manualmente")
                        return
                    print("[GitHub] ✅ Repositório clonado com sucesso")
                else:
                    # Pull para garantir que está atualizado
                    print("[GitHub] 🔄 Atualizando repositório local...")
                    pull_result = subprocess.run(
                        ["git", "pull", "origin", "main"],
                        cwd=backup_repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                    if pull_result.returncode != 0:
                        print(f"[GitHub] ⚠️ Aviso ao atualizar: {pull_result.stderr}")
                        # Continua mesmo se o pull falhar
                
                # Usa o caminho do banco passado como parâmetro (garante usar o da rede se foi selecionado)
                import shutil
                timestamp_db = datetime.now().strftime("%d-%m-%Y")
                db_backup_name = f"Confeitaria_Backup_{timestamp_db}.db"
                db_dest_path = os.path.join(backup_repo_dir, db_backup_name)
                
                # Copia o arquivo .db DIRETO da fonte (rede ou local)
                if os.path.isfile(source_db_path):
                    print(f"[GitHub] 📄 Copiando banco de dados DA FONTE: {source_db_path}")
                    shutil.copy2(source_db_path, db_dest_path)
                    db_size = os.path.getsize(db_dest_path) / 1024  # KB
                    print(f"[GitHub] ✅ Banco de dados copiado: {db_backup_name} ({db_size:.2f} KB)")
                else:
                    print(f"[GitHub] ⚠️ Banco de dados não encontrado: {source_db_path}")
                
                # Copia o backup ZIP também
                backup_filename = os.path.basename(backup_file)
                zip_dest_path = os.path.join(backup_repo_dir, backup_filename)
                shutil.copy2(backup_file, zip_dest_path)
                zip_size = os.path.getsize(zip_dest_path) / 1024  # KB
                print(f"[GitHub] ✅ Arquivo ZIP copiado: {backup_filename} ({zip_size:.2f} KB)")
                
                # Comandos git
                subprocess.run(["git", "config", "user.name", "Confeitaria Auto Backup"], 
                             cwd=backup_repo_dir, capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                subprocess.run(["git", "config", "user.email", "backup@confeitaria.local"], 
                             cwd=backup_repo_dir, capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                subprocess.run(["git", "add", db_backup_name, backup_filename], 
                             cwd=backup_repo_dir, capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                
                commit_msg = f"Backup automático - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                result_commit = subprocess.run(["git", "commit", "-m", commit_msg], 
                             cwd=backup_repo_dir, capture_output=True, text=True, timeout=10,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                
                if "nothing to commit" in result_commit.stdout:
                    print(f"[GitHub] ℹ️ Nenhuma alteração para enviar (backup idêntico ao anterior)")
                    return
                
                # Push para o GitHub (aumenta timeout para 60 segundos)
                print(f"[GitHub] 📤 Enviando para GitHub...")
                result = subprocess.run(["git", "push", "origin", "main"], 
                                      cwd=backup_repo_dir, capture_output=True, text=True, timeout=60,
                                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                
                if result.returncode == 0:
                    print(f"[GitHub] ✅ Backup enviado com sucesso para nuvem!")
                    # Usa QTimer.singleShot para chamar show_toast na thread principal (thread-safe)
                    try:
                        QTimer.singleShot(0, lambda: self.show_toast("☁️ Backup enviado para GitHub"))
                    except Exception:
                        pass
                else:
                    print(f"[GitHub] ❌ Erro ao fazer push para GitHub")
                    print(f"[GitHub] Detalhes: {result.stderr}")
                    print(f"[GitHub] ℹ️ Backup local salvo em: {BACKUP_DIR}")
                    
            except subprocess.TimeoutExpired:
                print("[GitHub] ⏱️ Timeout ao executar comando git")
                print("[GitHub] ℹ️ Verifique sua conexão com internet")
                print(f"[GitHub] ℹ️ Backup local salvo em: {BACKUP_DIR}")
            except FileNotFoundError as e:
                print(f"[GitHub] ❌ Arquivo não encontrado: {e}")
            except Exception as e:
                print(f"[GitHub] ❌ Erro ao enviar backup: {e}")
                import traceback
                traceback.print_exc()
                print(f"[GitHub] ℹ️ Backup local salvo em: {BACKUP_DIR}")
        
        # Executa em thread separada para não bloquear a UI
        thread = threading.Thread(target=upload_backup, daemon=True)
        thread.start()

    def _setup_auto_backup_hourly(self) -> None:
        """Configura backup automático de hora em hora.
        
        O primeiro backup será executado imediatamente ao iniciar,
        e depois a cada 1 hora automaticamente.
        """
        # Executa primeiro backup imediatamente
        print("[Backup] Sistema de backup automático inicializado")
        print("[Backup] Primeiro backup será executado em 5 minutos...")
        
        # Configura timer para executar a cada 1 hora (3600000 ms)
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self._perform_auto_backup)
        self.backup_timer.start(300000)  # 5 minutos para primeiro backup (300000 ms)
        
        # Após o primeiro backup, reconfigura para 1 hora
        def set_hourly_backup():
            self.backup_timer.stop()
            self.backup_timer.start(3600000)  # 1 hora em milissegundos
            print("[Backup] Timer reconfigurado para backup a cada 1 hora")
        
        # Agendar reconfiguração após primeiro backup
        QTimer.singleShot(301000, set_hourly_backup)  # 5min + 1seg

    def _setup_stock_reservation_check(self) -> None:
        """Roda check_and_reserve_stock() ao iniciar e depois a cada hora.

        Sem isso, pedidos com data de entrega futura nunca tinham o estoque
        baixado automaticamente quando a data chegava - a função existia mas
        nunca era chamada em lugar nenhum.
        """
        def run_check():
            try:
                processed = check_and_reserve_stock(self.db)
                if processed:
                    self.show_toast(f"📦 Estoque reservado para {processed} pedido(s)")
            except Exception as e:
                print(f"⚠️ Erro ao checar reservas de estoque: {e}")

        QTimer.singleShot(2000, run_check)  # roda logo após abrir a janela principal
        self.stock_reservation_timer = QTimer(self)
        self.stock_reservation_timer.timeout.connect(run_check)
        self.stock_reservation_timer.start(3600000)  # a cada 1 hora

    def _start_web_server(self) -> None:
        """Inicia o servidor web Flask em uma thread separada para o Painel da Cozinha"""
        try:
            print("\n" + "="*60)
            print("🌐 INICIANDO SERVIDOR WEB...")
            print("="*60)
            
            # Testar importação do Flask
            try:
                import flask
                from flask_cors import CORS
                try:
                    from importlib.metadata import version
                    flask_version = version("flask")
                except ImportError:
                    flask_version = getattr(flask, '__version__', 'unknown')
                print(f"✅ Flask {flask_version} detectado")
            except ImportError as e:
                print(f"❌ Flask não está instalado: {e}")
                print("   Execute: pip install Flask Flask-CORS")
                print("   O Painel da Cozinha não será iniciado.")
                return
            
            from core.web_server import start_server
            from core.config import get_database_path, get_web_panel_token

            # Diretório web (HTML, CSS, JS, imagens)
            web_dir = os.path.join(APP_DIR, 'web')

            # Verificar se o diretório web existe
            if not os.path.exists(web_dir):
                print(f"❌ Diretório web não encontrado: {web_dir}")
                print("   O Painel da Cozinha não será iniciado.")
                return

            print(f"✅ Diretório web encontrado: {web_dir}")

            # Usar o mesmo banco de dados configurado pela aplicação principal
            # (NÃO usar a constante DB_PATH: ela é calculada uma única vez na
            # importação do módulo e fica desatualizada se o usuário trocar o
            # caminho do banco - ex: apontar para um banco em rede - nas configurações)
            db_path = get_database_path()
            print(f"✅ Banco de dados: {db_path}")

            # Porta do servidor (padrão: 5000)
            port = 5000
            print(f"✅ Porta configurada: {port}")

            # PIN exigido para acessar a API pela rede (gerado/persistido em config.yaml)
            access_token = get_web_panel_token()
            self._web_panel_token = access_token
            print(f"✅ PIN de acesso ao painel: {access_token}")

            # Não precisa atualizar o label novamente pois já foi configurado no __init__

            # Iniciar servidor em thread daemon (termina quando o app principal fechar)
            print("🚀 Iniciando thread do servidor...")
            server_thread = threading.Thread(
                target=start_server,
                args=(db_path, web_dir, port, access_token),
                daemon=True,
                name="WebServerThread"
            )
            server_thread.start()
            
            # Aguardar um pouco para o servidor iniciar
            import time
            time.sleep(2)
            
            # Verificar se a thread está viva
            if server_thread.is_alive():
                print("✅ Servidor web iniciado com sucesso!")
                print("="*60 + "\n")
            else:
                print("❌ Thread do servidor encerrou inesperadamente")
                print("="*60 + "\n")
            
        except ImportError as e:
            print(f"❌ Erro de importação: {e}")
            print("   Execute: pip install Flask Flask-CORS")
            print("   O Painel da Cozinha não será iniciado.")
            print("="*60 + "\n")
        except Exception as e:
            print(f"❌ Erro ao iniciar servidor web: {e}")
            import traceback
            traceback.print_exc()
            print("   O Painel da Cozinha não será iniciado.")
            print("="*60 + "\n")
    
    def _get_local_ip(self) -> str:
        """Retorna o IP local da máquina"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    def _copy_web_address(self) -> None:
        """Copia o endereço de acesso ao painel web para a área de transferência"""
        try:
            if hasattr(self, '_web_url_rede'):
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app is None:
                    self.show_toast("❌ Aplicação não inicializada")
                    return
                clipboard = app.clipboard()
                if clipboard:
                    pin = getattr(self, '_web_panel_token', None)
                    text = f"{self._web_url_rede} (PIN: {pin})" if pin else self._web_url_rede
                    clipboard.setText(text)
                    self.show_toast(f"✅ Copiado: {text}")
                else:
                    self.show_toast("❌ Erro ao acessar área de transferência")
            else:
                self.show_toast("❌ Endereço do painel web não disponível")
        except Exception as e:
            self.show_toast(f"❌ Erro ao copiar: {e}")
    
    def _open_web_browser(self) -> None:
        """Abre o painel web no navegador padrão"""
        try:
            if hasattr(self, '_web_url_rede'):
                import webbrowser
                webbrowser.open(self._web_url_rede)
                self.show_toast(f"🌐 Abrindo navegador: {self._web_url_rede}")
            else:
                self.show_toast("❌ Endereço do painel web não disponível")
        except Exception as e:
            self.show_toast(f"❌ Erro ao abrir navegador: {e}")
