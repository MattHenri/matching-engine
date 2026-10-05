from matching_engine import MotorDeCasamento
from matching_engine.cli import executar_comando


def test_fluxo_basico() -> None:
    motor = MotorDeCasamento(ativo="TESTE")

    assert executar_comando(motor, "limit sell 10,50 100") == "ordem 1: aberta, executada 0/100"
    assert executar_comando(motor, "limit buy 10.40 50") == "ordem 2: aberta, executada 0/50"

    livro = executar_comando(motor, "livro")
    assert "SELL" in livro
    assert "BUY" in livro
    assert "spread 0.10" in livro

    assert executar_comando(motor, "market buy 30").splitlines() == [
        "Trade, price: 10.50, qty: 30",
        "ordem 3: executada, executada 30/30",
    ]

    assert "cancelada" in executar_comando(motor, "cancelar 2")
    assert "#1 Trade, price: 10.50, qty: 30" in executar_comando(motor, "negocios")


def test_uma_linha_por_trade() -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    executar_comando(motor, "limit buy 10 100")
    executar_comando(motor, "limit buy 10 200")
    executar_comando(motor, "limit buy 9 50")

    assert executar_comando(motor, "market sell 320").splitlines() == [
        "Trade, price: 10, qty: 100",
        "Trade, price: 10, qty: 200",
        "Trade, price: 9, qty: 20",
        "ordem 4: executada, executada 320/320",
    ]


def test_limit_que_cruza_e_executada() -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    executar_comando(motor, "limit sell 20 100")

    assert executar_comando(motor, "limit buy 25 150").splitlines() == [
        "Trade, price: 20, qty: 100",
        "ordem 2: parcialmente_executada, executada 100/150",
    ]
    assert motor.melhor_compra() == 25


def test_maiusculas() -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    assert "aberta" in executar_comando(motor, "LIMIT BUY 10 5")


def test_erros() -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    assert executar_comando(motor, "limit buy abc 10") == "erro: número inválido"
    assert executar_comando(motor, "limit buy 10 1.5") == "erro: número inválido"
    assert executar_comando(motor, "limit buy 10.001 10").startswith("erro: preço")
    assert executar_comando(motor, "limit buy 10") == "erro: uso: limit <buy|sell> <price> <qty>"
    assert executar_comando(motor, "market buy 10 10") == "erro: uso: market <buy|sell> <qty>"
    assert executar_comando(motor, "market hold 10") == "erro: uso: market <buy|sell> <qty>"
    assert executar_comando(motor, "market buy 0") == "erro: quantidade deve ser positiva"
    assert executar_comando(motor, "cancelar 7") == "erro: ordem 7 não existe"
    assert executar_comando(motor, "xyz").startswith("comando não reconhecido")
    assert executar_comando(motor, "   ") == ""
