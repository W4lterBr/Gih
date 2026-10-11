# -*- coding: utf-8 -*-
"""Categorias de movimentação de estoque e suas cores."""

from __future__ import annotations


# Categorias de movimentação de estoque - a coluna 'type' do banco continua só
# 'entrada'/'saida' (CHECK constraint existente), 'category' é o subtipo que
# permite reportar/filtrar por Perda, Produção, Venda etc.
MOVEMENT_CATEGORIES: dict[str, list[str]] = {
    "Entrada": ["Compra/Reposição", "Produção", "Devolução de Cliente", "Ajuste de Inventário", "Outro"],
    "Saída": ["Venda Avulsa", "Perda/Quebra", "Vencimento", "Ajuste de Inventário", "Outro"],
}


# Cor de destaque por categoria (usada na tabela de movimentações)
MOVEMENT_CATEGORY_COLORS: dict[str, str] = {
    "Perda/Quebra": "#EF4444",
    "Vencimento": "#F97316",
    "Produção": "#8B5CF6",
    "Compra/Reposição": "#10B981",
    "Devolução de Cliente": "#0EA5E9",
    "Venda Avulsa": "#10B981",
    "Ajuste de Inventário": "#6B7280",
    "Outro": "#6B7280",
}
