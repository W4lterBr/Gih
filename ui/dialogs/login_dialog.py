# login_dialog.py
# Diálogo de login de usuário

import os
import socket
import json
import base64
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QCheckBox

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login de Usuário")
        self.setMinimumWidth(340)
        # Definir ícone da janela
        from PyQt6.QtGui import QIcon
        ico_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icons", "logo.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        # QSS customizado para login
        # QSS exclusivo para tela de login, sempre fundo #debffa
        self.setStyleSheet("""
            QDialog {
                background: #debffa;
                border-radius: 16px;
            }
            QLabel {
                color: #3d246c;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                background: #f6edff;
                color: #3d246c;
                border: 1.5px solid #bfa2e0;
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 15px;
            }
            QLineEdit:focus {
                border: 1.5px solid #a259e6;
                background: #fff;
            }
            QDialogButtonBox QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a259e6, stop:1 #debffa);
                color: #fff;
                border-radius: 8px;
                padding: 7px 22px;
                font-weight: bold;
                font-size: 15px;
                border: none;
            }
            QDialogButtonBox QPushButton:hover {
                background: #c3a1e6;
                color: #3d246c;
            }
            QDialogButtonBox QPushButton:pressed {
                background: #a259e6;
                color: #fff;
            }
            QLabel#ip-info {
                background: #a259e6;
                color: #fff;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
            }
            QCheckBox {
                color: #3d246c;
                font-size: 14px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #bfa2e0;
                border-radius: 4px;
                background: #f6edff;
            }
            QCheckBox::indicator:checked {
                background: #a259e6;
                border-color: #a259e6;
            }
        """)
        from PyQt6.QtWidgets import QLabel, QVBoxLayout
        from PyQt6.QtGui import QPixmap
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(32, 24, 32, 24)
        vbox.setSpacing(10)
        
        # Aviso de acesso pelo celular (no topo)
        ip_info = QLabel()
        ip_info.setObjectName("ip-info")
        ip_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip_info.setWordWrap(True)
        
        # Detectar IP local automaticamente
        local_ip = self._get_local_ip()
        ip_info.setText(f"📱 Acesse pelo navegador do celular:\nhttp://{local_ip}:5000")
        vbox.addWidget(ip_info)
        
        # Logo
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icons", "logo.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            pixmap = QPixmap(logo_path)
            logo.setPixmap(pixmap.scaledToHeight(150))
            logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            vbox.addWidget(logo)
        
        # Título - buscar nome da empresa do banco
        company_name = self._get_company_name()
        title = QLabel(f"<b>{company_name}</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet("font-size: 18px; margin-bottom: 8px;")
        vbox.addWidget(title)
        # Formulário
        form = QFormLayout()
        form.setSpacing(16)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Digite seu usuário")
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Digite sua senha")
        form.addRow("Usuário:", self.username)
        form.addRow("Senha:", self.password)
        vbox.addLayout(form)
        
        # Checkbox "Lembrar credenciais"
        self.remember_checkbox = QCheckBox("Lembrar credenciais")
        self.remember_checkbox.setStyleSheet("margin-top: 8px; margin-bottom: 8px;")
        vbox.addWidget(self.remember_checkbox)
        
        # Carregar credenciais salvas (se existirem)
        self._load_saved_credentials()
        
        # Botões
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        vbox.addWidget(btns)
    
    def _get_company_name(self) -> str:
        """Busca o nome da empresa no banco de dados"""
        try:
            import sqlite3
            from core.config import get_database_path
            
            db_path = get_database_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT name FROM company WHERE id=1")
            row = cur.fetchone()
            conn.close()
            
            if row:
                return row["name"]
        except Exception:
            pass
        
        return "Confeitaria"
    
    def _get_local_ip(self) -> str:
        """Detecta o IP local da máquina automaticamente"""
        try:
            # Conectar a um endereço externo para descobrir o IP local
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "localhost"
    
    def get_values(self):
        return self.username.text().strip(), self.password.text()
    
    def _get_credentials_file(self):
        """Retorna o caminho para o arquivo de credenciais salvas"""
        home = Path.home()
        config_dir = home / ".confeitaria"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "credentials.json"
    
    def _load_saved_credentials(self):
        """Carrega credenciais salvas se existirem"""
        try:
            creds_file = self._get_credentials_file()
            if creds_file.exists():
                with open(creds_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Decodificar credenciais
                username = base64.b64decode(data.get('u', '')).decode('utf-8')
                password = base64.b64decode(data.get('p', '')).decode('utf-8')
                
                # Preencher campos
                self.username.setText(username)
                self.password.setText(password)
                self.remember_checkbox.setChecked(True)
        except Exception:
            pass
    
    def _save_credentials(self):
        """Salva credenciais se checkbox estiver marcado"""
        try:
            creds_file = self._get_credentials_file()
            
            if self.remember_checkbox.isChecked():
                # Codificar credenciais
                username_encoded = base64.b64encode(self.username.text().encode('utf-8')).decode('utf-8')
                password_encoded = base64.b64encode(self.password.text().encode('utf-8')).decode('utf-8')
                
                data = {
                    'u': username_encoded,
                    'p': password_encoded
                }
                
                with open(creds_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
            else:
                # Remover arquivo se existir
                if creds_file.exists():
                    creds_file.unlink()
        except Exception:
            pass
    
    def _on_accept(self):
        """Handler quando usuário clica em OK"""
        self._save_credentials()
        self.accept()