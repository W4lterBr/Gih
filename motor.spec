# -*- mode: python ; coding: utf-8 -*-
# Motor da Confeitaria empacotado para a interface nova (desktop/, Tauri).
#
# Ponto de entrada: servico_local.py (sem Qt). Leva junto o painel da cozinha (web/),
# os ícones padrão e o version.json.
#
# Gerar:  py -m PyInstaller --noconfirm motor.spec
# Saída:  dist\confeitaria-motor\  (copiada para desktop\src-tauri\motor pelo script
#         desktop\scripts\gerar-instalador.ps1)
#
# console=True de propósito: o Tauri inicia o motor com CREATE_NO_WINDOW (nenhuma janela
# aparece) e redireciona a saída para %LOCALAPPDATA%\Confeitaria\logs\servico_local.log —
# num executável "sem console" do PyInstaller, sys.stdout/stderr ficam None e os print()
# do motor quebrariam.
#
# Instalado (frozen), core/config.py usa %LOCALAPPDATA%\Confeitaria como pasta de dados:
# o MESMO banco e config.yaml da versão 1.x instalada (a atualização não perde dados).

from pathlib import Path

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / 'version.json'), '.'),
    (str(ROOT / 'web'), 'web'),
    (str(ROOT / 'assets' / 'icons'), 'assets/icons'),
]

hidden_imports = [
    'api', 'api.banco', 'api.cadastros', 'api.configuracoes', 'api.contexto', 'api.estoque', 'api.licenca',
    'api.pedidos', 'api.producao', 'api.relatorios', 'api.sistema', 'api.tarefas', 'api.util',
    'core.config', 'core.credenciais', 'core.database', 'core.extended_database', 'core.formatting', 'core.licenca',
    'core.logger', 'core.models', 'core.paths', 'core.security', 'core.services', 'core.stock_categories',
    'core.web_server',
    'flask', 'bcrypt', 'yaml', 'psutil', 'sqlite3',
    'openpyxl', 'openpyxl.styles', 'openpyxl.drawing.image', 'PIL', 'PIL.Image',
    'reportlab', 'reportlab.lib', 'reportlab.platypus', 'reportlab.lib.pagesizes', 'reportlab.lib.styles',
]

a = Analysis(
    [str(ROOT / 'servico_local.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    # O motor não usa Qt: deixar de fora reduz o tamanho em centenas de MB.
    excludes=['PyQt6', 'PyQt5', 'PySide6', 'qtawesome', 'matplotlib', 'numpy', 'pandas', 'scipy',
              'IPython', 'tkinter', 'ui', 'app'],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='confeitaria-motor',
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(ROOT / 'assets' / 'icons' / 'logo.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='confeitaria-motor',
)
