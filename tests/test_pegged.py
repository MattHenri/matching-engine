from decimal import Decimal

import pytest

from matching_engine import ErroDeOrdem, Lado, MotorDeCasamento, Referencia, TipoOrdem

C, V = Lado.COMPRA, Lado.VENDA
BID, OFFER = Referencia.BID, Referencia.OFFER


def D(valor: str) -> Decimal:  # noqa: N802
    return Decimal(valor)


@pytest.fixture
def motor() -> MotorDeCasamento:
    return MotorDeCasamento(ativo="TESTE")


def livro(motor: MotorDeCasamento, lado: Lado) -> list[tuple[int, Decimal]]:
    return [(o.quantidade, o.preco) for o in motor.ordens_no_livro(lado)]


def ids(motor: MotorDeCasamento, lado: Lado) -> list[int]:
    return [o.id for o in motor.ordens_no_livro(lado)]


def test_exemplo_do_enunciado(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 200, D("10"))
    motor.enviar_ordem_limitada(C, 100, D("9.99"))
    motor.enviar_ordem_limitada(V, 100, D("10.5"))

    r = motor.enviar_ordem_pegged(BID, C, 150)
    assert r.negocios == ()
    assert r.ordem.preco == D("10")
    assert livro(motor, C) == [(200, D("10")), (150, D("10")), (100, D("9.99"))]

    motor.enviar_ordem_limitada(C, 300, D("10.1"))
    assert livro(motor, C) == [
        (150, D("10.1")),
        (300, D("10.1")),
        (200, D("10")),
        (100, D("9.99")),
    ]
    assert livro(motor, V) == [(100, D("10.5"))]


def test_peg_to_the_offer(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(V, 100, D("10.5"))
    motor.enviar_ordem_limitada(C, 100, D("10"))

    peg = motor.enviar_ordem_pegged(OFFER, V, 50).ordem
    assert livro(motor, V) == [(100, D("10.5")), (50, D("10.5"))]

    motor.enviar_ordem_limitada(V, 10, D("10.4"))
    assert livro(motor, V) == [(50, D("10.4")), (10, D("10.4")), (100, D("10.5"))]
    assert ids(motor, V)[0] == peg.id


def test_acompanha_o_bid_quando_a_referencia_e_cancelada(motor: MotorDeCasamento) -> None:
    melhor = motor.enviar_ordem_limitada(C, 100, D("10")).ordem
    motor.enviar_ordem_limitada(C, 100, D("9.5"))
    motor.enviar_ordem_pegged(BID, C, 50)

    motor.cancelar_ordem(melhor.id)

    # A limitada a 9.5 chegou antes da pegged, então continua na frente.
    assert livro(motor, C) == [(100, D("9.5")), (50, D("9.5"))]


def test_acompanha_o_bid_quando_a_referencia_e_alterada(motor: MotorDeCasamento) -> None:
    referencia = motor.enviar_ordem_limitada(C, 100, D("10")).ordem
    peg = motor.enviar_ordem_pegged(BID, C, 50).ordem

    motor.alterar_ordem(referencia.id, preco=D("10.2"))

    # A pegged mantém a prioridade da chegada; a limitada alterada perdeu a dela.
    assert ids(motor, C) == [peg.id, referencia.id]
    assert livro(motor, C) == [(50, D("10.2")), (100, D("10.2"))]


def test_reprecifica_depois_que_o_bid_e_consumido(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 100, D("10"))
    motor.enviar_ordem_pegged(BID, C, 50)
    motor.enviar_ordem_limitada(C, 100, D("9.9"))

    r = motor.enviar_ordem_a_mercado(V, 100)

    assert [(n.preco, n.quantidade) for n in r.negocios] == [(D("10"), 100)]
    assert livro(motor, C) == [(50, D("9.9")), (100, D("9.9"))]


def test_agressora_executa_contra_o_livro_da_chegada(motor: MotorDeCasamento) -> None:
    # A pegged a 10 só é reprecificada depois que a agressora termina, então ela é executada
    # a 10, e não a 9.9.
    motor.enviar_ordem_limitada(C, 100, D("10"))
    peg = motor.enviar_ordem_pegged(BID, C, 50).ordem
    motor.enviar_ordem_limitada(C, 100, D("9.9"))

    r = motor.enviar_ordem_a_mercado(V, 200)

    assert [(n.preco, n.quantidade, n.id_ordem_compra) for n in r.negocios] == [
        (D("10"), 100, 1),
        (D("10"), 50, peg.id),
        (D("9.9"), 50, 3),
    ]


def test_pegged_executa_como_passiva(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 100, D("10"))
    peg = motor.enviar_ordem_pegged(BID, C, 50).ordem

    r = motor.enviar_ordem_limitada(V, 120, D("10"))

    assert [(n.quantidade, n.id_ordem_compra) for n in r.negocios] == [(100, 1), (20, peg.id)]
    assert peg.quantidade_restante == 30


def test_sem_referencia_no_envio_e_rejeitada(motor: MotorDeCasamento) -> None:
    with pytest.raises(ErroDeOrdem, match="não há bid"):
        motor.enviar_ordem_pegged(BID, C, 10)

    motor.enviar_ordem_limitada(C, 10, D("10"))  # só há bid
    with pytest.raises(ErroDeOrdem, match="não há offer"):
        motor.enviar_ordem_pegged(OFFER, V, 10)


def test_outra_pegged_nao_serve_de_referencia(motor: MotorDeCasamento) -> None:
    referencia = motor.enviar_ordem_limitada(C, 10, D("10")).ordem
    motor.enviar_ordem_pegged(BID, C, 20)
    motor.enviar_ordem_limitada(C, 10, D("9"))

    motor.cancelar_ordem(referencia.id)
    motor.enviar_ordem_pegged(BID, C, 30)

    assert livro(motor, C) == [(20, D("9")), (10, D("9")), (30, D("9"))]


def test_sem_referencia_fica_no_ultimo_preco(motor: MotorDeCasamento) -> None:
    referencia = motor.enviar_ordem_limitada(C, 100, D("10")).ordem
    peg = motor.enviar_ordem_pegged(BID, C, 50).ordem

    motor.cancelar_ordem(referencia.id)
    assert livro(motor, C) == [(50, D("10"))]

    motor.enviar_ordem_limitada(C, 10, D("9"))
    assert livro(motor, C) == [(50, D("9")), (10, D("9"))]
    assert ids(motor, C)[0] == peg.id


@pytest.mark.parametrize(("referencia", "lado"), [(BID, V), (OFFER, C)])
def test_combinacao_que_cruzaria_e_rejeitada(
    motor: MotorDeCasamento, referencia: Referencia, lado: Lado
) -> None:
    motor.enviar_ordem_limitada(C, 10, D("10"))
    motor.enviar_ordem_limitada(V, 10, D("11"))
    with pytest.raises(ErroDeOrdem, match="cruzaria"):
        motor.enviar_ordem_pegged(referencia, lado, 10)


def test_quantidade_invalida(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 10, D("10"))
    with pytest.raises(ErroDeOrdem, match="positiva"):
        motor.enviar_ordem_pegged(BID, C, 0)


def test_cancelar_pegged(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 10, D("10"))
    peg = motor.enviar_ordem_pegged(BID, C, 50).ordem
    motor.cancelar_ordem(peg.id)
    assert livro(motor, C) == [(10, D("10"))]


def test_alterar_preco_de_pegged_e_rejeitado(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 10, D("10"))
    peg = motor.enviar_ordem_pegged(BID, C, 50).ordem
    with pytest.raises(ErroDeOrdem, match="pegged"):
        motor.alterar_ordem(peg.id, preco=D("9"))


def test_alterar_quantidade_de_pegged(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 10, D("10"))
    peg = motor.enviar_ordem_pegged(BID, C, 50).ordem
    outra = motor.enviar_ordem_limitada(C, 10, D("10")).ordem

    motor.alterar_ordem(peg.id, quantidade=40)  # reduzir mantém a prioridade
    assert ids(motor, C) == [1, peg.id, outra.id]

    motor.alterar_ordem(peg.id, quantidade=60)  # aumentar perde
    assert ids(motor, C) == [1, outra.id, peg.id]
    assert livro(motor, C)[-1] == (60, D("10"))


def test_enviar_ordem_generico(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem(TipoOrdem.LIMITE, C, 10, D("10"))
    r = motor.enviar_ordem(TipoOrdem.PEGGED, C, 5, referencia=BID)
    assert r.ordem.tipo is TipoOrdem.PEGGED
    assert r.ordem.referencia is BID

    with pytest.raises(ErroDeOrdem, match="exige referência"):
        motor.enviar_ordem(TipoOrdem.PEGGED, C, 5)
    with pytest.raises(ErroDeOrdem, match="não aceita preço"):
        motor.enviar_ordem(TipoOrdem.PEGGED, C, 5, D("10"), BID)
    with pytest.raises(ErroDeOrdem, match="não aceita referência"):
        motor.enviar_ordem(TipoOrdem.LIMITE, C, 5, D("10"), BID)
    with pytest.raises(ErroDeOrdem, match="não aceita referência"):
        motor.enviar_ordem(TipoOrdem.MERCADO, C, 5, referencia=BID)
