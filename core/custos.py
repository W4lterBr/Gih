# -*- coding: utf-8 -*-
"""Cálculo de custos: insumos, fichas técnicas (receitas) e preço de venda.

Precisão: toda conta usa Decimal com 50 dígitos e NADA é arredondado no meio do
caminho. O custo por grama de um insumo (R$ 4,99 / 395 g = 0,01263291139…) é usado
com todas as casas; só o preço de venda final é arredondado (para cima, no múltiplo
escolhido nos parâmetros). Os valores saem como texto ("0.0126329113924050632911")
para a interface não perder casas convertendo para float.

Modelo:
- Insumo: comprado em embalagens (ex.: 2 × 395 g por R$ 9,98). Guarda a unidade-base
  (g, ml ou un), o aproveitamento (% que sobra depois de descascar, limpar, peneirar…)
  e, opcional, a densidade (g por ml) para converter receitas em ml de um insumo
  comprado em g e vice-versa.
- Custo do insumo por unidade-base: preço da última compra ou média ponderada das
  compras recentes (parâmetro), dividido pelo aproveitamento.
- Receita: itens (insumos ou outras receitas, ex.: recheio dentro do bolo) + perdas
  no preparo (%) + mão de obra (minutos × R$/hora) + outros custos (gás, energia) =
  custo do lote; ÷ rendimento = custo por unidade.
- Preço de venda (método do divisor, o usado em precificação de confeitaria):
  preço = custo ÷ (1 − (despesas fixas % + impostos % + taxas % + lucro %)).
  Assim o lucro desejado é % do PREÇO, não do custo, e as despesas que incidem
  sobre a venda já ficam cobertas.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import ROUND_CEILING, Context, Decimal, InvalidOperation, localcontext
from typing import Any, Optional

D = Decimal
ZERO = D(0)
CEM = D(100)
PRECISAO = 50


class ErroCusto(ValueError):
    """Dado inválido (mensagem para o usuário)."""


# Unidades aceitas na digitação -> (unidade-base, fator para a base). Exatos.
UNIDADES: dict[str, tuple[str, Decimal]] = {
    "mg": ("g", D("0.001")),
    "g": ("g", D(1)),
    "kg": ("g", D(1000)),
    "ml": ("ml", D(1)),
    "l": ("ml", D(1000)),
    "un": ("un", D(1)),
    "dz": ("un", D(12)),
}
BASES = ("g", "ml", "un")
CATEGORIAS = ("ingrediente", "embalagem", "decoracao", "outro")
ARREDONDAMENTOS = ("0.01", "0.05", "0.10", "0.50", "1.00")


# ---------------------------------------------------------------- números


def dec(valor: Any, campo: str, minimo: Optional[Decimal] = None, maximo: Optional[Decimal] = None,
        maior_que_zero: bool = False, vazio: Optional[Decimal] = None) -> Decimal:
    """Texto/número -> Decimal exato. Aceita "1,5", "1.5", "1.234,56" e números JSON.
    float vira texto antes (D(0.1) seria 0.1000000000000000055…)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if vazio is not None:
            return vazio
        raise ErroCusto(f"Informe {campo}.")
    if isinstance(valor, bool):
        raise ErroCusto(f"Valor inválido em {campo}.")
    if isinstance(valor, (int, float)):
        s = repr(valor) if isinstance(valor, float) else str(valor)
    else:
        s = str(valor).strip().replace(" ", "").replace("R$", "")
        if "," in s and "." in s[s.index(","):]:
            raise ErroCusto(f"Valor inválido em {campo}: use vírgula para os decimais (ex.: 1.234,56).")
        if "," in s:
            # Com vírgula, formato brasileiro: ponto é milhar ("1.234,56"). Só com ponto,
            # o ponto é decimal ("1.5"), como no resto do sistema.
            s = s.replace(".", "").replace(",", ".")
    if isinstance(valor, float) and "e" in s.lower():
        s = format(D(s), "f")  # 1e-05 vindo do JSON
    if not re.fullmatch(r"-?\d{1,15}(\.\d{1,15})?", s):
        raise ErroCusto(f"Valor inválido em {campo}.")
    try:
        n = D(s)
    except InvalidOperation:
        raise ErroCusto(f"Valor inválido em {campo}.")
    if not n.is_finite():
        raise ErroCusto(f"Valor inválido em {campo}.")
    if maior_que_zero and n < D("0.000001"):
        raise ErroCusto(f"{campo[0].upper() + campo[1:]} deve ser maior que zero.")
    if minimo is not None and n < minimo:
        raise ErroCusto(f"{campo[0].upper() + campo[1:]} deve ser no mínimo {txt(minimo)}.")
    if maximo is not None and n > maximo:
        raise ErroCusto(f"{campo[0].upper() + campo[1:]} deve ser no máximo {txt(maximo)}.")
    return n


def txt(n: Optional[Decimal], casas: int = 12) -> Optional[str]:
    """Decimal -> texto sem notação científica, até `casas` casas, sem zeros à direita."""
    if n is None:
        return None
    try:
        with localcontext(Context(prec=PRECISAO)):
            q = n.quantize(D(1).scaleb(-casas))
    except InvalidOperation:  # grande demais para as casas pedidas: mostra como está
        q = n
    s = format(q, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def guardar(n: Decimal) -> str:
    """Texto para gravar no banco (exato, sem limite de casas)."""
    with localcontext(Context(prec=PRECISAO)):
        return format(n.normalize() if n != 0 else D(0), "f")


def unidade(u: Any, campo: str = "unidade") -> str:
    s = str(u or "").strip().lower()
    if s == "lt":
        s = "l"
    if s not in UNIDADES:
        raise ErroCusto(f"Unidade inválida em {campo}.")
    return s


def converter(qtd: Decimal, de: str, para_base: str, densidade: Optional[Decimal] = None) -> Decimal:
    """Quantidade digitada (em `de`) -> unidade-base `para_base`. g<->ml só com densidade."""
    base, fator = UNIDADES[de]
    with localcontext(Context(prec=PRECISAO)):
        q = qtd * fator
        if base == para_base:
            return q
        if densidade and {base, para_base} == {"g", "ml"}:
            return q * densidade if base == "ml" else q / densidade
    nomes = {"g": "peso (g/kg)", "ml": "volume (ml/L)", "un": "unidades"}
    dica = " Informe a densidade do insumo para converter entre peso e volume." if {base, para_base} == {"g", "ml"} else ""
    raise ErroCusto(f"Não dá para converter {nomes[base]} em {nomes[para_base]}.{dica}")


def unidades_compativeis(base: str, densidade: Optional[Decimal]) -> list[str]:
    bases = {base} | ({"g", "ml"} if densidade and base in ("g", "ml") else set())
    return [u for u, (b, _) in UNIDADES.items() if b in bases]


# ---------------------------------------------------------------- parâmetros


def parametros(db: Any) -> dict:
    r = db.query("SELECT * FROM cost_settings WHERE id=1")
    r = dict(r[0]) if r else {}
    return {
        "cost_basis": r.get("cost_basis") or "ultima",
        "avg_days": int(r.get("avg_days") or 90),
        "labor_hour": D(r.get("labor_hour") or "0"),
        "fixed_pct": D(r.get("fixed_pct") or "0"),
        "tax_pct": D(r.get("tax_pct") or "0"),
        "fee_pct": D(r.get("fee_pct") or "0"),
        "margin_pct": D(r.get("margin_pct") or "0"),
        "rounding": D(r.get("rounding") or "0.01"),
    }


def parametros_json(p: dict) -> dict:
    out = {k: (txt(v) if isinstance(v, Decimal) else v) for k, v in p.items()}
    out["rounding"] = format(p["rounding"], ".2f")  # "0.10", como nas opções da tela
    return out


# ---------------------------------------------------------------- preço de venda


def precificar(custo: Decimal, prm: dict, margem: Optional[Decimal], preco_atual: Optional[Decimal],
               preco_teste: Optional[Decimal] = None) -> dict:
    """Preço sugerido pelo método do divisor e a decomposição do preço (sugerido e atual)."""
    with localcontext(Context(prec=PRECISAO)):
        lucro_pct = prm["margin_pct"] if margem is None else margem
        desp_pct = prm["fixed_pct"] + prm["tax_pct"] + prm["fee_pct"]
        soma = desp_pct + lucro_pct
        out: dict[str, Any] = {"margem_pct": txt(lucro_pct), "despesas_pct": txt(desp_pct), "aviso": None}

        def decompor(preco: Decimal) -> dict:
            fixas = preco * prm["fixed_pct"] / CEM
            impostos = preco * prm["tax_pct"] / CEM
            taxas = preco * prm["fee_pct"] / CEM
            lucro = preco - custo - fixas - impostos - taxas
            return {
                "preco": txt(preco), "custo": txt(custo), "despesas_fixas": txt(fixas), "impostos": txt(impostos),
                "taxas": txt(taxas), "lucro": txt(lucro),
                "margem_real_pct": txt(lucro / preco * CEM) if preco else None,
                "markup": txt(preco / custo) if custo else None,
            }

        if soma >= CEM:
            out["aviso"] = "Despesas + lucro chegam a 100% do preço ou mais: não há preço que cubra. Reduza os percentuais."
            out["sugerido"] = None
            out["preco_minimo"] = txt(custo / (1 - desp_pct / CEM)) if desp_pct < CEM else None
        else:
            bruto = custo / (1 - soma / CEM)
            r = prm["rounding"] if prm["rounding"] > 0 else D("0.01")
            preco = (bruto / r).to_integral_value(rounding=ROUND_CEILING) * r
            out["sugerido"] = decompor(preco)
            out["sugerido"]["preco_exato"] = txt(bruto)
            # Preço mínimo: cobre custo e despesas, lucro zero.
            out["preco_minimo"] = txt(custo / (1 - desp_pct / CEM))
        out["atual"] = decompor(preco_atual) if preco_atual and preco_atual > 0 else None
        out["teste"] = decompor(preco_teste) if preco_teste and preco_teste > 0 else None
        return out


# ---------------------------------------------------------------- cálculo


class Calculadora:
    """Calcula custos de insumos e receitas com cache por requisição."""

    def __init__(self, db: Any, prm: Optional[dict] = None):
        self.db = db
        self.prm = prm or parametros(db)
        self._ing: dict[int, dict] = {}
        self._rec: dict[int, dict] = {}

    # ---- insumos

    def insumo(self, iid: int) -> Optional[dict]:
        if iid in self._ing:
            return self._ing[iid]
        r = self.db.query("SELECT * FROM ingredients WHERE id=?", (iid,))
        if not r:
            self._ing[iid] = None  # type: ignore[assignment]
            return None
        info = self._custo_insumo(dict(r[0]))
        self._ing[iid] = info
        return info

    def _custo_insumo(self, ing: dict) -> dict:
        compras = [dict(c) for c in self.db.query(
            "SELECT * FROM ingredient_purchases WHERE ingredient_id=? ORDER BY purchased_at DESC, id DESC", (ing["id"],))]
        with localcontext(Context(prec=PRECISAO)):
            for c in compras:
                c["_qtd"] = D(c["packages"]) * D(c["package_qty"])  # já na unidade-base
                c["_total"] = D(c["total"])
                c["_unit"] = c["_total"] / c["_qtd"] if c["_qtd"] else None
            bruto: Optional[Decimal] = None
            base_txt = "sem compras"
            if compras:
                if self.prm["cost_basis"] == "media":
                    limite = (date.today() - timedelta(days=self.prm["avg_days"])).isoformat()
                    janela = [c for c in compras if c["purchased_at"] >= limite]
                    if janela:
                        q = sum((c["_qtd"] for c in janela), ZERO)
                        bruto = sum((c["_total"] for c in janela), ZERO) / q if q else None
                        base_txt = f"média ponderada de {len(janela)} compra(s) nos últimos {self.prm['avg_days']} dias"
                    else:
                        bruto = compras[0]["_unit"]
                        base_txt = f"última compra (nenhuma nos últimos {self.prm['avg_days']} dias)"
                else:
                    bruto = compras[0]["_unit"]
                    base_txt = "última compra"
            aproveitamento = D(ing["yield_pct"] or "100")
            efetivo = bruto / (aproveitamento / CEM) if bruto is not None and aproveitamento > 0 else None
            variacao = None
            if len(compras) >= 2 and compras[1]["_unit"]:
                variacao = (compras[0]["_unit"] / compras[1]["_unit"] - 1) * CEM
        densidade = D(ing["density"]) if ing.get("density") else None
        return {
            **{k: ing[k] for k in ("id", "name", "category", "base_unit", "notes")},
            "yield_pct": txt(aproveitamento), "density": txt(densidade),
            "_efetivo": efetivo, "_densidade": densidade,
            "preco_bruto": txt(bruto, 20), "preco_base": txt(efetivo, 20), "base_custo": base_txt,
            "variacao_pct": txt(variacao, 4),
            "compras": len(compras),
            "ultima_compra": None if not compras else {
                "data": compras[0]["purchased_at"], "fornecedor": compras[0]["supplier"],
                "embalagens": compras[0]["packages"],
                "conteudo": txt(D(compras[0]["package_qty"]) / UNIDADES[compras[0]["package_unit"]][1], 12),
                "unidade": compras[0]["package_unit"], "total": compras[0]["total"],
            },
            "unidades": unidades_compativeis(ing["base_unit"], densidade),
        }

    # ---- receitas

    def receita(self, rid: int, pilha: tuple[int, ...] = ()) -> Optional[dict]:
        if rid in pilha:
            raise ErroCusto("Uma receita não pode usar a si mesma, nem direta nem indiretamente (ex.: A usa B e B usa A).")
        if rid in self._rec:
            return self._rec[rid]
        r = self.db.query("SELECT * FROM recipes WHERE id=?", (rid,))
        if not r:
            return None
        itens = [dict(i) for i in self.db.query("SELECT * FROM recipe_items WHERE recipe_id=? ORDER BY position, id", (rid,))]
        res = self.calcular(dict(r[0]), itens, pilha + (rid,))
        self._rec[rid] = res
        return res

    def calcular(self, rec: dict, itens: list[dict], pilha: tuple[int, ...] = (), preco_teste: Optional[Decimal] = None) -> dict:
        """`rec`: campos de recipes; `itens`: ingredient_id|sub_recipe_id, quantity, unit."""
        pend: list[str] = []
        linhas: list[dict] = []
        with localcontext(Context(prec=PRECISAO)):
            soma = ZERO
            for it in itens:
                q = D(it["quantity"])
                u = it["unit"]
                linha: dict[str, Any] = {"quantity": it["quantity"], "unit": u, "custo": None, "pendencia": None}
                if it.get("ingredient_id"):
                    ing = self.insumo(int(it["ingredient_id"]))
                    linha.update(tipo="insumo", ref_id=int(it["ingredient_id"]))
                    if not ing:
                        linha.update(nome="(insumo excluído)", pendencia="Insumo não existe mais.")
                    else:
                        linha.update(nome=ing["name"], unidade_base=ing["base_unit"], unidades=ing["unidades"])
                        try:
                            qb = converter(q, u, ing["base_unit"], ing["_densidade"])
                            linha["qtd_base"] = txt(qb, 6)
                            if ing["_efetivo"] is None:
                                linha["pendencia"] = "Sem compra registrada: cadastre o preço."
                            else:
                                linha["preco_base"] = txt(ing["_efetivo"], 20)
                                linha["custo"] = qb * ing["_efetivo"]
                        except ErroCusto as e:
                            linha["pendencia"] = str(e)
                else:
                    sid = int(it["sub_recipe_id"])
                    linha.update(tipo="receita", ref_id=sid)
                    sub = self.receita(sid, pilha)
                    if not sub:
                        linha.update(nome="(receita excluída)", pendencia="Receita não existe mais.")
                    else:
                        linha.update(nome=sub["name"], unidade_base=sub["yield_base"], unidades=unidades_compativeis(sub["yield_base"], None))
                        try:
                            qb = converter(q, u, sub["yield_base"])
                            linha["qtd_base"] = txt(qb, 6)
                            linha["preco_base"] = txt(sub["_custo_base"], 20)
                            linha["custo"] = qb * sub["_custo_base"]
                            if sub["pendencias"]:
                                linha["pendencia"] = f"A receita \"{sub['name']}\" está incompleta: custo parcial."
                        except ErroCusto as e:
                            linha["pendencia"] = str(e)
                if linha["pendencia"]:
                    pend.append(f"{linha['nome']}: {linha['pendencia']}")
                if linha["custo"] is not None:
                    soma += linha["custo"]
                linhas.append(linha)

            for l in linhas:
                l["participacao_pct"] = txt(l["custo"] / soma * CEM, 4) if l["custo"] is not None and soma else None
                l["custo"] = txt(l["custo"], 20)

            perda_pct = D(rec.get("loss_pct") or "0")
            minutos = D(rec.get("labor_minutes") or "0")
            perdas = soma * perda_pct / CEM
            mao = minutos / 60 * self.prm["labor_hour"]
            extra = D(rec.get("extra_cost") or "0")
            total = soma + perdas + mao + extra

            yu = rec["yield_unit"]
            base, _ = UNIDADES[yu]
            rend = converter(D(rec["yield_qty"]), yu, base)
            custo_base = total / rend if rend else ZERO

            # Unidade de venda: produto vinculado manda; sem produto, segue o rendimento.
            prod = None
            if rec.get("product_id"):
                pr = self.db.query("SELECT id, name, size, unit, price FROM products WHERE id=?", (rec["product_id"],))
                prod = dict(pr[0]) if pr else None
            venda_un = ("kg" if base == "g" else "l" if base == "ml" else "un") if not prod else ("kg" if prod["unit"] == "kg" else "un")
            venda_base, fator_venda = UNIDADES[venda_un]
            aviso_venda = None
            if venda_base != base:
                aviso_venda = ("O produto é vendido por kg: informe o rendimento em peso (g ou kg)." if venda_un == "kg"
                               else "O produto é vendido por unidade: informe o rendimento em unidades (quantas peças a receita faz).")
                pend.append(aviso_venda)
                custo_venda = None
            else:
                custo_venda = custo_base * fator_venda

            margem = D(rec["margin_pct"]) if rec.get("margin_pct") not in (None, "") else None
            preco_atual = D(str(prod["price"])) if prod and prod.get("price") else None
            preco = precificar(custo_venda, self.prm, margem, preco_atual, preco_teste) if custo_venda is not None else None

        return {
            "id": rec.get("id"), "name": rec.get("name"), "product_id": rec.get("product_id"),
            "produto": prod, "notes": rec.get("notes"),
            "yield_qty": rec["yield_qty"], "yield_unit": yu, "yield_base": base, "rendimento_base": txt(rend, 6),
            "labor_minutes": txt(minutos), "loss_pct": txt(perda_pct), "extra_cost": txt(extra),
            "margin_pct": txt(margem),
            "itens": linhas,
            "custo_itens": txt(soma, 20), "custo_perdas": txt(perdas, 20), "custo_mao_obra": txt(mao, 20),
            "custo_extra": txt(extra, 20), "custo_total": txt(total, 20),
            "custo_base": txt(custo_base, 20), "_custo_base": custo_base,
            "venda_unidade": venda_un, "custo_venda": txt(custo_venda, 20),
            "preco": preco, "pendencias": pend,
        }


def limpar(res: dict) -> dict:
    """Tira os campos internos (_xxx, Decimal) antes de mandar para a interface."""
    return {k: v for k, v in res.items() if not k.startswith("_")}


def insumo_json(info: dict) -> dict:
    return {k: v for k, v in info.items() if not k.startswith("_")}


def verificar_ciclo(db: Any, rid: Optional[int], subs: list[int]) -> None:
    """Recusa salvar a receita `rid` se ela usar (direta ou indiretamente) a si mesma."""
    if rid is None:
        return
    vistos: set[int] = set()
    fila = list(subs)
    while fila:
        s = fila.pop()
        if s == rid:
            raise ErroCusto("Uma receita não pode usar a si mesma, nem direta nem indiretamente (ex.: A usa B e B usa A).")
        if s in vistos:
            continue
        vistos.add(s)
        fila.extend(int(r["sub_recipe_id"]) for r in db.query(
            "SELECT sub_recipe_id FROM recipe_items WHERE recipe_id=? AND sub_recipe_id IS NOT NULL", (s,)))
