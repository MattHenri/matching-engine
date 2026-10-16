from decimal import Decimal as D
from typing import Any

import pytest

from matching_engine import ErroDeOrdem, MotorDeCasamento, Ordem


@pytest.fixture
def motor() -> MotorDeCasamento:
    return MotorDeCasamento()


def livro(lado: list[Ordem]) -> list[tuple[int, D]]:
    """Resumo de um lado do livro: (quantidade em aberto, preço) de cada ordem."""
    return [(o.restante, o.preco) for o in lado]


# ---------- limit e market ----------


def test_ordem_que_nao_cruza_fica_no_livro(motor: MotorDeCasamento) -> None:
    compra, negocios1 = motor.enviar_limit("buy", 100, D("10.00"))
    _, negocios2 = motor.enviar_limit("sell", 100, D("10.01"))

    assert negocios1 == negocios2 == []
    assert compra.status == "aberta"
    assert motor.melhor_compra() == D("10.00")
    assert motor.melhor_venda() == D("10.01")


def test_execucao_total_esvazia_o_livro(motor: MotorDeCasamento) -> None:
    venda, _ = motor.enviar_limit("sell", 100, D("10.00"))
    compra, negocios = motor.enviar_limit("buy", 100, D("10.00"))

    assert len(negocios) == 1
    n = negocios[0]
    assert (n.quantidade, n.id_compra, n.id_venda, n.agressor) == (100, compra.id, venda.id, "buy")
    assert compra.status == venda.status == "executada"
    assert motor.compras == motor.vendas == []


def test_negocio_sai_pelo_preco_da_ordem_do_livro(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("sell", 100, D("10.00"))
    _, negocios = motor.enviar_limit("buy", 100, D("10.50"))
    assert negocios[0].preco == D("10.00")


def test_sobra_da_limit_fica_no_livro(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("sell", 30, D("10.00"))
    compra, _ = motor.enviar_limit("buy", 100, D("10.00"))

    assert compra.status == "parcial"
    assert livro(motor.compras) == [(70, D("10.00"))]
    assert motor.melhor_venda() is None


def test_execucao_parcial_da_ordem_do_livro(motor: MotorDeCasamento) -> None:
    venda, _ = motor.enviar_limit("sell", 100, D("10.00"))
    motor.enviar_limit("buy", 40, D("10.00"))

    assert venda.status == "parcial"
    assert livro(motor.vendas) == [(60, D("10.00"))]


def test_prioridade_de_preco(motor: MotorDeCasamento) -> None:
    cara, _ = motor.enviar_limit("sell", 100, D("10.05"))
    barata, _ = motor.enviar_limit("sell", 100, D("10.00"))
    _, negocios = motor.enviar_limit("buy", 100, D("10.10"))

    assert negocios[0].id_venda == barata.id
    assert cara.status == "aberta"


def test_prioridade_de_chegada_no_mesmo_preco(motor: MotorDeCasamento) -> None:
    primeira, _ = motor.enviar_limit("buy", 50, D("10.00"))
    segunda, _ = motor.enviar_limit("buy", 50, D("10.00"))
    _, negocios = motor.enviar_limit("sell", 70, D("10.00"))

    assert [(n.id_compra, n.quantidade) for n in negocios] == [(primeira.id, 50), (segunda.id, 20)]
    assert segunda.restante == 30


def test_ordem_passa_por_varios_precos(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("sell", 10, D("10.00"))
    motor.enviar_limit("sell", 10, D("10.01"))
    motor.enviar_limit("sell", 10, D("10.02"))
    compra, negocios = motor.enviar_limit("buy", 25, D("10.01"))

    assert [(n.preco, n.quantidade) for n in negocios] == [(D("10.00"), 10), (D("10.01"), 10)]
    assert compra.restante == 5
    assert motor.melhor_compra() == D("10.01")
    assert motor.melhor_venda() == D("10.02")


def test_market_executa_e_cancela_o_resto(motor: MotorDeCasamento) -> None:
    motor.enviar_limit("buy", 10, D("10.00"))
    motor.enviar_limit("buy", 10, D("9.00"))
    venda, negocios = motor.enviar_market("sell", 30)

    assert [(n.preco, n.quantidade) for n in negocios] == [(D("10.00"), 10), (D("9.00"), 10)]
    assert venda.status == "cancelada"
    assert venda.executada == 20
    assert motor.compras == []


def test_market_com_livro_vazio_e_cancelada(motor: MotorDeCasamento) -> None:
    ordem, negocios = motor.enviar_market("buy", 10)
    assert negocios == []
    assert ordem.status == "cancelada"


# ---------- cancelamento ----------


def test_cancelar_tira_do_livro(motor: MotorDeCasamento) -> None:
    ordem, _ = motor.enviar_limit("buy", 10, D("10.00"))
    motor.cancelar(ordem.id)

    assert ordem.status == "cancelada"
    assert motor.compras == []
    assert motor.enviar_market("sell", 10)[1] == []


def test_cancelar_nao_muda_a_fila_das_outras(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 10, D("10.00"))
    b, _ = motor.enviar_limit("buy", 10, D("10.00"))
    c, _ = motor.enviar_limit("buy", 10, D("10.00"))
    motor.cancelar(b.id)
    _, negocios = motor.enviar_market("sell", 20)

    assert [n.id_compra for n in negocios] == [a.id, c.id]


def test_cancelar_ordem_que_nao_existe(motor: MotorDeCasamento) -> None:
    with pytest.raises(ErroDeOrdem, match="não existe"):
        motor.cancelar(99)


def test_cancelar_ordem_ja_executada(motor: MotorDeCasamento) -> None:
    venda, _ = motor.enviar_limit("sell", 10, D("10.00"))
    motor.enviar_market("buy", 10)
    with pytest.raises(ErroDeOrdem, match="não está aberta"):
        motor.cancelar(venda.id)


def test_cancelar_duas_vezes(motor: MotorDeCasamento) -> None:
    ordem, _ = motor.enviar_limit("buy", 10, D("10.00"))
    motor.cancelar(ordem.id)
    with pytest.raises(ErroDeOrdem, match="não está aberta"):
        motor.cancelar(ordem.id)


# ---------- validação ----------


@pytest.mark.parametrize("quantidade", [0, -1, True, 1.5, "10"])
def test_quantidade_invalida(motor: MotorDeCasamento, quantidade: Any) -> None:
    with pytest.raises(ErroDeOrdem, match="inteiro positivo"):
        motor.enviar_limit("buy", quantidade, D("10.00"))
    with pytest.raises(ErroDeOrdem, match="inteiro positivo"):
        motor.enviar_market("buy", quantidade)


@pytest.mark.parametrize("preco", [D("0"), D("-1"), D("10.001"), D("NaN"), D("Infinity"), 10.0])
def test_preco_invalido(motor: MotorDeCasamento, preco: Any) -> None:
    with pytest.raises(ErroDeOrdem):
        motor.enviar_limit("buy", 10, preco)


def test_ordem_recusada_nao_gasta_id(motor: MotorDeCasamento) -> None:
    with pytest.raises(ErroDeOrdem):
        motor.enviar_limit("buy", 0, D("10.00"))
    assert motor.enviar_limit("buy", 1, D("10.00"))[0].id == 1


def test_tick_diferente() -> None:
    motor = MotorDeCasamento(tick=D("0.05"))
    motor.enviar_limit("buy", 1, D("10.05"))
    with pytest.raises(ErroDeOrdem, match="tick"):
        motor.enviar_limit("buy", 1, D("10.03"))


# ---------- alteração ----------


def test_alterar_preco_muda_de_lugar_e_perde_prioridade(motor: MotorDeCasamento) -> None:
    # exemplo do enunciado
    primeira, _ = motor.enviar_limit("buy", 200, D("10"))
    motor.enviar_limit("buy", 100, D("9.99"))
    motor.enviar_limit("sell", 100, D("10.5"))

    _, negocios = motor.alterar(primeira.id, preco=D("9.98"))

    assert negocios == []
    assert livro(motor.compras) == [(100, D("9.99")), (200, D("9.98"))]
    assert livro(motor.vendas) == [(100, D("10.5"))]


def test_alterar_preco_para_um_que_ja_existe_vai_pro_fim(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 10, D("10.00"))
    b, _ = motor.enviar_limit("buy", 20, D("10.01"))
    motor.alterar(b.id, preco=D("10.00"))

    assert [o.id for o in motor.compras] == [a.id, b.id]


def test_aumentar_quantidade_perde_prioridade(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 10, D("10.00"))
    b, _ = motor.enviar_limit("buy", 10, D("10.00"))
    motor.alterar(a.id, quantidade=50)

    assert [(o.id, o.restante) for o in motor.compras] == [(b.id, 10), (a.id, 50)]


def test_diminuir_quantidade_mantem_prioridade(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 50, D("10.00"))
    b, _ = motor.enviar_limit("buy", 10, D("10.00"))
    motor.alterar(a.id, quantidade=5)

    assert [(o.id, o.restante) for o in motor.compras] == [(a.id, 5), (b.id, 10)]


def test_alterar_pros_mesmos_valores_mantem_prioridade(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 10, D("10.00"))
    b, _ = motor.enviar_limit("buy", 10, D("10.00"))
    motor.alterar(a.id, preco=D("10.00"), quantidade=10)

    assert [o.id for o in motor.compras] == [a.id, b.id]


def test_alterar_preco_e_quantidade(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("sell", 10, D("10.50"))
    motor.alterar(a.id, preco=D("10.40"), quantidade=30)

    assert livro(motor.vendas) == [(30, D("10.40"))]
    assert a.quantidade == 30


def test_alterar_preco_que_cruza_executa(motor: MotorDeCasamento) -> None:
    venda, _ = motor.enviar_limit("sell", 30, D("10.50"))
    compra, _ = motor.enviar_limit("buy", 100, D("10.00"))

    _, negocios = motor.alterar(compra.id, preco=D("10.60"))

    assert len(negocios) == 1
    n = negocios[0]
    assert (n.preco, n.quantidade, n.id_compra, n.id_venda) == (D("10.50"), 30, compra.id, venda.id)
    assert livro(motor.compras) == [(70, D("10.60"))]
    assert motor.melhor_venda() is None


def test_alterar_quantidade_de_ordem_parcialmente_executada(motor: MotorDeCasamento) -> None:
    compra, _ = motor.enviar_limit("buy", 100, D("10.00"))
    motor.enviar_market("sell", 40)

    motor.alterar(compra.id, quantidade=20)  # 20 em aberto, além dos 40 que já executaram

    assert (compra.executada, compra.quantidade, compra.restante) == (40, 60, 20)
    assert livro(motor.compras) == [(20, D("10.00"))]


def test_alterar_sem_informar_nada(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 10, D("10.00"))
    with pytest.raises(ErroDeOrdem, match="informe"):
        motor.alterar(a.id)


def test_alterar_ordem_que_nao_existe(motor: MotorDeCasamento) -> None:
    with pytest.raises(ErroDeOrdem, match="não existe"):
        motor.alterar(99, preco=D("10.00"))


def test_alterar_ordem_cancelada(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 10, D("10.00"))
    motor.cancelar(a.id)
    with pytest.raises(ErroDeOrdem, match="não está aberta"):
        motor.alterar(a.id, quantidade=5)


def test_alterar_com_valor_invalido_nao_muda_nada(motor: MotorDeCasamento) -> None:
    a, _ = motor.enviar_limit("buy", 10, D("10.00"))
    with pytest.raises(ErroDeOrdem):
        motor.alterar(a.id, preco=D("10.001"))
    with pytest.raises(ErroDeOrdem):
        motor.alterar(a.id, preco=D("9.00"), quantidade=0)

    assert livro(motor.compras) == [(10, D("10.00"))]
