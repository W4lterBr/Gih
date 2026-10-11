# login_dialog.py
# Diálogo de login de usuário

import os
import socket
import json
import base64
import ctypes
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLineEdit, QDialogButtonBox, QCheckBox


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_protect(data: bytes) -> bytes:
    """Criptografa dados usando o DPAPI do Windows, vinculado à conta do usuário logado.

    Sem isso, a senha "lembrada" ficava só em base64 em credentials.json - qualquer
    pessoa/ferramenta que leia esse arquivo (backup, outro usuário local, etc.)
    recuperava a senha em texto puro trivialmente. Com DPAPI, só o mesmo usuário do
    Windows que gravou consegue descriptografar (a chave nunca fica no arquivo).
    """
    buf_in = ctypes.create_string_buffer(data, len(data))
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    buf_in = ctypes.create_string_buffer(data, len(data))
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _get_credentials_file() -> Path:
    """Retorna o caminho para o arquivo de credenciais salvas"""
    home = Path.home()
    config_dir = home / ".confeitaria"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "credentials.json"


def load_saved_credentials():
    """Carrega usuário/senha salvos (senha protegida via DPAPI), se existirem.

    Função de módulo (não depende de uma instância de LoginDialog/QDialog) para
    que o app possa tentar login automático antes de sequer criar a janela de
    login. Retorna (usuario, senha) ou None se não houver credenciais salvas
    ou válidas.
    """
    try:
        creds_file = _get_credentials_file()
        if not creds_file.exists():
            return None
        with open(creds_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        username = base64.b64decode(data.get('u', '')).decode('utf-8')
        password_blob = base64.b64decode(data.get('p', ''))
        password = _dpapi_unprotect(password_blob).decode('utf-8')
        return username, password
    except Exception:
        # Inclui o caso de um credentials.json de uma versão antiga (só base64,
        # sem DPAPI) - simplesmente não carrega.
        return None


def clear_saved_credentials() -> None:
    """Remove as credenciais salvas (permite trocar de usuário)."""
    try:
        creds_file = _get_credentials_file()
        if creds_file.exists():
            creds_file.unlink()
    except Exception:
        pass


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
                creds_file = _get_credentials_file()
                username_encoded = base64.b64encode(self.username.text().encode('utf-8')).decode('utf-8')
                # DPAPI: só a mesma conta do Windows que salvou consegue descriptografar
                password_protected = _dpapi_protect(self.password.text().encode('utf-8'))
                password_encoded = base64.b64encode(password_protected).decode('utf-8')

                data = {
                    'u': username_encoded,
                    'p': password_encoded
                }

                with open(creds_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
            else:
                clear_saved_credentials()
        except Exception:
            pass

    def _on_accept(self):
        """Handler quando usuário clica em OK"""
        self._save_credentials()
        self.accept()