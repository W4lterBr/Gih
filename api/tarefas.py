# -*- coding: utf-8 -*-
"""Tarefas de fundo do motor: painel da cozinha e rotinas periódicas.

Equivalem ao que a janela principal do app PyQt fazia com QTimer:
- painel da cozinha (Flask, porta 5000) em thread própria;
- reserva de estoque de pedidos cuja data de entrega chegou: 2 s após abrir e a cada hora;
- backup automático (ver api.banco.backup_automatico).
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from datetime import datetime

from api import contexto

# Avisos para a interface mostrar como toast (ex.: "Estoque reservado para 3 pedidos").
AVISOS: deque[dict] = deque(maxlen=50)
_seq = 0


def avisar(msg: str) -> None:
    global _seq
    _seq += 1
    AVISOS.append({"i": _seq, "hora": datetime.now().strftime("%H:%M:%S"), "msg": msg})


_painel = None  # instância do WebServer do painel da cozinha


def iniciar_painel_cozinha() -> None:
    global _painel
    try:
        from core.config import get_web_panel_token
        from core.paths import RESOURCE_DIR
        from core.web_server import WebServer
    except Exception as e:  # Flask ausente: o app funciona sem o painel
        print(f"[cozinha] painel não iniciado: {e}", flush=True)
        return
    web_dir = os.path.join(RESOURCE_DIR, "web")
    if not os.path.isdir(web_dir):
        print(f"[cozinha] pasta web não encontrada: {web_dir}", flush=True)
        return
    _painel = WebServer(contexto.banco_atual() or contexto.caminho_banco(), web_dir, 5000, get_web_panel_token())
    from core import licenca
    _painel.somente_leitura = licenca.somente_leitura

    def rodar():
        try:
            _painel.run()
        except BaseException as e:  # ex.: porta 5000 ocupada (werkzeug sai com SystemExit)
            print(f"[cozinha] painel parou: {e}", flush=True)
            avisar(f"Painel da cozinha indisponível: {e}")

    threading.Thread(target=rodar, daemon=True, name="PainelCozinha").start()


def painel_trocar_banco(caminho: str) -> None:
    """O painel abre uma conexão por requisição; basta apontar para o arquivo novo."""
    if _painel is not None:
        _painel.db_path = caminho


def _reservar_estoque() -> None:
    from core.extended_database import check_and_reserve_stock
    try:
        with contexto.TRAVA:
            n = check_and_reserve_stock(contexto.db())
        if n:
            avisar(f"Estoque reservado para {n} pedido(s) com entrega hoje.")
    except Exception as e:
        print(f"[tarefas] erro ao reservar estoque: {e}", flush=True)


def _laco(intervalo_s: int, atraso_inicial_s: int, fn) -> None:
    time.sleep(atraso_inicial_s)
    while True:
        fn()
        time.sleep(intervalo_s)


_ultima_situacao_licenca: list = [None]


def _verificar_licenca() -> None:
    """Consulta a licença (4 h de cache) e avisa a interface quando a situação muda."""
    from core import licenca
    try:
        s = licenca.situacao()
    except Exception as e:
        print(f"[licença] erro ao verificar: {type(e).__name__}", flush=True)
        return
    atual = s.get("situacao")
    anterior = _ultima_situacao_licenca[0]
    _ultima_situacao_licenca[0] = atual
    if anterior is None or atual == anterior:
        return
    if atual == "bloqueado":
        avisar("Licença DWM bloqueada: o sistema ficou em modo somente leitura. Veja em Configurações → Licença DWM.")
    elif atual == "tolerancia":
        avisar(s.get("mensagem") or "Há uma fatura DWM vencida. Regularize para evitar o bloqueio.")
    elif atual == "liberado" and anterior in ("bloqueado", "tolerancia"):
        avisar("Licença DWM regularizada. Obrigado!")


def iniciar_tarefas_periodicas() -> None:
    threading.Thread(target=_laco, args=(3600, 2, _reservar_estoque), daemon=True, name="ReservaEstoque").start()
    # Licença: logo após abrir e depois a cada 30 min (a consulta à DWM só sai a cada 4 h).
    threading.Thread(target=_laco, args=(1800, 5, _verificar_licenca), daemon=True, name="Licenca").start()
    try:
        from api import banco
        banco.iniciar_backup_automatico()
    except ImportError:
        pass
