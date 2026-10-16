"""Terminal pra usar a matching engine digitando comandos."""

from decimal import Decimal, InvalidOperation
from itertools import zip_longest

from matching_engine.motor import ErroDeOrdem, MotorDeCasamento
from matching_engine.ordem import Negocio, Ordem

AJUDA = """\
comandos:
  limit <buy|sell> <price> <qty>                  ordem limitada
  market <buy|sell> <qty>                         ordem a mercado
  peg bid buy <qty>                               compra que acompanha o bid
  peg offer sell <qty>                            venda que acompanha o offer
  cancel order <id>                               cancela uma ordem aberta
  change order <id> [price <price>] [qty <qty>]   altera preço, quantidade ou os dois
  book (ou print book)                            mostra o livro de ofertas
  trades                                          lista os negócios feitos
  help                                            mostra esta ajuda
  exit                                            sai

o <id> pode ser identificador_1 ou só 1.
no change, qty é a nova quantidade em aberto. na peg só dá pra mudar a qty."""

USO_LIMIT = "erro: uso: limit <buy|sell> <price> <qty>"
USO_MARKET = "erro: uso: market <buy|sell> <qty>"
USO_PEG = "erro: uso: peg <bid|offer> <buy|sell> <qty>"
USO_CANCEL = "erro: uso: cancel order <id>"
USO_CHANGE = "erro: uso: change order <id> [price <price>] [qty <qty>]"

BOM = chr(0xFEFF)  # caractere invisível que o PowerShell manda no começo quando usa pipe


# ---------- conversão de texto ----------


def nome_da_ordem(id_ordem: int) -> str:
    return f"identificador_{id_ordem}"


def ler_id(texto: str) -> int:
    return int(texto.replace("identificador_", ""))


def ler_preco(texto: str) -> Decimal:
    return Decimal(texto.replace(",", "."))  # aceita 10,5 e 10.5


# ---------- formatação da saída ----------


def texto_ordem(ordem: Ordem, quantidade: int) -> str:
    if ordem.tipo == "market":
        preco = "market"
    elif ordem.tipo == "peg":
        preco = f"{ordem.preco} (peg {ordem.referencia})"
    else:
        preco = str(ordem.preco)
    return f"{ordem.lado} {quantidade} @ {preco} {nome_da_ordem(ordem.id)}"


def texto_trade(negocio: Negocio) -> str:
    return f"Trade, price: {negocio.preco}, qty: {negocio.quantidade}"


def mostrar_livro(motor: MotorDeCasamento) -> str:
    """Livro em duas colunas, uma ordem por linha, do melhor preço pro pior."""
    linhas = ["Ordens de Compra    | Ordens de Venda", "--------------------|-----------------"]
    # zip_longest anda nas duas listas juntas e completa a menor com None
    for compra, venda in zip_longest(motor.compras, motor.vendas):
        esquerda = f"{compra.restante} @ {compra.preco}" if compra else ""
        direita = f"{venda.restante} @ {venda.preco}" if venda else ""
        linhas.append(f"{esquerda:<20}| {direita}".rstrip())
    return "\n".join(linhas)


def mostrar_negocios(motor: MotorDeCasamento) -> str:
    if not motor.negocios:
        return "nenhum negócio"
    linhas = []
    for n in motor.negocios:
        linhas.append(
            f"  #{n.id} {texto_trade(n)} (buy {nome_da_ordem(n.id_compra)}, "
            f"sell {nome_da_ordem(n.id_venda)}, agressor {n.agressor})"
        )
    return "\n".join(linhas)


def resposta_de_envio(ordem: Ordem, negocios: list[Negocio]) -> str:
    linhas = [f"Order created: {texto_ordem(ordem, ordem.quantidade)}"]
    for negocio in negocios:
        linhas.append(texto_trade(negocio))
    if ordem.tipo == "market" and ordem.cancelada:
        sobra = ordem.quantidade - ordem.executada
        linhas.append(f"Order cancelled: qty {sobra} sem contraparte")
    return "\n".join(linhas)


# ---------- comandos ----------


def executar_comando(motor: MotorDeCasamento, linha: str) -> str:
    """Lê uma linha digitada, chama o motor e devolve o texto da resposta."""
    partes = linha.replace(BOM, "").lower().split()
    if not partes:
        return ""
    try:
        return _executar(motor, partes, linha)
    except ErroDeOrdem as erro:
        return f"erro: {erro}"
    except (ValueError, InvalidOperation):  # int() ou Decimal() com texto que não é número
        return "erro: número inválido"


def _executar(motor: MotorDeCasamento, p: list[str], linha: str) -> str:
    comando = p[0]

    if comando == "limit":
        if len(p) != 4 or p[1] not in ("buy", "sell"):
            return USO_LIMIT
        ordem, negocios = motor.enviar_limit(p[1], int(p[3]), ler_preco(p[2]))
        return resposta_de_envio(ordem, negocios)

    if comando == "market":
        if len(p) != 3 or p[1] not in ("buy", "sell"):
            return USO_MARKET
        ordem, negocios = motor.enviar_market(p[1], int(p[2]))
        return resposta_de_envio(ordem, negocios)

    if comando == "peg":
        if len(p) != 4 or p[1] not in ("bid", "offer") or p[2] not in ("buy", "sell"):
            return USO_PEG
        ordem, negocios = motor.enviar_peg(p[1], p[2], int(p[3]))
        return resposta_de_envio(ordem, negocios)

    if comando == "cancel":
        if len(p) != 3 or p[1] != "order":
            return USO_CANCEL
        motor.cancelar(ler_id(p[2]))
        return "Order cancelled"

    if comando == "change":
        # change order <id> seguido de "price <p>", "qty <q>" ou os dois, em qualquer ordem
        if len(p) not in (5, 7) or p[1] != "order":
            return USO_CHANGE
        campos = dict(zip(p[3::2], p[4::2], strict=True))  # ex.: {"price": "9.98", "qty": "50"}
        if len(campos) != (len(p) - 3) // 2 or not set(campos) <= {"price", "qty"}:
            return USO_CHANGE  # campo repetido ou com nome errado
        preco = ler_preco(campos["price"]) if "price" in campos else None
        quantidade = int(campos["qty"]) if "qty" in campos else None
        ordem, negocios = motor.alterar(ler_id(p[2]), preco, quantidade)
        # mostra a quantidade que a ordem tinha logo depois da alteração (antes dos trades)
        executado_agora = sum(n.quantidade for n in negocios)
        linhas = [f"Order changed: {texto_ordem(ordem, ordem.restante + executado_agora)}"]
        for negocio in negocios:
            linhas.append(texto_trade(negocio))
        return "\n".join(linhas)

    if p in (["book"], ["print", "book"], ["livro"]):
        return mostrar_livro(motor)
    if p in (["trades"], ["negocios"]):
        return mostrar_negocios(motor)
    if comando in ("help", "ajuda"):
        return AJUDA
    return f"comando não reconhecido: {linha.strip()!r} (digite 'help')"


def main() -> None:
    motor = MotorDeCasamento()
    print(f"matching engine (tick {motor.tick}). Digite 'help' pra ver os comandos.")
    while True:
        try:
            linha = input(">>> ")
        except (EOFError, KeyboardInterrupt):  # Ctrl+C ou fim da entrada
            print()
            break
        if linha.strip().lower() in ("exit", "sair"):
            break
        resposta = executar_comando(motor, linha)
        if resposta:
            print(resposta)


if __name__ == "__main__":
    main()
