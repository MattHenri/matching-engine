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


class StatusOrdem(StrEnum):
    ABERTA = "aberta"
    PARCIALMENTE_EXECUTADA = "parcialmente_executada"
    EXECUTADA = "executada"
    CANCELADA = "cancelada"


@dataclass(slots=True)
class Ordem:
    """Ordem enviada ao motor.

    O `id` é sequencial e também define a prioridade de tempo: entre ordens do mesmo preço,
    a de menor `id` chegou antes e é executada primeiro.
    """

    id: int
    lado: Lado
    tipo: TipoOrdem
    quantidade: int
    preco: Decimal | None  # None em ordens a mercado
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
