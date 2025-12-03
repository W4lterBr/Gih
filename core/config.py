# config.py
# Configurações globais e leitura de YAML

from typing import Dict, Any, Optional
import yaml
import os
import sys
from PyQt6.QtWidgets import QWidget, QFileDialog

def get_app_data_directory() -> str:
    """
    Retorna o diretório de dados da aplicação de forma robusta.
    Funciona tanto em desenvolvimento quanto em executáveis PyInstaller.
    """
    try:
        # Se estamos executando via PyInstaller
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Para dados do usuário, usa o diretório dos dados de aplicação
            app_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Confeitaria")
        else:
            # Modo desenvolvimento - usa pasta data no projeto
            app_data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir
    except Exception:
        # Fallback seguro
        app_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Confeitaria")
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir

# Garante que o diretório de dados existe
_DATA_DIR = get_app_data_directory()

# Caminho para o arquivo de configuração
_CONFIG_PATH = os.path.join(_DATA_DIR, 'config.yaml')

# QSS para popups escuros (contraste garantido)
QSS_POPUP_DARK = """
QDialog, QMessageBox, QFileDialog, QInputDialog {
    background: #23272e;
    color: #f3f4f6;
}
QLabel, QLabel *, QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {
    color: #f3f4f6;
    background: transparent;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {
    color: #f3f4f6;
    background: #23272e;
    border: 1px solid #444;
}
QComboBox QAbstractItemView {
    background: #23272e;
    color: #f3f4f6;
    selection-background-color: #3b4252;
    selection-color: #f3f4f6;
}
QPushButton, QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
    background: #2d323b;
    color: #f3f4f6;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 4px 12px;
}
QPushButton:hover, QDialog QPushButton:hover, QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
    background: #3b4252;
}
QPushButton:pressed, QDialog QPushButton:pressed, QMessageBox QPushButton:pressed, QInputDialog QPushButton:pressed {
    background: #22262c;
}
QListView, QTreeView {
    background: #23272e;
    color: #f3f4f6;
}
QMenu {
    background: #23272e;
    color: #f3f4f6;
}
QMenu::item:selected {
    background: #3b4252;
}
QCalendarWidget {
    background: #23272e;
    border: 1px solid #444;
    border-radius: 4px;
    color: #f3f4f6;
}
QCalendarWidget QWidget {
    background: #23272e;
    color: #f3f4f6;
}
QCalendarWidget QAbstractItemView {
    background: #23272e;
    color: #f3f4f6;
    selection-background-color: #3b4252;
    selection-color: #f3f4f6;
    gridline-color: #444;
}
QCalendarWidget QAbstractItemView::item:selected {
    background: #3b4252;
    color: #f3f4f6;
    border-radius: 4px;
}
QCalendarWidget QAbstractItemView::item:hover {
    background: #2f3545;
    color: #f3f4f6;
}
QCalendarWidget QTableView {
    background: #23272e;
    color: #f3f4f6;
}
QCalendarWidget QToolButton {
    background: #2d323b;
    color: #f3f4f6;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 4px;
}
QCalendarWidget QToolButton:hover { 
    background: #3b4252;
}
QCalendarWidget QSpinBox {
    background: #23272e;
    color: #f3f4f6;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 4px;
}
QCalendarWidget QHeaderView::section {
    background: #2d323b;
    color: #f3f4f6;
    border: 1px solid #444;
    padding: 4px;
}
"""

# QSS para popups claros (tema light)
QSS_POPUP_LIGHT = """
QDialog, QMessageBox, QFileDialog, QInputDialog {
    background: #ffffff;
    color: #1f2937;
}
QLabel, QLabel *, QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {
    color: #1f2937;
    background: transparent;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {
    color: #111827;
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 6px;
    selection-background-color: #e8eefc;
    selection-color: #1b2240;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #111827;
    selection-background-color: #e8eefc;
    selection-color: #1b2240;
}
QPushButton, QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
    background: #e5e7eb;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 8px 14px;
}
QPushButton:hover, QDialog QPushButton:hover, QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
    background: #dbeafe;
    border-color: #bfdbfe;
}
QPushButton:pressed, QDialog QPushButton:pressed, QMessageBox QPushButton:pressed, QInputDialog QPushButton:pressed {
    background: #c7d2fe;
}
QListView, QTreeView {
    background: #ffffff;
    color: #1f2937;
}
QMenu {
    background: #ffffff;
    color: #1f2937;
}
QMenu::item:selected {
    background: #e8eefc;
}
QCalendarWidget {
    background: #ffffff;
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 8px;
}
QCalendarWidget QWidget {
    background: #ffffff;
    color: #1f2937;
}
QCalendarWidget QAbstractItemView {
    background: #ffffff;
    color: #1f2937;
    selection-background-color: #e8eefc;
    selection-color: #1b2240;
    border: 1px solid #d1d5db;
    border-radius: 4px;
}
QCalendarWidget QAbstractItemView::item:selected {
    background: #e8eefc;
    color: #1b2240;
    border-radius: 4px;
}
QCalendarWidget QAbstractItemView::item:hover {
    background: #f3f6ff;
    color: #111827;
}
QCalendarWidget QTableView {
    background: #ffffff;
    color: #1f2937;
}
QCalendarWidget QToolButton {
    background: #f9fafb;
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 4px;
}
QCalendarWidget QToolButton:hover {
    background: #e8eefc;
    border-color: #bfdbfe;
}
QCalendarWidget QToolButton:pressed {
    background: #dbeafe;
}
QCalendarWidget QSpinBox {
    background: #ffffff;
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 4px;
}
QCalendarWidget QHeaderView::section {
    background: #f9fafb;
    color: #1f2937;
    border: 1px solid #d1d5db;
    padding: 4px;
}
"""

def apply_popup_style(dialog: QWidget) -> None:
    """
    Aplica o estilo apropriado (claro ou escuro) a um diálogo baseado no tema ativo.
    
    Args:
        dialog: O widget de diálogo para aplicar o estilo
    """
    config = load_config()
    theme: str = config.get("theme", "light")
    if theme == "dark":
        dialog.setStyleSheet(QSS_POPUP_DARK)
    else:
        dialog.setStyleSheet(QSS_POPUP_LIGHT)
    
    # Forçar QFileDialog não nativo para aplicar QSS
    if isinstance(dialog, QFileDialog):
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

# Manter compatibilidade com função anterior
def apply_dark_popup_style(dialog: QWidget) -> None:
    """
    Aplica o estilo apropriado a um diálogo baseado no tema ativo.
    DEPRECATED: Use apply_popup_style() para melhor clareza.
    
    Args:
        dialog: O widget de diálogo para aplicar o estilo
    """
    apply_popup_style(dialog)

def load_config() -> Dict[str, Any]:
    """
    Carrega as configurações do arquivo YAML.
    
    Returns:
        Dict[str, Any]: Dicionário com as configurações
    """
    if not os.path.exists(_CONFIG_PATH):
        return {}
    with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def save_config(data: Dict[str, Any]) -> None:
    """
    Salva as configurações no arquivo YAML.
    
    Args:
        data: Dicionário com as configurações para salvar
    """
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True)

def get_database_path() -> str:
    """
    Retorna o caminho do banco de dados de forma robusta.
    
    IMPORTANTE: Quando um banco em REDE é configurado, SEMPRE retorna o caminho da rede.
    Isso garante que backups e operações usem o banco da rede, não uma cópia local.
    
    Procura em ordem de prioridade:
    1. Configuração do usuário (SEMPRE tem prioridade - pode ser rede ou local)
    2. Diferentes locais possíveis
    """
    # 1. SEMPRE verifica se o usuário configurou um banco específico (rede ou local)
    user_db_path = get_user_database_path()
    if user_db_path:
        # Se é caminho de rede, mostra aviso
        if user_db_path.startswith('\\\\') or (len(user_db_path) > 1 and user_db_path[1] == ':' and ord(user_db_path[0].upper()) > ord('C')):
            print(f"Banco de dados configurado encontrado: {user_db_path}")
            print("⚠️ ATENÇÃO: Usando banco de dados em REDE")
            print("   Todas as operações (incluindo backup) usarão o arquivo da rede")
        return user_db_path
    
    # 2. Busca em locais padrão usando configuração atual
    config = load_config()
    db_path = config.get('database_path', '')
    
    # Se existe caminho salvo e o arquivo existe, usa ele
    if db_path and os.path.isfile(db_path):
        print(f"Usando banco configurado: {db_path}")
        return os.path.abspath(db_path)
    
    # Procura banco padrão em vários locais
    possible_paths = [
        # 1. No diretório de dados da aplicação
        os.path.join(_DATA_DIR, 'confeitaria.db'),
        # 2. No diretório de instalação (se executável)
        os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 'confeitaria.db'),
        # 3. No diretório raiz do projeto (desenvolvimento)
        os.path.join(os.path.dirname(__file__), '..', 'confeitaria.db'),
        # 4. No diretório atual
        os.path.join(os.getcwd(), 'confeitaria.db'),
    ]
    
    # Procura por um banco existente
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.isfile(abs_path):
            print(f"Banco encontrado em: {abs_path}")
            # Salva este caminho como padrão para próximas execuções
            try:
                config['database_path'] = abs_path
                save_config(config)
            except Exception:
                pass
            return abs_path
    
    # Se nenhum banco foi encontrado, usa o primeiro local (diretório de dados)
    default_path = possible_paths[0]
    print(f"Usando banco padrão (será criado): {default_path}")
    return os.path.abspath(default_path)

def set_database_path(path: str) -> bool:
    """
    Define o caminho do banco de dados nas configurações.
    Valida se o arquivo existe ou se pode ser criado no local.
    
    Args:
        path: Caminho do arquivo de banco de dados
        
    Returns:
        bool: True se o caminho foi salvo com sucesso, False caso contrário
    """
    if not path:
        return False
    
    # Normaliza o caminho
    path = os.path.abspath(path)
    
    # Verifica se o arquivo já existe
    if os.path.isfile(path):
        # Tenta verificar se é um banco SQLite válido
        try:
            import sqlite3
            conn = sqlite3.connect(path)
            conn.close()
        except Exception as e:
            print(f"Erro ao validar banco de dados: {e}")
            return False
    else:
        # Verifica se o diretório existe e se podemos escrever nele
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"Erro ao criar diretório: {e}")
                return False
        
        # Verifica se podemos escrever no diretório
        if not os.access(directory, os.W_OK):
            print(f"Sem permissão de escrita no diretório: {directory}")
            return False
    
    # Salva nas configurações
    try:
        config = load_config()
        config['database_path'] = path
        save_config(config)
        return True
    except Exception as e:
        print(f"Erro ao salvar configuração: {e}")
        return False

def validate_database_path(path: str) -> tuple[bool, str]:
    """
    Valida se um caminho de banco de dados é válido.
    
    Args:
        path: Caminho para validar
        
    Returns:
        tuple[bool, str]: (é_válido, mensagem)
    """
    if not path:
        return False, "Caminho vazio"
    
    path = os.path.abspath(path)
    
    # Se o arquivo existe, verifica se é SQLite válido
    if os.path.isfile(path):
        try:
            import sqlite3
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            
            # Verifica se é um banco SQLite válido
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            
            # Verifica se tem as tabelas básicas do sistema
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'customers', 'products', 'orders')")
            tables = cur.fetchall()
            
            conn.close()
            
            if len(tables) >= 3:  # Pelo menos users, customers, products
                return True, f"Banco de dados válido com {len(tables)} tabelas do sistema"
            elif len(tables) > 0:
                return True, f"Banco SQLite válido ({len(tables)} tabelas reconhecidas). Esquema será atualizado automaticamente."
            else:
                return True, "Banco SQLite vazio. Esquema será criado automaticamente."
                
        except Exception as e:
            return False, f"Arquivo não é um banco de dados SQLite válido: {e}"
    
    # Se não existe, verifica se podemos criar
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        return False, f"Diretório não existe: {directory}"
    
    if not os.access(directory, os.W_OK):
        return False, f"Sem permissão de escrita no diretório: {directory}"
    
    # Verifica se o nome do arquivo tem extensão .db
    if not path.lower().endswith('.db'):
        return False, "O arquivo deve ter extensão .db"
    
    return True, "Caminho válido (banco será criado)"


def get_user_database_path() -> Optional[str]:
    """
    Obtém o caminho do banco de dados salvo nas configurações do usuário
    
    Returns:
        str ou None: Caminho do banco se configurado e válido, None caso contrário
    """
    try:
        config = load_config()
        db_path = config.get('database_path')
        
        if db_path:
            # Se o arquivo existe, valida
            if os.path.isfile(db_path):
                is_valid, _ = validate_database_path(db_path)
                if is_valid:
                    print(f"Banco de dados configurado encontrado: {db_path}")
                    return db_path
                else:
                    print(f"Banco configurado inválido: {db_path}")
                    return None
            else:
                # Se não existe ainda, retorna o caminho (será criado)
                # Importante para caminhos de rede que podem não estar disponíveis no momento
                print(f"Banco de dados configurado (será criado/conectado): {db_path}")
                return db_path
        
        return None
        
    except Exception as e:
        print(f"Erro ao carregar configuração do banco: {e}")
        return None
