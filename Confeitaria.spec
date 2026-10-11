# -*- mode: python ; coding: utf-8 -*-
# Confeitaria - Build Spec v1.15.0
# Atualizado: 2026-09-06
# SISTEMA 100% LOCAL
# =======================================
# 🛠️ Correções de integridade: estoque, lotes de pedidos, reparo/restauração de banco
# 🛠️ Editar data de pedido futuro para hoje reserva o estoque na hora
# 🛠️ Criação de pedido com múltiplos produtos desfaz tudo se algum item falhar
# 🛠️ Corrigida condição de corrida que podia deixar estoque negativo
# 🖱️ Excluir com múltipla seleção corrigido em Produtos, Clientes, Movimentação, Produção
# 🔒 Painel da Cozinha (rede) protegido por PIN de acesso
# 🔒 Login com bloqueio automático por tentativas incorretas
# 🔒 Credenciais salvas protegidas com criptografia do Windows (DPAPI)
# ⚡ Login automático com credenciais salvas (Shift força tela de login)
# 📦 Tela de Movimentação: entradas, saídas, produção e perdas de estoque
# 📦 Pronta Entrega mostra produtos esgotados em vez de escondê-los
# 🖥️ Correção de proporção de janela em telas/monitores diferentes
# 🏠 Sistema totalmente local (sem GitHub)
# 🔧 Sistema de reparo de banco corrompido com verificação de integridade
# 🔄 Correção na restauração de backups ZIP
# 📊 Dashboard completo com estatísticas
# 💰 Sistema de preços com formatação monetária brasileira
# 🎨 5 temas disponíveis (Escuro, Claro, Rosa, Roxo, Azul)
# 📦 Banco de dados incluído na distribuição
# ✅ Preserva banco de dados, configurações, backups e logs

a = Analysis(
    ['Confeitaria.py'],  # ← Código principal do sistema
    pathex=[],
    binaries=[
        # CRÍTICO: Adiciona DLLs do SQLite se necessário
        # PyInstaller deve incluir automaticamente, mas forçamos aqui
    ],
    datas=[
        ('assets', 'assets'),  # Ícones e recursos visuais
        ('core', 'core'),      # Lógica do sistema
        ('ui', 'ui'),          # Interface PyQt6
        ('data', 'data'),      # Configurações base
        ('web', 'web'),        # Painel web HTML
        ('version.json', '.'),        # Controle de versão
        ('confeitaria.db', '.'),      # BANCO DE DADOS com dados de exemplo
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
    icon=['assets\\icons\\logo.ico'],  # Ícone padrão (neutro)
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
