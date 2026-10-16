"""Testes com sequências aleatórias de operações (Hypothesis).

O Hypothesis gera várias listas de operações e, depois de cada uma, a gente confere regras
que nunca podem ser quebradas, como "o livro nunca fica cruzado".
"""

from contextlib import suppress
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from matching_engine import ErroDeOrdem, MotorDeCasamento

lados = st.sampled_from(["buy", "sell"])
quantidades = st.integers(min_value=1, max_value=100)
precos = st.integers(min_value=990, max_value=1010).map(lambda c: Decimal(c) / 100)
ids = st.integers(min_value=1, max_value=60)

operacoes = st.lists(
    st.one_of(
        st.tuples(st.just("limit"), lados, quantidades, precos),
        st.tuples(st.just("market"), lados, quantidades),
        st.tuples(st.just("cancel"), ids),
        st.tuples(st.just("change"), ids, st.none() | precos, st.none() | quantidades),
        st.tuples(st.just("peg"), lados, quantidades),
    ),
    max_size=60,
)


def aplicar(motor: MotorDeCasamento, op: tuple[object, ...]) -> None:
    # suppress ignora o erro quando a operação é inválida (ex.: cancelar uma ordem que não existe)
    with suppress(ErroDeOrdem):
        match op:
            case ("limit", str(lado), int(qtd), Decimal() as preco):
                motor.enviar_limit(lado, qtd, preco)
            case ("market", str(lado), int(qtd)):
                motor.enviar_market(lado, qtd)
            case ("cancel", int(id_ordem)):
                motor.cancelar(id_ordem)
            case ("change", int(id_ordem), Decimal() | None as preco, int() | None as qtd):
                motor.alterar(id_ordem, preco, qtd)
            case ("peg", str(lado), int(qtd)):
                motor.enviar_peg("bid" if lado == "buy" else "offer", lado, qtd)


@settings(max_examples=300)
@given(operacoes)
def test_regras_que_nunca_podem_quebrar(ops: list[tuple[object, ...]]) -> None:
    motor = MotorDeCasamento()

    for op in ops:
        negocios_antes = len(motor.negocios)
        aplicar(motor, op)

        # o livro nunca fica cruzado (melhor compra sempre menor que a melhor venda)
        compra, venda = motor.melhor_compra(), motor.melhor_venda()
        if compra is not None and venda is not None:
            assert compra < venda

        # toda peg está no preço da melhor limit do lado dela (se existir uma)
        for lado in (motor.compras, motor.vendas):
            limits = [o.preco for o in lado if o.tipo == "limit"]
            if limits:
                assert all(o.preco == limits[0] for o in lado if o.tipo == "peg")

        # os negócios desta operação respeitam o preço limite das ordens limit
        # (confere na hora porque um change depois pode mudar o preço da ordem)
        for n in motor.negocios[negocios_antes:]:
            c, v = motor.ordens[n.id_compra], motor.ordens[n.id_venda]
            assert c.tipo != "limit" or n.preco <= c.preco
            assert v.tipo != "limit" or n.preco >= v.preco

    ordens = list(motor.ordens.values())

    # a quantidade negociada é igual dos dois lados e igual à soma dos negócios
    total = sum(n.quantidade for n in motor.negocios)
    assert sum(o.executada for o in ordens if o.lado == "buy") == total
    assert sum(o.executada for o in ordens if o.lado == "sell") == total

    # nenhuma ordem executa mais do que a quantidade dela
    assert all(0 <= o.executada <= o.quantidade for o in ordens)

    # o livro tem exatamente as ordens abertas, cada uma uma vez só
    abertas = sorted(o.id for o in ordens if o.status in ("aberta", "parcial"))
    no_livro = sorted(o.id for o in motor.compras + motor.vendas)
    assert no_livro == abertas

    # cada lado está ordenado do melhor preço pro pior
    precos_compra = [o.preco for o in motor.compras]
    precos_venda = [o.preco for o in motor.vendas]
    assert precos_compra == sorted(precos_compra, reverse=True)
    assert precos_venda == sorted(precos_venda)
