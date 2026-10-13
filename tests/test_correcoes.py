# -*- coding: utf-8 -*-
"""Testes das correções da análise de 11/10/2026 (rodam no próprio processo, com um
banco temporário criado do zero — nunca tocam no banco nem no config.yaml reais).

Uso:
    py tests/test_correcoes.py
"""

from __future__ import annotations

import io
import contextlib
import os
import sqlite3
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="confeitaria_correcoes_")
os.environ["CONFEITARIA_DATA_DIR"] = os.path.join(TMP, "dados")  # antes de importar core.config
os.environ["CONFEITARIA_DB"] = os.path.join(TMP, "teste.db")
sys.path.insert(0, str(RAIZ))

FALHAS: list[str] = []


def checar(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FALHA ") + msg)
    if not cond:
        FALHAS.append(msg)


def silencioso(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()) as saida:
        r = fn(*a, **k)
    return r, saida.getvalue()


def proximo(dia_semana: int, minimo: date | None = None) -> date:
    d = minimo or date.today() + timedelta(days=1)
    while d.weekday() != dia_semana:
        d += timedelta(days=1)
    return d


def segunda_rodada(P, estoque_de, movimentos_de, painel, web, H) -> None:
    """Regras de negócio da segunda análise (estoque, situação do pedido, relatórios)."""
    import sqlite3 as _sq
    from api import ErroApi, contexto
    from api import cadastros, configuracoes, estoque, pedidos, producao, relatorios
    from core import extended_database as ed
    db = contexto.db
    hoje, amanha = date.today(), date.today() + timedelta(days=1)
    configuracoes.salvar_dias_fechados(P({"dias": []}))
    cid = cadastros.criar_cliente(P({"name": "Bia", "phone": "1111"}))["id"]
    cid2 = cadastros.criar_cliente(P({"name": "Bia", "phone": "2222"}))["id"]
    pa = estoque.criar_produto(P({"name": "Brigadeiro", "stock": 10, "price": 2}))["ids"][0]
    pb = estoque.criar_produto(P({"name": "Beijinho", "stock": 10, "price": 2}))["ids"][0]

    print("Produto: estoque desatualizado e tamanhos")
    tela = estoque_de(pb)
    web.post(f"/api/products/{pb}/adjust", json={"change": 7}, headers=H)
    estoque.atualizar_produto(P({"name": "Beijinho", "price": 3, "stock": tela, "min_stock": 0, "estoque_lido": tela}, {"id": str(pb)}))
    checar(estoque_de(pb) == tela + 7, "salvar só o preço não desfaz o que o painel lançou")
    try:
        estoque.atualizar_produto(P({"name": "Beijinho", "stock": 99, "min_stock": 0, "estoque_lido": tela}, {"id": str(pb)}))
        checar(False, "mexer no estoque com valor desatualizado é recusado")
    except ErroApi as e:
        checar(e.codigo == "estoque_mudou" and estoque_de(pb) == tela + 7, "mexer no estoque com valor desatualizado é recusado")
    vid = estoque.criar_produto(P({"name": "Pão", "stock": 5}))["ids"][0]
    estoque.atualizar_produto(P({"name": "Pão", "stock": 5, "sizes": ["P", "G", "15"]}, {"id": str(vid)}))
    var = {r[0]: r[1] for r in db().query("SELECT name, stock FROM products WHERE name LIKE 'Pão%'")}
    checar(var == {"Pão P": 5, "Pão G": 0, "Pão 15cm": 0}, f"tamanho em texto sem 'cm' e variante nova com estoque 0 ({var})")

    print("Reserva automática")
    oid = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": amanha.isoformat(), "products": [{"product_id": pa, "quantity": 2}]}))["ids"][0]
    db().execute("UPDATE orders SET delivery_date=? WHERE id=?", (hoje.isoformat(), oid))
    base = db()
    orig = base.execute

    def quebra(sql, params=()):
        if sql.startswith("INSERT INTO stock_movements"):
            raise _sq.OperationalError("disco cheio (simulado)")
        return orig(sql, params)
    antes = estoque_de(pa)
    base.execute = quebra
    silencioso(ed.check_and_reserve_stock, base)
    base.execute = orig
    sem_efeito = estoque_de(pa) == antes and db().query("SELECT stock_reserved FROM orders WHERE id=?", (oid,))[0][0] == 0
    silencioso(ed.check_and_reserve_stock, base)
    checar(sem_efeito and estoque_de(pa) == antes - 2, "falha no meio não baixa nada; a rodada seguinte baixa uma vez só")

    print("Situação do pedido")
    oc = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": hoje.isoformat(), "products": [{"product_id": pa, "quantity": 3}]}))["ids"][0]
    e0 = estoque_de(pa)
    pedidos.atualizar_lote(P({"ids": [oc], "situacao": "cancelado"}))
    checar(estoque_de(pa) == e0 + 3, "cancelar devolve o estoque reservado")
    silencioso(ed.check_and_reserve_stock, db())
    checar(estoque_de(pa) == e0 + 3, "reserva automática ignora pedido cancelado")
    pedidos.atualizar_lote(P({"ids": [oc], "situacao": "aberto"}))
    checar(estoque_de(pa) == e0, "reabrir baixa de novo")
    pedidos.atualizar_lote(P({"ids": [oc], "situacao": "entregue"}))
    of = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": (hoje + timedelta(days=5)).isoformat(), "products": [{"product_id": pa, "quantity": 1}]}))["ids"][0]
    e1 = estoque_de(pa)
    pedidos.atualizar_lote(P({"ids": [of], "situacao": "entregue"}))
    checar(estoque_de(pa) == e1 - 1, "entregue antes da data baixa o estoque na hora")
    lista = pedidos.listar_pedidos(P(q={"de": hoje.isoformat(), "ate": hoje.isoformat()}))["pedidos"]
    checar(any(x["id"] == oc and x["situacao"] == "entregue" for x in lista), "lista traz a situação")
    e2 = estoque_de(pa)
    r = pedidos.excluir_pedidos(P({"ids": [oc]}))
    checar(r["devolvidos"] == 0 and estoque_de(pa) == e2, "excluir pedido entregue não devolve estoque")
    checar(db().query("SELECT COUNT(*) FROM stock_movements WHERE reason LIKE ?", (f"% #{oc} (excluído)",))[0][0] >= 1,
           "a saída do pedido excluído fica no histórico")
    antigo = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": hoje.isoformat(), "products": [{"product_id": pa, "quantity": 4}]}))["ids"][0]
    db().execute("UPDATE orders SET delivery_date='2020-01-07' WHERE id=?", (antigo,))
    e3 = estoque_de(pa)
    checar(pedidos.contar_exclusao(P({"ids": [antigo]}))["devolve"] == 0, "confirmação avisa que pedido antigo não devolve")
    pedidos.excluir_pedidos(P({"ids": [antigo]}))
    checar(estoque_de(pa) == e3, "excluir pedido antigo (limpeza) não devolve estoque")
    futuro = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": hoje.isoformat(), "products": [{"product_id": pa, "quantity": 2}]}))["ids"][0]
    e4 = estoque_de(pa)
    r = pedidos.excluir_pedidos(P({"ids": [futuro]}))
    checar(r["devolvidos"] == 2 and estoque_de(pa) == e4 + 2, "excluir pedido de hoje ainda a entregar devolve")

    print("Início e relatórios")
    d0 = amanha + timedelta(days=1)
    pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": d0.isoformat(),
                            "products": [{"product_id": pa, "quantity": 1}, {"product_id": pb, "quantity": 1}, {"product_id": pa, "quantity": 2}]}))
    pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": d0.isoformat(), "status": "Pagamento na Retirada", "products": [{"product_id": pb, "quantity": 1}]}))
    cx = pedidos.criar_pedido(P({"customer_id": cid2, "delivery_date": d0.isoformat(), "products": [{"product_id": pb, "quantity": 1}]}))["ids"][0]
    pedidos.atualizar_lote(P({"ids": [cx], "situacao": "cancelado"}))
    dash = producao.dashboard(P())
    dia = [x for x in dash["por_dia"] if x["dia"] == d0.isoformat()]
    checar(dia and dia[0]["pedidos"] == 2 and dia[0]["itens"] == 5, "gráfico do Início conta lote como 1 pedido e ignora cancelado")
    rel = relatorios._entregas(d0.isoformat())
    pagamentos = sorted({linha[4] for linha in rel["linhas"]})
    checar(len(rel["linhas"]) == 4 and "Pagamento na Retirada" in pagamentos, "Entregas traz retirada/aguardando e não traz cancelado")
    ops = pedidos.opcoes_relatorio(P())["clientes"]
    checar(len([c for c in ops if c["nome"] == "Bia"]) == 2, "relatório separa clientes homônimos (por cadastro)")

    print("Regras de cadastro")
    try:
        pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": "2020-01-07", "products": [{"product_id": pa, "quantity": 1}]}))
        checar(False, "pedido com data passada é recusado")
    except ErroApi as e:
        checar(e.codigo == "data_passada", "pedido com data passada é recusado")
    oo = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": amanha.isoformat(), "notes": "LOTE:ab:2 itens | x",
                                 "products": [{"product_id": pa, "quantity": 1}]}))["ids"][0]
    nota = db().query("SELECT notes FROM orders WHERE id=?", (oo,))[0][0]
    checar(not nota.startswith("LOTE:"), "observação digitada não vira marca de lote")
    checar(len(cadastros.listar_clientes(P(q={"q": "%"}))["clientes"]) == 0, "busca por % procura o caractere, não tudo")
    comum = db().query("SELECT id FROM labels WHERE name='Comum'")[0][0]
    try:
        cadastros.excluir_etiqueta(P(params={"id": str(comum)}))
        checar(False, "etiqueta Comum não pode ser excluída")
    except ErroApi:
        checar(True, "etiqueta Comum não pode ser excluída")
    urg = db().query("SELECT id FROM labels WHERE name='Urgente'")[0][0]
    cadastros.excluir_etiqueta(P(params={"id": str(urg)}))
    silencioso(contexto.reabrir_banco)
    nomes = [r[0] for r in db().query("SELECT name FROM labels")]
    checar("Urgente" not in nomes and "Comum" in nomes, "etiqueta excluída não volta ao reabrir o sistema")

    print("Bancos antigos")
    velho = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": amanha.isoformat(), "products": [{"product_id": pa, "quantity": 1}]}))["ids"][0]
    canc = pedidos.criar_pedido(P({"customer_id": cid2, "delivery_date": amanha.isoformat(), "products": [{"product_id": pa, "quantity": 1}]}))["ids"][0]
    db().execute("UPDATE orders SET status='Entregue' WHERE id=?", (velho,))
    db().execute("UPDATE orders SET status='Cancelado' WHERE id=?", (canc,))
    silencioso(contexto.reabrir_banco)
    sit = {r[0]: r[1] for r in db().query("SELECT id, situacao FROM orders WHERE id IN (?, ?)", (velho, canc))}
    checar(sit == {velho: "entregue", canc: "cancelado"}, "status antigo 'Entregue'/'Cancelado' vira situação ao abrir")

    print("Movimentações")
    mid = estoque.criar_movimento(P({"type": "entrada", "category": "Compra/Reposição", "product_id": pb, "quantity": 50}))["id"]
    estoque.criar_movimento(P({"type": "saida", "category": "Venda Avulsa", "product_id": pb, "quantity": estoque_de(pb)}))
    try:
        estoque.excluir_movimentos(P({"ids": [mid]}))
        checar(False, "desfazer entrada já vendida pede confirmação")
    except ErroApi as e:
        checar(e.codigo == "estoque_negativo" and estoque_de(pb) == 0, "desfazer entrada já vendida pede confirmação")
    estoque.excluir_movimentos(P({"ids": [mid], "forcar": True}))
    checar(estoque_de(pb) == -50, "confirmando, exclui")


def venda_por_kg(P, estoque_de, web, H) -> None:
    """Produtos vendidos em kg: quantidades com decimais em todo o fluxo."""
    from api import ErroApi, contexto
    from api import estoque, pedidos, producao, relatorios
    db = contexto.db
    hoje = date.today()
    cid = db().query("SELECT id FROM customers LIMIT 1")[0][0]

    print("Venda por kg")
    kg = estoque.criar_produto(P({"name": "Doce de leite", "unit": "kg", "stock": "2,5", "min_stock": "0,5", "price": 40}))["ids"][0]
    un = estoque.criar_produto(P({"name": "Copo", "stock": 10}))["ids"][0]
    checar(estoque_de(kg) == 2.5, "produto em kg aceita estoque 2,5")
    try:
        estoque.criar_produto(P({"name": "Errado", "stock": "1,5"}))
        checar(False, "produto em unidade recusa estoque fracionado")
    except ErroApi:
        checar(True, "produto em unidade recusa estoque fracionado")
    ids = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": hoje.isoformat(),
                                  "products": [{"product_id": kg, "quantity": "1,2"}, {"product_id": un, "quantity": 2}]}))["ids"]
    checar(estoque_de(kg) == 1.3 and estoque_de(un) == 8, "pedido de 1,2 kg baixa 1,2 do estoque (sem lixo de arredondamento)")
    try:
        pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": hoje.isoformat(), "products": [{"product_id": un, "quantity": 1.5}]}))
        checar(False, "pedido de 1,5 de produto por unidade é recusado")
    except ErroApi:
        checar(True, "pedido de 1,5 de produto por unidade é recusado")
    pedidos.atualizar_pedido(P({"quantity": 0.75}, {"id": str(ids[0])}))
    checar(estoque_de(kg) == 1.75, "editar para 0,75 kg devolve a diferença exata")
    linha = [x for x in pedidos.listar_pedidos(P(q={"de": hoje.isoformat(), "ate": hoje.isoformat()}))["pedidos"] if ids[0] in x["ids"]][0]
    checar("0,75 kg" in linha["produto"] and "×2" in linha["produto"] and linha["unit"] == "misto", f"lote mostra '0,75 kg' e '×2' ({linha['produto']})")
    for _ in range(10):
        estoque.criar_movimento(P({"type": "entrada", "category": "Produção", "product_id": kg, "quantity": "0,1"}))
    checar(estoque_de(kg) == 2.75, "dez entradas de 0,1 kg somam exatamente 1 kg")
    try:
        estoque.criar_movimento(P({"type": "saida", "category": "Venda Avulsa", "product_id": kg, "quantity": 5}))
        checar(False, "saída maior que o estoque em kg é recusada")
    except ErroApi as e:
        checar("2,75 kg" in e.mensagem, f"saída maior que o estoque explica em kg ({e.mensagem})")
    iid = producao.adicionar_item(P({"product_id": kg, "quantity": "1,5"}))["id"]
    r, _ = silencioso(web.post, "/api/production/complete", headers=H)
    checar(r.status_code == 200 and estoque_de(kg) == 4.25, "produção de 1,5 kg pelo painel soma 1,5")
    _ = iid
    r1 = web.post(f"/api/products/{kg}/adjust", json={"change": -0.1}, headers=H)
    checar(r1.status_code == 200 and estoque_de(kg) == 4.15, "painel: − tira 100 g de produto em kg (e responde OK)")
    r2 = web.post(f"/api/products/{un}/adjust", json={"change": 1}, headers=H)
    checar(r2.status_code == 200 and r2.get_json()["new_quantity"] == estoque_de(un), "painel: + de produto por unidade responde OK")
    r = web.put(f"/api/products/{un}", json={"quantity": "2,5"}, headers=H)
    checar(r.status_code == 400, "painel recusa quantidade fracionada em produto por unidade")
    lista = web.get("/api/ready-stock", headers=H).get_json()["products"]
    checar(any(p["id"] == kg and p["unit"] == "kg" for p in lista), "painel recebe a unidade do produto")
    rel = relatorios._entregas(hoje.isoformat())
    checar(any("0,75 kg" == linha_[1] for linha_ in rel["linhas"]) and "kg" in rel["rodape"], "relatório de entregas mostra kg e total separado")
    try:
        estoque.atualizar_produto(P({"name": "Doce de leite", "unit": "un", "stock": 4, "price": 40}, {"id": str(kg)}))
        checar(False, "não muda a unidade de produto com pedidos")
    except ErroApi as e:
        checar(e.codigo == "unidade_fixa", "não muda a unidade de produto com pedidos")


def main() -> int:
    (_, saida) = silencioso(lambda: None)
    from api import ErroApi, Pedido, carregar_rotas, contexto
    from core.database import Database  # noqa: F401
    carregar_rotas()
    db, saida = silencioso(contexto.db)
    from api import banco, cadastros, configuracoes, estoque, pedidos, producao, sistema
    adm = {"id": 1, "username": "admin", "role": "admin"}
    contexto.definir_usuario(adm)

    def P(corpo=None, params=None, q=None):
        return Pedido("X", "", q or {}, corpo or {}, params or {}, adm)

    def estoque_de(pid):
        return contexto.db().query("SELECT stock FROM products WHERE id=?", (pid,))[0][0]

    def movimentos_de(pid):
        return contexto.db().query("SELECT COUNT(*) FROM stock_movements WHERE product_id=?", (pid,))[0][0]

    print("Banco e migrações")
    checar("price" not in saida.lower(), "abrir o banco não tenta mais remover a coluna price")
    checar("price" in [r[1] for r in db.query("PRAGMA table_info(products)")], "coluna price continua existindo")

    print("Admin padrão")
    db.execute("UPDATE users SET username='dona' WHERE id=1")
    silencioso(contexto.reabrir_banco)
    nomes = [r[0] for r in contexto.db().query("SELECT username FROM users")]
    checar(nomes == ["dona"], "admin renomeado não faz o sistema recriar 'admin'/'admin'")
    novo = os.path.join(TMP, "vazio.db")
    silencioso(Database, novo)
    c = sqlite3.connect(novo)
    checar([r[0] for r in c.execute("SELECT username FROM users")] == ["admin"], "banco sem usuários ganha o admin padrão")
    c.close()

    cid = cadastros.criar_cliente(P({"name": "Ana"}))["id"]
    pid = estoque.criar_produto(P({"name": "Bolo", "stock": 0}))["ids"][0]

    print("Produção")
    iid = producao.adicionar_item(P({"product_id": pid, "quantity": 10}))["id"]
    producao.editar_item(P({"quantity": 12}, {"id": str(iid)}))
    checar(estoque_de(pid) == 0, "editar a quantidade na lista não mexe no estoque")

    from core.web_server import COOKIE_SESSAO, WebServer
    configuracoes.criar_usuario(P({"username": "forno", "password": "Massa#77", "role": "cozinha"}))
    rid = configuracoes.criar_usuario(P({"username": "balcao", "password": "Massa#77", "role": "recepcao"}))["id"]
    painel = WebServer(contexto.banco_atual(), str(RAIZ / "web"), 5999)
    web = painel.app.test_client()
    H = {"X-Painel": "1"}

    print("Painel web: login com usuário e senha")
    r = web.get("/api/products")
    checar(r.status_code == 401 and r.get_json().get("login"), "sem login a API do painel pede usuário e senha")
    checar(web.post("/api/login", json={"usuario": "forno", "senha": "Massa#77"}).status_code == 403, "login sem o cabeçalho do painel é recusado (CSRF)")
    checar(web.post("/api/login", json={"usuario": "forno", "senha": "errada"}, headers=H).status_code == 401, "senha errada é recusada")
    r = web.post("/api/login", json={"usuario": "balcao", "senha": "Massa#77"}, headers=H)
    checar(r.status_code == 403 and web.get("/api/products").status_code == 401, "perfil Recepção não entra no painel")
    r = web.post("/api/login", json={"usuario": "forno", "senha": "Massa#77", "lembrar": True}, headers=H)
    ck = r.headers.get("Set-Cookie", "")
    checar(r.status_code == 200 and "HttpOnly" in ck and "SameSite=Strict" in ck and "Max-Age=2592000" in ck,
           "cozinha entra; 'manter conectado' grava cookie HttpOnly por 30 dias")
    checar(web.get("/api/sessao").get_json()["usuario"]["username"] == "forno", "sessão lembrada reconhece o usuário")
    checar(web.post("/api/products/1/adjust", json={"change": 1}).status_code == 403, "alteração sem o cabeçalho do painel é recusada (CSRF)")
    r = web.get("/api/products", headers={"Origin": "http://site-qualquer.com"})
    checar(r.headers.get("Access-Control-Allow-Origin") is None, "API do painel não libera outros sites (sem CORS)")
    so_sessao = painel.app.test_client()
    r = so_sessao.post("/api/login", json={"usuario": "forno", "senha": "Massa#77", "lembrar": False}, headers=H)
    checar(r.status_code == 200 and "Max-Age" not in r.headers.get("Set-Cookie", ""), "sem 'manter conectado' o cookie some ao fechar o navegador")
    so_sessao.post("/api/logout", headers=H)
    checar(so_sessao.get("/api/products").status_code == 401 and web.get("/api/products").status_code == 200,
           "sair encerra só a sessão daquele aparelho")
    outro = painel.app.test_client()
    for i in range(8):
        outro.post("/api/login", json={"usuario": "forno", "senha": f"errada{i}"}, headers=H)
    checar(outro.post("/api/login", json={"usuario": "forno", "senha": "Massa#77"}, headers=H).status_code == 429,
           "8 senhas erradas bloqueiam o aparelho")
    painel._falhas_pin.clear()
    from core.services import _lockout_file
    _lockout_file().unlink(missing_ok=True)  # bloqueio por usuário (o mesmo do sistema) também foi acionado

    r = web.put(f"/api/production/manual_{iid}", json={"quantity": 15}, headers=H)
    checar(r.status_code == 200 and estoque_de(pid) == 0, "editar pelo painel também não mexe no estoque")
    r, _ = silencioso(web.post, "/api/production/complete", headers=H)
    checar(r.status_code == 200 and estoque_de(pid) == 15, "'Produção feita' soma exatamente o que estava na lista (15)")

    print("Painel da cozinha")
    antes = movimentos_de(pid)
    web.post(f"/api/products/{pid}/adjust", json={"change": -3}, headers=H)
    web.put(f"/api/products/{pid}", json={"quantity": 20}, headers=H)
    checar(estoque_de(pid) == 20 and movimentos_de(pid) == antes + 2, "+/− e 'definir quantidade' viram movimentações")
    hist = contexto.db().query("SELECT COUNT(*) FROM audit_logs WHERE entity='product' AND entity_id=? AND user='forno (painel)'", (pid,))[0][0]
    checar(hist == 2, "ajustes do painel entram no histórico com o nome de quem fez")
    oid = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": proximo(2).isoformat(),
                                  "products": [{"product_id": pid, "quantity": 1}, {"product_id": pid, "quantity": 2}]}))["ids"][0]
    lista = web.get("/api/production", headers=H).get_json()["orders"]
    checar(all(o["source"] == "manual" for o in lista), "lista do painel traz só a lista de produção")
    r = web.put(f"/api/production/order_{oid}", json={"notes": "x", "size": "G"}, headers=H)
    nota = contexto.db().query("SELECT notes FROM orders WHERE id=?", (oid,))[0][0]
    checar(r.status_code == 400 and nota.startswith("LOTE:"), "painel não edita pedidos (marca de lote preservada)")
    html = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
    checar("${esc(p.name)}" in html and "${esc(i.product)}" in html and "${esc(obs)}" in html,
           "painel escapa nome e observação antes de pôr no HTML")
    checar('id="login-lembrar"' in html and "X-Panel-Token" not in html and "'X-Painel': '1'" in html,
           "painel tem login com 'manter conectado' e não usa mais PIN")
    checar(web.get("/acesso.html").status_code == 301, "endereço antigo do painel leva ao painel")

    print("Painel web: sessão derrubada pelo sistema")
    configuracoes.atualizar_usuario(P({"username": "forno", "password": "Forno#2026", "role": "cozinha"}, {"id": str(
        contexto.db().query("SELECT id FROM users WHERE username='forno'")[0][0])}))
    checar(web.get("/api/products").status_code == 401, "trocar a senha do usuário desconecta o painel")
    web.post("/api/login", json={"usuario": "forno", "senha": "Forno#2026", "lembrar": True}, headers=H)
    fid = contexto.db().query("SELECT id FROM users WHERE username='forno'")[0][0]
    configuracoes.atualizar_usuario(P({"username": "forno", "role": "recepcao"}, {"id": str(fid)}))
    checar(web.get("/api/products").status_code == 401, "mudar o perfil para Recepção desconecta o painel")
    configuracoes.atualizar_usuario(P({"username": "forno", "role": "cozinha"}, {"id": str(fid)}))
    web.post("/api/login", json={"usuario": "forno", "senha": "Forno#2026", "lembrar": True}, headers=H)
    configuracoes.desconectar_aparelho(P({"todos": True}))
    checar(web.get("/api/products").status_code == 401, "administrador desconecta os aparelhos")
    web.post("/api/login", json={"usuario": "forno", "senha": "Forno#2026", "lembrar": True}, headers=H)
    configuracoes.excluir_usuario(P(params={"id": str(rid)}))
    _ = COOKIE_SESSAO

    print("Contador do menu")
    hoje = date.today()
    configuracoes.salvar_dias_fechados(P({"dias": []}))
    for obs in ("sem açúcar", "vela azul", None):
        pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": hoje.isoformat(), "notes": obs,
                                "products": [{"product_id": pid, "quantity": 1}]}))
    pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": hoje.isoformat(),
                            "products": [{"product_id": pid, "quantity": 1}, {"product_id": pid, "quantity": 1}]}))
    linhas = pedidos.listar_pedidos(P(q={"de": hoje.isoformat(), "ate": hoje.isoformat()}))["pedidos"]
    menu = producao.contagens_menu(P())["pedidosHoje"]
    kpi = producao.dashboard(P())["kpis"]["pedidos_hoje"]
    checar(len(linhas) == 4 and menu == 4 and kpi == 4, f"menu e Início contam como a lista (lista {len(linhas)}, menu {menu}, início {kpi})")

    print("Dias sem expediente")
    configuracoes.salvar_dias_fechados(P({"dias": [0]}))
    checar(sistema.empresa(P())["dias_fechados"] == [0], "padrão segunda aparece em /empresa")
    seg, dom = proximo(0), proximo(6)
    try:
        pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": seg.isoformat(), "products": [{"product_id": pid, "quantity": 1}]}))
        checar(False, "segunda fechada recusa pedido")
    except ErroApi as e:
        checar(e.codigo == "dia_fechado" and e.mensagem.startswith("Segunda"), "segunda fechada recusa pedido")
    configuracoes.salvar_dias_fechados(P({"dias": [6]}))
    oid_seg = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": seg.isoformat(), "products": [{"product_id": pid, "quantity": 1}]}))["ids"][0]
    checar(True, "trocando para domingo, segunda passa a aceitar")
    try:
        pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": dom.isoformat(), "products": [{"product_id": pid, "quantity": 1}]}))
        checar(False, "domingo fechado recusa pedido")
    except ErroApi as e:
        checar(e.mensagem.startswith("Domingo"), "domingo fechado recusa pedido")
    configuracoes.salvar_dias_fechados(P({"dias": [0]}))
    pedidos.atualizar_lote(P({"ids": [oid_seg], "status": "Pago"}))
    st = contexto.db().query("SELECT status FROM orders WHERE id=?", (oid_seg,))[0][0]
    checar(st == "Pago", "pedido antigo num dia que fechou ainda muda pagamento")
    try:
        pedidos.atualizar_lote(P({"ids": [oid_seg], "delivery_date": proximo(0, seg + timedelta(days=1)).isoformat()}))
        checar(False, "mudar a data para outro dia fechado é recusado")
    except ErroApi:
        checar(True, "mudar a data para outro dia fechado é recusado")
    try:
        configuracoes.salvar_dias_fechados(P({"dias": list(range(7))}))
        checar(False, "não deixa fechar a semana inteira")
    except ErroApi:
        checar(True, "não deixa fechar a semana inteira")

    segunda_rodada(P, estoque_de, movimentos_de, painel, web, H)
    venda_por_kg(P, estoque_de, web, H)

    print("Banco não encontrado")
    bk = os.path.join(TMP, "bk.zip")
    silencioso(banco.criar_backup_zip, bk)
    from core import config
    perdido = os.path.join(TMP, "pasta_que_sumiu", "confeitaria.db")
    config.save_config({"database_path": perdido})
    os.environ.pop("CONFEITARIA_DB")
    contexto.fechar_banco()
    try:
        silencioso(contexto.reabrir_banco)
        checar(False, "caminho configurado inexistente não cria banco vazio")
    except contexto.BancoAusente as e:
        checar(e.caminho == perdido and not os.path.exists(perdido), "caminho configurado inexistente não cria banco vazio")
    checar(sistema.saude(P())["banco_ausente"] == perdido, "/saude informa o banco ausente")
    try:
        banco.localizar(P({"acao": "tentar"}))
        checar(False, "'tentar de novo' continua avisando")
    except ErroApi as e:
        checar(e.codigo == "banco_ausente", "'tentar de novo' continua avisando")
    silencioso(banco.localizar, P({"acao": "restaurar", "caminho": bk}))
    n = contexto.db().query("SELECT COUNT(*) FROM customers WHERE name='Ana'")[0][0]
    checar(contexto.banco_atual() == perdido and n == 1, "restaurar backup no lugar do banco que sumiu")
    try:
        banco.localizar(P({"acao": "criar"}))
        checar(False, "com o banco aberto a rota sem login fica fechada")
    except ErroApi as e:
        checar(e.status == 409, "com o banco aberto a rota sem login fica fechada")

    contexto.fechar_banco()
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{'FALHOU' if FALHAS else 'TUDO OK'}: {len(FALHAS)} falha(s)")
    return 1 if FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
