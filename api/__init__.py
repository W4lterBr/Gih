# -*- coding: utf-8 -*-
"""Rotas HTTP do motor da Confeitaria (usadas pela interface Tauri).

Cada módulo registra suas rotas com o decorador `rota`. Um handler recebe um
`Pedido` (query string, corpo JSON, usuário logado) e devolve um dict (200) ou
levanta `ErroApi` com o código HTTP e a mensagem para o usuário.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class ErroApi(Exception):
    def __init__(self, mensagem: str, status: int = 400, codigo: Optional[str] = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.codigo = codigo


@dataclass
class Pedido:
    metodo: str
    caminho: str
    query: dict[str, str]
    corpo: dict[str, Any]
    params: dict[str, str] = field(default_factory=dict)  # partes variáveis da rota (/pedidos/{id})
    usuario: Optional[dict[str, Any]] = None

    def q(self, nome: str, padrao: str = "") -> str:
        return self.query.get(nome, padrao)

    def c(self, nome: str, padrao: Any = None) -> Any:
        return self.corpo.get(nome, padrao)

    def id(self, nome: str = "id") -> int:
        try:
            return int(self.params[nome])
        except (KeyError, ValueError):
            raise ErroApi("Identificador inválido.", 400)


Handler = Callable[[Pedido], dict]


@dataclass
class _Rota:
    metodo: str
    padrao: re.Pattern
    handler: Handler
    publica: bool  # dispensa login (ex.: /saude, /login)
    admin: bool    # só administradores
    escreve: bool  # altera dados: recusada com a licença em modo somente leitura


_ROTAS: list[_Rota] = []


def rota(metodo: str, caminho: str, publica: bool = False, admin: bool = False, escreve: Optional[bool] = None):
    """Registra um handler. `caminho` aceita partes variáveis: /pedidos/{id}.
    `escreve`: padrão GET = não, demais = sim. Marque escreve=False em POST que só
    lê ou gera arquivo (relatórios, exportações), para funcionarem em somente leitura."""
    grava = metodo.upper() != "GET" if escreve is None else escreve
    regex = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", caminho) + "$"

    def deco(fn: Handler) -> Handler:
        _ROTAS.append(_Rota(metodo.upper(), re.compile(regex), fn, publica, admin, grava))
        return fn
    return deco


def resolver(metodo: str, caminho: str) -> tuple[Optional[_Rota], dict[str, str]]:
    achou_caminho = False
    # Rotas literais antes das com partes variáveis (/pedidos/lote antes de /pedidos/{id}).
    for r in sorted(_ROTAS, key=lambda r: r.padrao.groups):
        m = r.padrao.match(caminho)
        if m:
            achou_caminho = True
            if r.metodo == metodo:
                return r, m.groupdict()
    if achou_caminho:
        raise ErroApi("Método não permitido.", 405)
    return None, {}


def carregar_rotas() -> None:
    """Importa os módulos de rotas (cada um se registra ao ser importado)."""
    from api import banco, cadastros, configuracoes, custos, estoque, licenca, pedidos, producao, relatorios, sistema  # noqa: F401
