"""Tipos básicos: lado, ordem e negócio."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Lado(StrEnum):
    COMPRA = "compra"
    VENDA = "venda"

    @property
    def oposto(self) -> Lado:
        return Lado.VENDA if self is Lado.COMPRA else Lado.COMPRA


class TipoOrdem(StrEnum):
    LIMITE = "limite"
    MERCADO = "mercado"
    PEGGED = "pegged"


class Referencia(StrEnum):
    """Preço que uma ordem pegged acompanha."""

    BID = "bid"  # melhor preço de compra
    OFFER = "offer"  # melhor preço de venda

    @property
    def lado(self) -> Lado:
        """Lado do livro de onde vem o preço de referência."""
        return Lado.COMPRA if self is Referencia.BID else Lado.VENDA


class StatusOrdem(StrEnum):
    ABERTA = "aberta"
    PARCIALMENTE_EXECUTADA = "parcialmente_executada"
    EXECUTADA = "executada"
    CANCELADA = "cancelada"


@dataclass(slots=True)
class Ordem:
    """Ordem enviada ao motor.

    O `id` é sequencial e não muda. A prioridade de tempo dentro de um nível de preço vem de
    `prioridade`: menor executa antes. Ela é dada na chegada e só muda quando uma alteração
    faz a ordem perder a prioridade.
    """

    id: int
    lado: Lado
    tipo: TipoOrdem
    quantidade: int
    preco: Decimal | None  # None em ordens a mercado; nas pegged, muda com a referência
    prioridade: int
    referencia: Referencia | None = None  # só nas pegged
    quantidade_executada: int = 0
    cancelada: bool = False

    @property
    def quantidade_restante(self) -> int:
        return 0 if self.cancelada else self.quantidade - self.quantidade_executada

    @property
    def status(self) -> StatusOrdem:
        if self.cancelada:
            return StatusOrdem.CANCELADA
        if self.quantidade_executada == self.quantidade:
            return StatusOrdem.EXECUTADA
        if self.quantidade_executada > 0:
            return StatusOrdem.PARCIALMENTE_EXECUTADA
        return StatusOrdem.ABERTA


@dataclass(frozen=True, slots=True)
class Negocio:
    """Execução (trade) entre uma ordem de compra e uma de venda."""

    id: int
    preco: Decimal
    quantidade: int
    id_ordem_compra: int
    id_ordem_venda: int
    lado_agressor: Lado
