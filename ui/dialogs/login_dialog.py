# login_dialog.py
# Diálogo de login de usuário

import os
import socket
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLineEdit, QDialogButtonBox, QCheckBox


from core.credenciais import clear_saved_credentials, load_saved_credentials, save_credentials  # noqa: F401


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
        # Visual vem do tema global (ui/theme/qss.py); aqui só ajustes de layout
        from PyQt6.QtWidgets import QLabel, QVBoxLayout
        from PyQt6.QtGui import QPixmap
        self.setMinimumWidth(380)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(36, 28, 36, 24)
        vbox.setSpacing(8)

        # Logo - buscar logo customizada do banco primeiro
        logo_path = self._get_company_logo()
        if logo_path and os.path.exists(logo_path):
            logo = QLabel()
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                logo.setPixmap(pixmap.scaledToHeight(96, Qt.TransformationMode.SmoothTransformation))
                logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                vbox.addWidget(logo)
                vbox.addSpacing(4)

        # Título - buscar nome da empresa do banco
        company_name = self._get_company_name()
        title = QLabel(company_name)
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vbox.addWidget(title)
        subtitle = QLabel("Entre com seu usuário para continuar")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vbox.addWidget(subtitle)
        vbox.addSpacing(14)

        # Formulário (rótulos acima dos campos)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Digite seu usuário")
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Digite sua senha")
        for label_text, field in (("Usuário", self.username), ("Senha", self.password)):
            lbl = QLabel(label_text)
            lbl.setObjectName("CardTitle")
            vbox.addWidget(lbl)
            vbox.addWidget(field)
            vbox.addSpacing(6)

        # Checkbox "Lembrar credenciais"
        self.remember_checkbox = QCheckBox("Lembrar credenciais")
        vbox.addWidget(self.remember_checkbox)

        # Carregar credenciais salvas (se existirem)
        self._load_saved_credentials()

        # Botões
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_ok = btns.button(QDialogButtonBox.StandardButton.Ok)
        btn_ok.setText("Entrar")
        btn_ok.setDefault(True)
        btn_ok.setProperty("primary", True)
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        vbox.addSpacing(8)
        vbox.addWidget(btns)

        # Rodapé: endereço do painel da cozinha e dica de troca de usuário.
        # Com credenciais salvas, o próximo início entra direto sem mostrar esta
        # tela; segurar Shift ao abrir o app força esta tela a aparecer.
        vbox.addSpacing(10)
        local_ip = self._get_local_ip()
        footer = QLabel(f"📱 Painel da cozinha: http://{local_ip}:5000\n"
                        "Dica: segure Shift ao abrir o app para trocar de usuário")
        footer.setObjectName("Footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        vbox.addWidget(footer)
    
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
    
    def _get_company_logo(self) -> str:
        """Busca o caminho da logo customizada do banco de dados"""
        try:
            import sqlite3
            from core.config import get_database_path
            
            db_path = get_database_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT logo_path FROM company WHERE id=1")
            row = cur.fetchone()
            conn.close()
            
            if row and row["logo_path"]:
                return row["logo_path"]
        except Exception as e:
            print(f"Erro ao buscar logo da empresa: {e}")
        
        # Fallback para logo padrão
        default_logo = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icons", "logo.png")
        return default_logo if os.path.exists(default_logo) else None
    
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
    
    def _load_saved_credentials(self):
        """Carrega credenciais salvas se existirem, pré-preenchendo o formulário"""
        creds = load_saved_credentials()
        if creds:
            username, password = creds
            self.username.setText(username)
            self.password.setText(password)
            self.remember_checkbox.setChecked(True)

    def _save_credentials(self):
        """Salva credenciais se checkbox estiver marcado"""
        try:
            if self.remember_checkbox.isChecked():
                save_credentials(self.username.text(), self.password.text())
            else:
                clear_saved_credentials()
        except Exception:
            pass

    def _on_accept(self):
        """Handler quando usuário clica em OK"""
        self._save_credentials()
        self.accept()