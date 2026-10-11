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

    from core.web_server import WebServer
    painel = WebServer(contexto.banco_atual(), str(RAIZ / "web"), 5999, "123456")
    web = painel.app.test_client()
    H = {"X-Panel-Token": "123456"}
    r = web.put(f"/api/production/manual_{iid}", json={"quantity": 15}, headers=H)
    checar(r.status_code == 200 and estoque_de(pid) == 0, "editar pelo painel também não mexe no estoque")
    r, _ = silencioso(web.post, "/api/production/complete", headers=H)
    checar(r.status_code == 200 and estoque_de(pid) == 15, "'Produção feita' soma exatamente o que estava na lista (15)")

    print("Painel da cozinha")
    antes = movimentos_de(pid)
    web.post(f"/api/products/{pid}/adjust", json={"change": -3}, headers=H)
    web.put(f"/api/products/{pid}", json={"quantity": 20}, headers=H)
    checar(estoque_de(pid) == 20 and movimentos_de(pid) == antes + 2, "+/− e 'definir quantidade' viram movimentações")
    hist = contexto.db().query("SELECT COUNT(*) FROM audit_logs WHERE entity='product' AND entity_id=? AND user='painel-web'", (pid,))[0][0]
    checar(hist == 2, "ajustes do painel entram no histórico do produto")
    r = web.get("/api/products", headers={**H, "Origin": "http://site-qualquer.com"})
    checar(r.headers.get("Access-Control-Allow-Origin") is None, "API do painel não libera outros sites (sem CORS)")
    checar(web.get("/api/products?token=123456").status_code == 401, "PIN na URL não vale mais (só cabeçalho)")
    for i in range(3):
        web.get("/api/products", headers={"X-Panel-Token": "000000"})  # mesmo PIN repetido: não bloqueia
    checar(web.get("/api/products", headers=H).status_code == 200, "o mesmo PIN errado repetido (atualização automática) não bloqueia")
    for i in range(8):
        web.get("/api/products", headers={"X-Panel-Token": f"9{i:05d}"})
    checar(web.get("/api/products", headers=H).status_code == 429, "8 PINs errados diferentes bloqueiam o aparelho")
    painel._falhas_pin.clear()
    oid = pedidos.criar_pedido(P({"customer_id": cid, "delivery_date": proximo(2).isoformat(),
                                  "products": [{"product_id": pid, "quantity": 1}, {"product_id": pid, "quantity": 2}]}))["ids"][0]
    lista = web.get("/api/production", headers=H).get_json()["orders"]
    checar(all(o["source"] == "manual" for o in lista), "lista do painel traz só a lista de produção")
    r = web.put(f"/api/production/order_{oid}", json={"notes": "x", "size": "G"}, headers=H)
    nota = contexto.db().query("SELECT notes FROM orders WHERE id=?", (oid,))[0][0]
    checar(r.status_code == 400 and nota.startswith("LOTE:"), "painel não edita pedidos (marca de lote preservada)")
    html = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
    checar("${esc(product.name)}" in html and "${esc(order.notes)}" in html, "painel escapa nome e observação antes de pôr no HTML")

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
