# -*- coding: utf-8 -*-
"""Regras de senha: o que é fraco demais e o que vale como senha nova."""

from __future__ import annotations

from typing import Optional

TAMANHO_MINIMO = 6

# Senhas que qualquer pessoa tenta primeiro. "admin" é a senha que o sistema cria
# para o usuário admin num banco novo (core/database.py).
_COMUNS = {
    "admin", "senha", "1234", "12345", "123456", "1234567", "12345678", "123456789",
    "000000", "111111", "123123", "abc123", "qwerty", "confeitaria", "password",
}


def senha_fraca(usuario: str, senha: str) -> bool:
    """Senha que obriga a troca no próximo login (padrão, comum ou igual ao usuário)."""
    s = (senha or "").strip().lower()
    return len(s) < 4 or s in _COMUNS or s == (usuario or "").strip().lower()


def problema_senha_nova(usuario: str, nova: str, atual: Optional[str] = None) -> Optional[str]:
    """Mensagem do que está errado com a senha nova, ou None se ela serve."""
    if len(nova or "") < TAMANHO_MINIMO:
        return f"A senha deve ter pelo menos {TAMANHO_MINIMO} caracteres."
    if nova != nova.strip():
        return "A senha não pode começar nem terminar com espaço."
    if senha_fraca(usuario, nova):
        return "Senha fácil demais (padrão, comum ou igual ao usuário). Escolha outra."
    if atual is not None and nova == atual:
        return "A senha nova precisa ser diferente da atual."
    return None
