"""Invariantes do motor sob sequências aleatórias de ordens e cancelamentos."""

from contextlib import suppress
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from matching_engine import ErroDeOrdem, Lado, MotorDeCasamento, StatusOrdem

lados = st.sampled_from(list(Lado))
quantidades = st.integers(min_value=1, max_value=100)
precos = st.integers(min_value=990, max_value=1010).map(lambda c: Decimal(c) / 100)

operacoes = st.lists(
    st.one_of(
        st.tuples(st.just("limitada"), lados, quantidades, precos),
        st.tuples(st.just("mercado"), lados, quantidades),
        st.tuples(st.just("cancelar"), st.integers(min_value=1, max_value=60)),
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


@settings(max_examples=300)
@given(operacoes)
def test_invariantes(ops: list[tuple[object, ...]]) -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    for op in ops:
        _aplicar(motor, op)

        # O livro nunca fica cruzado.
        compra, venda = motor.melhor_compra(), motor.melhor_venda()
        if compra is not None and venda is not None:
            assert compra < venda

    ordens = [motor.ordem(i) for i in range(1, len(motor._ordens) + 1)]
    negocios = motor.negocios

    # Quantidade negociada bate dos dois lados e com a soma dos negócios.
    total = sum(n.quantidade for n in negocios)
    assert sum(o.quantidade_executada for o in ordens if o.lado is Lado.COMPRA) == total
    assert sum(o.quantidade_executada for o in ordens if o.lado is Lado.VENDA) == total

    # Nenhuma ordem executa mais que sua quantidade.
    assert all(0 <= o.quantidade_executada <= o.quantidade for o in ordens)

    # O livro contém exatamente o restante das ordens abertas.
    prof = motor.profundidade()
    abertas = [
        o for o in ordens if o.status in (StatusOrdem.ABERTA, StatusOrdem.PARCIALMENTE_EXECUTADA)
    ]
    assert sum(n.quantidade for n in prof.compras + prof.vendas) == sum(
        o.quantidade_restante for o in abertas
    )

    # Negócios respeitam o limite de preço das duas ordens.
    for n in negocios:
        oc, ov = motor.ordem(n.id_ordem_compra), motor.ordem(n.id_ordem_venda)
        assert oc.preco is None or n.preco <= oc.preco
        assert ov.preco is None or n.preco >= ov.preco
