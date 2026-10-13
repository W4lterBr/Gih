# -*- coding: utf-8 -*-
"""Testes da tela Custos (insumos, receitas, preço de venda). Banco temporário.

Uso:
    py tests/test_custos.py
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="confeitaria_custos_")
os.environ["CONFEITARIA_DATA_DIR"] = os.path.join(TMP, "dados")
os.environ["CONFEITARIA_DB"] = os.path.join(TMP, "teste.db")
sys.path.insert(0, str(RAIZ))

FALHAS: list[str] = []


def checar(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FALHA ") + msg)
    if not cond:
        FALHAS.append(msg)


def igual(a, b) -> bool:
    """O motor guarda 50 dígitos e devolve até 20 casas; aqui a conta é com 28."""
    return abs(D(a) - D(b)) < D("1e-15")


def main() -> int:
    from api import ErroApi, Pedido, carregar_rotas, contexto
    carregar_rotas()
    with contextlib.redirect_stdout(io.StringIO()):
        contexto.db()
    from api import custos, estoque
    adm = {"id": 1, "username": "admin", "role": "admin"}
    contexto.definir_usuario(adm)

    def P(corpo=None, params=None, q=None):
        return Pedido("X", "", q or {}, corpo or {}, params or {}, adm)

    def erro(fn, *a) -> str:
        try:
            fn(*a)
        except ErroApi as e:
            return e.mensagem
        return ""

    hoje = date.today()
    custos.salvar_parametros(P({"cost_basis": "ultima", "labor_hour": "0", "fixed_pct": "0", "tax_pct": "0", "fee_pct": "0", "margin_pct": "0", "rounding": "0.01"}))

    print("Insumos e compras")
    leite = custos.criar_insumo(P({"name": "Leite condensado", "base_unit": "g",
                                   "compra": {"embalagens": "1", "conteudo": "395", "unidade": "g", "total": "4,99"}}))["id"]
    info = custos.listar_insumos(P())["insumos"][0]
    checar(igual(info["preco_base"], D("4.99") / D("395")), f"custo por grama exato, sem arredondar ({info['preco_base']})")
    ovo = custos.criar_insumo(P({"name": "Ovo", "base_unit": "un", "compra": {"embalagens": "2", "conteudo": "1", "unidade": "dz", "total": "19,80"}}))["id"]
    ovo_info = next(i for i in custos.listar_insumos(P())["insumos"] if i["id"] == ovo)
    checar(D(ovo_info["preco_base"]) == D("0.825"), "2 dúzias por R$ 19,80 = R$ 0,825 o ovo")
    morango = custos.criar_insumo(P({"name": "Morango", "base_unit": "g", "yield_pct": "80",
                                     "compra": {"embalagens": "1", "conteudo": "1", "unidade": "kg", "total": "20"}}))["id"]
    m = next(i for i in custos.listar_insumos(P())["insumos"] if i["id"] == morango)
    checar(D(m["preco_base"]) == D("0.025"), "aproveitamento de 80%: R$ 20/kg vira R$ 0,025 por grama aproveitável")
    oleo = custos.criar_insumo(P({"name": "Óleo", "base_unit": "ml", "density": "0,92",
                                  "compra": {"embalagens": "1", "conteudo": "0,9", "unidade": "l", "total": "9"}}))["id"]
    checar("Já existe" in erro(custos.criar_insumo, P({"name": "ovo", "base_unit": "un"})), "nome repetido (sem diferenciar maiúsculas) é recusado")
    checar("não combina" in erro(custos.registrar_compra, P({"embalagens": 1, "conteudo": 1, "unidade": "kg", "total": 5}, {"id": str(ovo)})),
           "compra em kg de um insumo contado em unidades é recusada")
    checar("futuro" in erro(custos.registrar_compra, P({"conteudo": 1, "unidade": "dz", "total": 5, "data": (hoje + timedelta(days=1)).isoformat()}, {"id": str(ovo)})),
           "compra com data futura é recusada")

    print("Média ponderada")
    custos.registrar_compra(P({"embalagens": 3, "conteudo": "395", "unidade": "g", "total": "18", "data": (hoje - timedelta(days=10)).isoformat()}, {"id": str(leite)}))
    custos.registrar_compra(P({"embalagens": 1, "conteudo": "395", "unidade": "g", "total": "7", "data": (hoje - timedelta(days=400)).isoformat()}, {"id": str(leite)}))
    custos.salvar_parametros(P({"cost_basis": "media", "avg_days": 90, "margin_pct": "0", "rounding": "0.01"}))
    li = next(i for i in custos.listar_insumos(P())["insumos"] if i["id"] == leite)
    esperado = (D("4.99") + D("18")) / (D("395") * 4)
    checar(igual(li["preco_base"], esperado), "média ponderada pelas quantidades, só compras dentro do período")
    custos.salvar_parametros(P({"cost_basis": "ultima", "margin_pct": "0", "rounding": "0.01"}))
    li = next(i for i in custos.listar_insumos(P())["insumos"] if i["id"] == leite)
    checar(igual(li["preco_base"], D("4.99") / D("395")), "última compra = a de data mais recente (não a última digitada)")

    print("Receitas")
    pid = estoque.criar_produto(P({"name": "Brigadeiro", "stock": 0, "price": "2.50"}))["ids"][0]
    massa = {"name": "Massa de brigadeiro", "yield_qty": "500", "yield_unit": "g", "itens": [
        {"tipo": "insumo", "ref_id": leite, "quantity": "395", "unit": "g"},
        {"tipo": "insumo", "ref_id": oleo, "quantity": "10", "unit": "g"},  # óleo em g via densidade
    ]}
    rm = custos.criar_receita(P(massa))["id"]
    r = custos.detalhe_receita(P(params={"id": str(rm)}))
    oleo_g = D("10") / D("0.92") * (D("9") / D("900"))
    checar(igual(r["custo_itens"], D("4.99") + oleo_g), f"g -> ml pela densidade ({r['custo_itens']})")
    brig = custos.criar_receita(P({"name": "Brigadeiro", "product_id": pid, "yield_qty": "25", "yield_unit": "un",
                                   "labor_minutes": "30", "loss_pct": "5", "extra_cost": "1,50", "itens": [
                                       {"tipo": "receita", "ref_id": rm, "quantity": "0,5", "unit": "kg"},
                                       {"tipo": "insumo", "ref_id": ovo, "quantity": "1", "unit": "un"},
                                   ]}))["id"]
    custos.salvar_parametros(P({"cost_basis": "ultima", "labor_hour": "20", "fixed_pct": "10", "tax_pct": "6", "fee_pct": "4", "margin_pct": "30", "rounding": "0.10"}))
    r = custos.detalhe_receita(P(params={"id": str(brig)}))
    itens = D("4.99") + oleo_g + D("0.825")
    total = itens * D("1.05") + D("10") + D("1.5")
    unit = total / 25
    checar(igual(r["custo_total"], total), "lote = itens + 5% perdas + 30 min × R$ 20/h + R$ 1,50")
    checar(igual(r["custo_venda"], unit), "custo por brigadeiro = lote ÷ 25")
    bruto = unit / (1 - D("0.5"))
    preco = (bruto / D("0.10")).to_integral_value(rounding="ROUND_CEILING") * D("0.10")
    checar(D(r["preco"]["sugerido"]["preco"]) == preco, f"preço = custo ÷ (1 − 50%), arredondado para cima em R$ 0,10 ({r['preco']['sugerido']['preco']})")
    s = r["preco"]["sugerido"]
    soma = D(s["custo"]) + D(s["despesas_fixas"]) + D(s["impostos"]) + D(s["taxas"]) + D(s["lucro"])
    checar(abs(soma - D(s["preco"])) < D("1e-10"), "custo + despesas + impostos + taxas + lucro = preço")
    checar(D(s["margem_real_pct"]) >= 30, "arredondar para cima nunca baixa o lucro abaixo do desejado")
    checar(r["preco"]["atual"] and D(r["preco"]["atual"]["preco"]) == D("2.5"), "decompõe também o preço atual do produto")

    print("Proteções")
    checar("si mesma" in erro(custos.atualizar_receita, P({**massa, "itens": massa["itens"] + [{"tipo": "receita", "ref_id": brig, "quantity": "1", "unit": "un"}]}, {"id": str(rm)})),
           "ciclo (massa usa brigadeiro que usa massa) é recusado")
    checar("usado em" in erro(custos.excluir_insumo, P(params={"id": str(ovo)})), "insumo em receita não pode ser excluído")
    checar("usada em" in erro(custos.excluir_receita, P(params={"id": str(rm)})), "receita usada em outra não pode ser excluída")
    checar("mesma medida" in erro(custos.criar_receita, P({"name": "X", "yield_qty": 1, "yield_unit": "un", "itens": [{"tipo": "receita", "ref_id": rm, "quantity": 1, "unit": "un"}]})),
           "usar receita em g com quantidade em unidades é recusado")
    sim = custos.simular(P({"name": "Bolo kg", "product_id": pid, "yield_qty": 2, "yield_unit": "kg", "itens": []}))
    checar(any("por unidade" in x for x in sim["pendencias"]), "produto por unidade com rendimento em kg avisa")
    checar("100%" in erro(custos.salvar_parametros, P({"fixed_pct": 50, "margin_pct": 50})), "despesas + lucro >= 100% é recusado")
    checar("2 casas" in erro(custos.aplicar_preco, P({"price": "1.234"}, {"id": str(brig)})), "preço com mais de 2 casas é recusado")
    custos.aplicar_preco(P({"price": s["preco"]}, {"id": str(brig)}))
    pr = contexto.db().query("SELECT price FROM products WHERE id=?", (pid,))[0][0]
    checar(D(str(pr)) == D(s["preco"]), "aplicar grava o preço no produto")
    lista = custos.listar_receitas(P())["receitas"]
    checar(next(x for x in lista if x["id"] == rm)["usada_em_outras"], "lista marca receitas usadas em outras")
    dup = custos.duplicar_receita(P(params={"id": str(brig)}))["id"]
    checar(igual(custos.detalhe_receita(P(params={"id": str(dup)}))["custo_total"], total), "duplicar mantém os itens e o custo")

    print("Auditoria (12/10/2026)")
    checar("inválido" in erro(custos.registrar_compra, P({"conteudo": "1e-40", "unidade": "g", "total": "5"}, {"id": str(leite)})), "notação científica é recusada")
    checar("vírgula" in erro(custos.registrar_compra, P({"conteudo": "1,234.5", "unidade": "g", "total": "5"}, {"id": str(leite)})), "\"1,234.5\" (vírgula antes do ponto) é recusado")
    checar("maior que zero" in erro(custos.registrar_compra, P({"conteudo": "0,0000001", "unidade": "g", "total": "5"}, {"id": str(leite)})), "quantidade minúscula é recusada")
    sal = custos.criar_insumo(P({"name": "Sal", "base_unit": "g", "compra": {"conteudo": "0,57", "unidade": "mg", "total": "1"}}))["id"]
    ult = next(i for i in custos.listar_insumos(P())["insumos"] if i["id"] == sal)["ultima_compra"]
    checar(ult["conteudo"] == "0.57", f"última compra volta na unidade da embalagem, exata ({ult['conteudo']})")
    rx = custos.criar_receita(P({"name": "Usa óleo em g", "yield_qty": 1, "yield_unit": "un", "itens": [{"tipo": "insumo", "ref_id": oleo, "quantity": "5", "unit": "g"}]}))["id"]
    checar("densidade" in erro(custos.atualizar_insumo, P({"name": "Óleo", "base_unit": "ml", "density": ""}, {"id": str(oleo)})),
           "tirar a densidade de insumo usado em outra medida é recusado")
    custos.atualizar_insumo(P({"name": "Óleo", "base_unit": "ml", "density": "0,92", "notes": "x"}, {"id": str(oleo)}))
    checar(True, "editar o insumo mantendo a densidade continua permitido")
    custos.excluir_receita(P(params={"id": str(rx)}))
    custos.salvar_parametros(P({"rounding": "0.1", "margin_pct": "30"}))
    checar(custos.ler_parametros(P())["rounding"] == "0.10", "arredondamento \"0.1\" é aceito e guardado como 0.10")
    checar("escolha" in erro(custos.simular, P({"name": "x", "yield_qty": 1, "yield_unit": "un", "itens": [{"tipo": "insumo", "ref_id": "abc", "quantity": 1, "unit": "g"}]})), "item com referência inválida é recusado")

    print()
    if FALHAS:
        print(f"{len(FALHAS)} FALHA(S)")
        return 1
    print("Tudo certo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
