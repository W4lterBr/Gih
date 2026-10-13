# -*- coding: utf-8 -*-
"""Custos: insumos, compras, fichas técnicas (receitas) e preço de venda.

Só administradores: custo, margem e lucro são informação do dono. As contas ficam
em core/custos.py (Decimal, sem arredondar no meio do caminho)."""

from __future__ import annotations

from decimal import Decimal

from api import ErroApi, Pedido, contexto, rota
from api.util import agora, auditar, data_iso, hoje_iso, like, texto
from core import custos as C
from core.custos import ErroCusto, dec, guardar

D = Decimal


def _c(fn, *a, **k):
    """Converte ErroCusto (validação do motor de custos) em ErroApi 400."""
    try:
        return fn(*a, **k)
    except ErroCusto as e:
        raise ErroApi(str(e))


# ---------------------------------------------------------------- parâmetros


@rota("GET", "/custos/parametros", admin=True)
def ler_parametros(p: Pedido) -> dict:
    return C.parametros_json(C.parametros(contexto.db()))


@rota("PUT", "/custos/parametros", admin=True)
def salvar_parametros(p: Pedido) -> dict:
    db = contexto.db()
    base = p.c("cost_basis") or "ultima"
    if base not in ("ultima", "media"):
        raise ErroApi("Base de custo inválida.")
    dias = _c(dec, p.c("avg_days", 90), "o período da média", D(1), D(3650))
    if dias != dias.to_integral_value():
        raise ErroApi("O período da média deve ser em dias inteiros.")
    pct = lambda nome, rot: _c(dec, p.c(nome), rot, D(0), D("99.99"), vazio=D(0))  # noqa: E731
    v = {
        "labor_hour": _c(dec, p.c("labor_hour"), "o valor da hora de trabalho", D(0), D(100000), vazio=D(0)),
        "fixed_pct": pct("fixed_pct", "as despesas fixas"),
        "tax_pct": pct("tax_pct", "os impostos"),
        "fee_pct": pct("fee_pct", "as taxas"),
        "margin_pct": pct("margin_pct", "o lucro desejado"),
    }
    if v["fixed_pct"] + v["tax_pct"] + v["fee_pct"] + v["margin_pct"] >= 100:
        raise ErroApi("Despesas fixas + impostos + taxas + lucro precisam somar menos de 100% do preço.")
    try:
        arred = format(D(str(p.c("rounding") or "0.01").replace(",", ".")), ".2f")
    except Exception:
        arred = ""
    if arred not in C.ARREDONDAMENTOS:
        raise ErroApi("Arredondamento inválido.")
    antes = C.parametros_json(C.parametros(db))
    db.execute(
        "UPDATE cost_settings SET cost_basis=?, avg_days=?, labor_hour=?, fixed_pct=?, tax_pct=?, fee_pct=?, margin_pct=?, rounding=?, updated_at=? WHERE id=1",
        (base, int(dias), *(guardar(v[k]) for k in ("labor_hour", "fixed_pct", "tax_pct", "fee_pct", "margin_pct")), arred, agora()),
    )
    depois = C.parametros_json(C.parametros(db))
    mud = "; ".join(f"{k}: {antes[k]} -> {depois[k]}" for k in depois if antes.get(k) != depois[k])
    if mud:
        auditar(db, "cost_settings", 1, "update", mud)
    return {"ok": True}


# ---------------------------------------------------------------- insumos


def _usos(db, iid: int) -> list[str]:
    return [r["name"] for r in db.query(
        "SELECT DISTINCT r.name FROM recipe_items i JOIN recipes r ON r.id=i.recipe_id WHERE i.ingredient_id=? ORDER BY r.name", (iid,))]


@rota("GET", "/custos/insumos", admin=True)
def listar_insumos(p: Pedido) -> dict:
    db = contexto.db()
    termo = p.q("q").strip()
    if termo:
        rows = db.query("SELECT id FROM ingredients WHERE name LIKE ? ESCAPE '\\' OR notes LIKE ? ESCAPE '\\' ORDER BY name COLLATE NOCASE", (like(termo), like(termo)))
    else:
        rows = db.query("SELECT id FROM ingredients ORDER BY name COLLATE NOCASE")
    calc = C.Calculadora(db)
    usos = {r["ingredient_id"]: r["n"] for r in db.query(
        "SELECT ingredient_id, COUNT(DISTINCT recipe_id) AS n FROM recipe_items WHERE ingredient_id IS NOT NULL GROUP BY ingredient_id")}
    out = []
    for r in rows:
        info = C.insumo_json(calc.insumo(r["id"]))
        info["usos"] = usos.get(r["id"], 0)
        out.append(info)
    return {"insumos": out}


def _campos_insumo(p: Pedido) -> dict:
    nome = texto(p.c("name"))
    if not nome:
        raise ErroApi("Nome é obrigatório.")
    cat = str(p.c("category") or "ingrediente")
    if cat not in C.CATEGORIAS:
        raise ErroApi("Categoria inválida.")
    base = str(p.c("base_unit") or "")
    if base not in C.BASES:
        raise ErroApi("Escolha como o insumo é medido: peso, volume ou unidade.")
    aprov = _c(dec, p.c("yield_pct"), "o aproveitamento", vazio=D(100), maior_que_zero=True, maximo=D(100))
    dens = p.c("density")
    dens = None if dens in (None, "") else _c(dec, dens, "a densidade", maior_que_zero=True, maximo=D(100))
    if dens is not None and base == "un":
        dens = None
    return {"name": nome, "category": cat, "base_unit": base, "yield_pct": guardar(aprov),
            "density": guardar(dens) if dens is not None else None, "notes": texto(p.c("notes"))}


def _campos_compra(c: dict, base: str) -> dict:
    """{data, fornecedor, embalagens, conteudo, unidade, total}. Conteúdo é por embalagem."""
    if not isinstance(c, dict):
        raise ErroApi("Compra inválida.")
    un = _c(C.unidade, c.get("unidade"), "a unidade da embalagem")
    if C.UNIDADES[un][0] != base:
        raise ErroApi("A unidade da embalagem não combina com a medida do insumo (peso, volume ou unidade).")
    emb = _c(dec, c.get("embalagens"), "a quantidade de embalagens", maior_que_zero=True, maximo=D(1000000), vazio=D(1))
    conteudo = _c(dec, c.get("conteudo"), "o conteúdo da embalagem", maior_que_zero=True, maximo=D(100000000))
    total = _c(dec, c.get("total"), "o valor pago", maior_que_zero=True, maximo=D(100000000))
    data = data_iso(c.get("data") or hoje_iso(), "data da compra")
    if data > hoje_iso():
        raise ErroApi("A data da compra não pode ser no futuro.")
    return {
        "purchased_at": data, "supplier": texto(c.get("fornecedor")), "packages": guardar(emb),
        "package_qty": guardar(C.converter(conteudo, un, base)), "package_unit": un,
        "total": guardar(total), "notes": texto(c.get("obs")),
    }


def _gravar_compra(db, iid: int, c: dict) -> int:
    u = contexto.usuario["username"] if contexto.usuario else None
    cur = db.execute(
        "INSERT INTO ingredient_purchases(ingredient_id, purchased_at, supplier, packages, package_qty, package_unit, total, notes, created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (iid, c["purchased_at"], c["supplier"], c["packages"], c["package_qty"], c["package_unit"], c["total"], c["notes"], agora(), u),
    )
    auditar(db, "ingredient", iid, "purchase", f"{c['packages']} x {c['package_qty']} ({c['package_unit']}) por R$ {c['total']} em {c['purchased_at']}")
    return cur.lastrowid


@rota("POST", "/custos/insumos", admin=True)
def criar_insumo(p: Pedido) -> dict:
    db = contexto.db()
    f = _campos_insumo(p)
    if db.query("SELECT 1 FROM ingredients WHERE LOWER(name)=LOWER(?)", (f["name"],)):
        raise ErroApi("Já existe um insumo com este nome.")
    compra = _campos_compra(p.c("compra"), f["base_unit"]) if p.c("compra") else None
    with db.transaction():
        cur = db.execute(
            "INSERT INTO ingredients(name, category, base_unit, yield_pct, density, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (f["name"], f["category"], f["base_unit"], f["yield_pct"], f["density"], f["notes"], agora(), agora()),
        )
        iid = cur.lastrowid
        auditar(db, "ingredient", iid, "create", f"name={f['name']},base={f['base_unit']},aproveitamento={f['yield_pct']}%")
        if compra:
            _gravar_compra(db, iid, compra)
    return {"id": iid}


@rota("PUT", "/custos/insumos/{id}", admin=True)
def atualizar_insumo(p: Pedido) -> dict:
    db = contexto.db()
    iid = p.id()
    a = db.query("SELECT * FROM ingredients WHERE id=?", (iid,))
    if not a:
        raise ErroApi("Insumo não encontrado.", 404)
    a = dict(a[0])
    f = _campos_insumo(p)
    if db.query("SELECT 1 FROM ingredients WHERE LOWER(name)=LOWER(?) AND id<>?", (f["name"], iid)):
        raise ErroApi("Já existe um insumo com este nome.")
    if f["density"] != a["density"]:
        cruz = db.query(
            "SELECT DISTINCT r.name FROM recipe_items i JOIN recipes r ON r.id=i.recipe_id WHERE i.ingredient_id=? AND i.unit IN ({})".format(
                ",".join("?" * len([u for u, (b, _) in C.UNIDADES.items() if b in ("g", "ml") and b != a["base_unit"]]))),
            (iid, *[u for u, (b, _) in C.UNIDADES.items() if b in ("g", "ml") and b != a["base_unit"]]))
        if cruz and a["base_unit"] != "un":
            raise ErroApi(f"A densidade converte as quantidades em {'ml' if a['base_unit'] == 'g' else 'g'} usadas em: {', '.join(r['name'] for r in cruz)}. "
                          "Para mudá-la ou removê-la, ajuste primeiro essas receitas para a medida do insumo.")
    if f["base_unit"] != a["base_unit"]:
        if db.query("SELECT 1 FROM ingredient_purchases WHERE ingredient_id=? LIMIT 1", (iid,)):
            raise ErroApi("Este insumo já tem compras registradas: a medida (peso, volume ou unidade) não pode mudar. Cadastre um insumo novo.")
        if _usos(db, iid):
            raise ErroApi("Este insumo já está em receitas: a medida (peso, volume ou unidade) não pode mudar.")
    db.execute("UPDATE ingredients SET name=?, category=?, base_unit=?, yield_pct=?, density=?, notes=?, updated_at=? WHERE id=?",
               (f["name"], f["category"], f["base_unit"], f["yield_pct"], f["density"], f["notes"], agora(), iid))
    from api.util import diff
    auditar(db, "ingredient", iid, "update", diff([(k, a[k], f[k]) for k in ("name", "category", "base_unit", "yield_pct", "density", "notes")]))
    return {"ok": True}


@rota("DELETE", "/custos/insumos/{id}", admin=True)
def excluir_insumo(p: Pedido) -> dict:
    db = contexto.db()
    iid = p.id()
    r = db.query("SELECT name FROM ingredients WHERE id=?", (iid,))
    if not r:
        raise ErroApi("Insumo não encontrado.", 404)
    usos = _usos(db, iid)
    if usos:
        raise ErroApi(f"\"{r[0]['name']}\" é usado em: {', '.join(usos)}. Tire-o dessas receitas antes de excluir.")
    with db.transaction():
        db.execute("DELETE FROM ingredient_purchases WHERE ingredient_id=?", (iid,))
        db.execute("DELETE FROM ingredients WHERE id=?", (iid,))
        auditar(db, "ingredient", iid, "delete", f"name={r[0]['name']}")
    return {"ok": True}


@rota("GET", "/custos/insumos/{id}/compras", admin=True)
def compras_insumo(p: Pedido) -> dict:
    db = contexto.db()
    iid = p.id()
    calc = C.Calculadora(db)
    info = calc.insumo(iid)
    if not info:
        raise ErroApi("Insumo não encontrado.", 404)
    out = []
    from decimal import Context, localcontext
    for c in db.query("SELECT * FROM ingredient_purchases WHERE ingredient_id=? ORDER BY purchased_at DESC, id DESC", (iid,)):
        with localcontext(Context(prec=C.PRECISAO)):
            qtd = D(c["packages"]) * D(c["package_qty"])
            _, fator = C.UNIDADES[c["package_unit"]]
            out.append({
                "id": c["id"], "data": c["purchased_at"], "fornecedor": c["supplier"], "obs": c["notes"],
                "embalagens": C.txt(D(c["packages"])), "conteudo": C.txt(D(c["package_qty"]) / fator, 12), "unidade": c["package_unit"],
                "quantidade_base": C.txt(qtd, 6), "total": C.txt(D(c["total"]), 2),
                "preco_base": C.txt(D(c["total"]) / qtd, 20), "por": c["created_by"],
            })
    return {"insumo": C.insumo_json(info), "compras": out, "usos": _usos(db, iid)}


@rota("POST", "/custos/insumos/{id}/compras", admin=True)
def registrar_compra(p: Pedido) -> dict:
    db = contexto.db()
    iid = p.id()
    r = db.query("SELECT base_unit FROM ingredients WHERE id=?", (iid,))
    if not r:
        raise ErroApi("Insumo não encontrado.", 404)
    c = _campos_compra(p.corpo, r[0]["base_unit"])
    with db.transaction():
        novo = _gravar_compra(db, iid, c)
    return {"id": novo}


@rota("DELETE", "/custos/compras/{id}", admin=True)
def excluir_compra(p: Pedido) -> dict:
    db = contexto.db()
    r = db.query("SELECT * FROM ingredient_purchases WHERE id=?", (p.id(),))
    if not r:
        raise ErroApi("Compra não encontrada.", 404)
    c = r[0]
    db.execute("DELETE FROM ingredient_purchases WHERE id=?", (c["id"],))
    auditar(db, "ingredient", c["ingredient_id"], "purchase_delete", f"{c['packages']} x {c['package_qty']} por R$ {c['total']} em {c['purchased_at']}")
    return {"ok": True}


# ---------------------------------------------------------------- receitas


def _campos_receita(db, p: Pedido, rid=None) -> tuple[dict, list[dict]]:
    nome = texto(p.c("name"))
    if not nome:
        raise ErroApi("Dê um nome à receita.")
    yu = _c(C.unidade, p.c("yield_unit"), "o rendimento")
    yq = _c(dec, p.c("yield_qty"), "o rendimento", maior_que_zero=True, maximo=D(100000000))
    prod = p.c("product_id")
    if prod in (None, "", 0):
        prod = None
    else:
        try:
            prod = int(prod)
        except (TypeError, ValueError):
            raise ErroApi("Produto inválido.")
        if not db.query("SELECT 1 FROM products WHERE id=?", (prod,)):
            raise ErroApi("Produto não encontrado.")
    margem = p.c("margin_pct")
    margem = None if margem in (None, "") else _c(dec, margem, "o lucro desta receita", D(0), D("99.99"))
    rec = {
        "id": rid, "name": nome, "product_id": prod, "yield_qty": guardar(yq), "yield_unit": yu,
        "labor_minutes": guardar(_c(dec, p.c("labor_minutes"), "o tempo de preparo", D(0), D(100000), vazio=D(0))),
        "loss_pct": guardar(_c(dec, p.c("loss_pct"), "as perdas", D(0), D(99), vazio=D(0))),
        "extra_cost": guardar(_c(dec, p.c("extra_cost"), "outros custos", D(0), D(10000000), vazio=D(0))),
        "margin_pct": guardar(margem) if margem is not None else None,
        "notes": texto(p.c("notes")),
    }
    itens_in = p.c("itens") or []
    if not isinstance(itens_in, list):
        raise ErroApi("Itens inválidos.")
    itens = []
    for n, it in enumerate(itens_in, start=1):
        if not isinstance(it, dict):
            raise ErroApi("Item inválido.")
        tipo = it.get("tipo")
        bruto = it.get("ref_id")
        if bruto in (None, "", 0):
            continue  # linha em branco
        try:
            ref = int(bruto)
        except (TypeError, ValueError):
            raise ErroApi(f"Item {n}: escolha um insumo ou receita da lista.")
        if not ref:
            continue  # linha em branco
        q = _c(dec, it.get("quantity"), f"a quantidade do item {n}", maior_que_zero=True, maximo=D(100000000))
        u = _c(C.unidade, it.get("unit"), f"o item {n}")
        if tipo == "insumo":
            ing = db.query("SELECT name, base_unit, density FROM ingredients WHERE id=?", (ref,))
            if not ing:
                raise ErroApi(f"Item {n}: insumo não encontrado.")
            dens = D(ing[0]["density"]) if ing[0]["density"] else None
            if u not in C.unidades_compativeis(ing[0]["base_unit"], dens):
                raise ErroApi(f"Item {n} ({ing[0]['name']}): unidade \"{u}\" não combina com a medida do insumo.")
            itens.append({"ingredient_id": ref, "sub_recipe_id": None, "quantity": guardar(q), "unit": u})
        elif tipo == "receita":
            if rid is not None and ref == rid:
                raise ErroApi("Uma receita não pode usar a si mesma.")
            sub = db.query("SELECT name, yield_unit FROM recipes WHERE id=?", (ref,))
            if not sub:
                raise ErroApi(f"Item {n}: receita não encontrada.")
            if C.UNIDADES[u][0] != C.UNIDADES[sub[0]["yield_unit"]][0]:
                raise ErroApi(f"Item {n} ({sub[0]['name']}): use a mesma medida do rendimento dessa receita.")
            itens.append({"ingredient_id": None, "sub_recipe_id": ref, "quantity": guardar(q), "unit": u})
        else:
            raise ErroApi(f"Item {n}: tipo inválido.")
    _c(C.verificar_ciclo, db, rid, [i["sub_recipe_id"] for i in itens if i["sub_recipe_id"]])
    return rec, itens


def _gravar_itens(db, rid: int, itens: list[dict]) -> None:
    db.execute("DELETE FROM recipe_items WHERE recipe_id=?", (rid,))
    for pos, it in enumerate(itens):
        db.execute("INSERT INTO recipe_items(recipe_id, ingredient_id, sub_recipe_id, quantity, unit, position) VALUES (?,?,?,?,?,?)",
                   (rid, it["ingredient_id"], it["sub_recipe_id"], it["quantity"], it["unit"], pos))


def _resumo(res: dict) -> dict:
    """Linha da lista de receitas (sem os itens)."""
    out = {k: v for k, v in C.limpar(res).items() if k != "itens"}
    out["n_itens"] = len(res["itens"])
    return out


@rota("GET", "/custos/receitas", admin=True)
def listar_receitas(p: Pedido) -> dict:
    db = contexto.db()
    termo = p.q("q").strip()
    if termo:
        rows = db.query("SELECT r.id FROM recipes r LEFT JOIN products p ON p.id=r.product_id WHERE r.name LIKE ? ESCAPE '\\' OR p.name LIKE ? ESCAPE '\\' ORDER BY r.name COLLATE NOCASE", (like(termo), like(termo)))
    else:
        rows = db.query("SELECT id FROM recipes ORDER BY name COLLATE NOCASE")
    calc = C.Calculadora(db)
    out = []
    for r in rows:
        try:
            out.append(_resumo(calc.receita(r["id"])))
        except ErroCusto as e:  # ciclo gravado por versão antiga/edição manual
            nome = db.query("SELECT name FROM recipes WHERE id=?", (r["id"],))[0]["name"]
            out.append({"id": r["id"], "name": nome, "pendencias": [str(e)], "erro": True})
    usada = {r["sub_recipe_id"] for r in db.query("SELECT DISTINCT sub_recipe_id FROM recipe_items WHERE sub_recipe_id IS NOT NULL")}
    for o in out:
        o["usada_em_outras"] = o["id"] in usada
    return {"receitas": out, "parametros": C.parametros_json(calc.prm)}


@rota("GET", "/custos/receitas/{id}", admin=True)
def detalhe_receita(p: Pedido) -> dict:
    db = contexto.db()
    res = _c(C.Calculadora(db).receita, p.id())
    if not res:
        raise ErroApi("Receita não encontrada.", 404)
    return C.limpar(res)


@rota("POST", "/custos/simular", admin=True, escreve=False)
def simular(p: Pedido) -> dict:
    """Calcula uma receita ainda não salva (o editor mostra o custo enquanto digita)."""
    db = contexto.db()
    rid = p.c("id")
    rid = int(rid) if rid else None
    rec, itens = _campos_receita(db, p, rid)
    teste = p.c("preco_teste")
    teste = None if teste in (None, "") else _c(dec, teste, "o preço para testar", D(0), D("999999.99"))
    return C.limpar(_c(C.Calculadora(db).calcular, rec, itens, (rid,) if rid else (), teste))


@rota("POST", "/custos/receitas", admin=True)
def criar_receita(p: Pedido) -> dict:
    db = contexto.db()
    rec, itens = _campos_receita(db, p)
    with db.transaction():
        cur = db.execute(
            "INSERT INTO recipes(name, product_id, yield_qty, yield_unit, labor_minutes, loss_pct, extra_cost, margin_pct, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (rec["name"], rec["product_id"], rec["yield_qty"], rec["yield_unit"], rec["labor_minutes"], rec["loss_pct"], rec["extra_cost"], rec["margin_pct"], rec["notes"], agora(), agora()),
        )
        rid = cur.lastrowid
        _gravar_itens(db, rid, itens)
        auditar(db, "recipe", rid, "create", f"name={rec['name']},itens={len(itens)}")
    return {"id": rid}


@rota("PUT", "/custos/receitas/{id}", admin=True)
def atualizar_receita(p: Pedido) -> dict:
    db = contexto.db()
    rid = p.id()
    a = db.query("SELECT * FROM recipes WHERE id=?", (rid,))
    if not a:
        raise ErroApi("Receita não encontrada.", 404)
    a = dict(a[0])
    rec, itens = _campos_receita(db, p, rid)
    # Usada como ingrediente de outra receita: a medida do rendimento não pode mudar
    # (as quantidades lá estão em g/ml/un).
    if C.UNIDADES[rec["yield_unit"]][0] != C.UNIDADES[a["yield_unit"]][0]:
        usos = [r["name"] for r in db.query("SELECT DISTINCT r.name FROM recipe_items i JOIN recipes r ON r.id=i.recipe_id WHERE i.sub_recipe_id=?", (rid,))]
        if usos:
            raise ErroApi(f"Esta receita é usada em: {', '.join(usos)}. A medida do rendimento (peso, volume ou unidade) não pode mudar.")
    from api.util import diff
    with db.transaction():
        db.execute(
            "UPDATE recipes SET name=?, product_id=?, yield_qty=?, yield_unit=?, labor_minutes=?, loss_pct=?, extra_cost=?, margin_pct=?, notes=?, updated_at=? WHERE id=?",
            (rec["name"], rec["product_id"], rec["yield_qty"], rec["yield_unit"], rec["labor_minutes"], rec["loss_pct"], rec["extra_cost"], rec["margin_pct"], rec["notes"], agora(), rid),
        )
        _gravar_itens(db, rid, itens)
        auditar(db, "recipe", rid, "update", diff([(k, a[k], rec[k]) for k in ("name", "product_id", "yield_qty", "yield_unit", "labor_minutes", "loss_pct", "extra_cost", "margin_pct")]) or f"itens={len(itens)}")
    return {"ok": True}


@rota("POST", "/custos/receitas/{id}/duplicar", admin=True)
def duplicar_receita(p: Pedido) -> dict:
    db = contexto.db()
    rid = p.id()
    a = db.query("SELECT * FROM recipes WHERE id=?", (rid,))
    if not a:
        raise ErroApi("Receita não encontrada.", 404)
    a = dict(a[0])
    with db.transaction():
        cur = db.execute(
            "INSERT INTO recipes(name, product_id, yield_qty, yield_unit, labor_minutes, loss_pct, extra_cost, margin_pct, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"{a['name']} (cópia)", None, a["yield_qty"], a["yield_unit"], a["labor_minutes"], a["loss_pct"], a["extra_cost"], a["margin_pct"], a["notes"], agora(), agora()),
        )
        novo = cur.lastrowid
        itens = [dict(i) for i in db.query("SELECT * FROM recipe_items WHERE recipe_id=? ORDER BY position, id", (rid,))]
        _gravar_itens(db, novo, itens)
        auditar(db, "recipe", novo, "create", f"cópia de #{rid}")
    return {"id": novo}


@rota("DELETE", "/custos/receitas/{id}", admin=True)
def excluir_receita(p: Pedido) -> dict:
    db = contexto.db()
    rid = p.id()
    r = db.query("SELECT name FROM recipes WHERE id=?", (rid,))
    if not r:
        raise ErroApi("Receita não encontrada.", 404)
    usos = [x["name"] for x in db.query("SELECT DISTINCT r.name FROM recipe_items i JOIN recipes r ON r.id=i.recipe_id WHERE i.sub_recipe_id=?", (rid,))]
    if usos:
        raise ErroApi(f"\"{r[0]['name']}\" é usada em: {', '.join(usos)}. Tire-a dessas receitas antes de excluir.")
    with db.transaction():
        db.execute("DELETE FROM recipe_items WHERE recipe_id=?", (rid,))
        db.execute("DELETE FROM recipes WHERE id=?", (rid,))
        auditar(db, "recipe", rid, "delete", f"name={r[0]['name']}")
    return {"ok": True}


@rota("POST", "/custos/receitas/{id}/aplicar-preco", admin=True)
def aplicar_preco(p: Pedido) -> dict:
    """Grava o preço (sugerido ou digitado) no produto vinculado."""
    db = contexto.db()
    rid = p.id()
    r = db.query("SELECT product_id FROM recipes WHERE id=?", (rid,))
    if not r:
        raise ErroApi("Receita não encontrada.", 404)
    if not r[0]["product_id"]:
        raise ErroApi("Vincule a receita a um produto do catálogo para aplicar o preço.")
    preco = _c(dec, p.c("price"), "o preço", maior_que_zero=True, maximo=D("999999.99"))
    if preco != preco.quantize(D("0.01")):
        raise ErroApi("O preço de venda deve ter no máximo 2 casas (centavos).")
    pid = r[0]["product_id"]
    ant = db.query("SELECT name, price FROM products WHERE id=?", (pid,))
    if not ant:
        raise ErroApi("Produto não encontrado.", 404)
    db.execute("UPDATE products SET price=? WHERE id=?", (float(preco), pid))
    auditar(db, "product", pid, "update", f"price: {ant[0]['price']} -> {preco} (pela ficha de custo #{rid})")
    return {"ok": True, "produto": ant[0]["name"]}
