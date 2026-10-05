from matching_engine import MotorDeCasamento
from matching_engine.cli import executar_comando


def test_fluxo_basico() -> None:
    motor = MotorDeCasamento(ativo="TESTE")

    assert "aberta" in executar_comando(motor, "venda 100 10,50")
    assert "aberta" in executar_comando(motor, "compra 50 10.40")

    livro = executar_comando(motor, "livro")
    assert "VENDA" in livro
    assert "COMPRA" in livro
    assert "spread 0.10" in livro

    resposta = executar_comando(motor, "compra 30")
    assert "negócio #1: 30 @ 10.50" in resposta

    assert "cancelada" in executar_comando(motor, "cancelar 2")
    assert "#1: 30 @ 10.50" in executar_comando(motor, "negocios")


def test_erros() -> None:
    motor = MotorDeCasamento(ativo="TESTE")
    assert executar_comando(motor, "compra abc 10") == "erro: número inválido"
    assert executar_comando(motor, "compra 10 10.001").startswith("erro: preço")
    assert executar_comando(motor, "cancelar 7") == "erro: ordem 7 não existe"
    assert executar_comando(motor, "xyz").startswith("comando não reconhecido")
    assert executar_comando(motor, "   ") == ""
