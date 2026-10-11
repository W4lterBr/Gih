# -*- coding: utf-8 -*-
"""Caminhos da aplicação: pasta do app, recursos empacotados, dados e backups."""

from __future__ import annotations

import os
import sys


if getattr(sys, "frozen", False):  # executável (PyInstaller)
    APP_DIR = os.path.dirname(sys.executable)
else:                               # script .py
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto

# Onde ficam os recursos empacotados (assets/, web/). No executável PyInstaller
# (onedir) eles ficam em sys._MEIPASS (pasta _internal), não ao lado do .exe.
RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)


# Pasta de dados de execução (logs de ações, backups)
def get_base_directory() -> str:
    """
    Determina o diretório base da aplicação de forma robusta.
    Funciona tanto em desenvolvimento quanto em executáveis PyInstaller.
    """
    try:
        # Se estamos executando via PyInstaller
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Para dados do usuário, usa o diretório dos dados de aplicação
            app_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Confeitaria")
            os.makedirs(app_data_dir, exist_ok=True)
            return app_data_dir
        else:
            # Modo desenvolvimento
            return APP_DIR
    except NameError:
        # Fallback se __file__ não existir
        app_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Confeitaria")
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir


base_dir = get_base_directory()


BACKUP_DIR = os.path.join(base_dir, "backups")
