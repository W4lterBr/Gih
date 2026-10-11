# -*- coding: utf-8 -*-
"""Utilidades comuns das rotas: conversão de linhas, datas e validação."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

from api import ErroApi


def linhas(rows: Iterable[Any]) -> list[dict]:
    """sqlite3.Row → dict (serializável em JSON)."""
    return [dict(r) for r in rows]


def agora(segundos: bool = True) -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S" if segundos else "%Y-%m-%d %H:%M")


def hoje_iso() -> str:
    return date.today().isoformat()


def data_iso(valor: Any, campo: str = "data") -> str:
    """Valida AAAA-MM-DD."""
    try:
        return date.fromisoformat(str(valor)[:10]).isoformat()
    except (TypeError, ValueError):
        raise ErroApi(f"Data inválida em '{campo}'.")


def inteiro(valor: Any, campo: str, minimo: Optional[int] = None, maximo: Optional[int] = None) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ErroApi(f"Valor inválido em '{campo}'.")
    if minimo is not None and n < minimo:
        raise ErroApi(f"'{campo}' deve ser no mínimo {minimo}.")
    if maximo is not None and n > maximo:
        raise ErroApi(f"'{campo}' deve ser no máximo {maximo}.")
    return n


def texto(valor: Any) -> Optional[str]:
    """strip(); vazio vira None (como a versão 1.x gravava)."""
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def ids(valor: Any) -> list[int]:
    """Lista de ids sem duplicados, na ordem recebida."""
    if not isinstance(valor, list) or not valor:
        raise ErroApi("Nenhum item selecionado.")
    vistos: list[int] = []
    for v in valor:
        n = inteiro(v, "ids")
        if n not in vistos:
            vistos.append(n)
    return vistos


def auditar(db: Any, entidade: str, entidade_id: Any, acao: str, detalhes: Optional[str] = None) -> None:
    try:
        db.audit_log(entidade, entidade_id, acao, details=detalhes)
    except Exception:
        pass


def diff(campos: list[tuple[str, Any, Any]], aspas: bool = True) -> Optional[str]:
    """Texto de auditoria de update no formato do app: "campo: 'antigo' -> 'novo'; ..."."""
    partes = []
    for nome, antigo, novo in campos:
        if antigo != novo:
            if aspas:
                partes.append(f"{nome}: '{antigo if antigo is not None else ''}' -> '{novo if novo is not None else ''}'")
            else:
                partes.append(f"{nome}: {antigo} -> {novo}")
    return "; ".join(partes) or None
