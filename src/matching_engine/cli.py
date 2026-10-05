"""Terminal interativo para enviar ordens e ver o livro."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from matching_engine.motor import ErroDeOrdem, MotorDeCasamento
from matching_engine.ordem import Lado, Negocio, Ordem, TipoOrdem
from matching_engine.visualizacao import visualizar_livro

TIPOS = {"limit": TipoOrdem.LIMITE, "market": TipoOrdem.MERCADO}
LADOS = {"buy": Lado.COMPRA, "sell": Lado.VENDA}
NOMES_LADO = {Lado.COMPRA: "buy", Lado.VENDA: "sell"}
PREFIXO_ID = "identificador_"

AJUDA = """\
comandos:
  limit <buy|sell> <price> <qty>                     ordem limitada
  market <buy|sell> <qty>                            ordem a mercado
  cancel order <id>                                  cancela uma ordem aberta
  change order <id> [price <price>] [qty <qty>]      altera preço, quantidade ou ambos
  book                                               mostra o livro de ofertas
  trades                                             lista os negócios realizados
  help                                               mostra esta ajuda
  exit                                               encerra

<id> pode ser escrito como identificador_1 ou só 1.
Em change, qty é a nova quantidade em aberto."""

USO_LIMIT = "erro: uso: limit <buy|sell> <price> <qty>"
USO_MARKET = "erro: uso: market <buy|sell> <qty>"
USO_CANCEL = "erro: uso: cancel order <id>"
USO_CHANGE = "erro: uso: change order <id> [price <price>] [qty <qty>]"


def formatar_id(id_ordem: int) -> str:
    return f"{PREFIXO_ID}{id_ordem}"


def _ler_id(texto: str) -> int:
    return int(texto.removeprefix(PREFIXO_ID))


def _ler_preco(texto: str) -> Decimal:
    return Decimal(texto.replace(",", "."))


def formatar_negocio(negocio: Negocio) -> str:
    return f"Trade, price: {negocio.preco}, qty: {negocio.quantidade}"


def _formatar_ordem(ordem: Ordem, quantidade: int) -> str:
    preco = "market" if ordem.preco is None else ordem.preco
    return f"{NOMES_LADO[ordem.lado]} {quantidade} @ {preco} {formatar_id(ordem.id)}"


def formatar_negocios(motor: MotorDeCasamento) -> str:
    if not motor.negocios:
        return "nenhum negócio"
    return "\n".join(
        f"  #{n.id} {formatar_negocio(n)} (buy {formatar_id(n.id_ordem_compra)}, "
        f"sell {formatar_id(n.id_ordem_venda)}, agressor {NOMES_LADO[n.lado_agressor]})"
        for n in motor.negocios
    )


def _enviar(motor: MotorDeCasamento, tipo: TipoOrdem, args: list[str]) -> str:
    esperados = 3 if tipo is TipoOrdem.LIMITE else 2
    if len(args) != esperados or args[0].lower() not in LADOS:
        return USO_LIMIT if tipo is TipoOrdem.LIMITE else USO_MARKET
    lado = LADOS[args[0].lower()]
    quantidade = int(args[-1])
    preco = _ler_preco(args[1]) if tipo is TipoOrdem.LIMITE else None

    resultado = motor.enviar_ordem(tipo, lado, quantidade, preco)
    ordem = resultado.ordem
    linhas = [f"Order created: {_formatar_ordem(ordem, ordem.quantidade)}"]
    linhas += [formatar_negocio(n) for n in resultado.negocios]
    if tipo is TipoOrdem.MERCADO and ordem.quantidade_executada < ordem.quantidade:
        sobra = ordem.quantidade - ordem.quantidade_executada
        linhas.append(f"Order cancelled: qty {sobra} sem contraparte")
    return "\n".join(linhas)


def _cancelar(motor: MotorDeCasamento, args: list[str]) -> str:
    if len(args) != 2 or args[0].lower() != "order":
        return USO_CANCEL
    motor.cancelar_ordem(_ler_id(args[1]))
    return "Order cancelled"


def _alterar(motor: MotorDeCasamento, args: list[str]) -> str:
    # change order <id> [price <p>] [qty <q>], com price e qty em qualquer ordem
    if len(args) not in (4, 6) or args[0].lower() != "order":
        return USO_CHANGE
    campos = {chave.lower(): valor for chave, valor in zip(args[2::2], args[3::2], strict=True)}
    if not campos.keys() <= {"price", "qty"} or len(campos) != (len(args) - 2) // 2:
        return USO_CHANGE

    preco = _ler_preco(campos["price"]) if "price" in campos else None
    quantidade = int(campos["qty"]) if "qty" in campos else None
    resultado = motor.alterar_ordem(_ler_id(args[1]), preco=preco, quantidade=quantidade)

    ordem = resultado.ordem
    executado_agora = sum(n.quantidade for n in resultado.negocios)
    linhas = [
        f"Order changed: {_formatar_ordem(ordem, ordem.quantidade_restante + executado_agora)}"
    ]
    linhas += [formatar_negocio(n) for n in resultado.negocios]
    return "\n".join(linhas)


def executar_comando(motor: MotorDeCasamento, linha: str) -> str:  # noqa: PLR0911
    """Interpreta uma linha de comando e devolve o texto da resposta."""
    partes = linha.lstrip("﻿").split()  # BOM que o pipe do PowerShell envia
    if not partes:
        return ""
    comando, args = partes[0].lower(), partes[1:]
    try:
        if comando in TIPOS:
            return _enviar(motor, TIPOS[comando], args)
        if comando == "cancel":
            return _cancelar(motor, args)
        if comando == "change":
            return _alterar(motor, args)
        if comando in ("book", "livro") and not args:
            return visualizar_livro(motor)
        if comando in ("trades", "negocios") and not args:
            return formatar_negocios(motor)
        if comando in ("help", "ajuda"):
            return AJUDA
    except ErroDeOrdem as erro:
        return f"erro: {erro}"
    except (ValueError, InvalidOperation):
        return "erro: número inválido"
    return f"comando não reconhecido: {linha.strip()!r} (digite 'help')"


def main() -> None:
    motor = MotorDeCasamento(ativo="ATIVO")
    print(f"matching engine — ativo {motor.ativo}, tick {motor.tick}. Digite 'help'.")
    while True:
        try:
            linha = input(">>> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if linha.strip().lower() in ("exit", "sair"):
            break
        if resposta := executar_comando(motor, linha):
            print(resposta)


if __name__ == "__main__":
    main()
