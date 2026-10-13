# -*- coding: utf-8 -*-
"""Rotas de sistema: saúde do motor, login/logout e dados da empresa."""

from __future__ import annotations

import base64
import mimetypes
import os
import socket

from api import ErroApi, Pedido, contexto, rota
from core.credenciais import clear_saved_credentials, load_saved_credentials, save_credentials
from core.services import AuthService
from core.senhas import problema_senha_nova, senha_fraca

PORTA_COZINHA = 5000


def _versao() -> str:
    try:
        import json
        from core.paths import RESOURCE_DIR
        with open(os.path.join(RESOURCE_DIR, "version.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "?")
    except Exception:
        return "?"


def ip_local() -> str:
    """IP da máquina na rede local (para o celular acessar o painel da cozinha)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # não envia nada; só escolhe a interface de saída
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _usuario_publico(u) -> dict:
    return {"id": u.id, "username": u.username, "role": u.role}


@rota("GET", "/saude", publica=True)
def saude(p: Pedido) -> dict:
    return {
        "ok": True,
        "versao": _versao(),
        "banco": contexto.banco_atual(),
        "banco_ausente": contexto.banco_ausente(),
        "pid": os.getpid(),
        "usuario": contexto.usuario,
        "cozinha": f"http://{ip_local()}:{PORTA_COZINHA}",
    }


@rota("GET", "/avisos", publica=True)
def avisos(p: Pedido) -> dict:
    """Avisos das tarefas de fundo com número de sequência maior que `desde`."""
    from api.tarefas import AVISOS
    desde = int(p.q("desde", "0") or 0)
    return {"avisos": [a for a in AVISOS if a["i"] > desde]}


def _entrar(usuario: str, senha: str) -> dict:
    auth = AuthService(contexto.db())
    u = auth.authenticate(usuario, senha)
    if not u:
        raise ErroApi(auth.last_error or "Usuário ou senha inválidos.", 401, "login_invalido")
    publico = _usuario_publico(u)
    # Senha padrão/fraca: a sessão fica restrita até a troca (servico_local.py barra o resto).
    publico["trocar_senha"] = senha_fraca(u.username, senha)
    contexto.definir_usuario(publico)
    try:
        from core.logger import log_event
        log_event(f"✅ Login: {u.username} (Perfil: {u.role}) [interface desktop]")
    except Exception:
        pass
    return contexto.usuario  # com as telas do perfil


@rota("POST", "/login", publica=True, escreve=False)
def login(p: Pedido) -> dict:
    usuario = str(p.c("usuario") or "").strip()
    senha = str(p.c("senha") or "")
    if not usuario or not senha:
        raise ErroApi("Informe usuário e senha.")
    publico = _entrar(usuario, senha)
    # Só grava as credenciais depois de conferidas (o app antigo gravava antes).
    try:
        if p.c("lembrar"):
            save_credentials(usuario, senha)
        else:
            clear_saved_credentials()
    except Exception:
        pass
    return {"usuario": publico}


@rota("POST", "/login/automatico", publica=True, escreve=False)
def login_automatico(p: Pedido) -> dict:
    """Entra com as credenciais lembradas, se houver e ainda forem válidas."""
    salvo = load_saved_credentials()
    if not salvo:
        return {"usuario": None, "lembrado": None}
    try:
        return {"usuario": _entrar(*salvo), "lembrado": salvo[0]}
    except ErroApi:
        return {"usuario": None, "lembrado": salvo[0]}


@rota("POST", "/login/trocar-senha", publica=True, escreve=False)
def trocar_senha_no_login(p: Pedido) -> dict:
    """Troca a senha pela tela de login (sem entrar): exige usuário e senha atual.
    Tentativas erradas contam no bloqueio de login como um login comum."""
    usuario = str(p.c("usuario") or "").strip()
    atual = str(p.c("atual") or "")
    nova = str(p.c("nova") or "")
    if not usuario or not atual:
        raise ErroApi("Informe usuário e senha atual.")
    auth = AuthService(contexto.db())
    u = auth.authenticate(usuario, atual)
    if not u:
        raise ErroApi(auth.last_error or "Usuário ou senha atual inválidos.", 401, "login_invalido")
    gravar_senha_nova(u.id, u.username, nova, atual)
    return {"ok": True}


def gravar_senha_nova(uid: int, username: str, nova: str, atual: str) -> None:
    from core.security import hash_password
    erro = problema_senha_nova(username, nova, atual)
    if erro:
        raise ErroApi(erro, 400, "senha_invalida")
    h = hash_password(nova)
    if not h:
        raise ErroApi("Não foi possível gerar a senha. Tente de novo.", 500)
    contexto.db().execute("UPDATE users SET password_hash=? WHERE id=?", (h, uid))
    from core.extended_database import encerrar_sessoes_web
    encerrar_sessoes_web(contexto.db(), uid)  # o painel web pede login com a senha nova
    # Credencial lembrada deste usuário passa a ser a nova (senão o login automático falharia).
    try:
        salvo = load_saved_credentials()
        if salvo and salvo[0].lower() == username.lower():
            save_credentials(salvo[0], nova)
    except Exception:
        pass
    try:
        from core.logger import log_event
        log_event(f"🔑 Senha trocada: {username}")
    except Exception:
        pass


@rota("POST", "/logout", publica=True, escreve=False)
def logout(p: Pedido) -> dict:
    contexto.definir_usuario(None)
    if p.c("esquecer"):
        clear_saved_credentials()
    return {"ok": True}


def _logo_data_url(caminho: str | None) -> str | None:
    if not caminho or not os.path.isfile(caminho):
        return None
    tipo = mimetypes.guess_type(caminho)[0] or "image/png"
    try:
        with open(caminho, "rb") as f:
            return f"data:{tipo};base64,{base64.b64encode(f.read()).decode('ascii')}"
    except OSError:
        return None


@rota("GET", "/empresa", publica=True)
def empresa(p: Pedido) -> dict:
    """Nome e logo da confeitaria (tabela company) — usados no login e na barra lateral."""
    from api.pedidos import dias_fechados
    db = contexto.db()
    rows = db.query("SELECT name, logo_path FROM company WHERE id=1")
    nome = rows[0]["name"] if rows and rows[0]["name"] else "Confeitaria"
    logo = rows[0]["logo_path"] if rows else None
    return {"nome": nome, "logo": _logo_data_url(logo), "logo_path": logo, "dias_fechados": dias_fechados(db)}
