# -*- coding: utf-8 -*-
"""
Motor da Confeitaria: serviço local HTTP para a interface nova (Tauri, em desktop/).

A interface inicia este processo em segundo plano e conversa com ele por HTTP em
127.0.0.1. As regras de negócio são as mesmas do app PyQt (core/): reserva e baixa
de estoque, auditoria, migrações do banco.

Uso (normalmente quem chama é o Tauri, não uma pessoa):
    set CONFEITARIA_TOKEN=<segredo aleatório>
    python servico_local.py --porta 51234 --pai <pid do Tauri>

Variáveis opcionais:
    CONFEITARIA_DB           usa outro banco (testes; nunca o de produção em testes)
    CONFEITARIA_SEM_COZINHA  "1" = não sobe o painel da cozinha (porta 5000)
    CONFEITARIA_SEM_TAREFAS  "1" = sem backup automático e reserva de estoque periódica

Segurança:
- Escuta só em 127.0.0.1 e toda requisição precisa do cabeçalho `X-Token` igual a
  CONFEITARIA_TOKEN (sem isso, qualquer página aberta no navegador poderia mexer nos
  pedidos via localhost).
- CORS só para a própria janela do app.
- Rotas que não são públicas exigem login; rotas de administrador exigem perfil admin.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# A saída vai para um arquivo de log: sem isto, no executável empacotado a codificação
# padrão do Windows (cp1252) derruba o motor no primeiro print com "✓" ou emoji. Antes
# dos imports do projeto, que já imprimem ao carregar.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from api import ErroApi, Pedido, carregar_rotas, resolver  # noqa: E402
from api import contexto  # noqa: E402
from core import licenca  # noqa: E402

TOKEN = os.environ.get("CONFEITARIA_TOKEN", "")
ORIGENS_PERMITIDAS = {"http://tauri.localhost", "tauri://localhost", "http://localhost:1420"}
LIMITE_CORPO = 25 * 1024 * 1024  # logo da empresa e restauração de backup vêm em base64


class Handler(BaseHTTPRequestHandler):
    server_version = "ConfeitariaMotor/1"

    def log_message(self, fmt, *args):  # silencia o log de acesso
        pass

    def _cors(self):
        origem = self.headers.get("Origin")
        if origem in ORIGENS_PERMITIDAS:
            self.send_header("Access-Control-Allow-Origin", origem)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "X-Token, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

    def _json(self, codigo: int, corpo: dict):
        dados = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _tratar(self, metodo: str):
        if not TOKEN or self.headers.get("X-Token") != TOKEN:
            self._json(401, {"erro": "Token inválido."})
            return
        url = urlparse(self.path)
        try:
            rota, params = resolver(metodo, url.path)
            if rota is None:
                self._json(404, {"erro": "Rota desconhecida."})
                return
            corpo: dict = {}
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > LIMITE_CORPO:
                raise ErroApi("Arquivo grande demais.", 413)
            if tamanho:
                try:
                    corpo = json.loads(self.rfile.read(tamanho).decode("utf-8") or "{}")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise ErroApi("Corpo da requisição não é um JSON válido.", 400)
                if not isinstance(corpo, dict):
                    raise ErroApi("Corpo inválido.", 400)
            query = {k: v[-1] for k, v in parse_qs(url.query).items()}
            with contexto.TRAVA:
                usuario = contexto.usuario
                if not rota.publica and usuario is None:
                    raise ErroApi("Faça login para continuar.", 401, "sem_login")
                if rota.admin and (usuario or {}).get("role") != "admin":
                    raise ErroApi("Apenas administradores podem fazer isso.", 403)
                if rota.escreve and licenca.somente_leitura():
                    raise ErroApi("Licença DWM bloqueada: o sistema está em modo somente leitura até a fatura "
                                  "ser regularizada. Veja em Configurações → Licença DWM.", 423, "licenca_bloqueada")
                resposta = rota.handler(Pedido(metodo, url.path, query, corpo, params, usuario))
            self._json(200, resposta if resposta is not None else {"ok": True})
        except ErroApi as e:
            self._json(e.status, {"erro": e.mensagem, "codigo": e.codigo})
        except Exception as e:  # erro inesperado: registra e devolve mensagem curta
            traceback.print_exc()
            self._json(500, {"erro": f"Erro interno: {e}"})

    def do_GET(self):
        self._tratar("GET")

    def do_POST(self):
        self._tratar("POST")

    def do_PUT(self):
        self._tratar("PUT")

    def do_DELETE(self):
        self._tratar("DELETE")


def _vigiar_pai(pid_pai: int):
    """Encerra o serviço quando a interface fecha."""
    import psutil
    while True:
        time.sleep(2)
        if not psutil.pid_exists(pid_pai):
            with contexto.TRAVA:  # não interrompe uma gravação em andamento
                os._exit(0)


def main():
    ap = argparse.ArgumentParser(description="Motor da Confeitaria (serviço local para a interface desktop).")
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--pai", type=int, help="PID da interface; o serviço encerra quando ela fechar.")
    args = ap.parse_args()


    if not TOKEN:
        sys.exit("CONFEITARIA_TOKEN não definido — recusando iniciar sem autenticação.")

    carregar_rotas()
    contexto.db()  # abre o banco (e aplica migrações) antes da primeira requisição

    from api import tarefas
    if os.environ.get("CONFEITARIA_SEM_COZINHA") != "1":
        tarefas.iniciar_painel_cozinha()
    if os.environ.get("CONFEITARIA_SEM_TAREFAS") != "1":
        tarefas.iniciar_tarefas_periodicas()
    if args.pai:
        threading.Thread(target=_vigiar_pai, args=(args.pai,), daemon=True).start()

    servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)
    print(f"[servico_local] ouvindo em 127.0.0.1:{args.porta} (pid {os.getpid()})", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
