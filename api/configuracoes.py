# -*- coding: utf-8 -*-
"""Configurações: empresa (nome e logo), usuários e painel da cozinha."""

from __future__ import annotations

import os
import shutil

from api import ErroApi, Pedido, contexto, rota
from api.util import agora, inteiro, linhas, texto
from core.config import get_app_data_directory, get_web_panel_token
from core.security import hash_password

EXTENSOES_LOGO = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg", ".webp")

# ---------------------------------------------------------------- empresa


@rota("PUT", "/empresa/nome")
def salvar_nome(p: Pedido) -> dict:
    nome = texto(p.c("nome"))
    if not nome:
        raise ErroApi("Por favor, digite um nome para a empresa.")
    contexto.db().execute("UPDATE company SET name=?, updated_at=? WHERE id=1", (nome, agora()))
    return {"ok": True}


@rota("PUT", "/empresa/dias-fechados", admin=True)
def salvar_dias_fechados(p: Pedido) -> dict:
    """Dias da semana sem expediente (0 = segunda … 6 = domingo): pedidos não podem ser
    marcados para entrega nesses dias."""
    dias = p.c("dias")
    if not isinstance(dias, list):
        raise ErroApi("Dias inválidos.")
    escolhidos = sorted({inteiro(d, "dias", 0, 6) for d in dias})
    if len(escolhidos) == 7:
        raise ErroApi("Deixe pelo menos um dia da semana com expediente.")
    contexto.db().execute("UPDATE company SET closed_weekdays=?, updated_at=? WHERE id=1",
                          (",".join(map(str, escolhidos)), agora()))
    return {"ok": True, "dias_fechados": escolhidos}


@rota("PUT", "/empresa/logo")
def salvar_logo(p: Pedido) -> dict:
    """Copia a imagem escolhida para a pasta de dados do app (gravável mesmo com o app
    instalado em Arquivos de Programas) e registra o caminho no banco."""
    origem = str(p.c("caminho") or "")
    ext = os.path.splitext(origem)[1].lower()
    if ext not in EXTENSOES_LOGO:
        raise ErroApi("Escolha uma imagem (PNG, JPG, BMP, GIF, SVG ou WEBP).")
    if not os.path.isfile(origem):
        raise ErroApi("Arquivo não encontrado.")
    pasta = os.path.join(get_app_data_directory(), "company")
    os.makedirs(pasta, exist_ok=True)
    for antigo in os.listdir(pasta):  # um logo por vez (outra extensão não fica para trás)
        if antigo.startswith("logo."):
            try:
                os.remove(os.path.join(pasta, antigo))
            except OSError:
                pass
    destino = os.path.join(pasta, f"logo{ext}")
    shutil.copy2(origem, destino)
    contexto.db().execute("UPDATE company SET logo_path=?, updated_at=? WHERE id=1", (destino, agora()))
    return {"ok": True, "logo_path": destino}


@rota("DELETE", "/empresa/logo")
def remover_logo(p: Pedido) -> dict:
    db = contexto.db()
    r = db.query("SELECT logo_path FROM company WHERE id=1")
    caminho = r[0]["logo_path"] if r else None
    db.execute("UPDATE company SET logo_path=NULL, updated_at=? WHERE id=1", (agora(),))
    # Só apaga arquivos que o próprio app copiou (pasta company/), nunca o original do usuário.
    if caminho and os.path.basename(os.path.dirname(caminho)) == "company" and os.path.isfile(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass
    return {"ok": True}


# ---------------------------------------------------------------- painel da cozinha


@rota("GET", "/painel-cozinha")
def painel(p: Pedido) -> dict:
    from api.sistema import PORTA_COZINHA, ip_local
    ip = ip_local()
    return {"url": f"http://{ip}:{PORTA_COZINHA}", "local": f"http://localhost:{PORTA_COZINHA}", "pin": get_web_panel_token()}


# ---------------------------------------------------------------- usuários

PAPEIS = ("admin", "common")


@rota("GET", "/usuarios", admin=True)
def listar_usuarios(p: Pedido) -> dict:
    return {"usuarios": linhas(contexto.db().query("SELECT id, username, role FROM users ORDER BY username"))}


def _validar(p: Pedido, novo: bool) -> tuple[str, str, str]:
    nome = (p.c("username") or "").strip()
    senha = (p.c("password") or "")
    papel = p.c("role") or "common"
    if not nome:
        raise ErroApi("Nome de usuário é obrigatório")
    if len(nome) < 3:
        raise ErroApi("Nome de usuário deve ter pelo menos 3 caracteres")
    if novo and not senha:
        raise ErroApi("Senha é obrigatória para novos usuários")
    if senha:
        from core.senhas import problema_senha_nova
        erro = problema_senha_nova(nome, senha)
        if erro:
            raise ErroApi(erro)
    if papel not in PAPEIS:
        raise ErroApi("Tipo de usuário inválido.")
    return nome, senha, papel


def _admins(db) -> int:
    return db.query("SELECT COUNT(*) AS c FROM users WHERE role='admin'")[0]["c"]


@rota("POST", "/usuarios", admin=True)
def criar_usuario(p: Pedido) -> dict:
    db = contexto.db()
    nome, senha, papel = _validar(p, True)
    if db.query("SELECT 1 FROM users WHERE LOWER(username)=LOWER(?)", (nome,)):
        raise ErroApi(f"Já existe um usuário com o nome '{nome}'.")
    h = hash_password(senha)
    if not h:
        raise ErroApi("Erro ao gerar hash da senha.")
    cur = db.execute("INSERT INTO users(username, password_hash, role) VALUES (?,?,?)", (nome, h, papel))
    return {"id": cur.lastrowid}


@rota("PUT", "/usuarios/{id}", admin=True)
def atualizar_usuario(p: Pedido) -> dict:
    db = contexto.db()
    uid = p.id()
    r = db.query("SELECT username, role FROM users WHERE id=?", (uid,))
    if not r:
        raise ErroApi("Usuário não encontrado.", 404)
    nome, senha, papel = _validar(p, False)
    if db.query("SELECT 1 FROM users WHERE LOWER(username)=LOWER(?) AND id!=?", (nome, uid)):
        raise ErroApi(f"Já existe um usuário com o nome '{nome}'.")
    if r[0]["role"] == "admin" and papel != "admin" and _admins(db) <= 1:
        raise ErroApi("Este é o único administrador do sistema. Crie outro administrador antes de mudar o tipo deste.")
    eu = (p.usuario or {}).get("id") == uid
    if eu and papel != "admin":
        raise ErroApi("Você não pode tirar o perfil de administrador do seu próprio usuário.")
    if senha:
        h = hash_password(senha)
        if not h:
            raise ErroApi("Erro ao gerar hash da nova senha.")
        db.execute("UPDATE users SET username=?, password_hash=?, role=? WHERE id=?", (nome, h, papel, uid))
    else:
        db.execute("UPDATE users SET username=?, role=? WHERE id=?", (nome, papel, uid))
    if eu:
        contexto.definir_usuario({"id": uid, "username": nome, "role": papel})
    return {"ok": True}


@rota("DELETE", "/usuarios/{id}", admin=True)
def excluir_usuario(p: Pedido) -> dict:
    db = contexto.db()
    uid = p.id()
    r = db.query("SELECT username, role FROM users WHERE id=?", (uid,))
    if not r:
        raise ErroApi("Usuário não encontrado.", 404)
    if (p.usuario or {}).get("id") == uid:
        raise ErroApi("Você não pode excluir seu próprio usuário enquanto está logado com ele.")
    if r[0]["role"] == "admin" and _admins(db) <= 1:
        raise ErroApi("Este é o único administrador do sistema. Crie outro administrador antes de excluir este.")
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    return {"ok": True}


@rota("PUT", "/minha-senha")
def trocar_minha_senha(p: Pedido) -> dict:
    """Qualquer usuário troca a própria senha (confirmando a atual). Também é a única
    rota liberada enquanto a sessão está marcada para trocar a senha padrão."""
    from core.services import AuthService
    from api.sistema import gravar_senha_nova
    eu = p.usuario or {}
    atual = str(p.c("atual") or "")
    auth = AuthService(contexto.db())
    if not auth.authenticate(eu.get("username", ""), atual):
        raise ErroApi(auth.last_error or "Senha atual incorreta.", 400, "senha_atual")
    gravar_senha_nova(inteiro(eu.get("id"), "id"), eu.get("username", ""), str(p.c("nova") or ""), atual)
    contexto.definir_usuario({**eu, "trocar_senha": False})
    return {"ok": True}
