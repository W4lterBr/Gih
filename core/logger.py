# logger.py
# Logger e auditoria

import logging
import os
import sys
from datetime import datetime

def get_app_data_dir():
    """Retorna o diretório AppData do usuário para logs"""
    if sys.platform == 'win32':
        app_data = os.getenv('LOCALAPPDATA', os.getenv('APPDATA', ''))
        if app_data:
            log_dir = os.path.join(app_data, 'Confeitaria', 'logs')
        else:
            # Fallback para pasta do executável
            log_dir = os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), '..', 'logs')
    else:
        # Linux/Mac
        log_dir = os.path.expanduser('~/.confeitaria/logs')
    
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

# Diretório de logs no AppData do usuário
LOG_DIR = get_app_data_dir()
LOG_PATH = os.path.join(LOG_DIR, f'confeitaria_{datetime.now().strftime("%Y%m%d")}.log')

# Configuração de logging com rotação diária
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

# Adiciona também saída no console para debug
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
logging.getLogger().addHandler(console_handler)

def log_event(msg: str):
    """Registra evento informativo"""
    logging.info(msg)

def log_error(msg: str, exc: Exception = None):
    """Registra erro com traceback opcional"""
    if exc:
        logging.error(f"{msg}: {str(exc)}", exc_info=True)
    else:
        logging.error(msg)

def log_warning(msg: str):
    """Registra aviso"""
    logging.warning(msg)

def log_debug(msg: str):
    """Registra mensagem de debug"""
    logging.debug(msg)

def log_startup():
    """Registra informações de inicialização do sistema"""
    logging.info("="*60)
    logging.info("CONFEITARIA - SISTEMA INICIADO")
    logging.info("="*60)
    logging.info(f"Versão Python: {sys.version}")
    logging.info(f"Sistema Operacional: {sys.platform}")
    logging.info(f"Executável: {sys.executable if getattr(sys, 'frozen', False) else 'Script Python'}")
    logging.info(f"Diretório de instalação: {os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)}")
    logging.info(f"Diretório de logs: {LOG_DIR}")
    logging.info(f"Arquivo de log: {LOG_PATH}")
    logging.info("="*60)

# Log de inicialização automático
log_startup()
