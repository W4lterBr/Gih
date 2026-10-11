# -*- coding: utf-8 -*-
"""Testes da licença DWM (core/licenca.py) contra um servidor de licenças falso.

    py tests/test_licenca.py

Não acessa a DWM nem a pasta de dados real: usa CONFEITARIA_DATA_DIR temporária e
CONFEITARIA_LICENCA_URL apontando para um servidor local que imita
/api/licenca-cliente/status.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
_TMP = tempfile.mkdtemp(prefix="licenca_teste_")
os.environ["CONFEITARIA_DATA_DIR"] = _TMP

TOKEN_BOM = "A3B7-C9D2-E4F6-G8H3"


class Servidor:
    """Comportamento configurável: modo = liberado|tolerancia|bloqueado|inativo|401|429|500."""
    modo = "liberado"
    pedidos: list = []
    data_header: datetime | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def date_time_string(self, timestamp=None):
        # Hora "do servidor" controlável pelo teste (cabeçalho Date da resposta).
        if Servidor.data_header:
            return format_datetime(Servidor.data_header, usegmt=True)
        return super().date_time_string(timestamp)

    def do_GET(self):
        Servidor.pedidos.append({"path": self.path, "token": self.headers.get("X-License-Token")})
        token = self.headers.get("X-License-Token")
        m = Servidor.modo
        if m in ("401",) or token != TOKEN_BOM:
            return self._json(401, {"success": False, "error": "TOKEN_INVALIDO"})
        if m == "429":
            return self._json(429, {"success": False, "error": "MUITAS_TENTATIVAS"})
        if m == "500":
            return self._json(500, {"success": False, "error": "ERRO_INTERNO"})
        if m == "lixo":
            return self._json(200, {"acesso": {"status": "talvez"}})
        acesso = {
            "liberado": {"status": "liberado", "dias_atraso": 0, "dias_restantes_tolerancia": None, "mensagem": "Fatura em dia.", "fatura_vencida": None},
            "tolerancia": {"status": "tolerancia", "dias_atraso": 3, "dias_restantes_tolerancia": 4, "mensagem": "Regularize em 4 dias.",
                           "fatura_vencida": {"numero": "DWM-1", "valor": 89.9, "vencimento": "2026-10-08"}},
            "bloqueado": {"status": "bloqueado", "dias_atraso": 9, "dias_restantes_tolerancia": 0, "mensagem": "Bloqueado por atraso.",
                          "fatura_vencida": {"numero": "DWM-1", "valor": 89.9, "vencimento": "2026-10-02"}},
            "inativo": {"status": "bloqueado", "dias_atraso": None, "dias_restantes_tolerancia": None, "mensagem": "Cliente inativo.", "fatura_vencida": None},
        }[m]
        self._json(200, {"success": True, "cliente": {"nome": "Confeitaria Teste", "cnpj": "12345678000199"}, "acesso": acesso,
                         "faturas_pagas_recentes": [{"numero": "DWM-0", "valor": 89.9, "vencimento": "2026-09-10", "pago_em": "2026-09-09"}],
                         "proxima_fatura": {"numero": "DWM-2", "valor": 89.9, "vencimento": "2026-11-10", "status": "pending"},
                         "<script>": "ignorado"})

    def _json(self, codigo, corpo):
        dados = json.dumps(corpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["CONFEITARIA_LICENCA_URL"] = f"http://127.0.0.1:{srv.server_address[1]}/api/licenca-cliente/status"

from core import licenca  # noqa: E402

_agora_real = licenca._agora


class TesteLicenca(unittest.TestCase):
    def setUp(self):
        licenca._ultima_tentativa = 0.0
        licenca._bloqueado_ate_429 = 0.0
        licenca._agora = _agora_real
        Servidor.modo = "liberado"
        Servidor.pedidos = []
        Servidor.data_header = None
        try:
            licenca._arquivo().unlink()
        except FileNotFoundError:
            pass
        licenca._definir_marca(False)

    def _viajar(self, dias=0, horas=0):
        alvo = _agora_real() + timedelta(days=dias, hours=horas)
        licenca._agora = lambda: alvo
        licenca._ultima_tentativa = 0.0

    def test_sem_token_funciona(self):
        s = licenca.situacao()
        self.assertEqual(s["situacao"], "sem_token")
        self.assertFalse(s["somente_leitura"])
        self.assertFalse(licenca.somente_leitura())
        self.assertEqual(Servidor.pedidos, [], "sem token não consulta o servidor")

    def test_ativar_token_invalido_nao_grava(self):
        with self.assertRaises(licenca.ErroLicenca):
            licenca.ativar("ZZZZ-ZZZZ-ZZZZ-ZZZZ")
        self.assertFalse(licenca._arquivo().exists())
        self.assertEqual(licenca.situacao()["situacao"], "sem_token")

    def test_ativar_formato_invalido_nem_consulta(self):
        for ruim in ["", "abc", "A3B7 C9D2", "../../etc", "A" * 200, "A3B7-C9D2\nX-Admin: 1"]:
            with self.assertRaises(licenca.ErroLicenca):
                licenca.ativar(ruim)
        self.assertEqual(Servidor.pedidos, [])

    def test_ativar_e_liberado(self):
        s = licenca.ativar(TOKEN_BOM.lower())  # normaliza para maiúsculas
        self.assertEqual(s["situacao"], "liberado")
        self.assertFalse(s["somente_leitura"])
        self.assertEqual(s["dados"]["proxima_fatura"]["numero"], "DWM-2")
        self.assertNotIn("<script>", json.dumps(s))
        self.assertEqual(s["token_final"], "…G8H3")
        self.assertNotIn(TOKEN_BOM, json.dumps(s), "token completo nunca volta para a interface")

    def test_token_so_no_cabecalho_e_cifrado_no_disco(self):
        licenca.ativar(TOKEN_BOM)
        self.assertTrue(all(TOKEN_BOM not in p["path"] for p in Servidor.pedidos), "token nunca na URL")
        self.assertEqual(Servidor.pedidos[-1]["token"], TOKEN_BOM)
        bruto = licenca._arquivo().read_bytes()
        self.assertNotIn(TOKEN_BOM.encode(), bruto)
        self.assertNotIn(b"liberado", bruto)

    def test_tolerancia_nao_restringe(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "tolerancia"
        s = licenca.situacao(forcar=True)
        self.assertEqual(s["situacao"], "tolerancia")
        self.assertFalse(s["somente_leitura"])
        self.assertEqual(s["dados"]["dias_restantes_tolerancia"], 4)

    def test_bloqueado_vira_somente_leitura(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "bloqueado"
        s = licenca.situacao(forcar=True)
        self.assertEqual((s["situacao"], s["motivo"]), ("bloqueado", "fatura"))
        self.assertTrue(licenca.somente_leitura())
        Servidor.modo = "inativo"
        licenca._ultima_tentativa = 0.0
        self.assertEqual(licenca.situacao(forcar=True)["motivo"], "inativo")
        Servidor.modo = "liberado"
        licenca._ultima_tentativa = 0.0
        self.assertFalse(licenca.situacao(forcar=True)["somente_leitura"], "pagou: libera na hora")

    def test_queda_de_rede_usa_ultimo_status(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "500"
        s = licenca.situacao(forcar=True)
        self.assertEqual(s["situacao"], "sem_conexao")
        self.assertFalse(s["somente_leitura"])
        srv_url = os.environ["CONFEITARIA_LICENCA_URL"]
        os.environ["CONFEITARIA_LICENCA_URL"] = "http://127.0.0.1:1/x"  # porta fechada
        try:
            licenca._ultima_tentativa = 0.0
            s = licenca.situacao(forcar=True)
            self.assertEqual(s["situacao"], "sem_conexao")
            self.assertFalse(s["somente_leitura"])
        finally:
            os.environ["CONFEITARIA_LICENCA_URL"] = srv_url

    def test_bloqueado_continua_bloqueado_offline(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "bloqueado"
        licenca.situacao(forcar=True)
        Servidor.modo = "500"
        licenca._ultima_tentativa = 0.0
        self.assertTrue(licenca.situacao(forcar=True)["somente_leitura"], "desligar a internet não desbloqueia")

    def test_sete_dias_sem_confirmar(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "500"
        self._viajar(dias=6)
        self.assertFalse(licenca.situacao(forcar=True)["somente_leitura"])
        self._viajar(dias=8)
        s = licenca.situacao(forcar=True)
        self.assertEqual((s["situacao"], s["motivo"]), ("bloqueado", "sem_confirmacao"))
        Servidor.modo = "liberado"
        licenca._ultima_tentativa = 0.0
        licenca._agora = _agora_real
        self.assertFalse(licenca.situacao(forcar=True)["somente_leitura"], "voltou a internet: libera")

    def test_relogio_atrasado(self):
        licenca.ativar(TOKEN_BOM)
        self._viajar(dias=2)
        licenca.somente_leitura()             # registra o "maior horário visto" (dia +2)
        Servidor.modo = "500"                 # offline: é aqui que a proteção importa
        self._viajar(dias=-1)                 # alguém atrasou o relógio
        s = licenca.situacao()
        self.assertTrue(s["somente_leitura"])
        self.assertIn("relógio", s["mensagem"])
        Servidor.modo = "liberado"            # confirmação no servidor corrige
        licenca._agora = _agora_real
        licenca._ultima_tentativa = 0.0
        self.assertFalse(licenca.situacao(forcar=True)["somente_leitura"])

    def test_hora_do_servidor_vale_mais_que_relogio_adiantado(self):
        Servidor.data_header = _agora_real() - timedelta(days=10)  # relógio local 10 dias adiantado
        licenca.ativar(TOKEN_BOM)
        estado = licenca._ler_estado()
        confirmado = licenca._de_iso(estado["cache"]["confirmado_em"])
        self.assertLess(confirmado, _agora_real() - timedelta(days=9), "usa a hora do servidor")

    def test_429_para_de_tentar(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "429"
        licenca.situacao(forcar=True)
        n = len(Servidor.pedidos)
        for _ in range(5):
            licenca._ultima_tentativa = 0.0
            licenca.situacao(forcar=True)
        self.assertEqual(len(Servidor.pedidos), n, "depois de 429 não consulta por 15 min")

    def test_forcar_tem_intervalo_minimo(self):
        licenca.ativar(TOKEN_BOM)
        n = len(Servidor.pedidos)
        licenca.situacao(forcar=True)
        licenca.situacao(forcar=True)
        licenca.situacao(forcar=True)
        self.assertEqual(len(Servidor.pedidos), n + 1)

    def test_cache_de_4_horas(self):
        licenca.ativar(TOKEN_BOM)
        n = len(Servidor.pedidos)
        self.assertEqual(licenca.situacao()["origem"], "cache")
        self.assertEqual(len(Servidor.pedidos), n)
        self._viajar(horas=5)
        licenca.situacao()
        self.assertEqual(len(Servidor.pedidos), n + 1)

    def test_401_isolado_nao_bloqueia_e_repetido_24h_bloqueia(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "401"
        self.assertFalse(licenca.situacao(forcar=True)["somente_leitura"], "um 401 isolado não trava")
        self._viajar(horas=25)
        s = licenca.situacao(forcar=True)
        self.assertEqual((s["situacao"], s["motivo"]), ("bloqueado", "token_invalido"))

    def test_resposta_estranha_nao_bloqueia(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "lixo"
        s = licenca.situacao(forcar=True)
        self.assertFalse(s["somente_leitura"])
        self.assertEqual(s["situacao"], "sem_conexao")

    def test_arquivo_adulterado_ou_apagado(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "bloqueado"
        licenca.situacao(forcar=True)
        licenca._arquivo().write_bytes(b"x" * 64)          # adulterado
        self.assertTrue(licenca.somente_leitura(), "arquivo adulterado não libera")
        licenca._arquivo().unlink()                         # apagado
        s = licenca.situacao()
        self.assertEqual((s["situacao"], s["motivo"]), ("bloqueado", "token_ausente"))

    def test_remover_so_com_licenca_em_dia(self):
        licenca.ativar(TOKEN_BOM)
        Servidor.modo = "bloqueado"
        licenca.situacao(forcar=True)
        with self.assertRaises(licenca.ErroLicenca):
            licenca.remover()
        self.assertTrue(licenca.somente_leitura())
        Servidor.modo = "liberado"
        licenca._ultima_tentativa = 0.0
        licenca.situacao(forcar=True)
        licenca.remover()
        self.assertEqual(licenca.situacao()["situacao"], "sem_token")

    def test_https_obrigatorio(self):
        with self.assertRaises(licenca.ErroLicenca):
            licenca._validar_url("http://dwmsystems.com.br/api")
        licenca._validar_url("https://www.dwmsystems.com.br/api")


if __name__ == "__main__":
    unittest.main(verbosity=2)
