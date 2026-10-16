from matching_engine import MotorDeCasamento
from matching_engine.cli import executar_comando


def rodar(motor: MotorDeCasamento, linha: str) -> list[str]:
    return executar_comando(motor, linha).splitlines()


CABECALHO = ["Ordens de Compra    | Ordens de Venda", "--------------------|-----------------"]


# ---------- livro ----------


def test_livro_vazio() -> None:
    assert rodar(MotorDeCasamento(), "book") == CABECALHO


def test_livro_com_mais_vendas_que_compras() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit sell 11 5")
    rodar(motor, "limit sell 12 7")
    assert rodar(motor, "book")[2:] == [
        "                    | 5 @ 11",
        "                    | 7 @ 12",
    ]


# ---------- criar e cancelar ----------


def test_criar_e_cancelar_exemplo_do_enunciado() -> None:
    motor = MotorDeCasamento()
    assert rodar(motor, "limit buy 10 100") == ["Order created: buy 100 @ 10 identificador_1"]
    assert rodar(motor, "cancel order identificador_1") == ["Order cancelled"]
    assert motor.melhor_compra() is None


def test_cancelar_pelo_numero() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit sell 10 100")
    assert rodar(motor, "cancel order 1") == ["Order cancelled"]


def test_trades_respeitam_a_ordem_de_chegada() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit sell 20 100")
    rodar(motor, "limit sell 20 200")

    assert rodar(motor, "market buy 150") == [
        "Order created: buy 150 @ market identificador_3",
        "Trade, price: 20, qty: 100",
        "Trade, price: 20, qty: 50",
    ]


def test_market_sem_contraparte_suficiente() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit buy 10 100")

    assert rodar(motor, "market sell 130") == [
        "Order created: sell 130 @ market identificador_2",
        "Trade, price: 10, qty: 100",
        "Order cancelled: qty 30 sem contraparte",
    ]


def test_limit_que_cruza_e_executada() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit sell 20 100")

    assert rodar(motor, "limit buy 25 150") == [
        "Order created: buy 150 @ 25 identificador_2",
        "Trade, price: 20, qty: 100",
    ]
    assert motor.melhor_compra() == 25


# ---------- alterar ----------


def test_alterar_exemplo_do_enunciado() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit buy 10 200")
    rodar(motor, "limit buy 9.99 100")
    rodar(motor, "limit sell 10.5 100")
    assert rodar(motor, "book") == [
        *CABECALHO,
        "200 @ 10            | 100 @ 10.5",
        "100 @ 9.99          |",
    ]

    assert rodar(motor, "change order identificador_1 price 9.98") == [
        "Order changed: buy 200 @ 9.98 identificador_1"
    ]
    assert rodar(motor, "book")[2:] == ["100 @ 9.99          | 100 @ 10.5", "200 @ 9.98          |"]


def test_alterar_quantidade_e_preco_em_qualquer_ordem() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit buy 10 200")
    assert rodar(motor, "change order 1 qty 50") == ["Order changed: buy 50 @ 10 identificador_1"]
    assert rodar(motor, "change order 1 qty 70 price 11") == [
        "Order changed: buy 70 @ 11 identificador_1"
    ]


def test_alterar_preco_que_cruza_mostra_os_trades() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit sell 20 30")
    rodar(motor, "limit buy 10 100")

    assert rodar(motor, "change order 2 price 21") == [
        "Order changed: buy 100 @ 21 identificador_2",
        "Trade, price: 20, qty: 30",
    ]
    assert rodar(motor, "book")[2:] == ["70 @ 21             |"]


# ---------- peg ----------


def test_peg_exemplo_do_enunciado() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit buy 10 200")
    rodar(motor, "limit buy 9.99 100")
    rodar(motor, "limit sell 10.5 100")

    assert rodar(motor, "peg bid buy 150") == [
        "Order created: buy 150 @ 10 (peg bid) identificador_4"
    ]
    assert rodar(motor, "print book") == [
        *CABECALHO,
        "200 @ 10            | 100 @ 10.5",
        "150 @ 10            |",
        "100 @ 9.99          |",
    ]

    rodar(motor, "limit buy 10.1 300")
    assert rodar(motor, "print book")[2:] == [
        "150 @ 10.1          | 100 @ 10.5",
        "300 @ 10.1          |",
        "200 @ 10            |",
        "100 @ 9.99          |",
    ]


def test_peg_offer() -> None:
    motor = MotorDeCasamento()
    rodar(motor, "limit sell 10.5 100")
    assert rodar(motor, "peg offer sell 30") == [
        "Order created: sell 30 @ 10.5 (peg offer) identificador_2"
    ]


def test_peg_erros() -> None:
    motor = MotorDeCasamento()
    assert rodar(motor, "peg bid buy 10") == ["erro: não há bid no livro para acompanhar"]
    rodar(motor, "limit buy 10 100")
    assert rodar(motor, "peg bid sell 10") == [
        "erro: só existe peg bid buy e peg offer sell (o contrário cruzaria o livro)"
    ]
    assert rodar(motor, "peg bid buy") == ["erro: uso: peg <bid|offer> <buy|sell> <qty>"]
    assert rodar(motor, "peg mid buy 10") == ["erro: uso: peg <bid|offer> <buy|sell> <qty>"]
    rodar(motor, "peg bid buy 10")
    assert rodar(motor, "change order 2 price 9") == [
        "erro: o preço da peg segue a referência, só dá pra mudar a quantidade"
    ]
    assert rodar(motor, "change order 2 qty 5") == [
        "Order changed: buy 5 @ 10 (peg bid) identificador_2"
    ]


# ---------- outros comandos ----------


def test_trades_e_nomes_em_portugues() -> None:
    motor = MotorDeCasamento()
    assert rodar(motor, "trades") == ["nenhum negócio"]
    rodar(motor, "limit sell 20 30")
    rodar(motor, "market buy 10")
    assert rodar(motor, "negocios") == [
        "  #1 Trade, price: 20, qty: 10 (buy identificador_2, sell identificador_1, agressor buy)"
    ]
    assert rodar(motor, "livro") == rodar(motor, "book")
    assert rodar(motor, "ajuda") == rodar(motor, "help")


def test_maiusculas() -> None:
    motor = MotorDeCasamento()
    assert rodar(motor, "LIMIT BUY 10 5") == ["Order created: buy 5 @ 10 identificador_1"]


def test_bom_do_powershell_e_ignorado() -> None:
    motor = MotorDeCasamento()
    assert rodar(motor, chr(0xFEFF) + "limit buy 10 5") == [
        "Order created: buy 5 @ 10 identificador_1"
    ]


def test_erros() -> None:
    motor = MotorDeCasamento()
    erros = {
        "limit buy abc 10": "erro: número inválido",
        "limit buy 10 1.5": "erro: número inválido",
        "limit buy 10": "erro: uso: limit <buy|sell> <price> <qty>",
        "market buy 10 10": "erro: uso: market <buy|sell> <qty>",
        "market hold 10": "erro: uso: market <buy|sell> <qty>",
        "market buy 0": "erro: quantidade deve ser um inteiro positivo",
        "cancel order 7": "erro: ordem 7 não existe",
        "cancel 7": "erro: uso: cancel order <id>",
        "cancel order identificador_x": "erro: número inválido",
        "change order 1": "erro: uso: change order <id> [price <price>] [qty <qty>]",
        "change order 1 size 10": "erro: uso: change order <id> [price <price>] [qty <qty>]",
        "change order 1 qty 1 qty 2": "erro: uso: change order <id> [price <price>] [qty <qty>]",
        "change order 7 qty 10": "erro: ordem 7 não existe",
        "xyz": "comando não reconhecido: 'xyz' (digite 'help')",
        "   ": "",
    }
    for linha, esperado in erros.items():
        assert executar_comando(motor, linha) == esperado, linha
    assert executar_comando(motor, "limit buy 10.001 10").startswith("erro: preço")
