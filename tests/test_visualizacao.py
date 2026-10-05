from decimal import Decimal

from matching_engine import Lado, MotorDeCasamento, visualizar_livro


def test_livro_vazio() -> None:
    assert visualizar_livro(MotorDeCasamento(ativo="TESTE")) == (
        "Ordens de Compra    | Ordens de Venda\n--------------------|-----------------"
    )


def test_exemplo_do_enunciado() -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    primeira = motor.enviar_ordem_limitada(Lado.COMPRA, 200, Decimal("10")).ordem
    motor.enviar_ordem_limitada(Lado.COMPRA, 100, Decimal("9.99"))
    motor.enviar_ordem_limitada(Lado.VENDA, 100, Decimal("10.5"))

    assert visualizar_livro(motor).splitlines() == [
        "Ordens de Compra    | Ordens de Venda",
        "--------------------|-----------------",
        "200 @ 10            | 100 @ 10.5",
        "100 @ 9.99          |",
    ]

    motor.alterar_ordem(primeira.id, preco=Decimal("9.98"))

    assert visualizar_livro(motor).splitlines()[2:] == [
        "100 @ 9.99          | 100 @ 10.5",
        "200 @ 9.98          |",
    ]


def test_lado_de_venda_maior() -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    motor.enviar_ordem_limitada(Lado.VENDA, 5, Decimal("11"))
    motor.enviar_ordem_limitada(Lado.VENDA, 7, Decimal("12"))

    assert visualizar_livro(motor).splitlines()[2:] == [
        "                    | 5 @ 11",
        "                    | 7 @ 12",
    ]
