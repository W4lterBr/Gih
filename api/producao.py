# -*- coding: utf-8 -*-
"""Lista de produção (a mesma que o painel da cozinha lê) e Dashboard."""

from __future__ import annotations

from datetime import date

from api import ErroApi, Pedido, contexto, rota
from api.pedidos import separar_lote
from api.util import agora, data_iso, hoje_iso, ids, inteiro, linhas, texto

# Pedidos que entram na lista ao importar: todos os do dia que ainda vão ser entregues.
# (A versão 1.x deixava de fora "Pagamento na Retirada", que também precisa ser produzido.)
_STATUS_FORA = ("Entregue", "Cancelado", "cancelled", "completed", "Concluído")


@rota("GET", "/producao")
def listar_producao(p: Pedido) -> dict:
    """Itens da lista + estoque atual com as encomendas do dia escolhido."""
    db = contexto.db()
    dia = data_iso(p.q("data") or hoje_iso(), "data")
    itens = db.query("""
        SELECT pi.id, pi.product_id, p.name AS produto, pi.quantity, pi.size, pi.notes, pi.created_at
        FROM production_items pi JOIN products p ON p.id = pi.product_id
        ORDER BY pi.created_at DESC
    """)
    where, params = "", [dia]
    termo = p.q("q").strip()
    if termo:
        where = "WHERE p.name LIKE ?"
        params.append(f"%{termo}%")
    estoque = db.query(f"""
        SELECT p.id, p.name, p.stock, p.min_stock, COALESCE(SUM(o.quantity), 0) AS encomendas
        FROM products p
        LEFT JOIN orders o ON o.product_id = p.id AND o.status != 'Entregue' AND DATE(o.delivery_date) = ?
        {where}
        GROUP BY p.id, p.name, p.stock
        ORDER BY CASE WHEN p.stock <= 0 THEN 0 WHEN p.stock < 5 THEN 1 ELSE 2 END, p.name
    """, tuple(params))
    return {"itens": linhas(itens), "estoque": linhas(estoque)}


@rota("POST", "/producao")
def adicionar_item(p: Pedido) -> dict:
    db = contexto.db()
    pid = inteiro(p.c("product_id"), "Produto", 1)
    qtd = inteiro(p.c("quantity"), "Quantidade", 1, 1_000_000)
    if not db.query("SELECT 1 FROM products WHERE id=?", (pid,)):
        raise ErroApi("Produto não encontrado.")
    cur = db.execute(
        "INSERT INTO production_items (product_id, quantity, size, notes, created_at) VALUES (?, ?, ?, ?, ?)",
        (pid, qtd, texto(p.c("size")), texto(p.c("notes")), agora()),
    )
    return {"id": cur.lastrowid}


@rota("PUT", "/producao/{id}")
def editar_item(p: Pedido) -> dict:
    """Mudar a quantidade lança a diferença no estoque como movimentação 'Produção'
    (mesma regra do painel da cozinha)."""
    db = contexto.db()
    iid = p.id()
    r = db.query("SELECT product_id, quantity FROM production_items WHERE id=?", (iid,))
    if not r:
        raise ErroApi("Item não encontrado.", 404)
    diferenca = 0
    with db.transaction():
        if "quantity" in p.corpo:
            nova = inteiro(p.c("quantity"), "Quantidade", 1, 1_000_000)
            diferenca = nova - r[0]["quantity"]
            db.execute("UPDATE production_items SET quantity=? WHERE id=?", (nova, iid))
            if diferenca:
                db.execute("UPDATE products SET stock = stock + ? WHERE id=?", (diferenca, r[0]["product_id"]))
                db.execute(
                    "INSERT INTO stock_movements(product_id, type, category, quantity, reason, order_id, created_at, created_by) VALUES (?,?,?,?,?,?,?,?)",
                    (r[0]["product_id"], "entrada" if diferenca > 0 else "saida", "Produção", abs(diferenca),
                     "Ajuste na lista de produção", None, agora(), db.current_user or "unknown"),
                )
        if "size" in p.corpo:
            db.execute("UPDATE production_items SET size=? WHERE id=?", (texto(p.c("size")), iid))
        if "notes" in p.corpo:
            db.execute("UPDATE production_items SET notes=? WHERE id=?", (texto(p.c("notes")), iid))
    return {"ok": True, "estoque": diferenca}


@rota("POST", "/producao/remover")
def remover_itens(p: Pedido) -> dict:
    db = contexto.db()
    alvo = ids(p.c("ids"))
    with db.transaction():
        for iid in alvo:
            db.execute("DELETE FROM production_items WHERE id=?", (iid,))
    return {"removidos": len(alvo)}


@rota("POST", "/producao/limpar")
def limpar_lista(p: Pedido) -> dict:
    db = contexto.db()
    n = db.query("SELECT COUNT(*) AS c FROM production_items")[0]["c"]
    db.execute("DELETE FROM production_items")
    return {"removidos": n}


@rota("POST", "/producao/importar")
def importar_pedidos(p: Pedido) -> dict:
    """Substitui a lista pelos pedidos com entrega no dia. Sem `confirmar`, só informa
    quantos itens a lista tem (a interface pede confirmação antes de apagar)."""
    db = contexto.db()
    dia = data_iso(p.c("data") or hoje_iso(), "data")
    marcadores = ",".join("?" * len(_STATUS_FORA))
    pedidos = db.query(f"""
        SELECT o.id, c.name AS cliente, o.product_id, p.size, o.quantity, o.notes
        FROM orders o JOIN products p ON p.id = o.product_id LEFT JOIN customers c ON c.id = o.customer_id
        WHERE DATE(o.delivery_date) = ? AND o.status NOT IN ({marcadores})
        ORDER BY c.name, o.notes
    """, (dia, *_STATUS_FORA))
    if not pedidos:
        raise ErroApi(f"Nenhum pedido encontrado para {date.fromisoformat(dia).strftime('%d/%m/%Y')}.", 404, "vazio")
    atuais = db.query("SELECT COUNT(*) AS c FROM production_items")[0]["c"]
    if atuais and not p.c("confirmar"):
        return {"precisa_confirmar": True, "itens_atuais": atuais, "pedidos": len(pedidos)}
    with db.transaction():
        db.execute("DELETE FROM production_items")
        for o in pedidos:
            obs = separar_lote(o["notes"])[2]
            nota = f"{o['cliente'] or 'Cliente desconhecido'} - Importado de pedidos" + (f" · {obs}" if obs else "")
            db.execute(
                "INSERT INTO production_items (product_id, quantity, size, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                (o["product_id"], o["quantity"], o["size"], nota, agora()),
            )
    return {"importados": len(pedidos)}


# ---------------------------------------------------------------- dashboard


@rota("GET", "/dashboard")
def dashboard(p: Pedido) -> dict:
    """Indicadores do dia a dia. O app não controla preço por pedido (orders.total = 0),
    então o painel mostra quantidades; valor estimado usa o preço de cadastro do produto."""
    db = contexto.db()
    hoje = hoje_iso()
    um = lambda sql, *a: db.query(sql, a)[0][0]  # noqa: E731
    kpis = {
        "pedidos_hoje": um("SELECT COUNT(*) FROM orders WHERE DATE(delivery_date)=?", hoje),
        "itens_hoje": um("SELECT COALESCE(SUM(quantity),0) FROM orders WHERE DATE(delivery_date)=?", hoje),
        "aguardando_pagamento": um("SELECT COUNT(*) FROM orders WHERE status='Aguardando Pagamento' AND DATE(delivery_date)>=?", hoje),
        "proximos_7_dias": um("SELECT COUNT(*) FROM orders WHERE DATE(delivery_date) BETWEEN DATE(?, '+1 day') AND DATE(?, '+7 days')", hoje, hoje),
        "estoque_baixo": um("SELECT COUNT(*) FROM products WHERE stock <= min_stock AND min_stock > 0"),
        "esgotados": um("SELECT COUNT(*) FROM products WHERE stock <= 0"),
        "clientes": um("SELECT COUNT(*) FROM customers"),
        "valor_mes": um("""SELECT COALESCE(SUM(o.quantity * COALESCE(p.price,0)),0) FROM orders o JOIN products p ON p.id=o.product_id
                           WHERE strftime('%Y-%m', o.delivery_date)=strftime('%Y-%m', ?)""", hoje),
    }
    por_dia = db.query("""
        SELECT DATE(delivery_date) AS dia, COUNT(*) AS pedidos, COALESCE(SUM(quantity),0) AS itens
        FROM orders WHERE DATE(delivery_date) BETWEEN DATE(?, '-6 days') AND DATE(?, '+7 days')
        GROUP BY dia ORDER BY dia
    """, (hoje, hoje))
    status = db.query("SELECT status, COUNT(*) AS n FROM orders WHERE DATE(delivery_date)>=DATE(?, '-30 days') GROUP BY status ORDER BY n DESC", (hoje,))
    top = db.query("""
        SELECT p.name, SUM(o.quantity) AS quantidade, COALESCE(p.price,0) AS preco
        FROM orders o JOIN products p ON p.id=o.product_id
        WHERE DATE(o.delivery_date) >= DATE(?, '-30 days')
        GROUP BY p.id ORDER BY quantidade DESC LIMIT 8
    """, (hoje,))
    entregas = db.query("""
        SELECT MIN(o.id) AS id, c.name AS cliente, c.phone AS telefone, o.status, COALESCE(o.label,'Comum') AS label,
               l.color AS label_color, GROUP_CONCAT(p.name || ' ×' || o.quantity, ', ') AS produtos
        FROM orders o JOIN customers c ON c.id=o.customer_id JOIN products p ON p.id=o.product_id
        LEFT JOIN labels l ON LOWER(l.name)=LOWER(COALESCE(o.label,'Comum'))
        WHERE DATE(o.delivery_date)=?
        GROUP BY o.customer_id, o.status, CASE WHEN o.notes LIKE 'LOTE:%' THEN SUBSTR(o.notes,1,INSTR(o.notes,'|')) ELSE o.id END
        ORDER BY c.name
    """, (hoje,))
    baixo = db.query("SELECT id, name, stock, min_stock FROM products WHERE stock <= min_stock AND min_stock > 0 ORDER BY stock, name LIMIT 8")
    return {"kpis": kpis, "por_dia": linhas(por_dia), "status": linhas(status), "top": linhas(top),
            "entregas_hoje": linhas(entregas), "estoque_baixo": linhas(baixo)}


@rota("GET", "/menu")
def contagens_menu(p: Pedido) -> dict:
    """Números pequenos do menu lateral (consulta leve, chamada com frequência)."""
    db = contexto.db()
    return {
        "pedidosHoje": db.query("SELECT COUNT(DISTINCT customer_id || '|' || COALESCE(SUBSTR(notes,1,INSTR(notes,'|')), id)) FROM orders WHERE DATE(delivery_date)=?", (hoje_iso(),))[0][0],
        "producao": db.query("SELECT COUNT(*) FROM production_items")[0][0],
        "esgotados": db.query("SELECT COUNT(*) FROM products WHERE stock <= 0")[0][0],
    }
