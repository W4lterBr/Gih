# -*- coding: utf-8 -*-
"""Licença DWM da confeitaria (situação das faturas do cliente no servidor da DWM).

Por que este modelo (e não a API de Assinaturas com credencial HMAC):
a "Documentação de Faturas" da DWM proíbe colocar a credencial de produto num app
instalado no cliente — o segredo seria extraível e daria acesso às assinaturas de
todos os clientes do produto. Para apps desktop a DWM usa o endpoint de licença do
cliente (API_LICENCA_CLIENTE.md, o mesmo do Busca NF-e): a única credencial é o token
de licença DAQUELE cliente, que só enxerga a situação e as faturas dele.

    GET https://www.dwmsystems.com.br/api/licenca-cliente/status
    X-License-Token: <token>
    200 {"acesso": {"status": "liberado"|"tolerancia"|"bloqueado", ...}, "proxima_fatura": ...}
    401 TOKEN_INVALIDO · 429 MUITAS_TENTATIVAS · 500 ERRO_INTERNO

Regras (as da documentação do endpoint):
- Só um 200 com acesso.status == "bloqueado" restringe o uso (aqui: somente leitura).
- Rede, timeout, 5xx e 429 são indisponibilidade: vale o último status confirmado,
  por até DIAS_SEM_CONFIRMACAO dias (depois disso, exige uma consulta com sucesso —
  evita burlar o bloqueio desligando a internet de propósito).
- 401 só é tratado como token inválido quando se repete por TOKEN_RECUSADO_HORAS
  (um servidor com defeito respondendo 401 não pode travar todos os clientes).
- Sem token ativado: o sistema funciona normalmente e pede a ativação (decisão do
  responsável em 11/10/2026: nenhum cliente atual é travado pela atualização).

Segurança local:
- Token e cache gravados com DPAPI (só a mesma conta do Windows lê; adulteração do
  arquivo invalida o cache em vez de liberar).
- O token nunca vai para log (só os 4 últimos caracteres) nem para a URL.
- HTTPS com certificado verificado; URL alternativa (testes) só fora do executável.
- Relógio atrasado de propósito não estende a validade do cache.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

URL_PADRAO = "https://www.dwmsystems.com.br/api/licenca-cliente/status"
PORTAL_CLIENTE_URL = "https://dwmsystems.up.railway.app/portal/login"
WHATSAPP_SUPORTE = "5531981052030"

CACHE_SEGUNDOS = 4 * 3600          # consulta automática: a cada 4 h (doc: 4–12 h)
INTERVALO_MIN_FORCADO = 30         # "Já paguei" repetido não martela o servidor
ESPERA_APOS_429 = 15 * 60          # 429: para de tentar por 15 min
DIAS_SEM_CONFIRMACAO = 7
TOKEN_RECUSADO_HORAS = 24
RELOGIO_VOLTOU_TOLERANCIA = timedelta(hours=2)
TIMEOUT = 10.0

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{6,62}[A-Za-z0-9]$")
_trava = threading.Lock()
_ultima_tentativa = 0.0
_bloqueado_ate_429 = 0.0


class ErroLicenca(Exception):
    """Erro para mostrar ao usuário (ex.: token recusado na ativação)."""


# ---------------------------------------------------------------- armazenamento

def _pasta() -> Path:
    from core.config import get_app_data_directory
    p = Path(get_app_data_directory())
    p.mkdir(parents=True, exist_ok=True)
    return p


def _arquivo() -> Path:
    return _pasta() / "licenca.dat"


def _proteger(dados: bytes) -> bytes:
    from core.credenciais import _dpapi_protect
    return _dpapi_protect(dados)


def _desproteger(dados: bytes) -> bytes:
    from core.credenciais import _dpapi_unprotect
    return _dpapi_unprotect(dados)


def _ler_estado() -> dict:
    """Estado gravado: {"token", "cache": {...}, "recusado_desde", "max_visto"}.
    Arquivo ausente, de outra conta do Windows ou adulterado → estado vazio."""
    try:
        return json.loads(_desproteger(_arquivo().read_bytes()).decode("utf-8"))
    except Exception:
        return {}


def _gravar_estado(estado: dict) -> None:
    dados = _proteger(json.dumps(estado, ensure_ascii=False).encode("utf-8"))
    tmp = _arquivo().with_suffix(".tmp")
    tmp.write_bytes(dados)
    os.replace(tmp, _arquivo())


def _marca_ativada() -> bool:
    """Este computador já teve licença ativada? (marca em config.yaml, separada do
    arquivo do token: apagar licenca.dat não volta ao estado "sem token".)"""
    try:
        from core.config import load_config
        return bool(load_config().get("licenca_ativada"))
    except Exception:
        return False


def _definir_marca(valor: bool) -> None:
    from core.config import load_config, save_config
    cfg = load_config()
    if valor:
        cfg["licenca_ativada"] = True
    else:
        cfg.pop("licenca_ativada", None)
    save_config(cfg)


def mascarar(token: Optional[str]) -> str:
    t = (token or "").strip()
    return f"…{t[-4:]}" if len(t) >= 4 else "…"


def _url() -> str:
    """URL alternativa só em desenvolvimento/testes (nunca no executável instalado)."""
    if not getattr(sys, "frozen", False):
        alt = os.environ.get("CONFEITARIA_LICENCA_URL", "").strip()
        if alt:
            return alt
    return URL_PADRAO


def _validar_url(url: str) -> None:
    # HTTPS obrigatório; HTTP só para servidor de teste na própria máquina.
    if url.startswith("https://"):
        return
    if url.startswith(("http://127.0.0.1", "http://localhost")) and not getattr(sys, "frozen", False):
        return
    raise ErroLicenca("Endereço do servidor de licenças inválido (exige HTTPS).")


# ---------------------------------------------------------------- consulta ao servidor

class _RespostaHttp(Exception):
    def __init__(self, status: int, codigo: str = ""):
        super().__init__(f"HTTP {status} {codigo}")
        self.status = status
        self.codigo = codigo


def _consultar(token: str) -> tuple[dict, Optional[datetime]]:
    url = _url()
    _validar_url(url)
    req = urllib.request.Request(url, headers={
        "X-License-Token": token,
        "Accept": "application/json",
        "User-Agent": "ConfeitariaLicenseClient/2.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            corpo = resp.read(256 * 1024)  # resposta real tem poucos KB
            data = None
            try:
                data = parsedate_to_datetime(resp.headers.get("Date")) if resp.headers.get("Date") else None
            except (TypeError, ValueError):
                data = None
            js = json.loads(corpo.decode("utf-8"))
            if not isinstance(js, dict):
                raise ValueError("resposta não é um objeto")
            return js, data
    except urllib.error.HTTPError as e:
        codigo = ""
        try:
            codigo = str(json.loads(e.read(4096).decode("utf-8")).get("error") or "")
        except Exception:
            pass
        raise _RespostaHttp(e.code, codigo) from None


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat()


def _de_iso(s: Any) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(s))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _normalizar(js: dict) -> dict:
    """Só os campos que a interface usa, com tipos conferidos (o servidor é confiável,
    mas a resposta passa pela rede e vai para a tela)."""
    acesso = js.get("acesso") if isinstance(js.get("acesso"), dict) else {}
    status = acesso.get("status")
    if status not in ("liberado", "tolerancia", "bloqueado"):
        raise ValueError(f"status de acesso desconhecido: {status!r}")

    def fatura(f: Any) -> Optional[dict]:
        if not isinstance(f, dict):
            return None
        try:
            valor = float(f.get("valor") or 0)
        except (TypeError, ValueError):
            valor = 0.0
        return {
            "numero": str(f.get("numero") or "")[:40],
            "valor": round(valor, 2),
            "vencimento": str(f.get("vencimento") or "")[:10],
            "status": str(f.get("status") or "")[:20] or None,
            "pago_em": str(f.get("pago_em") or "")[:10] or None,
        }

    def inteiro(v: Any) -> Optional[int]:
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    cliente = js.get("cliente") if isinstance(js.get("cliente"), dict) else {}
    pagas = js.get("faturas_pagas_recentes") if isinstance(js.get("faturas_pagas_recentes"), list) else []
    return {
        "status": status,
        "dias_atraso": inteiro(acesso.get("dias_atraso")),
        "dias_restantes_tolerancia": inteiro(acesso.get("dias_restantes_tolerancia")),
        "mensagem": str(acesso.get("mensagem") or "")[:300],
        "fatura_vencida": fatura(acesso.get("fatura_vencida")),
        "proxima_fatura": fatura(js.get("proxima_fatura")),
        "faturas_pagas": [x for x in (fatura(f) for f in pagas[:3]) if x],
        "cliente": {"nome": str(cliente.get("nome") or "")[:150], "documento": str(cliente.get("cnpj") or "")[:20]},
    }


# ---------------------------------------------------------------- situação

def _situacao(estado: dict, origem: str, erro: Optional[str] = None) -> dict:
    """Monta o que a interface e o motor usam a partir do estado gravado.

    situacao: sem_token | liberado | tolerancia | bloqueado | sem_conexao
    somente_leitura: True só quando a licença deve restringir o uso.
    """
    token = estado.get("token")
    base = {"portal": PORTAL_CLIENTE_URL, "whatsapp": WHATSAPP_SUPORTE, "token_final": mascarar(token) if token else None,
            "origem": origem, "erro": erro}
    if not token:
        if _marca_ativada():
            return {**base, "situacao": "bloqueado", "somente_leitura": True, "motivo": "token_ausente",
                    "mensagem": "A licença deste computador não foi encontrada. Ative o token de licença novamente.",
                    "dados": None, "confirmado_em": None}
        return {**base, "situacao": "sem_token", "somente_leitura": False, "motivo": None,
                "mensagem": "Licença DWM não ativada neste computador."}

    cache = estado.get("cache") or {}
    confirmado = _de_iso(cache.get("confirmado_em"))
    dados = cache.get("dados")
    agora = _agora()
    max_visto = _de_iso(estado.get("max_visto"))

    if estado.get("token_invalido"):
        return {**base, "situacao": "bloqueado", "somente_leitura": True, "motivo": "token_invalido",
                "mensagem": "O token de licença foi recusado pela DWM. Fale com o suporte para receber um token válido.",
                "dados": None, "confirmado_em": None}

    relogio_voltou = bool(max_visto and max_visto - agora > RELOGIO_VOLTOU_TOLERANCIA)
    vencido = (confirmado is None or relogio_voltou
               or agora - confirmado > timedelta(days=DIAS_SEM_CONFIRMACAO))
    if not dados or vencido:
        return {**base, "situacao": "bloqueado", "somente_leitura": True, "motivo": "sem_confirmacao",
                "mensagem": ("O relógio do computador foi atrasado desde a última confirmação da licença."
                             if relogio_voltou else
                             f"Não foi possível confirmar a licença com a DWM nos últimos {DIAS_SEM_CONFIRMACAO} dias. "
                             "Verifique a internet e clique em \"Verificar agora\"."),
                "dados": dados, "confirmado_em": cache.get("confirmado_em")}

    status = dados["status"]
    # "sem_conexao": a consulta acabou de falhar, mas vale o último status confirmado.
    situacao = "sem_conexao" if erro and status != "bloqueado" else status
    return {**base, "situacao": situacao, "somente_leitura": status == "bloqueado",
            "motivo": ("fatura" if dados.get("dias_atraso") is not None else "inativo") if status == "bloqueado" else None,
            "status_confirmado": status,
            "mensagem": dados.get("mensagem") or "",
            "dados": dados, "confirmado_em": cache.get("confirmado_em")}


def situacao(forcar: bool = False) -> dict:
    """Situação atual. Consulta o servidor se o cache venceu (ou `forcar`), respeitando
    os intervalos mínimos; senão usa o último status confirmado."""
    global _ultima_tentativa, _bloqueado_ate_429
    with _trava:
        estado = _ler_estado()
        token = estado.get("token")
        if not token:
            return _situacao(estado, "local")

        agora_s = time.time()
        confirmado = _de_iso((estado.get("cache") or {}).get("confirmado_em"))
        idade = (_agora() - confirmado).total_seconds() if confirmado else None
        precisa = forcar or idade is None or idade > CACHE_SEGUNDOS or idade < -60
        if not precisa or agora_s < _bloqueado_ate_429 or agora_s - _ultima_tentativa < INTERVALO_MIN_FORCADO:
            return _situacao(estado, "cache")

        _ultima_tentativa = agora_s
        try:
            js, data_servidor = _consultar(token)
            dados = _normalizar(js)
        except _RespostaHttp as e:
            if e.status == 429:
                _bloqueado_ate_429 = agora_s + ESPERA_APOS_429
                return _situacao(estado, "cache", "Muitas consultas ao servidor de licenças; tentando de novo mais tarde.")
            if e.status == 401:
                agora = _agora()
                desde = _de_iso(estado.get("recusado_desde")) or agora
                estado["recusado_desde"] = _iso(desde)
                if agora - desde >= timedelta(hours=TOKEN_RECUSADO_HORAS):
                    estado["token_invalido"] = True
                _gravar_estado(estado)
                _log(f"licença: servidor recusou o token {mascarar(token)} (401)")
                return _situacao(estado, "cache", "O servidor de licenças recusou o token.")
            _log(f"licença: servidor indisponível (HTTP {e.status})")
            return _situacao(estado, "cache", "Servidor de licenças indisponível no momento.")
        except Exception as e:  # rede, DNS, timeout, resposta inválida
            _log(f"licença: sem conexão com o servidor ({type(e).__name__})")
            return _situacao(estado, "cache", "Sem conexão com o servidor de licenças.")

        # Sucesso: grava o status confirmado. A hora da confirmação é a do servidor
        # (cabeçalho Date) quando disponível — relógio local adiantado não estende nada.
        agora_local = _agora()
        confirmado_em = data_servidor.astimezone(timezone.utc) if data_servidor else agora_local
        if abs((confirmado_em - agora_local).total_seconds()) > 300:
            confirmado_em = min(confirmado_em, agora_local)
        # Confirmação no servidor recomeça a marca do "maior horário visto": um relógio que
        # esteve adiantado por engano e foi corrigido não fica acusando "relógio atrasado".
        max_visto = max(agora_local, confirmado_em)
        estado.update({"cache": {"dados": dados, "confirmado_em": _iso(confirmado_em)},
                       "max_visto": _iso(max_visto), "recusado_desde": None, "token_invalido": False})
        _gravar_estado(estado)
        return _situacao(estado, "servidor")


def somente_leitura() -> bool:
    """O motor consulta isto antes de cada gravação (rápido: não vai à rede)."""
    try:
        with _trava:
            estado = _ler_estado()
            # Atualiza o "maior horário visto" (proteção contra relógio atrasado).
            if estado.get("token"):
                agora = _agora()
                mv = _de_iso(estado.get("max_visto"))
                if mv is None or agora - mv > timedelta(minutes=10):
                    estado["max_visto"] = _iso(agora)
                    try:
                        _gravar_estado(estado)
                    except OSError:
                        pass
            return bool(_situacao(estado, "local")["somente_leitura"])
    except Exception:
        return False


def ativar(token: str) -> dict:
    """Confere o token no servidor ANTES de gravar (token digitado errado não fica salvo)."""
    t = (token or "").strip().upper()
    if not _TOKEN_RE.match(t):
        raise ErroLicenca("Token em formato inválido. Confira o token enviado pela DWM (ex.: A3B7-C9D2-E4F6-G8H3).")
    with _trava:
        try:
            js, data_servidor = _consultar(t)
            dados = _normalizar(js)
        except _RespostaHttp as e:
            if e.status == 401:
                raise ErroLicenca("Token não reconhecido pela DWM. Confira o token ou fale com o suporte.")
            if e.status == 429:
                raise ErroLicenca("Muitas tentativas com token inválido. Aguarde 15 minutos e tente de novo.")
            raise ErroLicenca(f"Servidor de licenças indisponível (HTTP {e.status}). Tente de novo em instantes.")
        except ErroLicenca:
            raise
        except Exception:
            raise ErroLicenca("Sem conexão com o servidor de licenças da DWM. Verifique a internet.")
        agora = _agora()
        confirmado_em = data_servidor.astimezone(timezone.utc) if data_servidor else agora
        if abs((confirmado_em - agora).total_seconds()) > 300:
            confirmado_em = min(confirmado_em, agora)
        _gravar_estado({"token": t, "cache": {"dados": dados, "confirmado_em": _iso(confirmado_em)},
                        "max_visto": _iso(max(agora, confirmado_em)), "recusado_desde": None, "token_invalido": False})
        _definir_marca(True)
        _log(f"licença: token {mascarar(t)} ativado ({dados['status']})")
        return _situacao(_ler_estado(), "servidor")


def remover() -> None:
    """Tira o token deste computador. Só com a licença em dia: com ela bloqueada,
    remover devolveria o sistema ao modo "sem token" (sem restrição)."""
    with _trava:
        if _situacao(_ler_estado(), "local")["somente_leitura"]:
            raise ErroLicenca("Com a licença bloqueada não é possível remover o token. "
                              "Regularize a fatura ou ative outro token válido.")
        try:
            _arquivo().unlink()
        except FileNotFoundError:
            pass
        _definir_marca(False)
    _log("licença: token removido deste computador")


def _log(msg: str) -> None:
    try:
        from core.logger import log_event
        log_event(msg)
    except Exception:
        print(msg, flush=True)
