"""Visualização do livro de ofertas em texto."""

from __future__ import annotations

from itertools import zip_longest

from matching_engine.motor import MotorDeCasamento, OrdemNoLivro
from matching_engine.ordem import Lado

LARGURA = 20


def _formatar(ordem: OrdemNoLivro | None) -> str:
    return "" if ordem is None else f"{ordem.quantidade} @ {ordem.preco}"


def visualizar_livro(motor: MotorDeCasamento) -> str:
    """Livro em duas colunas, uma ordem por linha, do melhor preço para o pior.

    Ordens de Compra    | Ordens de Venda
    --------------------|-----------------
    200 @ 10            | 100 @ 10.5
    100 @ 9.99          |
    """
    linhas = [
        f"{'Ordens de Compra':<{LARGURA}}| Ordens de Venda",
        f"{'-' * LARGURA}|{'-' * 17}",
    ]
    pares = zip_longest(motor.ordens_no_livro(Lado.COMPRA), motor.ordens_no_livro(Lado.VENDA))
    linhas += [
        f"{_formatar(compra):<{LARGURA}}| {_formatar(venda)}".rstrip() for compra, venda in pares
    ]
    return "\n".join(linhas)
