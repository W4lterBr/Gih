# settings_page.py
# Página de configurações do sistema

from PyQt6.QtWidgets import QWidget

from PyQt6.QtWidgets import (
    QVBoxLayout, QPushButton, QLabel, QGroupBox, QProgressBar,
    QHBoxLayout, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, QTimer
from core.config import load_config, save_config, QSS_POPUP_DARK, QSS_POPUP_LIGHT
from Confeitaria import qss_dark, qss_light

# Importa módulo de atualização
try:
    from core.updater import (
        check_for_updates, UpdaterThread, get_current_version,
        compare_versions, update_version_globally
    )
    UPDATER_AVAILABLE = True
except ImportError:
    UPDATER_AVAILABLE = False
    print("⚠️ Módulo de atualização não disponível")


class UpdateDialog(QDialog):
    """Diálogo de progresso da atualização"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atualizando Sistema")
        self.setModal(True)
        self.setFixedSize(500, 150)
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel("Preparando atualização...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        
        self.details = QLabel("")
        self.details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details.setStyleSheet("color: #6b7280; font-size: 11px;")
        layout.addWidget(self.details)
        
        # Aplica tema
        config = load_config()
        theme = config.get("theme", "light")
        if theme == "dark":
            self.setStyleSheet(QSS_POPUP_DARK)
        else:
            self.setStyleSheet(QSS_POPUP_LIGHT)
    
    def update_progress(self, percent: int, message: str):
        """Atualiza o progresso"""
        self.progress.setValue(percent)
        self.label.setText(message)
        if percent < 100:
            self.details.setText(f"{percent}% concluído")
        else:
            self.details.setText("Concluído!")


class SettingsPage(QWidget):
    def __init__(self, app=None, parent_window=None, toast_cb=None):
        super().__init__()
        self.app = app
        self.parent_window = parent_window
        self.toast_cb = toast_cb
        self.update_thread = None
        
        layout = QVBoxLayout(self)
        
        # === SEÇÃO: TEMA ===
        theme_group = QGroupBox("🎨 Aparência")
        theme_layout = QVBoxLayout()
        
        self.lbl_tema = QLabel("Tema atual: —")
        theme_layout.addWidget(self.lbl_tema)
        
        btn_layout = QHBoxLayout()
        self.btn_dark = QPushButton("Tema Escuro")
        self.btn_light = QPushButton("Tema Claro")
        btn_layout.addWidget(self.btn_dark)
        btn_layout.addWidget(self.btn_light)
        theme_layout.addLayout(btn_layout)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # === SEÇÃO: ATUALIZAÇÕES ===
        if UPDATER_AVAILABLE:
            update_group = QGroupBox("🔄 Atualizações")
            update_layout = QVBoxLayout()
            
            # Informações de versão
            self.lbl_version = QLabel(f"Versão instalada: v{get_current_version()}")
            self.lbl_version.setStyleSheet("font-weight: bold;")
            update_layout.addWidget(self.lbl_version)
            
            self.lbl_update_status = QLabel("Verificando atualizações...")
            self.lbl_update_status.setStyleSheet("color: #6b7280;")
            update_layout.addWidget(self.lbl_update_status)
            
            # Botões de atualização
            btn_update_layout = QHBoxLayout()
            
            self.btn_check_update = QPushButton("🔍 Verificar Atualizações")
            self.btn_check_update.clicked.connect(self.check_updates)
            btn_update_layout.addWidget(self.btn_check_update)
            
            self.btn_install_update = QPushButton("⬇️ Instalar Atualização")
            self.btn_install_update.clicked.connect(self.install_update)
            self.btn_install_update.setEnabled(False)
            self.btn_install_update.setStyleSheet("""
                QPushButton {
                    background: #10b981;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #059669;
                }
                QPushButton:disabled {
                    background: #6b7280;
                    color: #d1d5db;
                }
            """)
            btn_update_layout.addWidget(self.btn_install_update)
            
            update_layout.addLayout(btn_update_layout)
            
            # Changelog
            self.lbl_changelog = QLabel("")
            self.lbl_changelog.setWordWrap(True)
            self.lbl_changelog.setStyleSheet("""
                QLabel {
                    background: rgba(59, 130, 246, 0.1);
                    border: 1px solid rgba(59, 130, 246, 0.3);
                    border-radius: 8px;
                    padding: 10px;
                    margin-top: 10px;
                }
            """)
            self.lbl_changelog.hide()
            update_layout.addWidget(self.lbl_changelog)
            
            update_group.setLayout(update_layout)
            layout.addWidget(update_group)
            
            # Verifica atualizações ao iniciar (após 2 segundos)
            QTimer.singleShot(2000, self.check_updates_silent)
        
        layout.addStretch(1)
        
        # Conecta botões
        self.btn_dark.clicked.connect(self.set_dark)
        self.btn_light.clicked.connect(self.set_light)
        
        # Aplica tema salvo ao abrir
        config = load_config()
        theme = config.get("theme", "light")
        self.update_tema_label(theme)
        if self.app:
            if theme == "dark":
                self.app.setStyleSheet(qss_dark() + QSS_POPUP_DARK)
            else:
                self.app.setStyleSheet(qss_light() + QSS_POPUP_LIGHT)

    def set_dark(self):
        if self.app:
            self.app.setStyleSheet(qss_dark() + QSS_POPUP_DARK)
        config = load_config()
        config["theme"] = "dark"
        save_config(config)
        self.update_tema_label("dark")
        if self.toast_cb: self.toast_cb("Tema escuro ativado e salvo.")

    def set_light(self):
        if self.app:
            self.app.setStyleSheet(qss_light() + QSS_POPUP_LIGHT)
        config = load_config()
        config["theme"] = "light"
        save_config(config)
        self.update_tema_label("light")
        if self.toast_cb: self.toast_cb("Tema claro ativado e salvo.")

    def update_tema_label(self, tema):
        self.lbl_tema.setText(f"Tema atual: {'Escuro' if tema == 'dark' else 'Claro'}")
    
    def check_updates_silent(self):
        """Verifica atualizações silenciosamente (sem mostrar erros)"""
        if not UPDATER_AVAILABLE:
            return
        
        try:
            has_update, version_info, error = check_for_updates(timeout=5)
            
            if error:
                self.lbl_update_status.setText("✓ Sistema atualizado")
                self.lbl_update_status.setStyleSheet("color: #10b981;")
                return
            
            if has_update and version_info:
                remote_version = version_info.get('version', 'desconhecida')
                self.lbl_update_status.setText(f"🎉 Nova versão disponível: v{remote_version}")
                self.lbl_update_status.setStyleSheet("color: #f59e0b; font-weight: bold;")
                self.btn_install_update.setEnabled(True)
                
                # Mostra changelog
                changelog = version_info.get('changelog', [])
                if changelog:
                    changelog_text = "📋 Novidades:\n" + "\n".join(f"  • {item}" for item in changelog[:5])
                    self.lbl_changelog.setText(changelog_text)
                    self.lbl_changelog.show()
                
                # Toast de notificação
                if self.toast_cb:
                    self.toast_cb(f"Nova versão v{remote_version} disponível!")
            else:
                self.lbl_update_status.setText("✓ Sistema atualizado")
                self.lbl_update_status.setStyleSheet("color: #10b981;")
                
        except Exception as e:
            print(f"Erro ao verificar atualizações: {e}")
            self.lbl_update_status.setText("✓ Sistema atualizado")
            self.lbl_update_status.setStyleSheet("color: #10b981;")
    
    def check_updates(self):
        """Verifica atualizações (com feedback ao usuário)"""
        if not UPDATER_AVAILABLE:
            QMessageBox.warning(self, "Atualizações", "Módulo de atualização não disponível")
            return
        
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("Verificando...")
        self.lbl_update_status.setText("Verificando atualizações...")
        self.lbl_update_status.setStyleSheet("color: #6b7280;")
        
        # Usa QTimer para não travar a UI
        QTimer.singleShot(100, self._do_check_updates)
    
    def _do_check_updates(self):
        """Executa a verificação de atualizações"""
        try:
            has_update, version_info, error = check_for_updates(timeout=10)
            
            if error:
                QMessageBox.warning(
                    self,
                    "Erro ao Verificar Atualizações",
                    f"Não foi possível verificar atualizações:\n\n{error}\n\n"
                    "Verifique sua conexão com a internet."
                )
                self.lbl_update_status.setText("Erro ao verificar")
                self.lbl_update_status.setStyleSheet("color: #ef4444;")
            elif has_update and version_info:
                remote_version = version_info.get('version', 'desconhecida')
                changelog = version_info.get('changelog', [])
                
                self.lbl_update_status.setText(f"🎉 Nova versão disponível: v{remote_version}")
                self.lbl_update_status.setStyleSheet("color: #f59e0b; font-weight: bold;")
                self.btn_install_update.setEnabled(True)
                
                # Mostra changelog
                if changelog:
                    changelog_text = "📋 Novidades:\n" + "\n".join(f"  • {item}" for item in changelog[:5])
                    self.lbl_changelog.setText(changelog_text)
                    self.lbl_changelog.show()
                
                # Pergunta se quer instalar
                reply = QMessageBox.question(
                    self,
                    "Atualização Disponível",
                    f"Nova versão disponível: v{remote_version}\n\n"
                    f"Versão atual: v{get_current_version()}\n\n"
                    "Deseja instalar agora?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.install_update()
            else:
                self.lbl_update_status.setText("✓ Sistema atualizado")
                self.lbl_update_status.setStyleSheet("color: #10b981;")
                
                QMessageBox.information(
                    self,
                    "Sistema Atualizado",
                    f"Você já está usando a versão mais recente!\n\n"
                    f"Versão atual: v{get_current_version()}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro inesperado ao verificar atualizações:\n\n{e}"
            )
            self.lbl_update_status.setText("Erro ao verificar")
            self.lbl_update_status.setStyleSheet("color: #ef4444;")
        
        finally:
            self.btn_check_update.setEnabled(True)
            self.btn_check_update.setText("🔍 Verificar Atualizações")
    
    def install_update(self):
        """Instala a atualização disponível"""
        if not UPDATER_AVAILABLE:
            return
        
        # Confirmação
        reply = QMessageBox.question(
            self,
            "Confirmar Atualização",
            "A atualização será instalada agora.\n\n"
            "✓ Um backup será criado automaticamente\n"
            "✓ O processo leva cerca de 1-2 minutos\n"
            "✓ Você precisará reiniciar o aplicativo após a instalação\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Desabilita botões
        self.btn_check_update.setEnabled(False)
        self.btn_install_update.setEnabled(False)
        
        # Cria diálogo de progresso
        self.update_dialog = UpdateDialog(self)
        
        # Cria thread de atualização
        self.update_thread = UpdaterThread(auto_apply=True)
        self.update_thread.progress.connect(self.update_dialog.update_progress)
        self.update_thread.finished.connect(self._on_update_finished)
        
        # Inicia atualização
        self.update_dialog.show()
        self.update_thread.start()
    
    def _on_update_finished(self, success: bool, message: str):
        """Chamado quando a atualização termina"""
        # Fecha diálogo de progresso
        if hasattr(self, 'update_dialog'):
            self.update_dialog.close()
        
        # Reabilita botões
        self.btn_check_update.setEnabled(True)
        self.btn_install_update.setEnabled(False)
        
        if success:
            # Atualização bem-sucedida
            if "Atualização para v" in message:
                # Extrai a nova versão da mensagem
                import re
                match = re.search(r'v([\d.]+)', message)
                if match:
                    new_version = match.group(1)
                    update_version_globally(new_version)
                    self.lbl_version.setText(f"Versão instalada: v{new_version}")
            
            self.lbl_update_status.setText("✓ Atualização instalada!")
            self.lbl_update_status.setStyleSheet("color: #10b981; font-weight: bold;")
            self.lbl_changelog.hide()
            
            QMessageBox.information(
                self,
                "Atualização Concluída",
                message + "\n\n"
                "Clique em OK para reiniciar o aplicativo."
            )
            
            # Reinicia o aplicativo
            if self.parent_window:
                self.parent_window.close()
            
            import os
            import sys
            os.execl(sys.executable, sys.executable, *sys.argv)
            
        else:
            # Erro na atualização
            self.lbl_update_status.setText("❌ Erro ao atualizar")
            self.lbl_update_status.setStyleSheet("color: #ef4444;")
            
            QMessageBox.critical(
                self,
                "Erro na Atualização",
                message
            )
