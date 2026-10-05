"""Invariantes do motor sob sequências aleatórias de ordens, alterações e cancelamentos."""

from contextlib import suppress
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from matching_engine import ErroDeOrdem, Lado, MotorDeCasamento, StatusOrdem

lados = st.sampled_from(list(Lado))
quantidades = st.integers(min_value=1, max_value=100)
precos = st.integers(min_value=990, max_value=1010).map(lambda c: Decimal(c) / 100)
ids = st.integers(min_value=1, max_value=60)

operacoes = st.lists(
    st.one_of(
        st.tuples(st.just("limitada"), lados, quantidades, precos),
        st.tuples(st.just("mercado"), lados, quantidades),
        st.tuples(st.just("cancelar"), ids),
        st.tuples(st.just("alterar"), ids, st.none() | precos, st.none() | quantidades),
    ),
    max_size=60,
)


def _aplicar(motor: MotorDeCasamento, op: tuple[object, ...]) -> None:
    match op:
        case ("limitada", Lado() as lado, int(qtd), Decimal() as preco):
            motor.enviar_ordem_limitada(lado, qtd, preco)
        case ("mercado", Lado() as lado, int(qtd)):
            motor.enviar_ordem_a_mercado(lado, qtd)
        case ("cancelar", int(id_ordem)):
            with suppress(ErroDeOrdem):
                motor.cancelar_ordem(id_ordem)
        case ("alterar", int(id_ordem), Decimal() | None as preco, int() | None as qtd):
            with suppress(ErroDeOrdem):
                motor.alterar_ordem(id_ordem, preco=preco, quantidade=qtd)


@settings(max_examples=300)
@given(operacoes)
def test_invariantes(ops: list[tuple[object, ...]]) -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    for op in ops:
        negocios_antes = len(motor.negocios)
        _aplicar(motor, op)

        # O livro nunca fica cruzado.
        compra, venda = motor.melhor_compra(), motor.melhor_venda()
        if compra is not None and venda is not None:
            assert compra < venda

        # Negócios desta operação respeitam o limite de preço das duas ordens. A conferência
        # é feita na hora porque uma alteração posterior pode mudar o preço da ordem.
        for n in motor.negocios[negocios_antes:]:
            oc, ov = motor.ordem(n.id_ordem_compra), motor.ordem(n.id_ordem_venda)
            assert oc.preco is None or n.preco <= oc.preco
            assert ov.preco is None or n.preco >= ov.preco

    ordens = [motor.ordem(i) for i in range(1, len(motor._ordens) + 1)]
    negocios = motor.negocios

    # Quantidade negociada bate dos dois lados e com a soma dos negócios.
    total = sum(n.quantidade for n in negocios)
    assert sum(o.quantidade_executada for o in ordens if o.lado is Lado.COMPRA) == total
    assert sum(o.quantidade_executada for o in ordens if o.lado is Lado.VENDA) == total

    # Nenhuma ordem executa mais que sua quantidade.
    assert all(0 <= o.quantidade_executada <= o.quantidade for o in ordens)

    # O livro contém exatamente as ordens abertas, cada uma uma vez, com o restante delas.
    abertas = {
        o.id: o.quantidade_restante
        for o in ordens
        if o.status in (StatusOrdem.ABERTA, StatusOrdem.PARCIALMENTE_EXECUTADA)
    }
    no_livro = motor.ordens_no_livro(Lado.COMPRA) + motor.ordens_no_livro(Lado.VENDA)
    assert len(no_livro) == len(abertas)
    assert {o.id: o.quantidade for o in no_livro} == abertas

    # A visão por ordem e a visão por nível concordam.
    prof = motor.profundidade()
    assert sum(n.quantidade for n in prof.compras + prof.vendas) == sum(abertas.values())

    # Cada lado está ordenado do melhor preço para o pior.
    precos_compra = [o.preco for o in motor.ordens_no_livro(Lado.COMPRA)]
    precos_venda = [o.preco for o in motor.ordens_no_livro(Lado.VENDA)]
    assert precos_compra == sorted(precos_compra, reverse=True)
    assert precos_venda == sorted(precos_venda)
