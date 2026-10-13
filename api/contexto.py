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
    pelo app (core/config.py) — o mesmo da versão 1.x instalada."""
    env = os.environ.get("CONFEITARIA_DB")
    if env:
        return os.path.abspath(env)
    from core.config import get_database_path
    return get_database_path()


class BancoAusente(Exception):
    """O banco configurado não existe (apagado, movido, pasta da rede fora do ar)."""

    def __init__(self, caminho: str):
        super().__init__(caminho)
        self.caminho = caminho


_ausente: Optional[str] = None


def banco_ausente() -> Optional[str]:
    """Caminho do banco configurado que não foi encontrado na última tentativa de abrir."""
    return _ausente


def _caminho_configurado() -> bool:
    try:
        from core.config import load_config
        return bool(load_config().get("database_path"))
    except Exception:
        return False


def db() -> ExtendedDatabase:
    """Abre o banco na primeira chamada. Se o caminho configurado não existe mais,
    NÃO cria um banco vazio no lugar (para o usuário pareceria que perdeu tudo):
    levanta BancoAusente e a interface pergunta o que fazer. Banco novo só é criado
    sozinho na primeira instalação (nenhum caminho configurado ainda)."""
    global _db, _caminho_db, _ausente
    if _db is None:
        caminho = caminho_banco()
        if not os.path.isfile(caminho) and not os.environ.get("CONFEITARIA_DB") and _caminho_configurado():
            _ausente = caminho
            raise BancoAusente(caminho)
        _caminho_db = caminho
        os.makedirs(os.path.dirname(_caminho_db) or ".", exist_ok=True)
        _db = ExtendedDatabase(_caminho_db)
        _ausente = None
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
        db()  # pode levantar BancoAusente
    from api.tarefas import painel_trocar_banco
    painel_trocar_banco(_caminho_db)


def definir_usuario(u: Optional[dict[str, Any]]) -> None:
    """Sessão do usuário logado. Acrescenta as telas que o perfil pode abrir
    (api/permissoes.py), que a interface usa para montar o menu."""
    global usuario
    if u:
        from api import permissoes
        u = {**u, "telas": permissoes.telas(u.get("role")), "perfil": permissoes.nome(u.get("role"))}
    usuario = u
    if _db is not None:
        _db.current_user = u["username"] if u else None
        _db.current_role = u["role"] if u else None
