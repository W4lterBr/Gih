# -*- coding: utf-8 -*-
"""Rotas da licença DWM (situação das faturas do cliente). Lógica em core/licenca.py."""

from __future__ import annotations

from api import ErroApi, Pedido, rota
from core import licenca


@rota("GET", "/licenca")
def obter(p: Pedido) -> dict:
    """Situação atual (consulta o servidor só se o cache de 4 h venceu)."""
    return licenca.situacao()


@rota("POST", "/licenca/verificar", escreve=False)
def verificar(p: Pedido) -> dict:
    """ "Já paguei" / "Verificar agora": consulta o servidor (com intervalo mínimo de 30 s)."""
    return licenca.situacao(forcar=True)


@rota("POST", "/licenca/ativar", admin=True, escreve=False)
def ativar(p: Pedido) -> dict:
    try:
        return licenca.ativar(str(p.c("token") or ""))
    except licenca.ErroLicenca as e:
        raise ErroApi(str(e), 400, "token_recusado")


@rota("POST", "/licenca/remover", admin=True, escreve=False)
def remover(p: Pedido) -> dict:
    try:
        licenca.remover()
    except licenca.ErroLicenca as e:
        raise ErroApi(str(e), 409, "licenca_bloqueada")
    return licenca.situacao()
