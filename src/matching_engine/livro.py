"""Livro de ofertas: ordens limitadas que aguardam execução, agrupadas por nível de preço."""

from __future__ import annotations

from bisect import insort
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from matching_engine.ordem import Lado, Ordem


@dataclass(frozen=True, slots=True)
class NivelDePreco:
    preco: Decimal
    quantidade: int
    ordens: int


class LadoDoLivro:
    """Um lado do livro (compra ou venda), com os níveis ordenados do melhor para o pior.

    Cada nível guarda uma fila FIFO de ordens, o que dá a prioridade de tempo.
    """

    def __init__(self, lado: Lado) -> None:
        self.lado = lado
        self._niveis: dict[Decimal, deque[Ordem]] = {}
        self._precos: list[Decimal] = []  # do melhor para o pior

    def _chave(self, preco: Decimal) -> Decimal:
        # Na compra o melhor preço é o maior; na venda, o menor.
        return -preco if self.lado is Lado.COMPRA else preco

    @property
    def vazio(self) -> bool:
        return not self._precos

    def melhor_preco(self) -> Decimal | None:
        return self._precos[0] if self._precos else None

    def primeira_ordem(self) -> Ordem | None:
        """Ordem com maior prioridade: melhor preço e, nele, a mais antiga."""
        return self._niveis[self._precos[0]][0] if self._precos else None

    def adicionar(self, ordem: Ordem, preco: Decimal) -> None:
        fila = self._niveis.get(preco)
        if fila is None:
            fila = self._niveis[preco] = deque()
            insort(self._precos, preco, key=self._chave)
        fila.append(ordem)

    def remover_primeira(self) -> None:
        preco = self._precos[0]
        fila = self._niveis[preco]
        fila.popleft()
        if not fila:
            self._remover_nivel(preco)

    def remover(self, ordem: Ordem, preco: Decimal) -> None:
        fila = self._niveis[preco]
        fila.remove(ordem)
        if not fila:
            self._remover_nivel(preco)

    def _remover_nivel(self, preco: Decimal) -> None:
        del self._niveis[preco]
        self._precos.remove(preco)

    def ordens(self) -> list[Ordem]:
        """Todas as ordens, do melhor preço para o pior e, em cada preço, por chegada."""
        return [ordem for preco in self._precos for ordem in self._niveis[preco]]

    def niveis(self) -> list[NivelDePreco]:
        return [
            NivelDePreco(
                preco=preco,
                quantidade=sum(o.quantidade_restante for o in self._niveis[preco]),
                ordens=len(self._niveis[preco]),
            )
            for preco in self._precos
        ]


class LivroDeOfertas:
    def __init__(self) -> None:
        self.compras = LadoDoLivro(Lado.COMPRA)
        self.vendas = LadoDoLivro(Lado.VENDA)

    def lado(self, lado: Lado) -> LadoDoLivro:
        return self.compras if lado is Lado.COMPRA else self.vendas
