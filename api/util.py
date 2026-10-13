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
    # int(1.5) daria 1 sem avisar: número com casas decimais é recusado, não truncado.
    if isinstance(valor, float) and not valor.is_integer():
        raise ErroApi(f"'{campo}' deve ser um número inteiro.")
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


UNIDADES = ("un", "kg")


def quantidade(valor: Any, campo: str, unidade: str = "un", minimo_un: int = 1, maximo: float = 1_000_000) -> float | int:
    """Quantidade conforme a unidade do produto: "un" = inteiro; "kg" = até 3 casas
    decimais (gramas), aceitando vírgula ("1,5")."""
    if unidade != "kg":
        return inteiro(valor, campo, minimo_un, int(maximo))
    try:
        n = round(float(str(valor).strip().replace(",", ".")), 3)
    except (TypeError, ValueError):
        raise ErroApi(f"Valor inválido em '{campo}'.")
    if n != n or n in (float("inf"), float("-inf")):
        raise ErroApi(f"Valor inválido em '{campo}'.")
    minimo = 0.001 if minimo_un >= 1 else float(minimo_un)
    if n < minimo:
        raise ErroApi(f"'{campo}' deve ser maior que zero." if minimo_un >= 1 else f"'{campo}' não pode ser negativo.")
    if n > maximo:
        raise ErroApi(f"'{campo}' deve ser no máximo {maximo:g}.")
    return int(n) if n == int(n) else n


def unidade_de(db: Any, product_id: int) -> str:
    r = db.query("SELECT unit FROM products WHERE id=?", (product_id,))
    return (r[0]["unit"] if r and r[0]["unit"] else "un") if r else "un"


def qtd_texto(q: Any, unidade: Optional[str]) -> str:
    """1.5, "kg" -> "1,5 kg"; 3, "un" -> "3"."""
    try:
        n = float(q or 0)
    except (TypeError, ValueError):
        return str(q)
    s = (f"{n:.3f}".rstrip("0").rstrip(".") if n != int(n) else str(int(n))).replace(".", ",")
    return f"{s} kg" if unidade == "kg" else s


def like(termo: str) -> str:
    """Padrão para `coluna LIKE ? ESCAPE '\\'` que procura o texto literalmente:
    % e _ digitados na busca não viram curinga."""
    t = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{t}%"


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
