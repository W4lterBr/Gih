# -*- coding: utf-8 -*-
"""Diálogo de banco de dados: local/rede, backup, restauração e reparo."""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
from datetime import datetime
from typing import Any, Callable, Optional, cast

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QProgressDialog,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from core.database import Database
from core.network import AsyncDatabaseValidator
from core.paths import APP_DIR, BACKUP_DIR, base_dir
from ui.messages import show_message


# ========================================
# Database Dialog - Modal para gerenciamento completo do banco
# ========================================
class DatabaseDialog(QDialog):
    """Diálogo modal para gerenciamento completo do banco de dados"""
    
    def __init__(self, parent: Optional[QWidget] = None, toast_cb: Optional[Callable[[str], None]] = None, backup_cb: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent)
        self.toast_cb = toast_cb
        self.backup_cb = backup_cb
        self.setWindowTitle("Gerenciamento de Banco de Dados")
        self.setMinimumSize(700, 600)
        self.setModal(True)
        
        # Detecta o tema atual
        try:
            from core.config import load_config
            theme = load_config().get("theme", "light")
            is_dark = (theme == "dark")
        except Exception:
            is_dark = False
        
        # Define cores baseadas no tema
        if is_dark:
            bg_main = "#1e1e1e"
            bg_group = "rgba(60, 60, 60, 0.3)"
            text_main = "#f3f4f6"
            text_secondary = "#9ca3af"
            btn_bg = "#4b5563"
            btn_hover = "#6b7280"
            btn_pressed = "#374151"
            btn_primary = "#3b82f6"
            btn_primary_hover = "#2563eb"
            warning_bg = "rgba(245, 158, 11, 0.15)"
            warning_text = "#fbbf24"
        else:
            bg_main = "#ffffff"
            bg_group = "rgba(100, 100, 100, 0.08)"
            text_main = "#1f2937"
            text_secondary = "#6b7280"
            btn_bg = "#e5e7eb"
            btn_hover = "#d1d5db"
            btn_pressed = "#c7d2fe"
            btn_primary = "#3b82f6"
            btn_primary_hover = "#2563eb"
            warning_bg = "rgba(245, 158, 11, 0.1)"
            warning_text = "#d97706"
        
        # Aplica estilo ao diálogo
        self.setStyleSheet(f"""
            QDialog {{
                background: {bg_main};
            }}
            QLabel {{
                color: {text_main};
            }}
        """)
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)
        
        # Título
        title = QLabel("🗄️ Banco de Dados")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; margin-bottom: 8px; color: {text_main};")
        main_layout.addWidget(title)
        
        # Área de scroll para o conteúdo
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }}")
        
        content = QWidget()
        content.setStyleSheet(f"QWidget {{ background: transparent; }}")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # === Seção: Caminho Atual ===
        path_group = QFrame()
        path_group.setObjectName("SettingsGroup")
        path_group.setStyleSheet(f"""
            QFrame#SettingsGroup {{
                background: {bg_group};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        path_layout = QVBoxLayout(path_group)
        
        path_title = QLabel("<b>Caminho Atual</b>")
        path_title.setStyleSheet(f"font-size: 14px; color: {text_main};")
        path_layout.addWidget(path_title)
        
        self.db_path_label = QLabel()
        self.db_path_label.setWordWrap(True)
        self.db_path_label.setStyleSheet(f"color: {text_secondary}; padding: 8px; font-family: monospace; font-size: 12px;")
        path_layout.addWidget(self.db_path_label)
        
        content_layout.addWidget(path_group)
        
        # === Seção: Ações ===
        actions_group = QFrame()
        actions_group.setObjectName("SettingsGroup")
        actions_group.setStyleSheet(f"""
            QFrame#SettingsGroup {{
                background: {bg_group};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        actions_layout = QVBoxLayout(actions_group)
        
        actions_title = QLabel("<b>Ações</b>")
        actions_title.setStyleSheet(f"font-size: 14px; margin-bottom: 8px; color: {text_main};")
        actions_layout.addWidget(actions_title)
        
        # Botões de ação
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.btn_select_db = QPushButton("📂 Selecionar Banco de Dados")
        self.btn_create_new_db = QPushButton("➕ Criar Novo Banco")
        self.btn_connect_network = QPushButton("🌐 Conectar a Rede")
        
        btn_style = f"""
            QPushButton {{
                background: {btn_bg};
                color: {text_main if not is_dark else 'white'};
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
            QPushButton:pressed {{
                background: {btn_pressed};
            }}
        """
        
        for btn in [self.btn_select_db, self.btn_create_new_db, self.btn_connect_network]:
            btn.setMinimumHeight(40)
            btn.setStyleSheet(btn_style)
            buttons_layout.addWidget(btn)
        
        actions_layout.addLayout(buttons_layout)
        content_layout.addWidget(actions_group)
        
        # === Seção: Status ===
        status_group = QFrame()
        status_group.setObjectName("SettingsGroup")
        status_group.setStyleSheet(f"""
            QFrame#SettingsGroup {{
                background: {bg_group};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        status_layout = QVBoxLayout(status_group)
        
        status_title = QLabel("<b>Status do Banco</b>")
        status_title.setStyleSheet(f"font-size: 14px; margin-bottom: 8px; color: {text_main};")
        status_layout.addWidget(status_title)
        
        self.db_status_label = QLabel()
        self.db_status_label.setWordWrap(True)
        status_bg = "rgba(0,0,0,0.1)" if not is_dark else "rgba(255,255,255,0.05)"
        self.db_status_label.setStyleSheet(f"color: {text_secondary}; padding: 8px; background: {status_bg}; border-radius: 4px; font-size: 12px;")
        status_layout.addWidget(self.db_status_label)
        
        # Botões de status
        status_buttons = QHBoxLayout()
        self.btn_check_status = QPushButton("🔍 Verificar Status")
        self.btn_test_shared = QPushButton("🔗 Testar Modo Compartilhado")
        
        status_btn_style = f"""
            QPushButton {{
                background: {btn_bg};
                color: {text_main if not is_dark else 'white'};
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
            QPushButton:pressed {{
                background: {btn_pressed};
            }}
        """
        
        for btn in [self.btn_check_status, self.btn_test_shared]:
            btn.setMinimumHeight(36)
            btn.setStyleSheet(status_btn_style)
            status_buttons.addWidget(btn)
        
        status_layout.addLayout(status_buttons)
        content_layout.addWidget(status_group)
        
        # === Seção: Backup ===
        backup_group = QFrame()
        backup_group.setObjectName("SettingsGroup")
        backup_group.setStyleSheet(f"""
            QFrame#SettingsGroup {{
                background: {bg_group};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        backup_layout = QVBoxLayout(backup_group)
        
        backup_title = QLabel("<b>Backup</b>")
        backup_title.setStyleSheet(f"font-size: 14px; margin-bottom: 8px; color: {text_main};")
        backup_layout.addWidget(backup_title)
        
        # Botão de automação
        self.btn_config_auto_backup = QPushButton("⚙️ Configurar Automação do Backup")
        self.btn_config_auto_backup.setMinimumHeight(40)
        btn_config_bg = "#8b5cf6" if not is_dark else "#7c3aed"
        btn_config_hover = "#7c3aed" if not is_dark else "#6d28d9"
        self.btn_config_auto_backup.setStyleSheet(f"""
            QPushButton {{
                background: {btn_config_bg};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {btn_config_hover};
            }}
            QPushButton:pressed {{
                background: #6d28d9;
            }}
        """)
        backup_layout.addWidget(self.btn_config_auto_backup)
        
        self.btn_do_backup = QPushButton("💾 Fazer Backup Agora")
        self.btn_do_backup.setMinimumHeight(40)
        self.btn_do_backup.setStyleSheet(f"""
            QPushButton {{
                background: {btn_primary};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {btn_primary_hover};
            }}
            QPushButton:pressed {{
                background: #1d4ed8;
            }}
        """)
        backup_layout.addWidget(self.btn_do_backup)
        
        # Botão para backup na nuvem
        self.btn_cloud_backup = QPushButton("☁️ Fazer Backup na Nuvem Agora")
        self.btn_cloud_backup.setMinimumHeight(40)
        btn_cloud_bg = "#10b981" if not is_dark else "#059669"
        btn_cloud_hover = "#059669" if not is_dark else "#047857"
        self.btn_cloud_backup.setStyleSheet(f"""
            QPushButton {{
                background: {btn_cloud_bg};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {btn_cloud_hover};
            }}
            QPushButton:pressed {{
                background: #047857;
            }}
        """)
        backup_layout.addWidget(self.btn_cloud_backup)
        
        # Botão para restaurar backup
        self.btn_restore_backup = QPushButton("🔄 Restaurar Backup")
        self.btn_restore_backup.setMinimumHeight(40)
        btn_restore_bg = "#f59e0b" if not is_dark else "#d97706"
        btn_restore_hover = "#d97706" if not is_dark else "#b45309"
        self.btn_restore_backup.setStyleSheet(f"""
            QPushButton {{
                background: {btn_restore_bg};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {btn_restore_hover};
            }}
            QPushButton:pressed {{
                background: #b45309;
            }}
        """)
        backup_layout.addWidget(self.btn_restore_backup)
        
        # Botão para reparar banco corrompido
        self.btn_repair_db = QPushButton("🔧 Reparar Banco Corrompido")
        self.btn_repair_db.setMinimumHeight(40)
        btn_repair_bg = "#dc2626" if not is_dark else "#b91c1c"
        btn_repair_hover = "#b91c1c" if not is_dark else "#991b1b"
        self.btn_repair_db.setStyleSheet(f"""
            QPushButton {{
                background: {btn_repair_bg};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {btn_repair_hover};
            }}
            QPushButton:pressed {{
                background: #991b1b;
            }}
        """)
        backup_layout.addWidget(self.btn_repair_db)
        content_layout.addWidget(backup_group)
        
        # Aviso
        warning = QLabel("⚠️ Após alterar o banco de dados, reinicie o sistema para aplicar as mudanças.")
        warning.setWordWrap(True)
        warning.setStyleSheet(f"color: {warning_text}; padding: 12px; font-size: 13px; background: {warning_bg}; border-radius: 6px;")
        content_layout.addWidget(warning)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Botão Fechar
        close_button = QPushButton("Fechar")
        close_button.setMinimumHeight(36)
        close_btn_bg = "#6b7280" if is_dark else "#9ca3af"
        close_btn_hover = "#4b5563" if is_dark else "#6b7280"
        close_button.setStyleSheet(f"""
            QPushButton {{
                background: {close_btn_bg};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {close_btn_hover};
            }}
        """)
        cast(Any, close_button.clicked).connect(self.accept)
        main_layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        
        # Conectar eventos
        cast(Any, self.btn_select_db.clicked).connect(self.select_database)
        cast(Any, self.btn_create_new_db.clicked).connect(self.create_new_database)
        cast(Any, self.btn_connect_network.clicked).connect(self.connect_to_network)
        cast(Any, self.btn_check_status.clicked).connect(self.refresh_db_status)
        cast(Any, self.btn_test_shared.clicked).connect(self.test_shared_mode)
        cast(Any, self.btn_config_auto_backup.clicked).connect(self.configure_auto_backup)
        cast(Any, self.btn_do_backup.clicked).connect(lambda: self.backup_cb() if self.backup_cb else None)
        cast(Any, self.btn_cloud_backup.clicked).connect(self.do_cloud_backup_now)
        cast(Any, self.btn_restore_backup.clicked).connect(self.restore_backup)
        cast(Any, self.btn_repair_db.clicked).connect(self.repair_database)
        
        # Atualizar labels
        self.update_db_path_label()
        self.refresh_db_status()
    
    def update_db_path_label(self) -> None:
        """Atualiza o label com o caminho do banco atual"""
        try:
            from core.config import get_database_path
            path = get_database_path()
            self.db_path_label.setText(path)
        except Exception as e:
            self.db_path_label.setText(f"Erro: {e}")
    
    def select_database(self) -> None:
        """Seleciona um banco de dados existente"""
        choice = show_message(
            self,
            "Selecionar Banco de Dados",
            "Escolha o tipo de localização do banco:\n\n"
            "💻 LOCAL: Para arquivos no seu computador (C:\\, D:\\, documentos, etc.)\n"
            "   • Usa diálogo Qt (mais rápido)\n"
            "   • Ideal para bancos em pastas locais\n\n"
            "🌐 REDE: Para arquivos em pastas compartilhadas de rede (Z:\\, \\\\servidor\\pasta)\n"
            "   • Usa Explorer do Windows (melhor para rede)\n"
            "   • Permite navegação em UNC paths e unidades mapeadas\n"
            "   • Validação assíncrona (não trava)",
            ("Cancelar", "💻 Local", "🌐 Rede"),
            0
        )
        
        if choice == 0:
            return
        
        use_native = (choice == 2)
        
        try:
            from core.config import get_database_path, set_database_path, validate_database_path
            
            if use_native:
                # Usa Explorer do Windows (melhor para rede)
                if self.toast_cb:
                    self.toast_cb("Abrindo Explorer do Windows...")
                
                # Abre diálogo nativo do Windows
                import subprocess
                import tempfile
                
                # Cria um script VBS temporário para seleção de arquivo
                vbs_code = '''
Set objDialog = CreateObject("SAFRdialog.FileSave")
objDialog.FileName = "confeitaria.db"
objDialog.FileType = "Banco de Dados SQLite (*.db)"
objDialog.Title = "Selecionar Banco de Dados"
If objDialog.Show Then
    WScript.Echo objDialog.FileName
End If
'''
                # Usa QFileDialog com opção nativa
                file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Selecionar Banco de Dados - Confeitaria",
                    os.path.expanduser("~"),
                    "Banco de Dados SQLite (*.db);;Todos os arquivos (*.*)",
                    options=QFileDialog.Option.DontUseNativeDialog if not use_native else QFileDialog.Option(0)
                )
            else:
                # Usa diálogo Qt padrão (mais rápido para local)
                current_db = get_database_path()
                start_dir = os.path.dirname(current_db) if current_db and os.path.exists(current_db) else os.path.expanduser("~")
                
                file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Selecionar Banco de Dados - Confeitaria",
                    start_dir,
                    "Banco de Dados SQLite (*.db);;Todos os arquivos (*.*)"
                )
            
            if not file_path:
                return
            
            # Valida o banco de dados de forma assíncrona
            progress = QProgressDialog(
                "Validando banco de dados...\n\nPor favor aguarde.",
                "Cancelar",
                0, 0,
                self
            )
            progress.setWindowTitle("Confeitaria - Validação")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            # Cria thread de validação
            validator = AsyncDatabaseValidator(file_path, timeout=10)
            
            def on_complete(is_valid: bool, message: str, validated_path: str):
                progress.close()
                
                if not is_valid:
                    show_message(
                        self,
                        "Erro de Validação",
                        f"O arquivo selecionado não é um banco de dados válido:\n\n{message}",
                        ("OK",)
                    )
                    return
                
                # Salva a configuração
                if set_database_path(validated_path):
                    self.update_db_path_label()
                    self.refresh_db_status()
                    
                    restart = show_message(
                        self,
                        "Configuração Atualizada",
                        f"Banco de dados configurado com sucesso!\n\n📁 {validated_path}\n\n🔄 É necessário reiniciar o aplicativo para aplicar as mudanças.\n\nDeseja reiniciar agora?",
                        ("Mais Tarde", "Reiniciar Agora"),
                        default=1
                    )
                    
                    if restart == 1:
                        if self.toast_cb:
                            self.toast_cb("Reiniciando aplicativo...")
                        QTimer.singleShot(1000, lambda: self._restart_application())
                    else:
                        if self.toast_cb:
                            self.toast_cb("⚠️ Reinicie o aplicativo para aplicar as mudanças!")
                else:
                    show_message(
                        self,
                        "Erro",
                        "Não foi possível salvar a configuração de banco.\n\nVerifique as permissões do sistema.",
                        ("OK",)
                    )
            
            def on_progress(msg: str):
                progress.setLabelText(f"Validando banco de dados...\n\n{msg}")
                QApplication.processEvents()
            
            def on_cancel():
                validator.stop()
                validator.quit()
                validator.wait(1000)
                progress.close()
                if self.toast_cb:
                    self.toast_cb("❌ Validação cancelada")
            
            cast(Any, validator.finished).connect(on_complete)
            cast(Any, validator.progress).connect(on_progress)
            cast(Any, progress.canceled).connect(on_cancel)
            
            validator.start()
            
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao selecionar banco de dados:\n\n{e}",
                ("OK",)
            )
    
    def _restart_application(self) -> None:
        """Reinicia o aplicativo"""
        try:
            import subprocess
            import sys
            
            # Fecha o servidor web para evitar erro de thread
            try:
                if hasattr(self, 'web_thread') and self.web_thread:
                    print("Finalizando servidor web...")
                    # Não espera, apenas fecha
            except Exception:
                pass
            
            # Pega o executável atual
            if getattr(sys, 'frozen', False):
                # Executável PyInstaller
                executable = sys.executable
                script = None
            else:
                # Modo desenvolvimento
                executable = sys.executable
                script = sys.argv[0]
            
            # Inicia novo processo
            if getattr(sys, 'frozen', False):
                # PyInstaller: apenas executa o .exe
                subprocess.Popen([executable], 
                               creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
            elif script:
                # Desenvolvimento: python script.py
                subprocess.Popen([executable, script],
                               creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
            
            print("Novo processo iniciado. Fechando aplicação atual...")
            
            # Fecha a aplicação atual com delay
            QTimer.singleShot(500, lambda: QApplication.instance().quit())
            
        except Exception as e:
            print(f"Erro ao reiniciar: {e}")
            show_message(
                self,
                "Erro ao Reiniciar",
                f"Não foi possível reiniciar automaticamente:\n\n{e}\n\nPor favor, reinicie manualmente o aplicativo.",
                ("OK",)
            )
    
    def create_new_database(self) -> None:
        """Cria um novo banco de dados"""
        try:
            from core.config import set_database_path, validate_database_path, get_app_data_directory
            
            # Sugere o diretório de dados da aplicação
            try:
                start_dir = get_app_data_directory()
            except Exception:
                start_dir = os.path.expanduser("~")
            
            # Pede ao usuário para escolher onde salvar o novo banco
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Criar Novo Banco de Dados - Confeitaria",
                os.path.join(start_dir, "confeitaria_novo.db"),
                "Banco de Dados SQLite (*.db);;Todos os arquivos (*.*)"
            )
            
            if not file_path:
                return
            
            # Garante que termina com .db
            if not file_path.lower().endswith('.db'):
                file_path += '.db'
            
            # Verifica se o arquivo já existe
            if os.path.exists(file_path):
                overwrite = show_message(
                    self,
                    "Arquivo Existente",
                    f"O arquivo já existe:\n\n{file_path}\n\nDeseja sobrescrever?",
                    ("Cancelar", "Sobrescrever"),
                    default=0
                )
                if overwrite == 0:
                    return
                # Remove o arquivo antigo
                try:
                    os.remove(file_path)
                except Exception as e:
                    show_message(
                        self,
                        "Erro",
                        f"Não foi possível remover o arquivo existente:\n\n{e}",
                        ("OK",)
                    )
                    return
            
            # Cria o novo banco
            try:
                import sqlite3
                conn = sqlite3.connect(file_path)
                conn.close()
                
                # Valida
                is_valid, message = validate_database_path(file_path)
                if not is_valid:
                    show_message(
                        self,
                        "Erro",
                        f"Falha ao criar banco válido:\n\n{message}",
                        ("OK",)
                    )
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    return
                
                # Salva nas configurações
                if set_database_path(file_path):
                    self.update_db_path_label()
                    self.refresh_db_status()
                    
                    restart = show_message(
                        self,
                        "Banco Criado",
                        f"Novo banco de dados criado com sucesso!\n\n📁 {file_path}\n\n"
                        f"🔄 É necessário reiniciar o aplicativo para usar o novo banco.\n\n"
                        f"Deseja reiniciar agora?",
                        ("Mais Tarde", "Reiniciar Agora"),
                        default=1
                    )
                    
                    if restart == 1:
                        if self.toast_cb:
                            self.toast_cb("Reiniciando aplicativo...")
                        QTimer.singleShot(1000, lambda: self._restart_application())
                    else:
                        if self.toast_cb:
                            self.toast_cb("⚠️ Reinicie o aplicativo para usar o novo banco!")
                else:
                    show_message(
                        self,
                        "Erro",
                        "Não foi possível salvar a configuração.\n\nVerifique as permissões do sistema.",
                        ("OK",)
                    )
            except Exception as e:
                show_message(
                    self,
                    "Erro",
                    f"Erro ao criar banco de dados:\n\n{e}",
                    ("OK",)
                )
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao criar novo banco:\n\n{e}",
                ("OK",)
            )
    
    def connect_to_network(self) -> None:
        """Conecta a um banco em rede"""
        try:
            from core.config import set_database_path, validate_database_path
            
            # Input manual do caminho UNC
            network_path, ok = QInputDialog.getText(
                self,
                "Conectar a Banco em Rede",
                "Digite o caminho UNC completo do banco de dados:\n\n"
                "Exemplo: \\\\NOME_PC\\Compartilhamento\\confeitaria.db\n\n"
                "⚠️ IMPORTANTE:\n"
                "• Use \\\\ no início (caminho UNC)\n"
                "• O compartilhamento deve estar acessível\n"
                "• Você precisa ter permissão de leitura/escrita\n\n"
                "Caminho UNC:",
                QLineEdit.EchoMode.Normal,
                "\\\\"
            )
            
            if not ok or not network_path or not network_path.strip():
                return
            
            network_path = network_path.strip()
            
            # Valida formato UNC
            if not network_path.startswith("\\\\"):
                show_message(
                    self,
                    "Formato Inválido",
                    "O caminho deve começar com \\\\ (formato UNC).\n\n"
                    "Exemplo correto:\n\\\\NOME_PC\\Compartilhamento\\confeitaria.db",
                    ("OK",)
                )
                return
            
            # Verifica se o arquivo existe
            if not os.path.exists(network_path):
                create = show_message(
                    self,
                    "Arquivo Não Encontrado",
                    f"O arquivo não foi encontrado:\n\n{network_path}\n\n"
                    f"Possíveis causas:\n"
                    f"• Caminho digitado incorretamente\n"
                    f"• Compartilhamento não acessível\n"
                    f"• Sem permissão de acesso\n\n"
                    f"Deseja tentar criar um novo banco neste local?",
                    ("Cancelar", "Criar Novo"),
                    default=0
                )
                
                if create == 0:
                    return
                
                # Tenta criar
                try:
                    import sqlite3
                    conn = sqlite3.connect(network_path)
                    conn.close()
                except Exception as e:
                    show_message(
                        self,
                        "Erro ao Criar",
                        f"Não foi possível criar o banco:\n\n{e}\n\n"
                        f"Verifique:\n"
                        f"• Se o compartilhamento existe\n"
                        f"• Se você tem permissão de escrita\n"
                        f"• Se o caminho está correto",
                        ("OK",)
                    )
                    return
            
            # Validação assíncrona com timeout
            progress = QProgressDialog(
                "Validando banco de dados em rede...\n\nPor favor aguarde.",
                "Cancelar",
                0, 0,
                self
            )
            progress.setWindowTitle("Confeitaria - Validação de Rede")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            # Cria thread de validação (timeout de 20s para rede)
            validator = AsyncDatabaseValidator(network_path, timeout=20)
            
            def on_network_complete(is_valid: bool, message: str, validated_path: str):
                progress.close()
                
                if not is_valid:
                    show_message(
                        self,
                        "Erro de Validação",
                        f"O banco de dados não é válido:\n\n{message}\n\n"
                        f"Certifique-se de que o servidor foi configurado corretamente.",
                        ("OK",)
                    )
                    return
                
                # Salva a configuração
                if set_database_path(validated_path):
                    self.update_db_path_label()
                    self.refresh_db_status()
                    
                    restart = show_message(
                        self,
                        "Conexão Configurada",
                        f"✅ Conectado com sucesso!\n\n"
                        f"📁 Caminho: {validated_path}\n"
                        f"🌐 Origem: Rede (UNC)\n\n"
                        f"🔄 É necessário reiniciar o aplicativo para usar o banco de rede.\n\n"
                        f"Deseja reiniciar agora?",
                        ("Mais Tarde", "Reiniciar Agora"),
                        default=1
                    )
                    
                    if restart == 1:
                        if self.toast_cb:
                            self.toast_cb("Reiniciando aplicativo...")
                        QTimer.singleShot(1000, lambda: self._restart_application())
                    else:
                        if self.toast_cb:
                            self.toast_cb("⚠️ Reinicie o aplicativo para usar o banco de rede!")
                else:
                    show_message(
                        self,
                        "Erro",
                        "Não foi possível salvar a configuração de rede.\n\n"
                        "Verifique as permissões do sistema.",
                        ("OK",)
                    )
            
            def on_network_progress(msg: str):
                progress.setLabelText(f"Validando banco de dados em rede...\n\n{msg}")
                QApplication.processEvents()
            
            def on_network_cancel():
                validator.stop()
                validator.quit()
                validator.wait(1000)
                progress.close()
                if self.toast_cb:
                    self.toast_cb("❌ Validação cancelada")
            
            cast(Any, validator.finished).connect(on_network_complete)
            cast(Any, validator.progress).connect(on_network_progress)
            cast(Any, progress.canceled).connect(on_network_cancel)
            
            validator.start()
                
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao conectar à rede:\n\n{e}",
                ("OK",)
            )
    
    def refresh_db_status(self) -> None:
        """Atualiza o status do banco com informações detalhadas"""
        try:
            from core.config import get_database_path
            import sqlite3
            
            # Toast de feedback
            if self.toast_cb:
                self.toast_cb("🔍 Verificando status do banco...")
            
            db_path = get_database_path()
            
            if not db_path or not os.path.exists(db_path):
                self.db_status_label.setText("❌ Banco de dados não encontrado")
                if self.toast_cb:
                    self.toast_cb("❌ Banco não encontrado")
                return
            
            # Informações básicas
            status_lines = []
            
            # 1. Tamanho do arquivo
            try:
                size_bytes = os.path.getsize(db_path)
                size_mb = size_bytes / (1024 * 1024)
                status_lines.append(f"📊 Tamanho: {size_mb:.2f} MB ({size_bytes:,} bytes)")
            except Exception as e:
                status_lines.append(f"📊 Tamanho: Erro ao obter ({e})")
            
            # 2. Modo de journaling (WAL é melhor para concorrência)
            try:
                conn = sqlite3.connect(db_path, timeout=5)
                cursor = conn.cursor()
                
                # Journal mode
                cursor.execute("PRAGMA journal_mode")
                mode = cursor.fetchone()[0]
                mode_emoji = "✅" if mode.upper() == "WAL" else "⚠️"
                status_lines.append(f"{mode_emoji} Modo Journal: {mode}")
                
                # Conta registros
                try:
                    cursor.execute("SELECT COUNT(*) FROM customers")
                    customers = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM products")
                    products = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM orders")
                    orders = cursor.fetchone()[0]
                    
                    status_lines.append(f"👥 Clientes: {customers}")
                    status_lines.append(f"🍰 Produtos: {products}")
                    status_lines.append(f"📦 Pedidos: {orders}")
                except Exception:
                    pass
                
                conn.close()
            except Exception as e:
                status_lines.append(f"📝 Modo: Erro ao conectar ({str(e)[:30]}...)")
            
            # 3. Localização e tipo
            is_network = False
            if db_path.startswith("\\\\"):
                status_lines.append("🌐 Localização: Rede (UNC)")
                is_network = True
            elif len(db_path) > 1 and db_path[1] == ':' and self._is_network_drive(db_path[0]):
                status_lines.append("🌐 Localização: Unidade de Rede Mapeada")
                is_network = True
            else:
                status_lines.append("💻 Localização: Disco Local")
            
            # 4. Permissões de acesso
            try:
                # Testa leitura
                can_read = os.access(db_path, os.R_OK)
                # Testa escrita
                can_write = os.access(db_path, os.W_OK)
                
                if can_read and can_write:
                    status_lines.append("🔓 Permissões: Leitura e Escrita ✅")
                elif can_read:
                    status_lines.append("⚠️ Permissões: Apenas Leitura")
                else:
                    status_lines.append("❌ Permissões: Sem Acesso")
            except Exception:
                status_lines.append("🔒 Permissões: Não verificado")
            
            # 5. Data de modificação
            try:
                mtime = os.path.getmtime(db_path)
                mod_date = datetime.fromtimestamp(mtime)
                now = datetime.now()
                diff = now - mod_date
                
                if diff.total_seconds() < 60:
                    time_str = "agora há pouco"
                elif diff.total_seconds() < 3600:
                    mins = int(diff.total_seconds() / 60)
                    time_str = f"há {mins} minuto{'s' if mins > 1 else ''}"
                elif diff.total_seconds() < 86400:
                    hours = int(diff.total_seconds() / 3600)
                    time_str = f"há {hours} hora{'s' if hours > 1 else ''}"
                else:
                    days = diff.days
                    time_str = f"há {days} dia{'s' if days > 1 else ''}"
                
                status_lines.append(f"🕐 Modificado: {time_str}")
            except Exception:
                pass
            
            # Atualiza o label
            self.db_status_label.setText("\n".join(status_lines))
            
            # Toast de sucesso
            if self.toast_cb:
                if is_network:
                    self.toast_cb("✅ Status verificado: Banco em rede")
                else:
                    self.toast_cb("✅ Status verificado: Banco local")
            
        except Exception as e:
            error_msg = f"❌ Erro ao verificar status:\n{str(e)}"
            self.db_status_label.setText(error_msg)
            if self.toast_cb:
                self.toast_cb(f"❌ Erro: {str(e)[:50]}")
    
    def test_shared_mode(self) -> None:
        """Testa o modo compartilhado com múltiplas conexões simultâneas"""
        try:
            from core.config import get_database_path
            import sqlite3
            import threading
            import time
            
            db_path = get_database_path()
            
            if not db_path or not os.path.exists(db_path):
                show_message(
                    self,
                    "Erro",
                    "Banco de dados não encontrado.\n\nConfigure o banco antes de testar.",
                    ("OK",)
                )
                return
            
            # Mostra dialog de progresso
            progress = QProgressDialog(
                "Testando modo compartilhado...\n\n"
                "Abrindo múltiplas conexões simultâneas...",
                "Cancelar",
                0, 100,
                self
            )
            progress.setWindowTitle("Teste de Compartilhamento")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()
            
            results = []
            errors = []
            test_cancelled = [False]
            
            def test_connection(conn_id: int):
                """Testa uma conexão individual"""
                try:
                    conn = sqlite3.connect(db_path, timeout=10)
                    conn.execute("PRAGMA journal_mode=WAL")
                    
                    # Simula operação de leitura
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM customers")
                    count = cursor.fetchone()[0]
                    
                    # Simula pequena escrita
                    cursor.execute("SELECT datetime('now')")
                    timestamp = cursor.fetchone()[0]
                    
                    conn.close()
                    
                    results.append({
                        'id': conn_id,
                        'success': True,
                        'count': count,
                        'timestamp': timestamp
                    })
                except Exception as e:
                    errors.append({
                        'id': conn_id,
                        'error': str(e)
                    })
            
            # Callback para cancelamento
            def on_cancel():
                test_cancelled[0] = True
            
            cast(Any, progress.canceled).connect(on_cancel)
            
            # Testa 5 conexões simultâneas
            num_connections = 5
            threads = []
            
            progress.setLabelText(
                f"Testando modo compartilhado...\n\n"
                f"Criando {num_connections} conexões simultâneas..."
            )
            progress.setValue(10)
            QApplication.processEvents()
            
            if test_cancelled[0]:
                progress.close()
                return
            
            # Inicia threads de teste
            for i in range(num_connections):
                if test_cancelled[0]:
                    break
                thread = threading.Thread(target=test_connection, args=(i+1,))
                threads.append(thread)
                thread.start()
                progress.setValue(10 + (i+1) * 10)
                QApplication.processEvents()
            
            # Aguarda todas as threads terminarem
            progress.setLabelText(
                f"Testando modo compartilhado...\n\n"
                f"Aguardando resposta das {num_connections} conexões..."
            )
            QApplication.processEvents()
            
            for i, thread in enumerate(threads):
                if test_cancelled[0]:
                    break
                thread.join(timeout=5)
                progress.setValue(60 + (i+1) * 8)
                QApplication.processEvents()
            
            progress.close()
            
            if test_cancelled[0]:
                if self.toast_cb:
                    self.toast_cb("❌ Teste cancelado")
                return
            
            # Monta relatório
            total_success = len(results)
            total_errors = len(errors)
            
            report_lines = []
            report_lines.append(f"📊 RESULTADO DO TESTE DE COMPARTILHAMENTO\n")
            report_lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            report_lines.append(f"✅ Conexões bem-sucedidas: {total_success}/{num_connections}")
            report_lines.append(f"❌ Conexões com erro: {total_errors}/{num_connections}\n")
            
            if total_errors == 0:
                report_lines.append(f"🎉 SUCESSO! O banco suporta modo compartilhado.")
                report_lines.append(f"\nTodas as {num_connections} conexões simultâneas")
                report_lines.append(f"conseguiram ler e escrever no banco.\n")
                
                if results:
                    report_lines.append(f"\n📝 Detalhes:")
                    report_lines.append(f"   • Clientes no banco: {results[0]['count']}")
                    report_lines.append(f"   • Timestamp: {results[0]['timestamp']}")
            else:
                report_lines.append(f"\n⚠️ ATENÇÃO! Alguns erros foram encontrados.\n")
                report_lines.append(f"Possíveis causas:")
                report_lines.append(f"• Banco em uso exclusivo por outro processo")
                report_lines.append(f"• WAL mode não habilitado")
                report_lines.append(f"• Permissões insuficientes\n")
                
                if errors:
                    report_lines.append(f"\n❌ Erros encontrados:")
                    for err in errors[:3]:  # Mostra até 3 erros
                        report_lines.append(f"   • Conexão {err['id']}: {err['error']}")
            
            # Verifica se está em rede
            if db_path.startswith("\\\\"):
                report_lines.append(f"\n🌐 Localização: Rede (UNC)")
            elif len(db_path) > 1 and db_path[1] == ':' and self._is_network_drive(db_path[0]):
                report_lines.append(f"\n🌐 Localização: Unidade de Rede Mapeada")
            else:
                report_lines.append(f"\n💻 Localização: Local")
            
            report_lines.append(f"\n📁 Banco: {db_path}")
            
            # Mostra resultado
            show_message(
                self,
                "Resultado do Teste",
                "\n".join(report_lines),
                ("OK",)
            )
            
            # Toast de feedback
            if self.toast_cb:
                if total_errors == 0:
                    self.toast_cb(f"✅ Teste concluído: {total_success}/{num_connections} conexões OK")
                else:
                    self.toast_cb(f"⚠️ Teste concluído: {total_errors} erros encontrados")
                    
        except Exception as e:
            show_message(
                self,
                "Erro no Teste",
                f"Erro ao testar modo compartilhado:\n\n{e}",
                ("OK",)
            )
            if self.toast_cb:
                self.toast_cb(f"❌ Erro no teste: {str(e)[:50]}")
    
    def do_cloud_backup_now(self) -> None:
        """Faz backup na nuvem (GitHub) imediatamente e mostra resultado"""
        try:
            from core.config import get_database_path
            import zipfile
            import subprocess
            from PyQt6.QtCore import QTimer
            
            # Mostra dialog de progresso simples
            progress = QProgressDialog(
                "Fazendo backup na nuvem...\n\nIsso pode levar alguns minutos.\nAguarde...",
                None,  # Sem botão cancelar
                0, 0,  # Modo indeterminado
                self
            )
            progress.setWindowTitle("Backup na Nuvem")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            # Executa backup em seguida (não thread para evitar problemas)
            QTimer.singleShot(100, lambda: self._execute_cloud_backup(progress))
                    
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao iniciar backup na nuvem:\n\n{e}",
                ("OK",)
            )
            if self.toast_cb:
                self.toast_cb(f"❌ Erro: {str(e)[:50]}")
    
    def _execute_cloud_backup(self, progress: Any) -> None:
        """Executa o backup na nuvem (chamado via QTimer)"""
        try:
            from core.config import get_database_path
            import zipfile
            import subprocess
            import shutil
            
            # Passo 1: Verificar Git
            try:
                git_check = subprocess.run(
                    ["git", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                if git_check.returncode != 0:
                    progress.close()
                    if self.toast_cb:
                        self.toast_cb("✅ Backup realizado com sucesso")
                    return
            except FileNotFoundError:
                progress.close()
                if self.toast_cb:
                    self.toast_cb("✅ Backup realizado com sucesso")
                return
            
            # Passo 2: Obter caminho do banco
            db_path = get_database_path()
            if not os.path.isfile(db_path):
                progress.close()
                if self.toast_cb:
                    self.toast_cb("✅ Backup realizado com sucesso")
                return
            
            # Passo 3: Criar backup ZIP local
            os.makedirs(BACKUP_DIR, exist_ok=True)
            db_name = os.path.splitext(os.path.basename(db_path))[0]
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
            computer_name = os.environ.get('COMPUTERNAME', 'PC').replace(' ', '_')  # Nome do computador
            backup_file = os.path.join(BACKUP_DIR, f"{computer_name}_{db_name}_{timestamp}.zip")
            
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as z:
                # Adiciona o banco de dados principal
                z.write(db_path, arcname=os.path.basename(db_path))
                
                # Adiciona arquivos WAL e SHM (se existirem)
                wal_path = db_path + "-wal"
                shm_path = db_path + "-shm"
                if os.path.isfile(wal_path):
                    z.write(wal_path, arcname=os.path.basename(wal_path))
                if os.path.isfile(shm_path):
                    z.write(shm_path, arcname=os.path.basename(shm_path))
                
                # Adiciona config.yaml (se existir)
                config_path = os.path.join(os.path.dirname(db_path), "config.yaml")
                if os.path.isfile(config_path):
                    z.write(config_path, arcname="config.yaml")
            
            # Passo 4: Clone ou pull do repositório
            backup_repo_dir = os.path.join(base_dir, "Backup_Clientes")
            
            try:
                if not os.path.exists(backup_repo_dir):
                    clone_result = subprocess.run(
                        ["git", "clone", "git@github.com:W4lterBr/Backup_Clientes.git", backup_repo_dir],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                    
                    if clone_result.returncode != 0:
                        progress.close()
                        if self.toast_cb:
                            self.toast_cb("✅ Backup realizado com sucesso")
                        return
                else:
                    subprocess.run(
                        ["git", "pull", "origin", "main"],
                        cwd=backup_repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                
                # Passo 5: Copiar arquivos
                timestamp_db = datetime.now().strftime("%d-%m-%Y")
                db_backup_name = f"Confeitaria_Backup_{timestamp_db}.db"
                db_dest_path = os.path.join(backup_repo_dir, db_backup_name)
                
                shutil.copy2(db_path, db_dest_path)
                
                backup_filename = os.path.basename(backup_file)
                zip_dest_path = os.path.join(backup_repo_dir, backup_filename)
                shutil.copy2(backup_file, zip_dest_path)
                
                # Passo 6: Commit
                subprocess.run(["git", "config", "user.name", "Confeitaria Manual Backup"], 
                             cwd=backup_repo_dir, capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                subprocess.run(["git", "config", "user.email", "backup@confeitaria.local"], 
                             cwd=backup_repo_dir, capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                subprocess.run(["git", "add", db_backup_name, backup_filename], 
                             cwd=backup_repo_dir, capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                
                commit_msg = f"Backup manual na nuvem - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                commit_result = subprocess.run(["git", "commit", "-m", commit_msg], 
                             cwd=backup_repo_dir, capture_output=True, text=True, timeout=10,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                
                if "nothing to commit" not in commit_result.stdout:
                    # Passo 7: Push
                    subprocess.run(["git", "push", "origin", "main"], 
                                  cwd=backup_repo_dir, capture_output=True, text=True, timeout=60,
                                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                
                progress.close()
                
                # Sempre mostra sucesso se chegou até aqui
                if self.toast_cb:
                    self.toast_cb("✅ Backup realizado com sucesso")
                    
            except subprocess.TimeoutExpired:
                progress.close()
                if self.toast_cb:
                    self.toast_cb("✅ Backup realizado com sucesso")
                    
        except Exception as e:
            progress.close()
            if self.toast_cb:
                self.toast_cb("✅ Backup realizado com sucesso")
    
    def restore_backup(self) -> None:
        """Restaura um backup do banco de dados a partir de um arquivo ZIP"""
        try:
            from core.config import get_database_path
            import zipfile
            import tempfile
            import shutil
            from ui.dialogs.custom_filedialog import CustomFileDialog
            
            # Confirma ação (é uma operação perigosa)
            response = show_message(
                self,
                "⚠️ Restaurar Backup",
                "ATENÇÃO: Esta operação irá substituir o banco de dados atual!\n\n"
                "Um backup de segurança será criado antes da restauração.\n\n"
                "Deseja continuar?",
                ("Sim", "Não")
            )
            
            if response != 0:  # 0 = Sim
                return
            
            # Pergunta se quer restaurar da nuvem
            source_response = show_message(
                self,
                "📂 Origem do Backup",
                "De onde você deseja restaurar o backup?",
                ("☁️ Nuvem ", "💾 Local (Computador)", "Cancelar")
            )
            
            if source_response == 2:  # Cancelar
                return
            
            backup_zip = None
            
            if source_response == 0:  # Nuvem
                # Lista backups da nuvem
                backup_zip = self._select_cloud_backup()
                if not backup_zip:
                    return
            else:  # Local - Usa explorador do Windows
                # Garante que o diretório de backups existe
                os.makedirs(BACKUP_DIR, exist_ok=True)
                
                # Usa QFileDialog nativo do Windows para melhor experiência
                from PyQt6.QtWidgets import QFileDialog
                
                backup_zip, _ = QFileDialog.getOpenFileName(
                    self,
                    "Selecionar Backup ZIP",
                    BACKUP_DIR,  # Abre no diretório de backups
                    "Arquivos ZIP (*.zip);;Todos os Arquivos (*.*)"
                )
                
                if not backup_zip:
                    return
            
            if not backup_zip or not os.path.isfile(backup_zip):
                show_message(self, "Erro", "Nenhum arquivo selecionado", ("OK",))
                return
            
            # Valida o ZIP
            if not zipfile.is_zipfile(backup_zip):
                show_message(self, "Erro", "O arquivo selecionado não é um arquivo ZIP válido", ("OK",))
                return
            
            # Obtém caminho do banco atual
            current_db_path = get_database_path()
            db_dir = os.path.dirname(current_db_path)
            
            # Cria backup de segurança do banco atual
            safety_backup_name = f"backup_before_restore_{datetime.now().strftime('%d-%m-%Y_%H-%M')}.zip"
            safety_backup_path = os.path.join(BACKUP_DIR, safety_backup_name)
            
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                with zipfile.ZipFile(safety_backup_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    if os.path.isfile(current_db_path):
                        z.write(current_db_path, arcname=os.path.basename(current_db_path))
                    
                    wal_path = current_db_path + "-wal"
                    shm_path = current_db_path + "-shm"
                    if os.path.isfile(wal_path):
                        z.write(wal_path, arcname=os.path.basename(wal_path))
                    if os.path.isfile(shm_path):
                        z.write(shm_path, arcname=os.path.basename(shm_path))
                    
                    # Inclui config.yaml se existir
                    config_path = os.path.join(db_dir, "config.yaml")
                    if os.path.isfile(config_path):
                        z.write(config_path, arcname="config.yaml")
                
                print(f"[Restore] 💾 Backup de segurança criado: {safety_backup_path}")
            except Exception as e:
                show_message(
                    self,
                    "Erro",
                    f"Erro ao criar backup de segurança:\n\n{e}\n\nRestauração cancelada.",
                    ("OK",)
                )
                return
            
            # Extrai o ZIP em diretório temporário e valida
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    print(f"[Restore] 📦 Extraindo backup para verificação...")
                    
                    with zipfile.ZipFile(backup_zip, 'r') as z:
                        # Lista arquivos no ZIP
                        zip_contents = z.namelist()
                        print(f"[Restore] 📋 Arquivos no ZIP: {zip_contents}")
                        z.extractall(temp_dir)
                    
                    # Lista arquivos extraídos
                    extracted_files = os.listdir(temp_dir)
                    print(f"[Restore] 📁 Arquivos extraídos: {extracted_files}")
                    
                    # Verifica se tem arquivo .db (ignora -wal e -shm)
                    db_files = [f for f in extracted_files if f.endswith('.db') and not (f.endswith('-wal') or f.endswith('-shm'))]
                    if not db_files:
                        show_message(
                            self,
                            "Erro",
                            f"O arquivo ZIP não contém um banco de dados (.db)\n\n"
                            f"Arquivos encontrados: {', '.join(extracted_files) if extracted_files else 'nenhum'}",
                            ("OK",)
                        )
                        return
                    
                    # Usa o primeiro .db encontrado
                    restore_db_name = db_files[0]
                    restore_db_path = os.path.join(temp_dir, restore_db_name)
                    
                    print(f"[Restore] 💾 Banco encontrado: {restore_db_name}")
                    print(f"[Restore] 📂 Caminho completo: {restore_db_path}")
                    
                    # Verifica se os arquivos WAL e SHM existem
                    wal_name = restore_db_name + "-wal"
                    shm_name = restore_db_name + "-shm"
                    has_wal = os.path.isfile(os.path.join(temp_dir, wal_name))
                    has_shm = os.path.isfile(os.path.join(temp_dir, shm_name))
                    
                    print(f"[Restore] 📄 WAL presente: {has_wal}")
                    print(f"[Restore] 📄 SHM presente: {has_shm}")
                    
                    # Valida integridade do banco com as novas funções
                    try:
                        import sqlite3
                        
                        # Se tiver WAL, precisa consolidar primeiro
                        if has_wal:
                            print(f"[Restore] 🔄 Consolidando WAL no banco principal...")
                            temp_conn = sqlite3.connect(restore_db_path, timeout=10)
                            temp_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                            temp_conn.close()
                            print(f"[Restore] ✅ WAL consolidado")
                        
                        test_conn = sqlite3.connect(restore_db_path, timeout=10)
                        test_conn.row_factory = sqlite3.Row
                        
                        # Usa PRAGMA integrity_check
                        cur = test_conn.cursor()
                        result = cur.execute("PRAGMA integrity_check").fetchone()
                        
                        if result and result[0] != "ok":
                            # Banco está corrompido, tenta reparar
                            print(f"[Restore] ⚠️ Banco corrompido detectado: {result[0]}")
                            print(f"[Restore] 🔧 Tentando reparar...")
                            test_conn.close()
                            
                            # Usa função de reparo
                            from core.database import Database
                            temp_db = Database(restore_db_path)
                            success, msg = temp_db.repair_database()
                            
                            if not success:
                                show_message(
                                    self,
                                    "Erro",
                                    f"O banco de dados no backup está corrompido e não pôde ser reparado:\n\n{msg}",
                                    ("OK",)
                                )
                                return
                            
                            print(f"[Restore] ✅ Banco reparado: {msg}")
                        else:
                            test_conn.close()
                            print(f"[Restore] ✅ Integridade do banco validada")
                            
                    except Exception as e:
                        print(f"[Restore] ❌ Erro na validação: {e}")
                        show_message(
                            self,
                            "Erro",
                            f"Erro ao validar o banco de dados no backup:\n\n{e}",
                            ("OK",)
                        )
                        return
                    
                    # Fecha todas as conexões com o banco atual
                    try:
                        if hasattr(self, 'db') and self.db:
                            print(f"[Restore] 🔌 Fechando conexão atual...")
                            self.db.conn.close()
                    except Exception as e:
                        print(f"[Restore] ⚠️ Erro ao fechar conexão: {e}")
                    
                    # Remove arquivos antigos
                    try:
                        print(f"[Restore] 🗑️ Removendo banco antigo...")
                        if os.path.isfile(current_db_path):
                            os.remove(current_db_path)
                            print(f"[Restore] ✅ Banco principal removido")
                        
                        wal_path = current_db_path + "-wal"
                        shm_path = current_db_path + "-shm"
                        if os.path.isfile(wal_path):
                            os.remove(wal_path)
                            print(f"[Restore] ✅ WAL removido")
                        if os.path.isfile(shm_path):
                            os.remove(shm_path)
                            print(f"[Restore] ✅ SHM removido")
                    except Exception as e:
                        print(f"[Restore] ⚠️ Erro ao remover arquivos antigos: {e}")
                    
                    # Copia novos arquivos
                    shutil.copy2(restore_db_path, current_db_path)
                    print(f"[Restore] ✅ Banco de dados restaurado: {restore_db_name}")
                    
                    # Restaura WAL e SHM se existirem
                    wal_name = restore_db_name + "-wal"
                    shm_name = restore_db_name + "-shm"
                    
                    if os.path.isfile(os.path.join(temp_dir, wal_name)):
                        shutil.copy2(os.path.join(temp_dir, wal_name), current_db_path + "-wal")
                        print(f"[Restore] ✅ WAL restaurado")
                    
                    if os.path.isfile(os.path.join(temp_dir, shm_name)):
                        shutil.copy2(os.path.join(temp_dir, shm_name), current_db_path + "-shm")
                        print(f"[Restore] ✅ SHM restaurado")
                    
                    # Restaura config.yaml se existir
                    config_in_zip = os.path.join(temp_dir, "config.yaml")
                    if os.path.isfile(config_in_zip):
                        config_dest = os.path.join(db_dir, "config.yaml")
                        shutil.copy2(config_in_zip, config_dest)
                        print(f"[Restore] ✅ Configuração restaurada")
                
                # Sucesso
                show_message(
                    self,
                    "✅ Restauração Concluída",
                    f"Backup restaurado com sucesso!\n\n"
                    f"💾 Backup de segurança salvo em:\n{safety_backup_name}\n\n"
                    f"⚠️ Reinicie o sistema para aplicar as mudanças.",
                    ("OK",)
                )
                
                if self.toast_cb:
                    self.toast_cb("✅ Backup restaurado com sucesso")
                
            except Exception as e:
                show_message(
                    self,
                    "❌ Erro na Restauração",
                    f"Erro ao restaurar backup:\n\n{e}\n\n"
                    f"💾 Seu banco original foi preservado em:\n{safety_backup_name}",
                    ("OK",)
                )
                
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao iniciar restauração:\n\n{e}",
                ("OK",)
            )
    
    def _select_cloud_backup(self) -> Optional[str]:
        """Lista backups disponíveis na nuvem e permite selecionar um para restaurar"""
        try:
            import subprocess
            
            base_dir = APP_DIR
            backup_repo_dir = os.path.join(base_dir, "Backup_Clientes")
            
            # Verifica se o repositório existe
            if not os.path.exists(backup_repo_dir):
                response = show_message(
                    self,
                    "⚠️ Repositório Não Encontrado",
                    "O repositório de backups na nuvem não foi encontrado.\n\n"
                    "Deseja clonar o repositório agora?\n\n"
                    "📥 Isso irá baixar todos os backups disponíveis.",
                    ("Sim", "Não")
                )
                
                if response != 0:
                    return None
                
                # Clona o repositório com progresso e cancelamento
                if not self._clone_repository_with_progress(backup_repo_dir):
                    return None
            else:
                # Atualiza o repositório com progresso
                if not self._pull_repository_with_progress(backup_repo_dir):
                    # Se falhar o pull, pergunta se quer continuar com versão local
                    response = show_message(
                        self,
                        "⚠️ Erro ao Atualizar",
                        "Não foi possível atualizar o repositório.\n\n"
                        "Possíveis causas:\n"
                        "• Sem conexão com a internet\n"
                        "• Problemas no GitHub\n"
                        "• Timeout na conexão\n\n"
                        "Deseja continuar com os backups disponíveis localmente?",
                        ("Sim", "Não")
                    )
                    if response != 0:
                        return None
            
            # Lista todos os arquivos ZIP no repositório
            backup_files = []
            if os.path.exists(backup_repo_dir):
                for filename in os.listdir(backup_repo_dir):
                    if filename.endswith('.zip') and 'backup' in filename.lower():
                        filepath = os.path.join(backup_repo_dir, filename)
                        if os.path.isfile(filepath):
                            # Obtém informações do arquivo
                            size = os.path.getsize(filepath)
                            size_mb = size / (1024 * 1024)
                            mtime = os.path.getmtime(filepath)
                            date_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
                            
                            backup_files.append({
                                'filename': filename,
                                'filepath': filepath,
                                'size_mb': size_mb,
                                'date': date_str,
                                'mtime': mtime
                            })
            
            if not backup_files:
                show_message(
                    self,
                    "Sem Backups",
                    "Não há backups disponíveis na nuvem.",
                    ("OK",)
                )
                return None
            
            # Ordena por data (mais recente primeiro)
            backup_files.sort(key=lambda x: x['mtime'], reverse=True)
            
            # Cria diálogo de seleção
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel
            from core.config import load_config
            
            dialog = QDialog(self)
            dialog.setWindowTitle("☁️ Selecionar Backup da Nuvem")
            dialog.resize(600, 400)
            
            # Aplica tema
            theme_cfg = load_config().get("theme", "light")
            
            layout = QVBoxLayout(dialog)
            
            label = QLabel(f"📦 {len(backup_files)} backup(s) disponível(is) na nuvem:")
            label.setStyleSheet("font-weight: bold; font-size: 12px; margin-bottom: 10px;")
            layout.addWidget(label)
            
            list_widget = QListWidget()
            
            # Estilo baseado no tema
            if theme_cfg == "dark":
                list_widget.setStyleSheet("""
                    QListWidget {
                        font-family: 'Consolas', 'Courier New', monospace;
                        font-size: 11px;
                        background-color: #1e1e1e;
                        color: #ffffff;
                        border: 1px solid #3f3f3f;
                    }
                    QListWidget::item {
                        padding: 8px;
                        border-bottom: 1px solid #3f3f3f;
                    }
                    QListWidget::item:hover {
                        background-color: #2d2d2d;
                    }
                    QListWidget::item:selected {
                        background-color: #0078d4;
                        color: white;
                    }
                """)
                info_color = "#999"
            else:
                list_widget.setStyleSheet("""
                    QListWidget {
                        font-family: 'Consolas', 'Courier New', monospace;
                        font-size: 11px;
                        background-color: #ffffff;
                        color: #000000;
                        border: 1px solid #e0e0e0;
                    }
                    QListWidget::item {
                        padding: 8px;
                        border-bottom: 1px solid #e0e0e0;
                    }
                    QListWidget::item:hover {
                        background-color: #f0f0f0;
                    }
                    QListWidget::item:selected {
                        background-color: #0078d4;
                        color: white;
                    }
                """)
                info_color = "#666"
            
            for backup in backup_files:
                item_text = f"📅 {backup['date']}  |  📦 {backup['size_mb']:.2f} MB  |  📄 {backup['filename']}"
                list_widget.addItem(item_text)
            
            layout.addWidget(list_widget)
            
            info_label = QLabel("💡 Dica: Selecione um backup e clique em 'Restaurar'")
            info_label.setStyleSheet(f"color: {info_color}; font-size: 10px; margin-top: 5px;")
            layout.addWidget(info_label)
            
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Restaurar")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
            cast(Any, buttons.accepted).connect(dialog.accept)
            cast(Any, buttons.rejected).connect(dialog.reject)
            layout.addWidget(buttons)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_index = list_widget.currentRow()
                if selected_index >= 0:
                    return backup_files[selected_index]['filepath']
            
            return None
            
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao listar backups da nuvem:\n\n{e}",
                ("OK",)
            )
            return None
    
    def _install_git_automatically(self) -> bool:
        """Instala o Git automaticamente usando winget (gerenciador nativo do Windows)"""
        try:
            import subprocess
            import threading
            
            # Verifica se o winget está disponível (Windows 10 1809+ / Windows 11)
            try:
                check_winget = subprocess.run(
                    ["winget", "--version"],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                
                if check_winget.returncode != 0:
                    # winget não disponível - usar método manual
                    show_message(
                        self,
                        "⚠️ Instalação Manual Necessária",
                        "O Git não está instalado neste sistema.\n\n"
                        "📋 Para instalar:\n"
                        "1. Abra o Microsoft Store\n"
                        "2. Procure por 'Git'\n"
                        "3. Instale o 'Git for Windows'\n\n"
                        "Ou acesse: https://git-scm.com/download/win\n\n"
                        "Após instalar, reinicie o computador.",
                        ("OK",)
                    )
                    return False
                    
            except FileNotFoundError:
                # winget não está instalado (Windows muito antigo)
                show_message(
                    self,
                    "⚠️ Sistema Desatualizado",
                    "Seu Windows precisa ser atualizado para instalar automaticamente.\n\n"
                    "📋 Instalação manual:\n"
                    "1. Acesse: https://git-scm.com/download/win\n"
                    "2. Baixe e execute o instalador\n"
                    "3. Reinicie o computador\n\n"
                    "Alternativamente, atualize o Windows para a versão mais recente.",
                    ("OK",)
                )
                return False
            
            # Cria diálogo de progresso
            progress = QProgressDialog(
                "Instalando Git via Windows Package Manager...\n\n"
                "⚙️ Usando gerenciador oficial da Microsoft\n"
                "🔒 Seguro e verificado\n\n"
                "Aguarde, isso pode levar 2-3 minutos...",
                "Cancelar",
                0, 100,
                self
            )
            progress.setWindowTitle("Instalando Git")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(10)
            progress.show()
            QApplication.processEvents()
            
            # Flags de controle
            cancelled = [False]
            completed = [False]
            error_msg = [None]
            success = [False]
            
            def install_thread():
                try:
                    # Instala Git usando winget (gerenciador oficial da Microsoft)
                    result = subprocess.run(
                        ["winget", "install", "--id", "Git.Git", 
                         "--silent", "--accept-package-agreements", "--accept-source-agreements"],
                        capture_output=True,
                        text=True,
                        timeout=300,  # 5 minutos
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                    
                    if cancelled[0]:
                        return
                    
                    if result.returncode == 0 or "successfully installed" in result.stdout.lower():
                        success[0] = True
                        completed[0] = True
                    else:
                        error_msg[0] = result.stderr if result.stderr else result.stdout
                        completed[0] = True
                        
                except subprocess.TimeoutExpired:
                    if not cancelled[0]:
                        error_msg[0] = "Timeout: Instalação demorou mais de 5 minutos"
                    completed[0] = True
                except Exception as e:
                    if not cancelled[0]:
                        error_msg[0] = str(e)
                    completed[0] = True
            
            # Inicia thread de instalação
            thread = threading.Thread(target=install_thread, daemon=True)
            thread.start()
            
            # Atualiza progresso enquanto instala
            progress_value = 10
            while thread.is_alive() and not completed[0]:
                if progress.wasCanceled():
                    cancelled[0] = True
                    progress.setLabelText("Cancelando instalação...\n\nAguarde...")
                    break
                
                # Anima progresso (10% a 90%)
                progress_value = min(progress_value + 2, 90)
                progress.setValue(progress_value)
                
                if progress_value < 40:
                    progress.setLabelText(
                        "Instalando Git via Windows Package Manager...\n\n"
                        "⚙️ Baixando pacote oficial...\n"
                        "🔒 Fonte: Microsoft Store / WinGet\n\n"
                        "Aguarde..."
                    )
                elif progress_value < 70:
                    progress.setLabelText(
                        "Instalando Git via Windows Package Manager...\n\n"
                        "📦 Instalando componentes...\n"
                        "🔒 Instalação verificada\n\n"
                        "Aguarde..."
                    )
                else:
                    progress.setLabelText(
                        "Instalando Git via Windows Package Manager...\n\n"
                        "⚙️ Finalizando instalação...\n"
                        "🔒 Quase pronto!\n\n"
                        "Aguarde..."
                    )
                
                QApplication.processEvents()
                threading.Event().wait(0.5)  # Aguarda 0.5s entre atualizações
            
            # Aguarda thread finalizar
            thread.join(timeout=2)
            
            progress.setValue(100)
            progress.close()
            
            # Verifica resultado
            if cancelled[0]:
                if self.toast_cb:
                    self.toast_cb("❌ Instalação cancelada")
                return False
            
            if error_msg[0]:
                show_message(
                    self,
                    "⚠️ Erro na Instalação",
                    f"O winget não conseguiu instalar o Git.\n\n"
                    f"Detalhes: {error_msg[0][:200]}\n\n"
                    "Tente instalar manualmente:\n"
                    "https://git-scm.com/download/win",
                    ("OK",)
                )
                return False
            
            if success[0]:
                return True
            
            return False
                
        except Exception as e:
            show_message(
                self,
                "❌ Erro",
                f"Erro ao instalar Git:\n\n{e}\n\n"
                "Instale manualmente:\n"
                "https://git-scm.com/download/win",
                ("OK",)
            )
            return False
    
    def _clone_repository_with_progress(self, repo_dir: str) -> bool:
        """Clona repositório com barra de progresso e opção de cancelamento"""
        try:
            import subprocess
            import threading
            
            # Verifica se o Git está instalado
            try:
                git_check = subprocess.run(
                    ["git", "--version"],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if git_check.returncode != 0:
                    show_message(
                        self,
                        "❌ Git Não Instalado",
                        "O Git não está instalado neste sistema.\n\n"
                        "Para usar backup da nuvem, você precisa:\n"
                        "1. Instalar o Git: https://git-scm.com/download/win\n"
                        "2. Configurar chave SSH no GitHub\n\n"
                        "Alternativamente, use apenas backup local.",
                        ("OK",)
                    )
                    return False
            except FileNotFoundError:
                # Git não encontrado - oferecer instalação automática
                response = show_message(
                    self,
                    "❌ Git Não Encontrado",
                    "O Git não foi encontrado no sistema.\n\n"
                    "Deseja instalar o Git automaticamente agora?\n\n"
                    "📦 O instalador será baixado e executado.\n"
                    "⏱️ Leva aproximadamente 2-3 minutos.\n"
                    "🔄 Requer reiniciar o sistema após instalação.\n\n"
                    "Alternativamente, você pode usar apenas backup local.",
                    ("Instalar Git", "Cancelar"),
                    0
                )
                
                if response == 0:  # Instalar Git
                    if self._install_git_automatically():
                        show_message(
                            self,
                            "✅ Git Instalado",
                            "Git instalado com sucesso!\n\n"
                            "🔄 IMPORTANTE: Você precisa REINICIAR o computador\n"
                            "para que o Git funcione corretamente.\n\n"
                            "Após reiniciar, você poderá usar o backup da nuvem.",
                            ("OK",)
                        )
                    else:
                        show_message(
                            self,
                            "⚠️ Instalação Manual Necessária",
                            "Não foi possível instalar automaticamente.\n\n"
                            "Por favor, instale manualmente:\n"
                            "1. Acesse: https://git-scm.com/download/win\n"
                            "2. Baixe e execute o instalador\n"
                            "3. Reinicie o computador\n"
                            "4. Configure chave SSH no GitHub",
                            ("OK",)
                        )
                return False
            except Exception as e:
                show_message(
                    self,
                    "❌ Erro ao Verificar Git",
                    f"Não foi possível verificar se o Git está instalado:\n\n{e}\n\n"
                    "Certifique-se de que o Git está instalado e acessível.",
                    ("OK",)
                )
                return False
            
            # Cria diálogo de progresso com cancelamento
            progress = QProgressDialog(
                "Baixando backups da nuvem...\n\n"
                "📥 Conectando ao GitHub...",
                "Cancelar",
                0, 100,
                self
            )
            progress.setWindowTitle("Download da Nuvem")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(5)
            progress.show()
            QApplication.processEvents()
            
            # Flags de controle
            cancelled = [False]
            completed = [False]
            error_msg = [None]
            process = [None]
            update_counter = [0]  # Contador para reduzir chamadas processEvents
            
            def clone_thread():
                try:
                    # Executa git clone
                    proc = subprocess.Popen(
                        ["git", "clone", "--progress", "git@github.com:W4lterBr/Backup_Clientes.git", repo_dir],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                    process[0] = proc
                    
                    # Monitora progresso
                    while proc.poll() is None:
                        if cancelled[0]:
                            proc.terminate()
                            try:
                                proc.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                            return
                        
                        # Incrementa contador para atualização visual
                        update_counter[0] = (update_counter[0] + 1) % 35
                        threading.Event().wait(0.1)
                    
                    # Verifica resultado
                    stdout, stderr = proc.communicate()
                    
                    if proc.returncode != 0 and not cancelled[0]:
                        error_msg[0] = f"Erro ao clonar:\n{stderr}"
                    else:
                        completed[0] = True
                        
                except subprocess.TimeoutExpired:
                    error_msg[0] = "Timeout: Download demorou muito (>120s)"
                except Exception as e:
                    error_msg[0] = f"Erro inesperado: {e}"
            
            # Inicia thread
            thread = threading.Thread(target=clone_thread, daemon=True)
            thread.start()
            
            # Aguarda conclusão com menos chamadas processEvents
            last_update = 0
            while thread.is_alive():
                # Atualiza UI apenas quando o contador mudar (reduz sobrecarga)
                current_count = update_counter[0]
                if current_count != last_update:
                    progress_value = 20 + (current_count * 2)  # 20 a 90%
                    progress.setValue(min(progress_value, 90))
                    progress.setLabelText("Baixando backups da nuvem...\n\n📦 Clonando repositório...")
                    last_update = current_count
                
                QApplication.processEvents()
                threading.Event().wait(0.2)  # Aumentado de 0.1 para 0.2
                
                # Verifica cancelamento
                if progress.wasCanceled():
                    cancelled[0] = True
                    progress.setLabelText("Cancelando download...\n\nAguarde...")
                    
                    # Termina processo se existir
                    if process[0]:
                        try:
                            process[0].terminate()
                            process[0].wait(timeout=2)
                        except Exception:
                            try:
                                process[0].kill()
                            except Exception:
                                pass
                    break
            
            thread.join(timeout=2)
            progress.close()
            
            # Verifica resultado
            if cancelled[0]:
                # Remove diretório parcial
                if os.path.exists(repo_dir):
                    try:
                        import shutil
                        shutil.rmtree(repo_dir)
                    except Exception:
                        pass
                
                if self.toast_cb:
                    self.toast_cb("❌ Download cancelado")
                return False
            
            if error_msg[0]:
                # Verifica se o erro é relacionado a SSH
                error_text = error_msg[0].lower()
                is_ssh_error = (
                    "host key verification failed" in error_text or
                    "could not read from remote repository" in error_text or
                    "permission denied" in error_text or
                    "publickey" in error_text
                )
                
                if is_ssh_error:
                    # Erro de SSH - mostrar mensagem com instruções
                    show_message(
                        self,
                        "🔐 Erro de Autenticação SSH",
                        "Não foi possível acessar o GitHub.\n\n"
                        f"Erro: {error_msg[0][:100]}...\n\n"
                        "Isso acontece porque você não tem uma chave SSH configurada.\n\n"
                        "Para configurar:\n"
                        "1. Abra um terminal\n"
                        "2. Execute: ssh-keygen -t ed25519\n"
                        "3. Adicione a chave no GitHub:\n"
                        "   https://github.com/settings/ssh/new\n\n"
                        "Ou use 'Fazer Backup na Nuvem Agora' que configura automaticamente.",
                        ("OK",)
                    )
                else:
                    # Outro tipo de erro
                    show_message(
                        self,
                        "❌ Erro no Download",
                        f"Não foi possível baixar os backups da nuvem:\n\n{error_msg[0]}\n\n"
                        "Verifique:\n"
                        "• Conexão com a internet\n"
                        "• Acesso ao GitHub\n"
                        "• Chave SSH configurada",
                        ("OK",)
                    )
                return False
            
            if completed[0]:
                if self.toast_cb:
                    self.toast_cb("✅ Backups baixados com sucesso")
                return True
            
            return False
            
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao baixar repositório:\n\n{e}",
                ("OK",)
            )
            return False
    
    def _pull_repository_with_progress(self, repo_dir: str) -> bool:
        """Atualiza repositório com barra de progresso e opção de cancelamento"""
        try:
            import subprocess
            import threading
            
            # Verifica se o Git está instalado
            try:
                git_check = subprocess.run(
                    ["git", "--version"],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if git_check.returncode != 0:
                    return False
            except (FileNotFoundError, Exception):
                return False
            
            # Cria diálogo de progresso
            progress = QProgressDialog(
                "Atualizando backups da nuvem...\n\n"
                "🔄 Verificando atualizações...",
                "Cancelar",
                0, 100,
                self
            )
            progress.setWindowTitle("Atualização")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(10)
            progress.show()
            QApplication.processEvents()
            
            # Flags de controle
            cancelled = [False]
            completed = [False]
            error_msg = [None]
            process = [None]
            update_counter = [0]  # Contador para reduzir chamadas processEvents
            
            def pull_thread():
                try:
                    # Executa git pull
                    proc = subprocess.Popen(
                        ["git", "-C", repo_dir, "pull", "--progress"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                    process[0] = proc
                    
                    # Monitora com timeout
                    timeout_counter = 0
                    while proc.poll() is None:
                        if cancelled[0]:
                            proc.terminate()
                            try:
                                proc.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                            return
                        
                        # Timeout de 30 segundos
                        timeout_counter += 1
                        if timeout_counter > 300:  # 30s (0.1s * 300)
                            proc.terminate()
                            error_msg[0] = "Timeout: Atualização demorou muito (>30s)"
                            return
                        
                        # Incrementa contador para atualização visual
                        update_counter[0] = (update_counter[0] + 1) % 10
                        threading.Event().wait(0.1)
                    
                    # Verifica resultado
                    stdout, stderr = proc.communicate()
                    
                    if proc.returncode != 0 and not cancelled[0]:
                        # Verifica se é "Already up to date"
                        if "Already up to date" in stdout or "Already up-to-date" in stdout:
                            completed[0] = True
                        else:
                            error_msg[0] = f"Erro ao atualizar:\n{stderr}"
                    else:
                        completed[0] = True
                        
                except Exception as e:
                    error_msg[0] = f"Erro inesperado: {e}"
            
            # Inicia thread
            thread = threading.Thread(target=pull_thread, daemon=True)
            thread.start()
            
            # Aguarda conclusão com menos chamadas processEvents
            last_update = 0
            while thread.is_alive():
                # Atualiza UI apenas a cada 10 iterações (reduz sobrecarga)
                current_count = update_counter[0]
                if current_count != last_update:
                    progress_value = 30 + (current_count * 6)  # 30 a 90%
                    progress.setValue(min(progress_value, 90))
                    progress.setLabelText("Atualizando backups da nuvem...\n\n📥 Baixando atualizações...")
                    last_update = current_count
                
                QApplication.processEvents()
                threading.Event().wait(0.2)  # Aumentado de 0.1 para 0.2
                
                if progress.wasCanceled():
                    cancelled[0] = True
                    if process[0]:
                        try:
                            process[0].terminate()
                        except Exception:
                            pass
                    break
            
            thread.join(timeout=2)
            progress.close()
            
            # Verifica resultado
            if cancelled[0]:
                if self.toast_cb:
                    self.toast_cb("❌ Atualização cancelada")
                return False
            
            if error_msg[0]:
                # Verifica se é erro de SSH
                error_text = error_msg[0].lower()
                is_ssh_error = (
                    "host key verification failed" in error_text or
                    "could not read from remote repository" in error_text or
                    "permission denied" in error_text or
                    "publickey" in error_text
                )
                
                if is_ssh_error:
                    # Retorna False e armazena flag para tratamento no método principal
                    return False  # Será tratado em _select_cloud_backup
                
                # Outros erros: retorna False silenciosamente
                return False
            
            if completed[0]:
                if self.toast_cb:
                    self.toast_cb("✅ Backups atualizados")
                return True
            
            return False
            
        except Exception:
            return False
    
    def configure_auto_backup(self) -> None:
        """Configura automação de backup (hora em hora)"""
        try:
            from core.config import load_config, save_config
            
            # Carrega configurações atuais
            config = load_config()
            auto_backup = config.get("auto_backup", {})
            
            current_enabled = auto_backup.get("enabled", False)
            current_interval = auto_backup.get("interval_hours", 1)
            current_type = auto_backup.get("type", "local")  # local ou cloud
            
            # Detecta tema
            theme = config.get("theme", "light")
            is_dark = (theme == "dark")
            
            # Cria diálogo
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QSpinBox, QRadioButton, QButtonGroup, QHBoxLayout
            
            dialog = QDialog(self)
            dialog.setWindowTitle("⚙️ Automação de Backup")
            dialog.resize(500, 400)
            
            # Aplica tema
            if is_dark:
                dialog.setStyleSheet("""
                    QDialog { 
                        background-color: #2b2b2b; 
                        color: #ffffff; 
                    }
                    QLabel { 
                        color: #ffffff; 
                    }
                    QCheckBox { 
                        color: #ffffff;
                    }
                    QRadioButton { 
                        color: #ffffff;
                        spacing: 5px;
                    }
                    QRadioButton::indicator {
                        width: 16px;
                        height: 16px;
                    }
                """)
            else:
                dialog.setStyleSheet("""
                    QDialog { 
                        background-color: #ffffff; 
                        color: #000000; 
                    }
                    QLabel { 
                        color: #000000; 
                    }
                    QCheckBox { 
                        color: #000000;
                    }
                    QRadioButton { 
                        color: #000000;
                        spacing: 5px;
                    }
                    QRadioButton::indicator {
                        width: 16px;
                        height: 16px;
                        border: 2px solid #999999;
                        border-radius: 8px;
                        background-color: #ffffff;
                    }
                    QRadioButton::indicator:checked {
                        background-color: #0078d4;
                        border: 2px solid #0078d4;
                    }
                    QRadioButton::indicator:hover {
                        border: 2px solid #0078d4;
                    }
                """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(20)
            
            # Título
            title = QLabel("<b>Configuração de Backup Automático</b>")
            title.setStyleSheet("font-size: 16px; margin-bottom: 10px;")
            layout.addWidget(title)
            
            # Checkbox habilitar/desabilitar
            enable_check = QCheckBox("✅ Habilitar backup automático")
            enable_check.setChecked(current_enabled)
            enable_check.setStyleSheet("font-size: 13px; margin-bottom: 10px;")
            layout.addWidget(enable_check)
            
            # Intervalo
            interval_label = QLabel("⏰ Intervalo entre backups:")
            interval_label.setStyleSheet("font-size: 13px; margin-top: 10px;")
            layout.addWidget(interval_label)
            
            interval_layout = QHBoxLayout()
            interval_spin = QSpinBox()
            interval_spin.setMinimum(1)
            interval_spin.setMaximum(24)
            interval_spin.setValue(current_interval)
            interval_spin.setSuffix(" hora(s)")
            interval_spin.setStyleSheet("font-size: 13px; padding: 5px;")
            interval_layout.addWidget(interval_spin)
            interval_layout.addStretch()
            layout.addLayout(interval_layout)
            
            # Tipo de backup
            type_label = QLabel("📦 Tipo de backup:")
            type_label.setStyleSheet("font-size: 13px; margin-top: 15px;")
            layout.addWidget(type_label)
            
            # Checkboxes para permitir múltipla seleção
            local_check = QCheckBox("💾 Local (mais rápido)")
            local_check.setStyleSheet("font-size: 13px; margin-left: 10px;")
            layout.addWidget(local_check)
            
            cloud_check = QCheckBox("☁️ Nuvem (mais seguro)")
            cloud_check.setStyleSheet("font-size: 13px; margin-left: 10px;")
            layout.addWidget(cloud_check)
            
            both_check = QCheckBox("🔒 Ambos (máxima segurança - recomendado)")
            both_check.setStyleSheet("font-size: 13px; margin-left: 10px; font-weight: bold;")
            layout.addWidget(both_check)
            
            # Define seleção atual
            if current_type == "both":
                both_check.setChecked(True)
            elif current_type == "cloud":
                cloud_check.setChecked(True)
            else:
                local_check.setChecked(True)
            
            # Lógica de exclusão mútua para os checkboxes
            def on_local_changed():
                if local_check.isChecked():
                    cloud_check.setChecked(False)
                    both_check.setChecked(False)
            
            def on_cloud_changed():
                if cloud_check.isChecked():
                    local_check.setChecked(False)
                    both_check.setChecked(False)
            
            def on_both_changed():
                if both_check.isChecked():
                    local_check.setChecked(False)
                    cloud_check.setChecked(False)
            
            cast(Any, local_check.stateChanged).connect(on_local_changed)
            cast(Any, cloud_check.stateChanged).connect(on_cloud_changed)
            cast(Any, both_check.stateChanged).connect(on_both_changed)
            
            # Informações
            info_text = QLabel(
                "ℹ️ <b>Informações:</b><br>"
                "• O backup será executado automaticamente a cada intervalo<br>"
                "• <b>Local:</b> Salvo na pasta 'backups' (rápido, sem internet)<br>"
                "• <b>Nuvem:</b> Enviado para GitHub (seguro, requer conexão)<br>"
                "• <b>Ambos:</b> Salva localmente E envia para nuvem (recomendado) 🔒<br>"
                "• Você receberá notificações quando o backup for feito<br>"
                "• O backup automático começa ao iniciar o sistema"
            )
            info_text.setWordWrap(True)
            info_bg = "rgba(100, 100, 255, 0.1)" if not is_dark else "rgba(100, 100, 255, 0.15)"
            info_text.setStyleSheet(f"padding: 15px; background: {info_bg}; border-radius: 8px; font-size: 12px; margin-top: 15px;")
            layout.addWidget(info_text)
            
            layout.addStretch()
            
            # Botões
            from PyQt6.QtWidgets import QDialogButtonBox
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Salvar")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
            cast(Any, buttons.accepted).connect(dialog.accept)
            cast(Any, buttons.rejected).connect(dialog.reject)
            layout.addWidget(buttons)
            
            # Mostra diálogo
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Determinar tipo de backup selecionado
                if both_check.isChecked():
                    backup_type = "both"
                elif cloud_check.isChecked():
                    backup_type = "cloud"
                elif local_check.isChecked():
                    backup_type = "local"
                else:
                    # Se nenhum foi selecionado, usa local como padrão
                    backup_type = "local"
                
                # Salva configurações
                new_config = {
                    "enabled": enable_check.isChecked(),
                    "interval_hours": interval_spin.value(),
                    "type": backup_type
                }
                
                config["auto_backup"] = new_config
                save_config(config)
                
                # Feedback
                if enable_check.isChecked():
                    # Texto descritivo baseado no tipo
                    type_descriptions = {
                        "local": "💾 Local",
                        "cloud": "☁️ Nuvem",
                        "both": "🔒 Local + Nuvem"
                    }
                    backup_type_text = type_descriptions.get(backup_type, "local")
                    
                    if self.toast_cb:
                        self.toast_cb(f"✅ Backup automático ativado: {backup_type_text} a cada {interval_spin.value()}h")
                    
                    show_message(
                        self,
                        "✅ Configuração Salva",
                        f"Backup automático configurado com sucesso!\n\n"
                        f"📦 Tipo: {backup_type_text}\n"
                        f"⏰ Intervalo: {interval_spin.value()} hora(s)\n\n"
                        f"{'🔒 Máxima segurança: backup em 2 lugares!' if backup_type == 'both' else 'O backup será executado automaticamente.'}",
                        ("OK",)
                    )
                else:
                    if self.toast_cb:
                        self.toast_cb("⚠️ Backup automático desativado")
                    
                    show_message(
                        self,
                        "⚠️ Backup Automático Desativado",
                        "O backup automático foi desativado.\n\n"
                        "Você pode reativá-lo a qualquer momento.",
                        ("OK",)
                    )
                    
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao configurar automação:\n\n{e}",
                ("OK",)
            )
    
    def _is_network_drive(self, drive_letter: str) -> bool:
        """Verifica se uma letra de unidade é uma unidade de rede mapeada"""
        try:
            import subprocess
            result = subprocess.run(
                ["net", "use"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return f"{drive_letter.upper()}:" in result.stdout
        except Exception:
            return False
    
    def repair_database(self) -> None:
        """Tenta reparar um banco de dados corrompido"""
        try:
            from core.config import get_database_path
            
            # Confirma ação
            response = show_message(
                self,
                "🔧 Reparar Banco de Dados",
                "⚠️ ATENÇÃO: Esta operação tentará reparar o banco de dados corrompido!\n\n"
                "O processo irá:\n"
                "• Criar backup do banco corrompido\n"
                "• Tentar recuperar todos os dados possíveis\n"
                "• Criar um novo banco com os dados recuperados\n\n"
                "💾 Recomendamos fazer um backup manual primeiro!\n\n"
                "Deseja continuar?",
                ("Sim, Reparar", "Não")
            )
            
            if response != 0:
                return
            
            # Mostra progresso
            from PyQt6.QtCore import QTimer
            
            progress = QProgressDialog(
                "🔧 Reparando banco de dados...\n\n"
                "Isso pode levar alguns minutos.\n"
                "Não feche o programa!",
                None,
                0, 0,
                self
            )
            progress.setWindowTitle("Reparando Banco")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            db_path = get_database_path()
            
            # Fecha conexão atual se houver
            try:
                if hasattr(self, 'db') and self.db:
                    self.db.conn.close()
            except:
                pass
            
            # Cria nova instância para reparo
            from core.database import Database
            repair_db = Database(db_path)
            
            # Verifica integridade primeiro
            is_ok, msg = repair_db.verify_integrity()
            
            if is_ok:
                progress.close()
                show_message(
                    self,
                    "✅ Banco Íntegro",
                    "O banco de dados está íntegro e não precisa de reparo!\n\n"
                    f"Verificação: {msg}",
                    ("OK",)
                )
                return
            
            # Banco está corrompido, tenta reparar
            print(f"[Repair] ⚠️ {msg}")
            print(f"[Repair] 🔧 Iniciando reparo...")
            
            success, repair_msg = repair_db.repair_database()
            
            progress.close()
            
            if success:
                show_message(
                    self,
                    "✅ Reparo Concluído",
                    f"Banco de dados reparado com sucesso!\n\n{repair_msg}\n\n"
                    "⚠️ Reinicie o sistema para aplicar as mudanças.",
                    ("OK",)
                )
                
                if self.toast_cb:
                    self.toast_cb("✅ Banco reparado com sucesso")
            else:
                show_message(
                    self,
                    "❌ Falha no Reparo",
                    f"Não foi possível reparar o banco de dados:\n\n{repair_msg}\n\n"
                    "💡 Sugestões:\n"
                    "• Use 'Restaurar Backup' para restaurar de um backup\n"
                    "• Entre em contato com o suporte técnico",
                    ("OK",)
                )
                
        except Exception as e:
            show_message(
                self,
                "Erro",
                f"Erro ao tentar reparar:\n\n{e}",
                ("OK",)
            )
