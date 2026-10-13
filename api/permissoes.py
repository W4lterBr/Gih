# -*- coding: utf-8 -*-
"""Perfis de usuário e o que cada um pode fazer — a ÚNICA tabela de permissões.

Perfis:
- admin     Administrador: tudo.
- recepcao  Recepção: pedidos e clientes; vê produção, pronta entrega e produtos.
- cozinha   Cozinha: produção, estoque (pronta entrega, movimentação) e o painel web;
            vê os pedidos (sem alterar).
- common    Perfil das versões antigas ("Usuário"): mantém o acesso de antes (tudo
            menos as rotas de administrador) para ninguém perder acesso na
            atualização. Não é oferecido para usuários novos; o administrador deve
            trocar por Recepção ou Cozinha.

Lista de permissão: para recepção e cozinha, rota que não está aqui é recusada.
O motor (servico_local.py) confere em toda requisição; a interface usa a mesma
regra (GET /permissoes) só para esconder o que não pode ser usado.
"""

from __future__ import annotations

import re
from typing import Optional

PAPEIS = ("admin", "recepcao", "cozinha", "common")
PAPEIS_NOVOS = ("admin", "recepcao", "cozinha")
NOMES = {"admin": "Administrador", "recepcao": "Recepção", "cozinha": "Cozinha", "common": "Completo (antigo)"}

# Quem entra no painel web da cozinha (celular/tablet na rede).
PAINEL_WEB = {"admin", "cozinha", "common"}

R, K = "recepcao", "cozinha"
TODOS = {R, K}

# (métodos, caminho regex, perfis). Rotas de administrador (admin=True) nunca entram aqui.
_REGRAS: list[tuple[str, str, set[str]]] = [
    # Qualquer usuário logado
    ("GET", r"/(menu|dashboard|licenca)", TODOS),
    ("POST", r"/licenca/verificar", TODOS),
    ("PUT", r"/minha-senha", TODOS),
    # Pedidos: recepção altera; cozinha só vê (e imprime)
    ("GET", r"/pedidos(/\d+|/relatorio/opcoes)?", TODOS),
    ("POST", r"/pedidos/relatorio", TODOS),
    ("POST", r"/pedidos(/editar|/excluir|/excluir/contar)?", {R}),
    ("PUT", r"/pedidos/(\d+|lote)", {R}),
    ("GET", r"/etiquetas", TODOS),
    ("GET", r"/etiquetas/\d+/uso", {R}),
    ("POST", r"/etiquetas", {R}),
    ("PUT|DELETE", r"/etiquetas/\d+", {R}),
    # Clientes: só recepção
    ("GET", r"/clientes", {R}),
    ("POST", r"/clientes(/excluir)?", {R}),
    ("PUT", r"/clientes/\d+", {R}),
    # Produtos e pronta entrega: todos veem; cadastro só o administrador
    ("GET", r"/produtos(/estoque-baixo)?", TODOS),
    # Produção: cozinha altera; recepção vê
    ("GET", r"/producao", TODOS),
    ("POST", r"/producao(/remover|/limpar|/importar)?", {K}),
    ("PUT", r"/producao/\d+", {K}),
    # Movimentação de estoque: cozinha
    ("GET", r"/movimentos", {K}),
    ("POST", r"/movimentos(/excluir|/exportar)?", {K}),
    # Endereço do painel web
    ("GET", r"/painel-cozinha", {K}),
]
_COMPILADAS = [(set(m.split("|")), re.compile(f"^{c}$"), p) for m, c, p in _REGRAS]


def normalizar(papel: Optional[str]) -> Optional[str]:
    """Perfis de versões antigas ("common", "func", …) contam como "common"."""
    if not papel:
        return None
    return papel if papel in ("admin", R, K) else "common"


def permitido(papel: Optional[str], metodo: str, caminho: str, rota_admin: bool) -> bool:
    papel = normalizar(papel)
    if papel == "admin":
        return True
    if rota_admin or not papel:
        return False
    if papel == "common":
        return True  # comportamento das versões antigas
    return any(metodo in ms and rx.match(caminho) and papel in ps for ms, rx, ps in _COMPILADAS)


# Telas da interface por perfil ("ver" = só consulta). Espelha a tabela acima.
TELAS: dict[str, dict[str, str]] = {
    "admin": {t: "editar" for t in ("inicio", "pedidos", "producao", "pronta", "custos", "clientes", "produtos", "movimentacao", "relatorios", "config")},
    "common": {t: "editar" for t in ("inicio", "pedidos", "producao", "pronta", "clientes", "produtos", "movimentacao", "relatorios")},
    R: {"inicio": "ver", "pedidos": "editar", "producao": "ver", "pronta": "ver", "clientes": "editar", "produtos": "ver"},
    K: {"inicio": "ver", "pedidos": "ver", "producao": "editar", "pronta": "editar", "produtos": "ver", "movimentacao": "editar"},
}


def telas(papel: Optional[str]) -> dict[str, str]:
    return dict(TELAS.get(normalizar(papel) or "", {}))


def nome(papel: Optional[str]) -> str:
    return NOMES.get(normalizar(papel) or "", papel or "")


def entra_no_painel(papel: Optional[str]) -> bool:
    return normalizar(papel) in PAINEL_WEB
