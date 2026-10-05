from decimal import Decimal
from typing import Any

import pytest

from matching_engine import ErroDeOrdem, Lado, MotorDeCasamento, StatusOrdem

C, V = Lado.COMPRA, Lado.VENDA


def D(valor: str) -> Decimal:  # noqa: N802
    return Decimal(valor)


@pytest.fixture
def motor() -> MotorDeCasamento:
    return MotorDeCasamento(ativo="TESTE")


def test_ordem_que_nao_cruza_fica_no_livro(motor: MotorDeCasamento) -> None:
    r1 = motor.enviar_ordem_limitada(C, 100, D("10.00"))
    r2 = motor.enviar_ordem_limitada(V, 100, D("10.01"))

    assert r1.negocios == r2.negocios == ()
    assert r1.ordem.status is StatusOrdem.ABERTA
    assert motor.melhor_compra() == D("10.00")
    assert motor.melhor_venda() == D("10.01")


def test_execucao_total_esvazia_o_livro(motor: MotorDeCasamento) -> None:
    venda = motor.enviar_ordem_limitada(V, 100, D("10.00")).ordem
    r = motor.enviar_ordem_limitada(C, 100, D("10.00"))

    (negocio,) = r.negocios
    assert negocio.quantidade == 100
    assert negocio.id_ordem_compra == r.ordem.id
    assert negocio.id_ordem_venda == venda.id
    assert negocio.lado_agressor is C
    assert r.ordem.status is venda.status is StatusOrdem.EXECUTADA
    assert motor.profundidade().compras == motor.profundidade().vendas == ()


def test_negocio_sai_pelo_preco_da_ordem_passiva(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(V, 100, D("10.00"))
    r = motor.enviar_ordem_limitada(C, 100, D("10.50"))
    assert r.negocios[0].preco == D("10.00")


def test_restante_da_agressora_limitada_fica_no_livro(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(V, 30, D("10.00"))
    r = motor.enviar_ordem_limitada(C, 100, D("10.00"))

    assert r.ordem.status is StatusOrdem.PARCIALMENTE_EXECUTADA
    assert r.ordem.quantidade_restante == 70
    assert motor.profundidade().compras[0].quantidade == 70
    assert motor.melhor_venda() is None


def test_execucao_parcial_da_passiva(motor: MotorDeCasamento) -> None:
    venda = motor.enviar_ordem_limitada(V, 100, D("10.00")).ordem
    motor.enviar_ordem_limitada(C, 40, D("10.00"))

    assert venda.status is StatusOrdem.PARCIALMENTE_EXECUTADA
    assert motor.profundidade().vendas[0].quantidade == 60


def test_prioridade_de_preco(motor: MotorDeCasamento) -> None:
    cara = motor.enviar_ordem_limitada(V, 100, D("10.05")).ordem
    barata = motor.enviar_ordem_limitada(V, 100, D("10.00")).ordem
    r = motor.enviar_ordem_limitada(C, 100, D("10.10"))

    assert r.negocios[0].id_ordem_venda == barata.id
    assert cara.status is StatusOrdem.ABERTA


def test_prioridade_de_tempo_no_mesmo_preco(motor: MotorDeCasamento) -> None:
    primeira = motor.enviar_ordem_limitada(C, 50, D("10.00")).ordem
    segunda = motor.enviar_ordem_limitada(C, 50, D("10.00")).ordem
    r = motor.enviar_ordem_limitada(V, 70, D("10.00"))

    assert [(n.id_ordem_compra, n.quantidade) for n in r.negocios] == [
        (primeira.id, 50),
        (segunda.id, 20),
    ]
    assert segunda.quantidade_restante == 30


def test_agressora_varre_varios_niveis(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(V, 10, D("10.00"))
    motor.enviar_ordem_limitada(V, 10, D("10.01"))
    motor.enviar_ordem_limitada(V, 10, D("10.02"))
    r = motor.enviar_ordem_limitada(C, 25, D("10.01"))

    assert [(n.preco, n.quantidade) for n in r.negocios] == [(D("10.00"), 10), (D("10.01"), 10)]
    assert r.ordem.quantidade_restante == 5
    assert motor.melhor_compra() == D("10.01")
    assert motor.melhor_venda() == D("10.02")


def test_ordem_a_mercado_executa_e_cancela_o_restante(motor: MotorDeCasamento) -> None:
    motor.enviar_ordem_limitada(C, 10, D("10.00"))
    motor.enviar_ordem_limitada(C, 10, D("9.00"))
    r = motor.enviar_ordem_a_mercado(V, 30)

    assert [(n.preco, n.quantidade) for n in r.negocios] == [(D("10.00"), 10), (D("9.00"), 10)]
    assert r.ordem.status is StatusOrdem.CANCELADA
    assert r.ordem.quantidade_executada == 20
    assert motor.profundidade().compras == ()


def test_ordem_a_mercado_com_livro_vazio_e_cancelada(motor: MotorDeCasamento) -> None:
    r = motor.enviar_ordem_a_mercado(C, 10)
    assert r.negocios == ()
    assert r.ordem.status is StatusOrdem.CANCELADA


def test_cancelar_remove_do_livro(motor: MotorDeCasamento) -> None:
    ordem = motor.enviar_ordem_limitada(C, 10, D("10.00")).ordem
    motor.cancelar_ordem(ordem.id)

    assert ordem.status is StatusOrdem.CANCELADA
    assert motor.melhor_compra() is None
    assert motor.enviar_ordem_a_mercado(V, 10).negocios == ()


def test_cancelar_preserva_a_fila_do_nivel(motor: MotorDeCasamento) -> None:
    a = motor.enviar_ordem_limitada(C, 10, D("10.00")).ordem
    b = motor.enviar_ordem_limitada(C, 10, D("10.00")).ordem
    c = motor.enviar_ordem_limitada(C, 10, D("10.00")).ordem
    motor.cancelar_ordem(b.id)
    r = motor.enviar_ordem_a_mercado(V, 20)

    assert [n.id_ordem_compra for n in r.negocios] == [a.id, c.id]


def test_cancelar_ordem_inexistente(motor: MotorDeCasamento) -> None:
    with pytest.raises(ErroDeOrdem, match="não existe"):
        motor.cancelar_ordem(99)


def test_cancelar_ordem_ja_executada(motor: MotorDeCasamento) -> None:
    venda = motor.enviar_ordem_limitada(V, 10, D("10.00")).ordem
    motor.enviar_ordem_a_mercado(C, 10)
    with pytest.raises(ErroDeOrdem, match="não está aberta"):
        motor.cancelar_ordem(venda.id)


def test_cancelar_duas_vezes(motor: MotorDeCasamento) -> None:
    ordem = motor.enviar_ordem_limitada(C, 10, D("10.00")).ordem
    motor.cancelar_ordem(ordem.id)
    with pytest.raises(ErroDeOrdem, match="não está aberta"):
        motor.cancelar_ordem(ordem.id)


@pytest.mark.parametrize("quantidade", [0, -1, True, 1.5, "10"])
def test_quantidade_invalida(motor: MotorDeCasamento, quantidade: Any) -> None:
    with pytest.raises(ErroDeOrdem):
        motor.enviar_ordem_limitada(C, quantidade, D("10.00"))
    with pytest.raises(ErroDeOrdem):
        motor.enviar_ordem_a_mercado(C, quantidade)


@pytest.mark.parametrize("preco", [D("0"), D("-1"), D("10.001"), D("NaN"), D("Infinity"), 10.0])
def test_preco_invalido(motor: MotorDeCasamento, preco: Any) -> None:
    with pytest.raises(ErroDeOrdem):
        motor.enviar_ordem_limitada(C, 10, preco)


def test_ordem_rejeitada_nao_consome_id(motor: MotorDeCasamento) -> None:
    with pytest.raises(ErroDeOrdem):
        motor.enviar_ordem_limitada(C, 0, D("10.00"))
    assert motor.enviar_ordem_limitada(C, 1, D("10.00")).ordem.id == 1


def test_tick_configuravel() -> None:
    motor = MotorDeCasamento(ativo="TESTE", tick=D("0.05"))
    motor.enviar_ordem_limitada(C, 1, D("10.05"))
    with pytest.raises(ErroDeOrdem, match="tick"):
        motor.enviar_ordem_limitada(C, 1, D("10.03"))
