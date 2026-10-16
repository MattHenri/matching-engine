from decimal import Decimal as D

import pytest

from matching_engine import ErroDeOrdem, MotorDeCasamento, Ordem


@pytest.fixture
def motor() -> MotorDeCasamento:
    return MotorDeCasamento()


def livro(lado: list[Ordem]) -> list[tuple[int, D]]:
    return [(o.restante, o.preco) for o in lado]


def ids(lado: list[Ordem]) -> list[int]:
    return [o.id for o in lado]


def test_exemplo_do_enunciado(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 200, D("10"))
    motor.enviar_limit("buy", 100, D("9.99"))
    motor.enviar_limit("sell", 100, D("10.5"))

    peg, negocios = motor.enviar_peg("bid", "buy", 150)
    assert negocios == []
    assert peg.preco == D("10")
    assert livro(motor.compras) == [(200, D("10")), (150, D("10")), (100, D("9.99"))]

    motor.enviar_limit("buy", 300, D("10.1"))
    assert livro(motor.compras) == [
        (150, D("10.1")),
        (300, D("10.1")),
        (200, D("10")),
        (100, D("9.99")),
    ]
    assert livro(motor.vendas) == [(100, D("10.5"))]


def test_peg_offer(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("sell", 100, D("10.5"))
    motor.enviar_limit("buy", 100, D("10"))

    peg, _ = motor.enviar_peg("offer", "sell", 50)
    assert livro(motor.vendas) == [(100, D("10.5")), (50, D("10.5"))]

    motor.enviar_limit("sell", 10, D("10.4"))
    assert livro(motor.vendas) == [(50, D("10.4")), (10, D("10.4")), (100, D("10.5"))]
    assert ids(motor.vendas)[0] == peg.id


def test_segue_o_bid_quando_a_referencia_e_cancelada(motor: MotorDeCasamento) -> None:
    melhor, _ = motor.enviar_limit("buy", 100, D("10"))
    motor.enviar_limit("buy", 100, D("9.5"))
    motor.enviar_peg("bid", "buy", 50)

    motor.cancelar(melhor.id)

    # a limit de 9.5 chegou antes da peg, então continua na frente
    assert livro(motor.compras) == [(100, D("9.5")), (50, D("9.5"))]


def test_segue_o_bid_quando_a_referencia_e_alterada(motor: MotorDeCasamento) -> None:
    referencia, _ = motor.enviar_limit("buy", 100, D("10"))
    peg, _ = motor.enviar_peg("bid", "buy", 50)

    motor.alterar(referencia.id, preco=D("10.2"))

    # a peg mantém a prioridade de quando chegou; a limit alterada perdeu a dela
    assert ids(motor.compras) == [peg.id, referencia.id]
    assert livro(motor.compras) == [(50, D("10.2")), (100, D("10.2"))]


def test_muda_de_preco_depois_que_o_bid_e_consumido(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 100, D("10"))
    motor.enviar_peg("bid", "buy", 50)
    motor.enviar_limit("buy", 100, D("9.9"))

    _, negocios = motor.enviar_market("sell", 100)

    assert [(n.preco, n.quantidade) for n in negocios] == [(D("10"), 100)]
    assert livro(motor.compras) == [(50, D("9.9")), (100, D("9.9"))]


def test_market_executa_a_peg_no_preco_que_ela_tinha(motor: MotorDeCasamento) -> None:
    # a peg só muda de preço depois que a market termina, então ela executa a 10, e não a 9.9
    motor.enviar_limit("buy", 100, D("10"))
    peg, _ = motor.enviar_peg("bid", "buy", 50)
    motor.enviar_limit("buy", 100, D("9.9"))

    _, negocios = motor.enviar_market("sell", 200)

    assert [(n.preco, n.quantidade, n.id_compra) for n in negocios] == [
        (D("10"), 100, 1),
        (D("10"), 50, peg.id),
        (D("9.9"), 50, 3),
    ]


def test_peg_executa_quando_alguem_agride(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 100, D("10"))
    peg, _ = motor.enviar_peg("bid", "buy", 50)

    _, negocios = motor.enviar_limit("sell", 120, D("10"))

    assert [(n.quantidade, n.id_compra) for n in negocios] == [(100, 1), (20, peg.id)]
    assert peg.restante == 30


def test_sem_referencia_a_peg_e_recusada(motor: MotorDeCasamento) -> None:
    with pytest.raises(ErroDeOrdem, match="não há bid"):
        motor.enviar_peg("bid", "buy", 10)

    motor.enviar_limit("buy", 10, D("10"))  # agora só tem bid
    with pytest.raises(ErroDeOrdem, match="não há offer"):
        motor.enviar_peg("offer", "sell", 10)


def test_outra_peg_nao_serve_de_referencia(motor: MotorDeCasamento) -> None:
    referencia, _ = motor.enviar_limit("buy", 10, D("10"))
    motor.enviar_peg("bid", "buy", 20)
    motor.enviar_limit("buy", 10, D("9"))

    motor.cancelar(referencia.id)
    motor.enviar_peg("bid", "buy", 30)

    assert livro(motor.compras) == [(20, D("9")), (10, D("9")), (30, D("9"))]


def test_sem_referencia_fica_no_ultimo_preco(motor: MotorDeCasamento) -> None:
    referencia, _ = motor.enviar_limit("buy", 100, D("10"))
    peg, _ = motor.enviar_peg("bid", "buy", 50)

    motor.cancelar(referencia.id)
    assert livro(motor.compras) == [(50, D("10"))]

    motor.enviar_limit("buy", 10, D("9"))
    assert livro(motor.compras) == [(50, D("9")), (10, D("9"))]
    assert ids(motor.compras)[0] == peg.id


@pytest.mark.parametrize(("referencia", "lado"), [("bid", "sell"), ("offer", "buy")])
def test_combinacao_que_cruzaria_e_recusada(
    motor: MotorDeCasamento, referencia: str, lado: str
) -> None:
    motor.enviar_limit("buy", 10, D("10"))
    motor.enviar_limit("sell", 10, D("11"))
    with pytest.raises(ErroDeOrdem, match="cruzaria"):
        motor.enviar_peg(referencia, lado, 10)


def test_quantidade_invalida(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 10, D("10"))
    with pytest.raises(ErroDeOrdem, match="inteiro positivo"):
        motor.enviar_peg("bid", "buy", 0)


def test_cancelar_peg(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 10, D("10"))
    peg, _ = motor.enviar_peg("bid", "buy", 50)
    motor.cancelar(peg.id)
    assert livro(motor.compras) == [(10, D("10"))]


def test_nao_da_pra_mudar_o_preco_da_peg(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 10, D("10"))
    peg, _ = motor.enviar_peg("bid", "buy", 50)
    with pytest.raises(ErroDeOrdem, match="peg"):
        motor.alterar(peg.id, preco=D("9"))


def test_mudar_a_quantidade_da_peg(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 10, D("10"))
    peg, _ = motor.enviar_peg("bid", "buy", 50)
    outra, _ = motor.enviar_limit("buy", 10, D("10"))

    motor.alterar(peg.id, quantidade=40)  # diminuir mantém o lugar
    assert ids(motor.compras) == [1, peg.id, outra.id]

    motor.alterar(peg.id, quantidade=60)  # aumentar vai pro fim
    assert ids(motor.compras) == [1, outra.id, peg.id]
    assert livro(motor.compras)[-1] == (60, D("10"))
