# -*- coding: utf-8 -*-
"""Clientes, etiquetas e histórico de auditoria (logs)."""

from __future__ import annotations

from api import ErroApi, Pedido, contexto, rota
from api.util import agora, auditar, diff, ids, like, linhas, texto

ESC = " ESCAPE '\\'"

# ---------------------------------------------------------------- clientes


@rota("GET", "/clientes")
def listar_clientes(p: Pedido) -> dict:
    db = contexto.db()
    termo = p.q("q").strip()
    if termo:
        t = like(termo)
        rows = db.query(
            "SELECT * FROM customers WHERE name LIKE ?{0} OR phone LIKE ?{0} OR address LIKE ?{0} OR observation LIKE ?{0} ORDER BY name".format(ESC),
            (t, t, t, t),
        )
    else:
        rows = db.query("SELECT * FROM customers ORDER BY name")
    return {"clientes": linhas(rows)}


def _campos_cliente(p: Pedido) -> tuple:
    nome = texto(p.c("name"))
    if not nome:
        raise ErroApi("Nome é obrigatório.")
    return nome, texto(p.c("phone")), texto(p.c("address")), texto(p.c("observation"))


@rota("POST", "/clientes")
def criar_cliente(p: Pedido) -> dict:
    db = contexto.db()
    nome, fone, end, obs = _campos_cliente(p)
    cur = db.execute("INSERT INTO customers(name, phone, address, observation) VALUES (?,?,?,?)", (nome, fone, end, obs))
    novo = cur.lastrowid
    auditar(db, "customer", novo, "create", f"name={nome},phone={fone}")
    return {"id": novo}


@rota("PUT", "/clientes/{id}")
def atualizar_cliente(p: Pedido) -> dict:
    db = contexto.db()
    cid = p.id()
    antigo = db.query("SELECT * FROM customers WHERE id=?", (cid,))
    if not antigo:
        raise ErroApi("Cliente não encontrado.", 404)
    a = antigo[0]
    nome, fone, end, obs = _campos_cliente(p)
    db.execute("UPDATE customers SET name=?, phone=?, address=?, observation=? WHERE id=?", (nome, fone, end, obs, cid))
    auditar(db, "customer", cid, "update", diff([
        ("name", a["name"], nome), ("phone", a["phone"], fone),
        ("address", a["address"], end), ("observation", a["observation"], obs),
    ]))
    return {"ok": True}


@rota("POST", "/clientes/excluir")
def excluir_clientes(p: Pedido) -> dict:
    """Exclui vários; clientes com pedidos são preservados e devolvidos em `bloqueados`."""
    db = contexto.db()
    excluidos, bloqueados = 0, []
    with db.transaction():
        for cid in ids(p.c("ids")):
            if db.query("SELECT COUNT(*) AS c FROM orders WHERE customer_id=?", (cid,))[0]["c"] > 0:
                r = db.query("SELECT name FROM customers WHERE id=?", (cid,))
                bloqueados.append(r[0]["name"] if r else f"#{cid}")
                continue
            db.execute("DELETE FROM customers WHERE id=?", (cid,))
            auditar(db, "customer", cid, "delete")
            excluidos += 1
    return {"excluidos": excluidos, "bloqueados": bloqueados}


# ---------------------------------------------------------------- etiquetas


@rota("GET", "/etiquetas")
def listar_etiquetas(p: Pedido) -> dict:
    rows = contexto.db().query("SELECT id, name, color FROM labels ORDER BY name")
    return {"etiquetas": [{**dict(r), "color": r["color"] or "#6B7280"} for r in rows]}


def _cor(valor) -> str:
    cor = str(valor or "#6B7280").strip().lower()
    if len(cor) != 7 or not cor.startswith("#"):
        raise ErroApi("Cor inválida.")
    return cor


@rota("POST", "/etiquetas")
def criar_etiqueta(p: Pedido) -> dict:
    db = contexto.db()
    nome = texto(p.c("name"))
    if not nome:
        raise ErroApi("O nome não pode estar vazio.")
    if db.query("SELECT 1 FROM labels WHERE LOWER(name)=LOWER(?)", (nome,)):
        raise ErroApi("Já existe uma etiqueta com este nome.")
    cur = db.execute("INSERT INTO labels(name, color, created_at) VALUES (?,?,?)", (nome, _cor(p.c("color")), agora()))
    return {"id": cur.lastrowid}


@rota("PUT", "/etiquetas/{id}")
def atualizar_etiqueta(p: Pedido) -> dict:
    db = contexto.db()
    eid = p.id()
    atual = db.query("SELECT * FROM labels WHERE id=?", (eid,))
    if not atual:
        raise ErroApi("Etiqueta não encontrada.", 404)
    nome_antigo = atual[0]["name"]
    nome = texto(p.c("name"))
    if not nome:
        raise ErroApi("O nome não pode estar vazio.")
    if nome_antigo.lower() == "comum" and nome != nome_antigo:
        raise ErroApi("\"Comum\" é a etiqueta padrão dos pedidos e não pode ser renomeada (a cor pode mudar).")
    if nome != nome_antigo and db.query("SELECT 1 FROM labels WHERE LOWER(name)=LOWER(?) AND id!=?", (nome, eid)):
        raise ErroApi("Já existe uma etiqueta com este nome.")
    with db.transaction():
        db.execute("UPDATE labels SET name=?, color=? WHERE id=?", (nome, _cor(p.c("color")), eid))
        if nome != nome_antigo:
            db.execute("UPDATE orders SET label=? WHERE LOWER(label)=LOWER(?)", (nome, nome_antigo))
    return {"ok": True}


@rota("GET", "/etiquetas/{id}/uso")
def uso_etiqueta(p: Pedido) -> dict:
    db = contexto.db()
    r = db.query("SELECT name FROM labels WHERE id=?", (p.id(),))
    if not r:
        raise ErroApi("Etiqueta não encontrada.", 404)
    n = db.query("SELECT COUNT(*) AS c FROM orders WHERE LOWER(label)=LOWER(?)", (r[0]["name"],))[0]["c"]
    return {"pedidos": n}


@rota("DELETE", "/etiquetas/{id}")
def excluir_etiqueta(p: Pedido) -> dict:
    db = contexto.db()
    eid = p.id()
    r = db.query("SELECT name FROM labels WHERE id=?", (eid,))
    if not r:
        raise ErroApi("Etiqueta não encontrada.", 404)
    if r[0]["name"].lower() == "comum":
        raise ErroApi("\"Comum\" é a etiqueta padrão dos pedidos e não pode ser excluída.")
    with db.transaction():
        # Pedidos com esta etiqueta passam a 'Comum' (comparação sem diferenciar maiúsculas,
        # igual ao renomear).
        db.execute("UPDATE orders SET label='Comum' WHERE LOWER(label)=LOWER(?)", (r[0]["name"],))
        db.execute("DELETE FROM labels WHERE id=?", (eid,))
    return {"ok": True}


# ---------------------------------------------------------------- logs


@rota("GET", "/logs", admin=True)
def logs(p: Pedido) -> dict:
    entidade = p.q("entidade")
    if entidade not in ("order", "customer", "product", "stock_movement"):
        raise ErroApi("Entidade inválida.")
    rows = contexto.db().query(
        "SELECT created_at, user, action, details FROM audit_logs WHERE entity=? AND entity_id=? ORDER BY created_at DESC",
        (entidade, int(p.q("id", "0") or 0)),
    )
    return {"logs": linhas(rows)}
