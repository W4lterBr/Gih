# config.py
# Configurações globais e leitura de YAML

from typing import Dict, Any, Optional
import yaml
import os
import sys

def get_app_data_directory() -> str:
    """
    Retorna o diretório de dados da aplicação de forma robusta.
    Funciona tanto em desenvolvimento quanto em executáveis PyInstaller.
    """
    # Testes automatizados: pasta de dados isolada (config.yaml, licença), nunca a real.
    isolada = os.environ.get("CONFEITARIA_DATA_DIR")
    if isolada:
        os.makedirs(isolada, exist_ok=True)
        return os.path.abspath(isolada)
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

def load_config() -> Dict[str, Any]:
    """
    Carrega as configurações do arquivo YAML.

    Returns:
        Dict[str, Any]: Dicionário com as configurações
    """
    if not os.path.exists(_CONFIG_PATH):
        return {}
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        # config.yaml corrompido (ex: processo encerrado durante escrita) -
        # não deixa o app inteiro travar na inicialização, apenas usa defaults.
        print(f"⚠️ config.yaml corrompido, ignorando e usando padrões: {e}")
        return {}

def save_config(data: Dict[str, Any]) -> None:
    """
    Salva as configurações no arquivo YAML.

    Escreve em um arquivo temporário e substitui o original de forma
    atômica (os.replace), para que uma queda no meio da escrita não deixe
    o config.yaml truncado/inválido para a próxima leitura.

    Args:
        data: Dicionário com as configurações para salvar
    """
    tmp_path = _CONFIG_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    os.replace(tmp_path, _CONFIG_PATH)


def get_web_panel_token() -> str:
    """
    Retorna o PIN de acesso ao Painel da Cozinha (servidor web na rede local).

    Gerado automaticamente na primeira execução e persistido em config.yaml,
    para exigir autenticação mínima de quem acessa a API pela rede Wi-Fi.

    Returns:
        str: PIN numérico de 6 dígitos
    """
    config = load_config()
    token = config.get('web_panel_token')
    if not token:
        import secrets
        token = f"{secrets.randbelow(1_000_000):06d}"
        config['web_panel_token'] = token
        save_config(config)
    return token

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
