# -*- coding: utf-8 -*-
"""Estado compartilhado do motor: banco aberto, usuário logado e trava.

O app é de um usuário por vez (desktop), então há uma única sessão. Todas as
requisições passam pela mesma trava: a conexão SQLite é uma só e as regras de
estoque (reserva, baixa) não podem rodar intercaladas.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Optional

from core.extended_database import ExtendedDatabase

TRAVA = threading.RLock()

_db: Optional[ExtendedDatabase] = None
_caminho_db: Optional[str] = None
usuario: Optional[dict[str, Any]] = None  # {"id", "username", "role"} após o login


def caminho_banco() -> str:
    """Caminho do banco: CONFEITARIA_DB (testes/desenvolvimento) ou o configurado
    pelo app (core/config.py), o mesmo que a interface PyQt usa."""
    env = os.environ.get("CONFEITARIA_DB")
    if env:
        return os.path.abspath(env)
    from core.config import get_database_path
    return get_database_path()


def db() -> ExtendedDatabase:
    global _db, _caminho_db
    if _db is None:
        _caminho_db = caminho_banco()
        os.makedirs(os.path.dirname(_caminho_db) or ".", exist_ok=True)
        _db = ExtendedDatabase(_caminho_db)
        if usuario:
            _db.current_user = usuario["username"]
            _db.current_role = usuario["role"]
    return _db


def banco_atual() -> Optional[str]:
    return _caminho_db


def fechar_banco() -> None:
    """Fecha a conexão (para substituir o arquivo do banco). Chamar com TRAVA."""
    global _db
    if _db is not None:
        try:
            _db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        try:
            _db.conn.close()
        except Exception:
            pass
    _db = None


def reabrir_banco() -> None:
    """Fecha e reabre o banco (depois de trocar o caminho ou restaurar um backup)."""
    global _caminho_db
    with TRAVA:
        fechar_banco()
        _caminho_db = None
        db()
    from api.tarefas import painel_trocar_banco
    painel_trocar_banco(_caminho_db)


def definir_usuario(u: Optional[dict[str, Any]]) -> None:
    global usuario
    usuario = u
    if _db is not None:
        _db.current_user = u["username"] if u else None
        _db.current_role = u["role"] if u else None
