# -*- coding: utf-8 -*-
"""Lista de produção (a mesma que o painel da cozinha lê) e Dashboard."""

from __future__ import annotations

from datetime import date

from api import ErroApi, Pedido, contexto, rota
from api.pedidos import separar_lote
from api.util import agora, data_iso, hoje_iso, ids, inteiro, like, linhas, quantidade, texto, unidade_de

# Pedidos que ainda vão ser produzidos/entregues: nem entregues nem cancelados (o
# pagamento não importa — "Pagamento na Retirada" também precisa ser produzido).
A_ENTREGAR = "COALESCE(o.situacao, 'aberto') = 'aberto'"


@rota("GET", "/producao")
def listar_producao(p: Pedido) -> dict:
    """Itens da lista + estoque atual com as encomendas do dia escolhido."""
    db = contexto.db()
    dia = data_iso(p.q("data") or hoje_iso(), "data")
    itens = db.query("""
        SELECT pi.id, pi.product_id, p.name AS produto, p.unit, pi.quantity, pi.size, pi.notes, pi.created_at
        FROM production_items pi JOIN products p ON p.id = pi.product_id
        ORDER BY pi.created_at DESC
    """)
    where, params = "", [dia]
    termo = p.q("q").strip()
    if termo:
        where = "WHERE p.name LIKE ? ESCAPE '\\'"
        params.append(like(termo))
    estoque = db.query(f"""
        SELECT p.id, p.name, p.unit, p.stock, p.min_stock, ROUND(COALESCE(SUM(o.quantity), 0), 3) AS encomendas
        FROM products p
        LEFT JOIN orders o ON o.product_id = p.id AND COALESCE(o.situacao, 'aberto') = 'aberto' AND DATE(o.delivery_date) = ?
        {where}
        GROUP BY p.id, p.name, p.stock
        ORDER BY CASE WHEN p.stock <= 0 THEN 0 WHEN p.stock < 5 THEN 1 ELSE 2 END, p.name
    """, tuple(params))
    return {"itens": linhas(itens), "estoque": linhas(estoque)}


@rota("POST", "/producao")
def adicionar_item(p: Pedido) -> dict:
    db = contexto.db()
    pid = inteiro(p.c("product_id"), "Produto", 1)
    if not db.query("SELECT 1 FROM products WHERE id=?", (pid,)):
        raise ErroApi("Produto não encontrado.")
    qtd = quantidade(p.c("quantity"), "Quantidade", unidade_de(db, pid))
    cur = db.execute(
        "INSERT INTO production_items (product_id, quantity, size, notes, created_at) VALUES (?, ?, ?, ?, ?)",
        (pid, qtd, texto(p.c("size")), texto(p.c("notes")), agora()),
    )
    return {"id": cur.lastrowid}


@rota("PUT", "/producao/{id}")
def editar_item(p: Pedido) -> dict:
    """Edita um item da lista. Não mexe no estoque: a lista diz o que produzir e o
    estoque só recebe as quantidades em "Produção feita" no painel da cozinha (antes a
    edição lançava a diferença e a conclusão somava tudo de novo — contagem dupla)."""
    db = contexto.db()
    iid = p.id()
    r = db.query("SELECT product_id FROM production_items WHERE id=?", (iid,))
    if not r:
        raise ErroApi("Item não encontrado.", 404)
    with db.transaction():
        if "quantity" in p.corpo:
            nova = quantidade(p.c("quantity"), "Quantidade", unidade_de(db, r[0]["product_id"]))
            db.execute("UPDATE production_items SET quantity=? WHERE id=?", (nova, iid))
        if "size" in p.corpo:
            db.execute("UPDATE production_items SET size=? WHERE id=?", (texto(p.c("size")), iid))
        if "notes" in p.corpo:
            db.execute("UPDATE production_items SET notes=? WHERE id=?", (texto(p.c("notes")), iid))
    return {"ok": True}


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
    pedidos = db.query(f"""
        SELECT o.id, c.name AS cliente, o.product_id, p.size, o.quantity, o.notes
        FROM orders o JOIN products p ON p.id = o.product_id LEFT JOIN customers c ON c.id = o.customer_id
        WHERE DATE(o.delivery_date) = ? AND {A_ENTREGAR}
        ORDER BY c.name, o.notes
    """, (dia,))
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

# Pedidos como a lista de Pedidos mostra: os itens de um lote são um pedido só, pedidos
# separados do mesmo cliente são pedidos diferentes. Cancelados ficam de fora de todos
# os números. Use como CTE: "WITH pedidos AS (...) SELECT ... FROM pedidos".
CTE_PEDIDOS = """
    pedidos AS (
        SELECT DATE(o.delivery_date) AS dia, o.status, COALESCE(o.situacao, 'aberto') AS situacao,
               MIN(o.id) AS id, o.customer_id, COALESCE(o.label, 'Comum') AS label,
               SUM(CASE WHEN pr.unit = 'kg' THEN 1 ELSE o.quantity END) AS itens, GROUP_CONCAT(o.product_id) AS produtos_ids
        FROM orders o LEFT JOIN products pr ON pr.id = o.product_id
        WHERE COALESCE(o.situacao, 'aberto') != 'cancelado'
        GROUP BY o.customer_id, o.delivery_date, o.status, COALESCE(o.situacao, 'aberto'),
                 CASE WHEN o.notes LIKE 'LOTE:%' THEN SUBSTR(o.notes, 1, INSTR(o.notes, '|')) ELSE o.id END
    )"""
SQL_PEDIDOS_DO_DIA = "WITH" + CTE_PEDIDOS + " SELECT COUNT(*) FROM pedidos WHERE dia = ?"


@rota("GET", "/dashboard")
def dashboard(p: Pedido) -> dict:
    """Indicadores do dia a dia, contando pedidos como a lista de Pedidos (lote = 1).
    O app não controla preço por pedido (orders.total = 0); o valor estimado usa o
    preço de cadastro do produto."""
    db = contexto.db()
    hoje = hoje_iso()
    um = lambda sql, *a: db.query("WITH" + CTE_PEDIDOS + " " + sql, a)[0][0]  # noqa: E731
    kpis = {
        "pedidos_hoje": um("SELECT COUNT(*) FROM pedidos WHERE dia = ?", hoje),
        "itens_hoje": um("SELECT COALESCE(SUM(itens), 0) FROM pedidos WHERE dia = ?", hoje),
        # A receber: não pagos que ainda vão ser entregues, ou já entregues sem pagar (fiado).
        "aguardando_pagamento": um("SELECT COUNT(*) FROM pedidos WHERE status IN ('Aguardando Pagamento', 'Pagamento na Retirada') AND (dia >= ? OR situacao = 'entregue')", hoje),
        "proximos_7_dias": um("SELECT COUNT(*) FROM pedidos WHERE dia BETWEEN DATE(?, '+1 day') AND DATE(?, '+7 days')", hoje, hoje),
        "estoque_baixo": db.query("SELECT COUNT(*) FROM products WHERE stock <= min_stock AND min_stock > 0")[0][0],
        "esgotados": db.query("SELECT COUNT(*) FROM products WHERE stock <= 0")[0][0],
        "clientes": db.query("SELECT COUNT(*) FROM customers")[0][0],
        "valor_mes": db.query("""SELECT COALESCE(SUM(o.quantity * COALESCE(p.price,0)),0) FROM orders o JOIN products p ON p.id=o.product_id
                                 WHERE strftime('%Y-%m', o.delivery_date)=strftime('%Y-%m', ?)
                                 AND COALESCE(o.situacao, 'aberto') != 'cancelado'""", (hoje,))[0][0],
    }
    por_dia = db.query("WITH" + CTE_PEDIDOS + """
        SELECT dia, COUNT(*) AS pedidos, COALESCE(SUM(itens), 0) AS itens
        FROM pedidos WHERE dia BETWEEN DATE(?, '-6 days') AND DATE(?, '+7 days')
        GROUP BY dia ORDER BY dia
    """, (hoje, hoje))
    status = db.query("WITH" + CTE_PEDIDOS + """
        SELECT status, COUNT(*) AS n FROM pedidos WHERE dia >= DATE(?, '-30 days') GROUP BY status ORDER BY n DESC
    """, (hoje,))
    top = db.query("""
        SELECT p.name, p.unit, ROUND(SUM(o.quantity), 3) AS quantidade, COALESCE(p.price,0) AS preco
        FROM orders o JOIN products p ON p.id=o.product_id
        WHERE DATE(o.delivery_date) >= DATE(?, '-30 days') AND COALESCE(o.situacao, 'aberto') != 'cancelado'
        GROUP BY p.id ORDER BY quantidade DESC LIMIT 8
    """, (hoje,))
    entregas = db.query("""
        SELECT MIN(o.id) AS id, c.name AS cliente, c.phone AS telefone, o.status, COALESCE(o.situacao, 'aberto') AS situacao,
               COALESCE(o.label,'Comum') AS label,
               l.color AS label_color, GROUP_CONCAT(p.name || ' ' || CASE WHEN p.unit = 'kg' THEN REPLACE(CAST(o.quantity AS TEXT), '.', ',') || ' kg' ELSE '×' || CAST(o.quantity AS INTEGER) END, ', ') AS produtos
        FROM orders o JOIN customers c ON c.id=o.customer_id JOIN products p ON p.id=o.product_id
        LEFT JOIN labels l ON LOWER(l.name)=LOWER(COALESCE(o.label,'Comum'))
        WHERE DATE(o.delivery_date)=? AND COALESCE(o.situacao, 'aberto') != 'cancelado'
        GROUP BY o.customer_id, o.status, COALESCE(o.situacao, 'aberto'),
                 CASE WHEN o.notes LIKE 'LOTE:%' THEN SUBSTR(o.notes,1,INSTR(o.notes,'|')) ELSE o.id END
        ORDER BY COALESCE(o.situacao, 'aberto') = 'entregue', c.name
    """, (hoje,))
    baixo = db.query("SELECT id, name, stock, min_stock, unit FROM products WHERE stock <= min_stock AND min_stock > 0 ORDER BY stock, name LIMIT 8")
    top = linhas(top)
    if (p.usuario or {}).get("role") in ("recepcao", "cozinha"):
        # Faturamento e preços são do administrador.
        kpis["valor_mes"] = None
        for t in top:
            t["preco"] = None
    return {"kpis": kpis, "por_dia": linhas(por_dia), "status": linhas(status), "top": top,
            "entregas_hoje": linhas(entregas), "estoque_baixo": linhas(baixo)}


@rota("GET", "/menu")
def contagens_menu(p: Pedido) -> dict:
    """Números pequenos do menu lateral (consulta leve, chamada com frequência)."""
    db = contexto.db()
    return {
        "pedidosHoje": db.query(SQL_PEDIDOS_DO_DIA, (hoje_iso(),))[0][0],
        "producao": db.query("SELECT COUNT(*) FROM production_items")[0][0],
        "esgotados": db.query("SELECT COUNT(*) FROM products WHERE stock <= 0")[0][0],
    }
