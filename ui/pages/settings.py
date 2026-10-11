# -*- coding: utf-8 -*-
"""Página de Configurações: empresa, tema, banco e usuários."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable, Optional, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QVBoxLayout,
)

from core.database import Database
from core.paths import APP_DIR
from ui.messages import show_message
from ui.pages.base import BasePage
from ui.theme.qss import apply_theme


class SettingsPage(BasePage):
    def __init__(self, db: Database, app: QApplication, parent_window: QMainWindow,
                 toast_cb: Optional[Callable[[str], None]] = None,
                 backup_cb: Optional[Callable[[], None]] = None) -> None:
        super().__init__("Configurações", "Personalização do sistema")
        self.db = db
        self.app = app
        self.parent_window = parent_window
        self.toast_cb = toast_cb
        self.backup_cb = backup_cb
        self.update_thread = None
        
        bl = QVBoxLayout(self.body)
        
        # === Seção: Tema ===
        theme_group = QFrame()
        theme_group.setObjectName("SettingsGroup")
        theme_layout = QVBoxLayout(theme_group)
        theme_title = QLabel("<b>🎨 Aparência</b>")
        theme_layout.addWidget(theme_title)
        
        # Primeira linha de botões: Escuro e Claro
        theme_buttons_1 = QHBoxLayout()
        self.btn_dark: QPushButton = QPushButton("🌙 Tema Escuro")
        self.btn_light: QPushButton = QPushButton("☀️ Tema Claro")
        theme_buttons_1.addWidget(self.btn_dark)
        theme_buttons_1.addWidget(self.btn_light)
        theme_buttons_1.addStretch(1)
        theme_layout.addLayout(theme_buttons_1)
        
        # Segunda linha de botões: Rosa, Roxo e Azul
        theme_buttons_2 = QHBoxLayout()
        self.btn_pink: QPushButton = QPushButton("🌸 Tema Rosa")
        self.btn_purple: QPushButton = QPushButton("💜 Tema Roxo")
        self.btn_blue: QPushButton = QPushButton("💙 Tema Azul")
        theme_buttons_2.addWidget(self.btn_pink)
        theme_buttons_2.addWidget(self.btn_purple)
        theme_buttons_2.addWidget(self.btn_blue)
        theme_buttons_2.addStretch(1)
        theme_layout.addLayout(theme_buttons_2)
        
        bl.addWidget(theme_group)
        
        # === Seção: Empresa ===
        company_group = QFrame()
        company_group.setObjectName("SettingsGroup")
        company_layout = QVBoxLayout(company_group)
        company_title = QLabel("<b>🏢 Empresa</b>")
        company_layout.addWidget(company_title)
        
        # Carregar dados atuais da empresa
        try:
            company_data = self.db.query("SELECT name, logo_path FROM company WHERE id=1")
            if company_data:
                self.current_company_name = company_data[0]["name"]
                self.current_logo_path = company_data[0]["logo_path"]
            else:
                self.current_company_name = "Confeitaria"
                self.current_logo_path = None
        except Exception:
            self.current_company_name = "Confeitaria"
            self.current_logo_path = None
        
        # Nome da empresa
        name_layout = QHBoxLayout()
        name_label = QLabel("Nome da Empresa:")
        name_layout.addWidget(name_label)
        
        self.company_name_input = QLineEdit()
        self.company_name_input.setText(self.current_company_name)
        self.company_name_input.setPlaceholderText("Digite o nome da empresa")
        name_layout.addWidget(self.company_name_input, 1)
        
        btn_save_name = QPushButton("💾 Salvar Nome")
        cast(Any, btn_save_name.clicked).connect(self.save_company_name)
        name_layout.addWidget(btn_save_name)
        
        company_layout.addLayout(name_layout)
        
        # Logo da empresa
        logo_layout = QHBoxLayout()
        logo_label = QLabel("Logo da Empresa:")
        logo_layout.addWidget(logo_label)
        
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(64, 64)
        self.logo_preview.setStyleSheet("""
            QLabel {
                border: 2px dashed #cbd5e1;
                border-radius: 8px;
                background: #f8fafc;
            }
        """)
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Carregar logo se existir
        if self.current_logo_path and os.path.exists(self.current_logo_path):
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(self.current_logo_path)
            if not pixmap.isNull():
                self.logo_preview.setPixmap(pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.logo_preview.setText("🖼️")
        else:
            self.logo_preview.setText("🖼️")
        
        logo_layout.addWidget(self.logo_preview)
        
        btn_select_logo = QPushButton("📁 Selecionar Logo")
        cast(Any, btn_select_logo.clicked).connect(self.select_company_logo)
        logo_layout.addWidget(btn_select_logo)
        
        btn_remove_logo = QPushButton("🗑️ Remover Logo")
        cast(Any, btn_remove_logo.clicked).connect(self.remove_company_logo)
        logo_layout.addWidget(btn_remove_logo)
        
        logo_layout.addStretch(1)
        company_layout.addLayout(logo_layout)
        
        # Descrição
        info_label = QLabel("💡 A logo será exibida no topo do sistema")
        info_label.setStyleSheet("color: #6b7280; font-size: 11px; margin-top: 5px;")
        company_layout.addWidget(info_label)
        
        bl.addWidget(company_group)
        
        # === Seção: Backup ===
        if backup_cb:
            backup_group = QFrame()
            backup_group.setObjectName("SettingsGroup")
            backup_layout = QVBoxLayout(backup_group)
            backup_title = QLabel("<b>💾 Backup</b>")
            backup_layout.addWidget(backup_title)
            
            self.btn_backup = QPushButton("Fazer Backup do Banco de Dados")
            cast(Any, self.btn_backup.clicked).connect(backup_cb)
            backup_layout.addWidget(self.btn_backup)
            
            bl.addWidget(backup_group)
        
        bl.addStretch(1)
        
        # Conecta eventos (tema com persistência)
        cast(Any, self.btn_dark.clicked).connect(lambda: self.set_theme('dark'))
        cast(Any, self.btn_light.clicked).connect(lambda: self.set_theme('light'))
        cast(Any, self.btn_pink.clicked).connect(lambda: self.set_theme('pink'))
        cast(Any, self.btn_purple.clicked).connect(lambda: self.set_theme('purple'))
        cast(Any, self.btn_blue.clicked).connect(lambda: self.set_theme('blue'))
    
    def set_theme(self, theme: str) -> None:
        """Aplica e salva o tema escolhido (dark/light/pink/purple/blue)."""
        try:
            from core.config import load_config, save_config
            apply_theme(self.app, theme)
            theme_name = {'dark': 'escuro', 'pink': 'rosa', 'purple': 'roxo', 'blue': 'azul'}.get(theme, 'claro')
            
            # Persiste em config.yaml
            cfg = load_config()
            cfg['theme'] = theme
            save_config(cfg)
            
            if self.toast_cb:
                self.toast_cb(f"Tema {theme_name} aplicado e salvo.")
        except Exception as e:
            try:
                show_message(self.parent_window, 'Erro', f'Não foi possível aplicar/salvar o tema: {e}', ('OK',))
            except Exception:
                pass
    
    def save_company_name(self) -> None:
        """Salva o nome da empresa no banco de dados"""
        try:
            new_name = self.company_name_input.text().strip()
            if not new_name:
                show_message(self.parent_window, 'Atenção', 'Por favor, digite um nome para a empresa.', ('OK',))
                return
            
            # Atualizar no banco
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db.execute("UPDATE company SET name=?, updated_at=? WHERE id=1", (new_name, now))
            
            self.current_company_name = new_name
            
            # Atualizar título da janela principal
            if hasattr(self.parent_window, '_update_window_title'):
                self.parent_window._update_window_title()
            
            if self.toast_cb:
                self.toast_cb(f"✓ Nome da empresa atualizado para '{new_name}'")
                
        except Exception as e:
            show_message(self.parent_window, 'Erro', f'Não foi possível salvar o nome da empresa: {e}', ('OK',))
    
    def select_company_logo(self) -> None:
        """Permite selecionar uma imagem para logo da empresa"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self.parent_window,
                "Selecionar Logo da Empresa",
                "",
                "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;Todos os arquivos (*.*)"
            )
            
            if not file_path:
                return
            
            # Copiar imagem para pasta da aplicação
            import shutil
            logo_dir = os.path.join(APP_DIR, "assets", "company")
            os.makedirs(logo_dir, exist_ok=True)
            
            # Nome do arquivo de destino
            file_ext = os.path.splitext(file_path)[1]
            dest_path = os.path.join(logo_dir, f"logo{file_ext}")
            
            # Copiar arquivo
            shutil.copy2(file_path, dest_path)
            
            # Atualizar no banco
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db.execute("UPDATE company SET logo_path=?, updated_at=? WHERE id=1", (dest_path, now))
            
            self.current_logo_path = dest_path
            
            # Atualizar preview
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(dest_path)
            if not pixmap.isNull():
                self.logo_preview.setPixmap(pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            
            # Atualizar logo no cabeçalho da janela principal
            if hasattr(self.parent_window, '_update_header_logo'):
                self.parent_window._update_header_logo(dest_path)
            
            # Atualizar ícone da janela
            if hasattr(self.parent_window, '_setup_window_icon'):
                self.parent_window._setup_window_icon()
            
            if self.toast_cb:
                self.toast_cb("✓ Logo da empresa atualizada")
                
        except Exception as e:
            show_message(self.parent_window, 'Erro', f'Não foi possível salvar a logo: {e}', ('OK',))
    
    def remove_company_logo(self) -> None:
        """Remove a logo da empresa"""
        try:
            # Confirmar remoção
            reply = show_message(
                self.parent_window,
                'Confirmar',
                'Deseja realmente remover a logo da empresa?',
                ('Sim', 'Não'),
                default=1
            )
            
            if reply != 0:  # Não clicou em "Sim"
                return
            
            # Atualizar no banco (remover caminho)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db.execute("UPDATE company SET logo_path=NULL, updated_at=? WHERE id=1", (now,))
            
            # Tentar deletar arquivo físico
            if self.current_logo_path and os.path.exists(self.current_logo_path):
                try:
                    os.remove(self.current_logo_path)
                except Exception:
                    pass  # Não é crítico se falhar
            
            self.current_logo_path = None
            
            # Resetar preview
            self.logo_preview.clear()
            self.logo_preview.setText("🖼️")
            
            # Remover logo do cabeçalho da janela principal
            if hasattr(self.parent_window, '_update_header_logo'):
                self.parent_window._update_header_logo(None)
            
            # Atualizar ícone da janela para voltar ao padrão
            if hasattr(self.parent_window, '_setup_window_icon'):
                self.parent_window._setup_window_icon()
            
            if self.toast_cb:
                self.toast_cb("✓ Logo removida")
                
        except Exception as e:
            show_message(self.parent_window, 'Erro', f'Não foi possível remover a logo: {e}', ('OK',))
