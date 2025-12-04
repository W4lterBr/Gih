# -*- mode: python ; coding: utf-8 -*-
# Confeitaria - Build Spec v1.11.30
# Atualizado: 2025-11-19
# SISTEMA DE LOGS COMPLETO + ATUALIZAÇÃO REMOTA
# =======================================
# ✅ Atualização COMPLETA via GitHub (código + interface + recursos)
# ✅ Token GitHub em texto simples (github_token.txt)
# ✅ Status de licença no rodapé (Em dia / Pendente / Inadimplente / Sem internet)
# ✅ Sistema de LOGS completo em AppData\Local\Confeitaria\logs\
# ✅ Logs por dia com todas operações (inicialização, banco, login, atualizações)
# ✅ Preserva banco de dados, configurações, backups e logs
# ✅ Atualizações de ~500KB vs ~200MB do instalador
# ✅ Clientes atualizam com 1 clique em Configurações
# 
# GARANTIAS DE ATUALIZAÇÃO:
# - Substitui: .py, core/, ui/, src/, assets/, web/
# - Preserva: confeitaria.db, config.yaml, token, logs, backups
# - Limpeza de cache PyQt6 automática
# - Rollback automático em caso de falha

a = Analysis(
    ['launcher.py'],  # ← Launcher compacto que carrega Confeitaria.py externo
    pathex=[],
    binaries=[
        # CRÍTICO: Adiciona DLLs do SQLite se necessário
        # PyInstaller deve incluir automaticamente, mas forçamos aqui
    ],
    datas=[
        ('assets', 'assets'),  # Ícones e recursos visuais (ATUALIZADO REMOTAMENTE)
        ('core', 'core'),      # Lógica do sistema (ATUALIZADO REMOTAMENTE)
        ('src', 'src'),        # Módulos auxiliares (ATUALIZADO REMOTAMENTE)
        ('ui', 'ui'),          # Interface PyQt6 (ATUALIZADO REMOTAMENTE)
        ('data', 'data'),      # Configurações base (PRESERVADO EM ATUALIZAÇÕES)
        ('web', 'web'),        # Painel web HTML (ATUALIZADO REMOTAMENTE)
        ('Confeitaria.py', '.'),      # CRÍTICO: Código principal EXTERNO (atualizável)
        ('version.json', '.'),        # CRÍTICO: Controle de versão para auto-update
        ('github_token.txt', '.'),    # CRÍTICO: Token para repositório privado
        ('TOKEN_SETUP.md', '.')       # Documentação do sistema de licença
    ],
    hiddenimports=[
        'PyQt6.QtCore', 
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets', 
        'PyQt6.QtCharts', 
        'bcrypt', 
        'yaml', 
        'openpyxl', 
        'reportlab',
        'qtawesome',  # Ícones
        'flask',  # Servidor web
        'flask_cors',  # CORS para API
        'sqlite3',  # CRÍTICO: Banco de dados SQLite
        '_sqlite3',  # CRÍTICO: Módulo interno do SQLite
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib.tests', 'test', 'unittest', 'PIL.tests'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Confeitaria',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icons\\logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Confeitaria',
)
