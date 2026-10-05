"""Terminal interativo para enviar ordens e ver o livro."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from matching_engine.motor import ErroDeOrdem, MotorDeCasamento, ResultadoEnvio
from matching_engine.ordem import Lado, Negocio, TipoOrdem

TIPOS = {"limit": TipoOrdem.LIMITE, "market": TipoOrdem.MERCADO}
LADOS = {"buy": Lado.COMPRA, "sell": Lado.VENDA}

AJUDA = """\
comandos:
  limit <buy|sell> <price> <qty>   ordem limitada
  market <buy|sell> <qty>          ordem a mercado
  cancelar <id>                    cancela uma ordem aberta
  livro                            mostra o livro de ofertas
  negocios                         lista os negócios realizados
  ajuda                            mostra esta ajuda
  sair                             encerra"""


def formatar_negocio(negocio: Negocio) -> str:
    return f"Trade, price: {negocio.preco}, qty: {negocio.quantidade}"


def formatar_livro(motor: MotorDeCasamento) -> str:
    prof = motor.profundidade()
    linhas = [f"livro {motor.ativo}"]
    linhas += [
        f"  SELL {n.preco:>10} {n.quantidade:>8} ({n.ordens})" for n in reversed(prof.vendas)
    ]
    compra, venda = motor.melhor_compra(), motor.melhor_venda()
    spread = f"spread {venda - compra}" if compra is not None and venda is not None else "spread -"
    linhas.append(f"  {'-' * 10} {spread}")
    linhas += [f"  BUY  {n.preco:>10} {n.quantidade:>8} ({n.ordens})" for n in prof.compras]
    return "\n".join(linhas)


def formatar_negocios(motor: MotorDeCasamento) -> str:
    if not motor.negocios:
        return "nenhum negócio"
    return "\n".join(
        f"  #{n.id} {formatar_negocio(n)} "
        f"(buy {n.id_ordem_compra}, sell {n.id_ordem_venda}, agressor {n.lado_agressor})"
        for n in motor.negocios
    )


def _formatar_resultado(resultado: ResultadoEnvio) -> str:
    o = resultado.ordem
    linhas = [formatar_negocio(n) for n in resultado.negocios]
    linhas.append(f"ordem {o.id}: {o.status}, executada {o.quantidade_executada}/{o.quantidade}")
    return "\n".join(linhas)


def _enviar(motor: MotorDeCasamento, tipo: TipoOrdem, args: list[str]) -> str:
    esperados = 3 if tipo is TipoOrdem.LIMITE else 2
    if len(args) != esperados or args[0].lower() not in LADOS:
        uso = "limit <buy|sell> <price> <qty>" if esperados == 3 else "market <buy|sell> <qty>"
        return f"erro: uso: {uso}"
    lado = LADOS[args[0].lower()]
    quantidade = int(args[-1])
    preco = Decimal(args[1].replace(",", ".")) if tipo is TipoOrdem.LIMITE else None
    return _formatar_resultado(motor.enviar_ordem(tipo, lado, quantidade, preco))


def executar_comando(motor: MotorDeCasamento, linha: str) -> str:  # noqa: PLR0911
    """Interpreta uma linha de comando e devolve o texto da resposta."""
    partes = linha.lstrip("﻿").split()  # BOM que o pipe do PowerShell envia
    if not partes:
        return ""
    comando, args = partes[0].lower(), partes[1:]
    try:
        if comando in TIPOS:
            return _enviar(motor, TIPOS[comando], args)
        if comando == "cancelar" and len(args) == 1:
            ordem = motor.cancelar_ordem(int(args[0]))
            return f"ordem {ordem.id} cancelada"
        if comando == "livro" and not args:
            return formatar_livro(motor)
        if comando == "negocios" and not args:
            return formatar_negocios(motor)
        if comando == "ajuda":
            return AJUDA
    except ErroDeOrdem as erro:
        return f"erro: {erro}"
    except (ValueError, InvalidOperation):
        return "erro: número inválido"
    return f"comando não reconhecido: {linha.strip()!r} (digite 'ajuda')"


def main() -> None:
    motor = MotorDeCasamento(ativo="ATIVO")
    print(f"matching engine — ativo {motor.ativo}, tick {motor.tick}. Digite 'ajuda'.")
    while True:
        try:
            linha = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if linha.strip().lower() == "sair":
            break
        if resposta := executar_comando(motor, linha):
            print(resposta)


if __name__ == "__main__":
    main()
