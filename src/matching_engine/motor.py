"""Motor de casamento de ordens com prioridade preço-tempo, para um único ativo."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import count

from matching_engine.livro import LivroDeOfertas, NivelDePreco
from matching_engine.ordem import Lado, Negocio, Ordem, TipoOrdem


class ErroDeOrdem(ValueError):
    """Ordem ou cancelamento rejeitado pelo motor."""


@dataclass(frozen=True, slots=True)
class ResultadoEnvio:
    ordem: Ordem
    negocios: tuple[Negocio, ...]


@dataclass(frozen=True, slots=True)
class Profundidade:
    """Foto do livro, com os níveis de cada lado do melhor para o pior."""

    compras: tuple[NivelDePreco, ...]
    vendas: tuple[NivelDePreco, ...]


class MotorDeCasamento:
    """Recebe ordens, casa contra o livro e mantém tudo em memória.

    Regras:
    - Prioridade preço-tempo: melhor preço primeiro; no mesmo preço, quem chegou antes.
    - O negócio sai pelo preço da ordem que já estava no livro (a passiva).
    - Ordem limitada: executa o que cruzar e o restante fica no livro. Uma limitada com preço
      que já cruza o livro (ex.: compra acima da melhor venda) é executada, não ignorada:
      é o que as bolsas fazem, a ordem nunca sai a preço pior que o limite (sai ao preço da
      passiva) e o livro nunca fica cruzado.
    - Ordem a mercado: executa contra o que houver no livro e o restante é cancelado.
    """

    def __init__(self, ativo: str, tick: Decimal = Decimal("0.01")) -> None:
        if not tick.is_finite() or tick <= 0:
            raise ValueError("tick deve ser um Decimal positivo")
        self.ativo = ativo
        self.tick = tick
        self._livro = LivroDeOfertas()
        self._ordens: dict[int, Ordem] = {}
        self._negocios: list[Negocio] = []
        self._ids_ordem = count(1)
        self._ids_negocio = count(1)

    # --- envio e cancelamento -------------------------------------------------------------

    def enviar_ordem(
        self, tipo: TipoOrdem, lado: Lado, quantidade: int, preco: Decimal | None = None
    ) -> ResultadoEnvio:
        """Envia uma ordem de qualquer tipo. O preço é obrigatório só na limitada."""
        if tipo is TipoOrdem.LIMITE:
            if preco is None:
                raise ErroDeOrdem("ordem limitada exige preço")
            return self.enviar_ordem_limitada(lado, quantidade, preco)
        if preco is not None:
            raise ErroDeOrdem("ordem a mercado não aceita preço")
        return self.enviar_ordem_a_mercado(lado, quantidade)

    def enviar_ordem_limitada(self, lado: Lado, quantidade: int, preco: Decimal) -> ResultadoEnvio:
        self._validar_quantidade(quantidade)
        self._validar_preco(preco)
        ordem = Ordem(next(self._ids_ordem), lado, TipoOrdem.LIMITE, quantidade, preco)
        self._ordens[ordem.id] = ordem
        negocios = self._casar(ordem)
        if ordem.quantidade_restante > 0:
            self._livro.lado(lado).adicionar(ordem, preco)
        return ResultadoEnvio(ordem, negocios)

    def enviar_ordem_a_mercado(self, lado: Lado, quantidade: int) -> ResultadoEnvio:
        self._validar_quantidade(quantidade)
        ordem = Ordem(next(self._ids_ordem), lado, TipoOrdem.MERCADO, quantidade, None)
        self._ordens[ordem.id] = ordem
        negocios = self._casar(ordem)
        if ordem.quantidade_restante > 0:
            ordem.cancelada = True
        return ResultadoEnvio(ordem, negocios)

    def cancelar_ordem(self, id_ordem: int) -> Ordem:
        ordem = self._ordens.get(id_ordem)
        if ordem is None:
            raise ErroDeOrdem(f"ordem {id_ordem} não existe")
        if ordem.quantidade_restante == 0:
            raise ErroDeOrdem(f"ordem {id_ordem} não está aberta ({ordem.status})")
        # Só ordens limitadas ficam abertas, então o preço existe.
        assert ordem.preco is not None
        self._livro.lado(ordem.lado).remover(ordem, ordem.preco)
        ordem.cancelada = True
        return ordem

    # --- consultas ------------------------------------------------------------------------

    def ordem(self, id_ordem: int) -> Ordem:
        try:
            return self._ordens[id_ordem]
        except KeyError:
            raise ErroDeOrdem(f"ordem {id_ordem} não existe") from None

    def profundidade(self) -> Profundidade:
        return Profundidade(
            compras=tuple(self._livro.compras.niveis()),
            vendas=tuple(self._livro.vendas.niveis()),
        )

    def melhor_compra(self) -> Decimal | None:
        return self._livro.compras.melhor_preco()

    def melhor_venda(self) -> Decimal | None:
        return self._livro.vendas.melhor_preco()

    @property
    def negocios(self) -> tuple[Negocio, ...]:
        return tuple(self._negocios)

    # --- casamento ------------------------------------------------------------------------

    def _casar(self, agressora: Ordem) -> tuple[Negocio, ...]:
        contraparte = self._livro.lado(agressora.lado.oposto)
        negocios: list[Negocio] = []

        while agressora.quantidade_restante > 0:
            passiva = contraparte.primeira_ordem()
            preco = contraparte.melhor_preco()
            if passiva is None or preco is None or not self._cruza(agressora, preco):
                break

            quantidade = min(agressora.quantidade_restante, passiva.quantidade_restante)
            agressora.quantidade_executada += quantidade
            passiva.quantidade_executada += quantidade
            if passiva.quantidade_restante == 0:
                contraparte.remover_primeira()

            compra, venda = (
                (agressora, passiva) if agressora.lado is Lado.COMPRA else (passiva, agressora)
            )
            negocios.append(
                Negocio(
                    id=next(self._ids_negocio),
                    preco=preco,
                    quantidade=quantidade,
                    id_ordem_compra=compra.id,
                    id_ordem_venda=venda.id,
                    lado_agressor=agressora.lado,
                )
            )

        self._negocios.extend(negocios)
        return tuple(negocios)

    @staticmethod
    def _cruza(agressora: Ordem, preco_passivo: Decimal) -> bool:
        if agressora.preco is None:  # a mercado aceita qualquer preço
            return True
        if agressora.lado is Lado.COMPRA:
            return agressora.preco >= preco_passivo
        return agressora.preco <= preco_passivo

    # --- validação ------------------------------------------------------------------------

    @staticmethod
    def _validar_quantidade(quantidade: int) -> None:
        if isinstance(quantidade, bool) or not isinstance(quantidade, int):
            raise ErroDeOrdem("quantidade deve ser um inteiro")
        if quantidade <= 0:
            raise ErroDeOrdem("quantidade deve ser positiva")

    def _validar_preco(self, preco: Decimal) -> None:
        if not isinstance(preco, Decimal):
            raise ErroDeOrdem("preço deve ser Decimal")
        if not preco.is_finite() or preco <= 0:
            raise ErroDeOrdem("preço deve ser positivo")
        if preco % self.tick != 0:
            raise ErroDeOrdem(f"preço {preco} não é múltiplo do tick {self.tick}")
