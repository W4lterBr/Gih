# -*- coding: utf-8 -*-
"""Formatação de valores, datas e tamanhos para exibição."""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def money(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_size(size_str: Optional[str]) -> str:
    """Formata tamanho(s) adicionando 'cm' após cada valor numérico.

    Exemplos:
        "30" -> "30 cm"
        "15, 20, 25" -> "15 cm, 20 cm, 25 cm"
        "Grande (3kg)" -> "Grande (3kg)"
        "" -> ""
        None -> ""
    """
    if not size_str:
        return ""

    # Separa por vírgula, adiciona 'cm' apenas a valores numéricos e junta novamente
    sizes = [s.strip() for s in size_str.split(",") if s.strip()]
    formatted = [f"{s} cm" if s.replace(".", "", 1).isdigit() else s for s in sizes]
    return ", ".join(formatted)


def format_date(date_str: str) -> str:
    """Converte data do formato YYYY-MM-DD para DD/MM/YYYY"""
    if not date_str:
        return ""
    try:
        # Se já estiver no formato DD/MM/YYYY, retorna como está
        if "/" in date_str:
            return date_str
        # Converte de YYYY-MM-DD para DD/MM/YYYY
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except Exception:
        return date_str


def format_datetime(dt_str: str) -> str:
    """Converte data/hora de ISO (YYYY-MM-DD HH:MM[:SS]) para DD/MM/YYYY HH:MM.

    Mantém como está se já parecer no formato brasileiro.
    """
    if not dt_str:
        return ""
    s = str(dt_str)
    try:
        # Já no padrão brasileiro?
        if "/" in s and (" " in s or len(s) == 10):
            return s
        # Tenta com segundos
        try:
            d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Tenta sem segundos
            try:
                d = datetime.strptime(s, "%Y-%m-%d %H:%M")
            except ValueError:
                # Tenta somente data
                d = datetime.strptime(s, "%Y-%m-%d")
        return d.strftime("%d/%m/%Y %H:%M") if " " in s else d.strftime("%d/%m/%Y")
    except Exception:
        return s


def format_price_br(value: float) -> str:
    """Formata valor monetário no padrão brasileiro.
    
    Exemplos:
        1234.56 -> "R$ 1.234,56"
        1000000.00 -> "R$ 1.000.000,00"
        0.5 -> "R$ 0,50"
    """
    try:
        # Converte para string formatada com 2 casas decimais
        formatted = f"{value:,.2f}"
        # Substitui vírgula por ponto temporário e ponto por vírgula
        formatted = formatted.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return "R$ 0,00"
