# -*- coding: utf-8 -*-
"""Confeitaria – Sistema de Pedidos (PyQt6 + SQLite).

Ponto de entrada do aplicativo (também usado pelo PyInstaller).
O código fica organizado em:
  core/  - banco, caminhos, segurança, formatação, servidor web
  ui/    - janela principal, páginas, diálogos, widgets e temas
  app.py - inicialização (banco, login, tema)

Como executar:
    python Confeitaria.py
"""

from app import main

if __name__ == "__main__":
    main()
