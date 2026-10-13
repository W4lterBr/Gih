# -*- coding: utf-8 -*-
"""Licença DWM no motor: modo somente leitura de ponta a ponta.

    py tests/test_licenca_motor.py <banco_de_teste.db>

Sobe um servidor de licenças falso e o motor (pasta de dados temporária, nunca a real)
e confere: bloqueado recusa gravações (423) mas deixa ler, exportar e fazer backup;
só administrador ativa/remove; o token não aparece no log nem nas respostas.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_servico_local import Cliente, checar, porta_livre, FALHAS, TOKEN, RAIZ  # noqa: E402

TOKEN_LIC = "Q1W2-E3R4-T5Y6-U7I8"
MODO = {"v": "liberado"}


class Lic(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.headers.get("X-License-Token") != TOKEN_LIC:
            corpo, cod = {"success": False, "error": "TOKEN_INVALIDO"}, 401
        else:
            st = MODO["v"]
            corpo, cod = {"success": True, "cliente": {"nome": "Teste", "cnpj": "1"},
                          "acesso": {"status": st, "dias_atraso": 9 if st == "bloqueado" else 0,
                                     "dias_restantes_tolerancia": 0, "mensagem": f"Situação: {st}",
                                     "fatura_vencida": {"numero": "F1", "valor": 50, "vencimento": "2026-10-01"} if st != "liberado" else None},
                          "faturas_pagas_recentes": [], "proxima_fatura": None}, 200
        d = json.dumps(corpo).encode()
        self.send_response(cod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        self.wfile.write(d)


def main() -> int:
    banco = os.path.abspath(sys.argv[1])
    lic = ThreadingHTTPServer(("127.0.0.1", 0), Lic)
    threading.Thread(target=lic.serve_forever, daemon=True).start()
    dados = tempfile.mkdtemp(prefix="motor_lic_")
    porta = porta_livre()
    log = os.path.join(dados, "motor.log")
    env = {**os.environ, "CONFEITARIA_TOKEN": TOKEN, "CONFEITARIA_DB": banco, "CONFEITARIA_DATA_DIR": dados,
           "CONFEITARIA_LICENCA_URL": f"http://127.0.0.1:{lic.server_address[1]}/api/licenca-cliente/status",
           "CONFEITARIA_SEM_COZINHA": "1", "CONFEITARIA_SEM_TAREFAS": "1", "PYTHONIOENCODING": "utf-8"}
    with open(log, "w", encoding="utf-8") as saida:
        proc = subprocess.Popen([sys.executable, str(RAIZ / "servico_local.py"), "--porta", str(porta)],
                                cwd=RAIZ, env=env, stdout=saida, stderr=subprocess.STDOUT)
    c = Cliente(porta)
    try:
        for _ in range(60):
            try:
                if c.req("GET", "/saude")[0] == 200:
                    break
            except OSError:
                time.sleep(0.25)
        c.ok("POST", "/login", {"usuario": "admin", "senha": "admin"})
        c.ok("PUT", "/minha-senha", {"atual": "admin", "nova": "Doce#2026"})  # senha padrão exige troca

        print("Sem token")
        s = c.ok("GET", "/licenca")
        checar(s["situacao"] == "sem_token" and not s["somente_leitura"], "sem token: funciona normalmente")
        checar(c.req("POST", "/clientes", {"name": "Livre"})[0] == 200, "sem token: grava")

        print("Ativação")
        st, js = c.req("POST", "/licenca/ativar", {"token": "AAAA-BBBB-CCCC-DDDD"})
        checar(st == 400 and js.get("codigo") == "token_recusado", "token errado é recusado")
        s = c.ok("POST", "/licenca/ativar", {"token": TOKEN_LIC})
        checar(s["situacao"] == "liberado", "token certo ativa")
        checar(TOKEN_LIC not in json.dumps(s), "resposta não traz o token completo")
        uid = c.ok("POST", "/usuarios", {"username": "func9", "password": "Massa#77", "role": "recepcao"})["id"]

        print("Bloqueado = somente leitura")
        MODO["v"] = "bloqueado"
        time.sleep(0.1)
        s = c.ok("POST", "/licenca/verificar")
        checar(s["situacao"] == "bloqueado" and s["somente_leitura"], "servidor diz bloqueado")
        st, js = c.req("POST", "/clientes", {"name": "Bloqueado"})
        checar(st == 423 and js.get("codigo") == "licenca_bloqueada", "criar cliente recusado (423)")
        checar(c.req("POST", "/pedidos", {"customer_id": 1, "delivery_date": "2030-01-08", "products": [{"product_id": 1, "quantity": 1}]})[0] == 423, "criar pedido recusado")
        checar(c.req("PUT", "/clientes/1", {"name": "X"})[0] == 423, "editar recusado")
        checar(c.req("POST", "/clientes/excluir", {"ids": [1]})[0] == 423, "excluir recusado")
        checar(c.req("POST", "/banco/restaurar", {"caminho": "x.zip"})[0] == 423, "restaurar backup recusado")
        checar(c.req("GET", "/pedidos")[0] == 200 and c.req("GET", "/dashboard")[0] == 200, "leitura continua")
        with tempfile.TemporaryDirectory() as tmp:
            checar(c.req("POST", "/relatorios/exportar", {"tipo": "producao", "de": "2020-01-01", "ate": "2030-01-01",
                                                           "caminho": os.path.join(tmp, "r.xlsx")})[0] == 200, "exportar relatório continua")
            checar(c.req("POST", "/banco/backup", {"caminho": os.path.join(tmp, "b.zip")})[0] == 200, "backup continua (protege os dados)")
        st, js = c.req("POST", "/licenca/remover")
        checar(st == 409, "não remove o token com a licença bloqueada")

        print("Permissões")
        c.ok("POST", "/logout")
        c.ok("POST", "/login", {"usuario": "func9", "senha": "Massa#77"})
        checar(c.req("POST", "/licenca/ativar", {"token": TOKEN_LIC})[0] == 403, "usuário comum não ativa licença")
        checar(c.req("GET", "/licenca")[0] == 200, "usuário comum vê a situação")
        c.ok("POST", "/logout")
        c.ok("POST", "/login", {"usuario": "admin", "senha": "Doce#2026"})

        print("Pagou")
        MODO["v"] = "liberado"
        time.sleep(31)  # intervalo mínimo entre verificações forçadas
        s = c.ok("POST", "/licenca/verificar")
        checar(s["situacao"] == "liberado" and not s["somente_leitura"], "liberado de novo")
        checar(c.req("POST", "/clientes", {"name": "Depois de pagar"})[0] == 200, "volta a gravar")
        c.ok("DELETE", f"/usuarios/{uid}")
        c.ok("POST", "/licenca/remover")
        checar(c.ok("GET", "/licenca")["situacao"] == "sem_token", "remove o token com a licença em dia")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        texto = Path(log).read_text(encoding="utf-8", errors="replace")
        checar(TOKEN_LIC not in texto, "token nunca aparece no log do motor")
        arquivos = [p for p in Path(dados).iterdir() if p.is_file()]
        checar(all(TOKEN_LIC.encode() not in p.read_bytes() for p in arquivos), "token não fica em texto puro na pasta de dados")
        if FALHAS:
            print(texto[-3000:])
    print(f"\n{'FALHOU' if FALHAS else 'TUDO OK'}: {len(FALHAS)} falha(s)")
    return 1 if FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
