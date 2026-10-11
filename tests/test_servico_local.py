# -*- coding: utf-8 -*-
"""Teste de integração do motor (servico_local.py) contra uma CÓPIA de banco.

Uso:
    py tests/test_servico_local.py <banco_de_teste.db>

Nunca aponte para o banco de produção: o teste cria, edita e exclui registros.
Sobe o motor numa porta livre (sem painel da cozinha e sem tarefas periódicas),
percorre as rotas e confere os efeitos no estoque.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TOKEN = "teste-token"
FALHAS: list[str] = []


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Cliente:
    def __init__(self, porta: int):
        self.base = f"http://127.0.0.1:{porta}"

    def req(self, metodo: str, caminho: str, corpo=None, token: str = TOKEN):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        caminho = urllib.parse.quote(caminho, safe="/?&=%")
        r = urllib.request.Request(self.base + caminho, data=dados, method=metodo,
                                   headers={"X-Token": token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def ok(self, metodo, caminho, corpo=None):
        st, js = self.req(metodo, caminho, corpo)
        if st != 200:
            raise AssertionError(f"{metodo} {caminho} -> {st} {js}")
        return js


def checar(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FALHA ") + msg)
    if not cond:
        FALHAS.append(msg)


def proxima_terca(base: date) -> date:
    d = base
    while d.weekday() != 1:
        d += timedelta(days=1)
    return d


def main() -> int:
    banco = os.path.abspath(sys.argv[1])
    porta = porta_livre()
    env = {**os.environ, "CONFEITARIA_TOKEN": TOKEN, "CONFEITARIA_DB": banco,
           "CONFEITARIA_DATA_DIR": tempfile.mkdtemp(prefix="motor_teste_"),  # nunca o config.yaml real
           "CONFEITARIA_SEM_COZINHA": "1", "CONFEITARIA_SEM_TAREFAS": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen([sys.executable, str(RAIZ / "servico_local.py"), "--porta", str(porta)],
                            cwd=RAIZ, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    c = Cliente(porta)
    try:
        for _ in range(60):
            try:
                if c.req("GET", "/saude")[0] == 200:
                    break
            except OSError:
                time.sleep(0.25)
        print("Segurança")
        checar(c.req("GET", "/saude", token="errado")[0] == 401, "token errado é recusado")
        checar(c.req("GET", "/clientes")[0] == 401, "rota protegida exige login")
        checar(c.req("POST", "/login", {"usuario": "admin", "senha": "x"})[0] == 401, "senha errada é recusada")
        ruim = urllib.request.Request(c.base + "/login", data=rb'{"x": "\q', method="POST", headers={"X-Token": TOKEN})
        try:
            urllib.request.urlopen(ruim, timeout=10)
            st_ruim = 200
        except urllib.error.HTTPError as e:
            st_ruim = e.code
        checar(st_ruim == 400, "JSON inválido responde 400 (não erro interno)")
        login = c.ok("POST", "/login", {"usuario": "admin", "senha": "admin"})

        print("Senha padrão")
        checar(login["usuario"]["trocar_senha"] is True, "admin/admin obriga a trocar a senha")
        st, js = c.req("GET", "/clientes")
        checar(st == 403 and js.get("codigo") == "trocar_senha", "com a senha padrão o resto fica bloqueado")
        checar(c.req("PUT", "/minha-senha", {"atual": "admin", "nova": "123456"})[0] == 400, "senha nova comum é recusada")
        checar(c.req("PUT", "/minha-senha", {"atual": "admin", "nova": "abc"})[0] == 400, "senha nova curta é recusada")
        checar(c.req("PUT", "/minha-senha", {"atual": "errada", "nova": "Doce#2026"})[0] == 400, "senha atual errada é recusada")
        c.ok("PUT", "/minha-senha", {"atual": "admin", "nova": "Doce#2026"})
        checar(c.req("GET", "/clientes")[0] == 200, "depois de trocar, libera")
        c.ok("POST", "/logout")
        checar(c.req("POST", "/login", {"usuario": "admin", "senha": "admin"})[0] == 401, "senha antiga não entra mais")
        checar(c.req("POST", "/login/trocar-senha", {"usuario": "admin", "atual": "Doce#2026", "nova": "Doce#2026"})[0] == 400, "troca no login exige senha diferente")
        c.ok("POST", "/login/trocar-senha", {"usuario": "admin", "atual": "Doce#2026", "nova": "Bolo!2026"})
        checar(c.req("POST", "/login/trocar-senha", {"usuario": "admin", "atual": "Doce#2026", "nova": "Outra!2026"})[0] == 401, "troca no login confere a senha atual")
        login = c.ok("POST", "/login", {"usuario": "admin", "senha": "Bolo!2026"})
        checar(login["usuario"]["trocar_senha"] is False, "senha forte não pede troca")

        print("Clientes")
        cid = c.ok("POST", "/clientes", {"name": "  Cliente Teste  ", "phone": "", "address": "Rua X"})["id"]
        cli = [x for x in c.ok("GET", "/clientes?q=Cliente Teste")["clientes"] if x["id"] == cid][0]
        checar(cli["name"] == "Cliente Teste" and cli["phone"] is None, "cria com strip e vazio→NULL")
        checar(c.req("POST", "/clientes", {"name": " "})[0] == 400, "nome obrigatório")
        c.ok("PUT", f"/clientes/{cid}", {"name": "Cliente Teste 2", "phone": "9999"})

        print("Produtos")
        pid = c.ok("POST", "/produtos", {"name": "Bolo Teste", "stock": 10, "min_stock": 2, "price": 50})["ids"][0]
        vari = c.ok("POST", "/produtos", {"name": "Torta Teste", "sizes": ["15", "20 cm"], "stock": 3, "price": 10})["ids"]
        nomes = {x["id"]: x["name"] for x in c.ok("GET", "/produtos")["produtos"]}
        checar(nomes.get(vari[0]) == "Torta Teste 15cm" and nomes.get(vari[1]) == "Torta Teste 20 cm", "um produto por tamanho, sem 'cmcm'")
        estoque = lambda: {x["id"]: x["stock"] for x in c.ok("GET", "/produtos")["produtos"]}  # noqa: E731

        print("Pedidos")
        segunda = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
        st, js = c.req("POST", "/pedidos", {"customer_id": cid, "delivery_date": segunda.isoformat(), "products": [{"product_id": pid, "quantity": 1}]})
        checar(st == 400 and js.get("codigo") == "dia_fechado", "segunda-feira (dia sem expediente padrão) é recusada")
        futuro = proxima_terca(date.today() + timedelta(days=1))
        lote = c.ok("POST", "/pedidos", {"customer_id": cid, "delivery_date": futuro.isoformat(), "label": "Urgente", "notes": "sem açúcar",
                                         "products": [{"product_id": pid, "quantity": 2}, {"product_id": vari[0], "quantity": 1}]})["ids"]
        checar(estoque()[pid] == 10, "entrega futura não baixa estoque")
        linha = [x for x in c.ok("GET", f"/pedidos?de={futuro}&ate={futuro}")["pedidos"] if x["customer_id"] == cid][0]
        checar(sorted(linha["ids"]) == sorted(lote) and linha["obs"] == "sem açúcar" and linha["quantity"] == 3, "lote numa linha, obs sem marcador")
        checar(any(x["customer_id"] == cid for x in c.ok("GET", "/pedidos?q=urgente")["pedidos"]), "busca encontra pela etiqueta")
        det = c.ok("GET", f"/pedidos/{lote[0]}")["pedido"]
        checar(len(det["itens"]) == 2 and det["label"] == "Urgente", "detalhe traz itens do lote")
        # editar sem mandar etiqueta não a perde
        c.ok("PUT", f"/pedidos/{lote[0]}", {"quantity": 4})
        det = c.ok("GET", f"/pedidos/{lote[0]}")["pedido"]
        checar(det["label"] == "Urgente" and det["notes"].startswith("LOTE:") and det["obs"] == "sem açúcar", "edição preserva etiqueta e marcador de lote")
        # trazer a data para hoje reserva o estoque
        hoje = date.today()
        if hoje.weekday() != 0:
            c.ok("PUT", f"/pedidos/{lote[0]}", {"delivery_date": hoje.isoformat()})
            checar(estoque()[pid] == 6, "data para hoje reserva (10-4=6)")
            c.ok("PUT", f"/pedidos/{lote[0]}", {"quantity": 5})
            checar(estoque()[pid] == 5, "já reservado: ajusta pela diferença")
            c.ok("PUT", f"/pedidos/{lote[0]}", {"product_id": vari[1]})
            e = estoque()
            checar(e[pid] == 10 and e[vari[1]] == -2, "troca de produto devolve e baixa")
        c.ok("POST", "/pedidos/editar", {"label": "Especial", "notes": "com vela",
                                          "itens": [{"id": lote[0], "product_id": pid, "quantity": 3}, {"id": lote[1], "product_id": vari[0], "quantity": 2}]})
        det = c.ok("GET", f"/pedidos/{lote[0]}")["pedido"]
        checar(det["label"] == "Especial" and det["obs"] == "com vela" and sorted(i["quantity"] for i in det["itens"]) == [2, 3], "edição completa do lote numa transação")
        st, _ = c.req("POST", "/pedidos/editar", {"itens": [{"id": lote[0], "product_id": pid, "quantity": 0}]})
        checar(st == 400 and c.ok("GET", f"/pedidos/{lote[0]}")["pedido"]["quantity"] == 3, "edição inválida não altera nada")
        checar(set(c.ok("GET", "/menu")) == {"pedidosHoje", "producao", "esgotados"}, "contadores do menu")
        c.ok("PUT", "/pedidos/lote", {"ids": lote, "status": "Pago"})
        checar(all(c.ok("GET", f"/pedidos/{i}")["pedido"]["status"] == "Pago" for i in lote), "status do lote todo")
        checar(c.ok("POST", "/pedidos/excluir/contar", {"ids": [lote[1]]})["itens"] == 2, "excluir 1 item conta o lote inteiro")
        antes = estoque()
        c.ok("POST", "/pedidos/excluir", {"ids": [lote[1]]})
        e = estoque()
        checar(all(c.req("GET", f"/pedidos/{i}")[0] == 404 for i in lote), "lote excluído")
        if hoje.weekday() != 0:
            # só o 1º item estava reservado (data trazida para hoje): 3 un de "Bolo Teste" voltam
            checar(e[pid] == antes[pid] + 3 and e[vari[0]] == antes[vari[0]], "exclusão devolve só o estoque reservado")

        print("Etiquetas e logs")
        eid = c.ok("POST", "/etiquetas", {"name": "Teste Etq", "color": "#123456"})["id"]
        checar(c.req("POST", "/etiquetas", {"name": "teste etq"})[0] == 400, "etiqueta duplicada (maiúsc./minúsc.)")
        c.ok("PUT", f"/etiquetas/{eid}", {"name": "Teste Etq 2", "color": "#654321"})
        c.ok("DELETE", f"/etiquetas/{eid}")
        checar(len(c.ok("GET", f"/logs?entidade=order&id={lote[0]}")["logs"]) >= 3, "auditoria registrada")

        print("Movimentações")
        st, js = c.req("POST", "/movimentos", {"type": "saida", "category": "Perda/Quebra", "product_id": pid, "quantity": 9999})
        checar(st == 409, "saída maior que o estoque é recusada")
        mid = c.ok("POST", "/movimentos", {"type": "entrada", "category": "Compra/Reposição", "product_id": pid, "quantity": 5})["id"]
        e = estoque()[pid]
        c.ok("POST", "/movimentos/excluir", {"ids": [mid]})
        checar(estoque()[pid] == e - 5, "excluir movimentação desfaz o estoque")
        mv = c.ok("GET", "/movimentos?periodo=hoje&filtro=todas")
        checar("resumo" in mv and isinstance(mv["movimentos"], list), "lista e resumo")
        with tempfile.TemporaryDirectory() as tmp:
            arq = os.path.join(tmp, "mov.xlsx")
            c.ok("POST", "/movimentos/exportar", {"caminho": arq, "filtros": {"periodo": "tudo"}})
            checar(os.path.getsize(arq) > 0, "exporta Excel")

        print("Produção")
        iid = c.ok("POST", "/producao", {"product_id": pid, "quantity": 2, "size": "15"})["id"]
        e = estoque()[pid]
        c.ok("PUT", f"/producao/{iid}", {"quantity": 5})
        checar(estoque()[pid] == e, "mudar qtd na lista não mexe no estoque (só 'Produção feita')")
        dados = c.ok("GET", "/producao")
        checar(any(i["id"] == iid for i in dados["itens"]) and dados["estoque"], "lista + estoque")
        c.ok("POST", "/producao/remover", {"ids": [iid]})

        print("Relatórios e dashboard")
        d = c.ok("GET", "/dashboard")
        checar("kpis" in d and "entregas_hoje" in d, "dashboard")
        for tipo in ("entregas", "producao", "fechamento"):
            r = c.ok("GET", f"/relatorios?tipo={tipo}")
            checar(isinstance(r["linhas"], list) and r["colunas"], f"relatório {tipo}")
        with tempfile.TemporaryDirectory() as tmp:
            for ext in ("pdf", "xlsx"):
                arq = os.path.join(tmp, f"fech.{ext}")
                c.ok("POST", "/relatorios/exportar", {"tipo": "fechamento", "de": "2020-01-01", "ate": "2030-12-31", "caminho": arq})
                checar(os.path.getsize(arq) > 0, f"exporta fechamento .{ext}")
            st, js = c.req("POST", "/pedidos/relatorio", {"de": "2000-01-01", "ate": "2000-01-02", "formato": "pdf", "caminho": os.path.join(tmp, "x.pdf")})
            checar(st == 404 and js.get("codigo") == "vazio", "relatório de pedidos vazio avisa")
            opc = c.ok("GET", "/pedidos/relatorio/opcoes")
            checar("clientes" in opc, "opções do relatório")
            for fmt in ("pdf", "xlsx"):
                arq = os.path.join(tmp, f"ped.{fmt}")
                c.ok("POST", "/pedidos/relatorio", {"de": "2020-01-01", "ate": "2030-12-31", "formato": fmt, "caminho": arq})
                checar(os.path.getsize(arq) > 0, f"relatório de pedidos .{fmt}")

        print("Usuários")
        checar(c.req("POST", "/usuarios", {"username": "func1", "password": "1234", "role": "common"})[0] == 400, "usuário novo com senha fraca é recusado")
        uid = c.ok("POST", "/usuarios", {"username": "func1", "password": "Massa#77", "role": "common"})["id"]
        checar(c.req("POST", "/usuarios", {"username": "FUNC1", "password": "Massa#77"})[0] == 400, "usuário duplicado")
        me = c.ok("GET", "/saude")["usuario"]
        checar(c.req("DELETE", f"/usuarios/{me['id']}")[0] == 400, "não exclui a si mesmo")
        c.ok("DELETE", f"/usuarios/{uid}")

        print("Banco")
        info = c.ok("GET", "/banco")
        checar(info["contagens"]["pedidos"] >= 0, "informações do banco")
        checar(c.ok("POST", "/banco/verificar")["ok"], "integridade ok")
        with tempfile.TemporaryDirectory() as tmp:
            bk = c.ok("POST", "/banco/backup", {"caminho": os.path.join(tmp, "bk.zip")})["caminho"]
            cid2 = c.ok("POST", "/clientes", {"name": "Some Depois Da Restauração"})["id"]
            c.ok("POST", "/banco/restaurar", {"caminho": bk})
            nomes = [x["name"] for x in c.ok("GET", "/clientes")["clientes"]]
            checar("Some Depois Da Restauração" not in nomes and "Cliente Teste 2" in nomes, "restauração volta ao backup")
            checar(c.ok("GET", "/saude")["usuario"] is not None, "sessão continua após restaurar")
        c.ok("POST", "/clientes/excluir", {"ids": [cid]})
        _ = cid2
    finally:
        proc.terminate()
        try:
            saida = proc.communicate(timeout=5)[0].decode("utf-8", "replace")
        except Exception:
            saida = ""
        if FALHAS and saida:
            print("---- saída do motor ----")
            print(saida[-4000:])
    print(f"\n{'FALHOU' if FALHAS else 'TUDO OK'}: {len(FALHAS)} falha(s)")
    return 1 if FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
