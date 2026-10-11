# -*- coding: utf-8 -*-
"""Banco de dados: informações, backup, restauração, troca de arquivo e reparo.

Diferenças em relação à versão 1.x (deliberadas, por segurança):
- O backup usa a API de backup do SQLite (cópia consistente), não a cópia crua do
  arquivo em uso; o ZIP leva o banco e o config.yaml.
- A restauração fecha a conexão do motor antes de substituir o arquivo e reabre depois
  (sem reiniciar o app); um backup de segurança é feito antes, sempre.
- O backup automático respeita a configuração `auto_backup` (antes era ignorada).
- Backup em nuvem (repositório GitHub compartilhado entre clientes) e "Configurar Rede
  Local" (habilitava Convidado sem senha) não foram trazidos para a interface nova.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from datetime import datetime

from api import ErroApi, Pedido, contexto, rota
from core.config import get_app_data_directory, load_config, save_config, set_database_path, validate_database_path
from core.paths import BACKUP_DIR

CONFIG_BACKUP_PADRAO = {"enabled": True, "interval_hours": 1}


def _nome_pc() -> str:
    return (os.environ.get("COMPUTERNAME") or "PC").replace(" ", "")


def criar_backup_zip(destino: str) -> str:
    """ZIP com uma cópia consistente do banco (API de backup do SQLite) + config.yaml."""
    contexto.db()  # garante o banco aberto
    origem = contexto.banco_atual()
    if not origem or not os.path.isfile(origem):
        raise ErroApi(f"Banco de dados não encontrado:\n{origem}", 404)
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        copia = os.path.join(tmp, os.path.basename(origem))
        with contexto.TRAVA:
            alvo = sqlite3.connect(copia)
            try:
                contexto.db().conn.backup(alvo)
            finally:
                alvo.close()
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copia, os.path.basename(origem))
            cfg = os.path.join(get_app_data_directory(), "config.yaml")
            if os.path.isfile(cfg):
                z.write(cfg, "config.yaml")
    return destino


# ---------------------------------------------------------------- informações


@rota("GET", "/banco", admin=True)
def info(p: Pedido) -> dict:
    db = contexto.db()
    caminho = contexto.banco_atual() or ""
    tamanho = os.path.getsize(caminho) if os.path.isfile(caminho) else 0
    modificado = datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%Y-%m-%d %H:%M:%S") if tamanho else None
    um = lambda t: db.query(f"SELECT COUNT(*) FROM {t}")[0][0]  # noqa: E731
    rede = caminho.startswith("\\\\") or caminho.startswith("//")
    backups = _backups_recentes()
    cfg = {**CONFIG_BACKUP_PADRAO, **(load_config().get("auto_backup") or {})}
    return {
        "caminho": caminho,
        "tamanho": tamanho,
        "modificado": modificado,
        "rede": rede,
        "journal": db.query("PRAGMA journal_mode")[0][0],
        "contagens": {"clientes": um("customers"), "produtos": um("products"), "pedidos": um("orders")},
        "pasta_backups": BACKUP_DIR,
        "backups": backups,
        "auto_backup": {"enabled": bool(cfg.get("enabled", True)), "interval_hours": int(cfg.get("interval_hours") or 1)},
        "ultimo_backup_auto": _estado_auto["ultimo"],
    }


@rota("POST", "/banco/verificar", admin=True, escreve=False)
def verificar(p: Pedido) -> dict:
    r = contexto.db().query("PRAGMA integrity_check")
    resultado = [x[0] for x in r]
    return {"ok": resultado == ["ok"], "detalhes": resultado[:20]}


# ---------------------------------------------------------------- backup


@rota("POST", "/banco/backup", admin=True, escreve=False)
def backup(p: Pedido) -> dict:
    destino = str(p.c("caminho") or "").strip()
    if not destino:
        stem = os.path.splitext(os.path.basename(contexto.banco_atual() or "confeitaria.db"))[0]
        destino = os.path.join(BACKUP_DIR, f"backup_{stem}_{datetime.now().strftime('%d-%m-%Y_%H-%M')}.zip")
    if not destino.lower().endswith(".zip"):
        destino += ".zip"
    criar_backup_zip(destino)
    return {"caminho": destino, "tamanho": os.path.getsize(destino)}


@rota("PUT", "/banco/backup-automatico", admin=True)
def configurar_auto(p: Pedido) -> dict:
    horas = int(p.c("interval_hours") or 1)
    if not 1 <= horas <= 24:
        raise ErroApi("O intervalo deve ser de 1 a 24 horas.")
    cfg = load_config()
    cfg["auto_backup"] = {**(cfg.get("auto_backup") or {}), "enabled": bool(p.c("enabled")), "interval_hours": horas, "type": "local"}
    save_config(cfg)
    return {"ok": True}


_estado_auto: dict = {"ultimo": None}


def _laco_backup_automatico() -> None:
    time.sleep(300)  # primeiro backup 5 min após abrir (como na versão 1.x)
    while True:
        cfg = {**CONFIG_BACKUP_PADRAO, **(load_config().get("auto_backup") or {})}
        horas = max(1, min(24, int(cfg.get("interval_hours") or 1)))
        if cfg.get("enabled", True):
            try:
                stem = os.path.splitext(os.path.basename(contexto.banco_atual() or "confeitaria.db"))[0]
                destino = os.path.join(BACKUP_DIR, f"{_nome_pc()}_{stem}_{datetime.now().strftime('%d-%m-%Y_%H-%M')}.zip")
                criar_backup_zip(destino)
                _estado_auto["ultimo"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[backup] automático: {destino}", flush=True)
            except Exception as e:
                print(f"[backup] falhou: {e}", flush=True)
                from api.tarefas import avisar
                avisar(f"Backup automático falhou: {e}")
        time.sleep(horas * 3600)


def iniciar_backup_automatico() -> None:
    threading.Thread(target=_laco_backup_automatico, daemon=True, name="BackupAutomatico").start()


# ---------------------------------------------------------------- restauração


def _banco_do_zip(zip_path: str, tmp: str) -> str:
    if not zipfile.is_zipfile(zip_path):
        raise ErroApi("O arquivo selecionado não é um arquivo ZIP válido.")
    with zipfile.ZipFile(zip_path) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".db") and "/" not in n.strip("/")]
        if not nomes:
            raise ErroApi("O arquivo ZIP não contém um banco de dados (.db).")
        principal = nomes[0]
        for n in z.namelist():
            if n in (principal, principal + "-wal", principal + "-shm"):
                z.extract(n, tmp)
    return os.path.join(tmp, principal)


def _validar_backup(origem: str, tmp: str) -> str:
    """Copia o banco do backup (.zip ou .db) para `tmp`, consolida o WAL e confere a
    integridade e as tabelas. Devolve o caminho da cópia pronta para usar."""
    if origem.lower().endswith(".zip"):
        novo = _banco_do_zip(origem, tmp)
    elif origem.lower().endswith(".db"):
        novo = os.path.join(tmp, "restaurar.db")
        shutil.copy2(origem, novo)
    else:
        raise ErroApi("Escolha um backup .zip ou um arquivo .db.")
    try:
        c = sqlite3.connect(novo)
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        ok = c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tabelas = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        c.close()
    except sqlite3.DatabaseError as e:
        raise ErroApi(f"O arquivo não é um banco de dados válido: {e}")
    if not ok:
        raise ErroApi("O banco de dados no backup está corrompido. Nada foi alterado.")
    if not {"orders", "products", "customers"} <= tabelas:
        raise ErroApi("O arquivo não parece ser um banco da Confeitaria (faltam tabelas de pedidos, produtos ou clientes).")
    return novo


@rota("POST", "/banco/restaurar", admin=True)
def restaurar(p: Pedido) -> dict:
    """Substitui o banco atual pelo do backup (.zip ou .db), com backup de segurança antes."""
    origem = str(p.c("caminho") or "")
    if not os.path.isfile(origem):
        raise ErroApi("Nenhum arquivo selecionado.")
    atual = contexto.banco_atual()
    if not atual:
        raise ErroApi("Banco atual desconhecido.")
    with tempfile.TemporaryDirectory() as tmp:
        novo = _validar_backup(origem, tmp)
        seguranca = os.path.join(BACKUP_DIR, f"backup_before_restore_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.zip")
        criar_backup_zip(seguranca)

        with contexto.TRAVA:
            contexto.fechar_banco()
            try:
                for sufixo in ("-wal", "-shm"):
                    if os.path.exists(atual + sufixo):
                        os.remove(atual + sufixo)
                shutil.copyfile(novo, atual)
            finally:
                contexto.reabrir_banco()
    return {"ok": True, "seguranca": seguranca}


# ---------------------------------------------------------------- trocar / criar banco


@rota("POST", "/banco/usar", admin=True)
def usar_banco(p: Pedido) -> dict:
    """Passa a usar outro arquivo (local ou de rede \\\\PC\\pasta\\arquivo.db). `criar`: cria
    um banco novo vazio no caminho (nunca sobrescreve um arquivo existente)."""
    caminho = os.path.abspath(str(p.c("caminho") or "").strip())
    if not caminho.lower().endswith(".db"):
        raise ErroApi("O arquivo deve ter extensão .db")
    if p.c("criar"):
        if os.path.exists(caminho):
            raise ErroApi("Já existe um arquivo com esse nome. Escolha outro nome.")
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        sqlite3.connect(caminho).close()
    elif not os.path.isfile(caminho):
        raise ErroApi("Arquivo não encontrado.")
    valido, msg = validate_database_path(caminho)
    if not valido:
        raise ErroApi(msg)
    if not set_database_path(caminho):
        raise ErroApi("Não foi possível salvar a configuração de banco. Verifique as permissões do sistema.")
    contexto.reabrir_banco()
    return {"ok": True, "caminho": contexto.banco_atual(), "mensagem": msg}


def _backups_recentes(limite: int = 30) -> list[dict]:
    lista = []
    if os.path.isdir(BACKUP_DIR):
        for nome in os.listdir(BACKUP_DIR):
            if nome.lower().endswith(".zip"):
                f = os.path.join(BACKUP_DIR, nome)
                lista.append({"nome": nome, "caminho": f, "tamanho": os.path.getsize(f),
                              "data": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M:%S")})
    lista.sort(key=lambda b: b["data"], reverse=True)
    return lista[:limite]


@rota("GET", "/banco/ausente", publica=True)
def info_ausente(p: Pedido) -> dict:
    """Para a tela "banco não encontrado": o caminho que sumiu e os backups locais."""
    ausente = contexto.banco_ausente()
    if not ausente:
        raise ErroApi("O banco de dados já está aberto.", 409)
    return {"caminho": ausente, "backups": _backups_recentes(5)}


@rota("POST", "/banco/localizar", publica=True, escreve=False)
def localizar(p: Pedido) -> dict:
    """Banco configurado não encontrado (tela de abertura). Sem login, porque os
    usuários ficam no próprio banco — por isso só funciona enquanto o banco está
    ausente. `acao`:
      tentar     abre de novo o caminho configurado (ex.: pasta da rede voltou);
      abrir      passa a usar outro arquivo .db existente;
      restaurar  extrai um backup (.zip ou .db) para o caminho configurado;
      criar      começa um banco vazio no caminho configurado (pedido explícito)."""
    ausente = contexto.banco_ausente()
    if not ausente:
        raise ErroApi("O banco de dados já está aberto.", 409)
    acao = p.c("acao")
    caminho = str(p.c("caminho") or "").strip()
    with contexto.TRAVA:
        if acao == "tentar":
            pass
        elif acao == "abrir":
            caminho = os.path.abspath(caminho)
            if not caminho.lower().endswith(".db") or not os.path.isfile(caminho):
                raise ErroApi("Escolha um arquivo .db existente.")
            valido, msg = validate_database_path(caminho)
            if not valido:
                raise ErroApi(msg)
            if not set_database_path(caminho):
                raise ErroApi("Não foi possível salvar a configuração de banco.")
        elif acao == "restaurar":
            if not os.path.isfile(caminho):
                raise ErroApi("Nenhum arquivo selecionado.")
            with tempfile.TemporaryDirectory() as tmp:
                novo = _validar_backup(caminho, tmp)
                os.makedirs(os.path.dirname(ausente) or ".", exist_ok=True)
                for sufixo in ("-wal", "-shm"):  # restos do banco que sumiu não podem ser aplicados
                    if os.path.exists(ausente + sufixo):
                        os.remove(ausente + sufixo)
                shutil.copyfile(novo, ausente)
        elif acao == "criar":
            os.makedirs(os.path.dirname(ausente) or ".", exist_ok=True)
            sqlite3.connect(ausente).close()
        else:
            raise ErroApi("Ação inválida.")
        try:
            contexto.reabrir_banco()
        except contexto.BancoAusente as e:
            raise ErroApi(f"O banco ainda não foi encontrado: {e.caminho}", 404, "banco_ausente")
    return {"ok": True, "caminho": contexto.banco_atual()}


@rota("POST", "/banco/reparar", admin=True)
def reparar(p: Pedido) -> dict:
    db = contexto.db()
    if db.query("PRAGMA integrity_check")[0][0] == "ok":
        return {"ok": True, "integro": True, "mensagem": "O banco de dados está íntegro e não precisa de reparo."}
    criar_backup_zip(os.path.join(BACKUP_DIR, f"backup_before_repair_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.zip"))
    sucesso, msg = db.repair_database()
    contexto.reabrir_banco()
    if not sucesso:
        raise ErroApi(msg, 500)
    return {"ok": True, "integro": False, "mensagem": msg}
