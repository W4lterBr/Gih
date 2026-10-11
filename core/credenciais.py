# -*- coding: utf-8 -*-
"""Credenciais lembradas no login ("Lembrar credenciais").

Arquivo ~/.confeitaria/credentials.json: usuário em base64 e senha protegida pelo
DPAPI do Windows (só a mesma conta do Windows consegue ler). Usado pela tela de
login do app PyQt e pelo motor da interface nova (servico_local.py).
"""

import base64
import ctypes
import json
from pathlib import Path


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_protect(data: bytes) -> bytes:
    """Criptografa dados usando o DPAPI do Windows, vinculado à conta do usuário logado.

    Sem isso, a senha "lembrada" ficava só em base64 em credentials.json - qualquer
    pessoa/ferramenta que leia esse arquivo (backup, outro usuário local, etc.)
    recuperava a senha em texto puro trivialmente. Com DPAPI, só o mesmo usuário do
    Windows que gravou consegue descriptografar (a chave nunca fica no arquivo).
    """
    buf_in = ctypes.create_string_buffer(data, len(data))
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    buf_in = ctypes.create_string_buffer(data, len(data))
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _get_credentials_file() -> Path:
    """Retorna o caminho para o arquivo de credenciais salvas"""
    home = Path.home()
    config_dir = home / ".confeitaria"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "credentials.json"


def load_saved_credentials():
    """Carrega usuário/senha salvos (senha protegida via DPAPI), se existirem.

    Função de módulo (não depende de uma instância de LoginDialog/QDialog) para
    que o app possa tentar login automático antes de sequer criar a janela de
    login. Retorna (usuario, senha) ou None se não houver credenciais salvas
    ou válidas.
    """
    try:
        creds_file = _get_credentials_file()
        if not creds_file.exists():
            return None
        with open(creds_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        username = base64.b64decode(data.get('u', '')).decode('utf-8')
        password_blob = base64.b64decode(data.get('p', ''))
        password = _dpapi_unprotect(password_blob).decode('utf-8')
        return username, password
    except Exception:
        # Inclui o caso de um credentials.json de uma versão antiga (só base64,
        # sem DPAPI) - simplesmente não carrega.
        return None


def clear_saved_credentials() -> None:
    """Remove as credenciais salvas (permite trocar de usuário)."""
    try:
        creds_file = _get_credentials_file()
        if creds_file.exists():
            creds_file.unlink()
    except Exception:
        pass


def save_credentials(username: str, password: str) -> None:
    """Grava usuário/senha (senha via DPAPI)."""
    data = {
        'u': base64.b64encode(username.encode('utf-8')).decode('utf-8'),
        # DPAPI: só a mesma conta do Windows que salvou consegue descriptografar
        'p': base64.b64encode(_dpapi_protect(password.encode('utf-8'))).decode('utf-8'),
    }
    with open(_get_credentials_file(), 'w', encoding='utf-8') as f:
        json.dump(data, f)
