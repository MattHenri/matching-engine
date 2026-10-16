"""Classes que guardam os dados de uma ordem e de um negócio (trade)."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Ordem:
    id: int
    lado: str  # "buy" ou "sell"
    tipo: str  # "limit", "market" ou "peg"
    quantidade: int
    preco: Decimal  # na market fica 0, porque ela não tem preço
    prioridade: int  # no mesmo preço, quem tem o número menor é atendido primeiro
    referencia: str = ""  # só na peg: "bid" ou "offer"
    executada: int = 0  # quanto já virou negócio
    cancelada: bool = False

    @property
    def restante(self) -> int:
        # o que ainda falta executar; ordem cancelada não tem mais nada
        if self.cancelada:
            return 0
        return self.quantidade - self.executada

    @property
    def status(self) -> str:
        # cancelada vem primeiro porque uma market pode executar uma parte e cancelar o resto
        if self.cancelada:
            return "cancelada"
        if self.executada == self.quantidade:
            return "executada"
        if self.executada > 0:
            return "parcial"
        return "aberta"


@dataclass
class Negocio:
    id: int
    preco: Decimal
    quantidade: int
    id_compra: int  # id da ordem de compra
    id_venda: int  # id da ordem de venda
    agressor: str  # lado da ordem que chegou e gerou o negócio
