# matching-engine

Matching engine simples para um único ativo. Tudo fica em memória: ordens, livro e negócios
somem quando o processo termina.

## Regras de casamento

- **Prioridade preço-tempo**: o melhor preço é executado primeiro; no mesmo preço, a ordem que
  chegou antes.
- **Preço do negócio**: o da ordem que já estava no livro (passiva).
- **Ordem limit**: ordem passiva a um preço fixo. Executa o que cruzar com o livro; o restante
  fica no livro.
- **Ordem market**: executa imediatamente no melhor preço disponível, percorrendo os níveis do
  livro; o que não encontrar contraparte é cancelado (não fica no livro).
- Preços em `Decimal`, múltiplos do tick (padrão `0.01`). Quantidades inteiras e positivas.

### Limit com preço que cruza o livro: executada, não ignorada

Uma limit de compra a um preço maior ou igual à melhor venda (ou de venda a um preço menor ou
igual à melhor compra) é **executada** contra o livro, e só o restante fica parado nele.
Motivos:

1. **É o comportamento das bolsas reais** (B3, NASDAQ, NYSE). O preço da limit é o pior preço
   que o participante aceita, não um preço exato; quem manda uma compra a 25 com venda a 20
   no livro quer comprar.
2. **O participante nunca sai prejudicado**: o negócio sai pelo preço da ordem passiva, então
   quem comprou com limite 25 paga 20.
3. **O livro nunca fica cruzado** (melhor compra sempre menor que a melhor venda). Se a ordem
   fosse colocada no livro sem executar, existiriam duas ordens dispostas a negociar entre si
   paradas, e a melhor compra/venda deixaria de fazer sentido. Ignorar a ordem evitaria isso,
   mas descartaria em silêncio uma intenção válida de negociar.

Esse invariante é verificado por um teste de propriedades (`tests/test_propriedades.py`).

### Alteração de ordem e prioridade

Uma ordem aberta pode ter o preço, a quantidade ou ambos alterados. A quantidade informada é
a nova quantidade **em aberto** (a que aparece no livro); o que já foi executado não muda.

- **Mudar o preço**: a ordem sai da fila em que estava e entra no **fim** da fila do novo
  preço, perdendo a prioridade, como se tivesse acabado de chegar.
- **Aumentar a quantidade**: também perde a prioridade. Se não perdesse, bastaria colocar uma
  ordem pequena cedo e aumentá-la depois para passar na frente de quem chegou antes.
- **Reduzir a quantidade**: mantém a posição na fila, porque não prejudica ninguém.
- Se o novo preço cruzar o livro, a ordem executa, pela mesma regra da limit nova.

É a regra usada pela B3 e pela maioria das bolsas.

## Uso

```bash
uv sync
uv run matching-engine
```

Comandos:

```
limit <buy|sell> <price> <qty>                  ordem limitada
market <buy|sell> <qty>                         ordem a mercado
cancel order <id>                               cancela uma ordem aberta
change order <id> [price <price>] [qty <qty>]   altera preço, quantidade ou ambos
book                                            mostra o livro
trades                                          lista os negócios realizados
help / exit
```

O `<id>` pode ser escrito como `identificador_1` ou só `1`. Cada negócio gera uma linha
`Trade, price: <preço>, qty: <quantidade>`.

```
>>> limit buy 10 100
Order created: buy 100 @ 10 identificador_1
>>> cancel order identificador_1
Order cancelled
>>> limit buy 10 200
Order created: buy 200 @ 10 identificador_2
>>> limit buy 9.99 100
Order created: buy 100 @ 9.99 identificador_3
>>> limit sell 10.5 100
Order created: sell 100 @ 10.5 identificador_4
>>> book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
200 @ 10            | 100 @ 10.5
100 @ 9.99          |
>>> change order identificador_2 price 9.98
Order changed: buy 200 @ 9.98 identificador_2
>>> book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
100 @ 9.99          | 100 @ 10.5
200 @ 9.98          |
>>> limit sell 20 100
Order created: sell 100 @ 20 identificador_5
>>> limit sell 20 200
Order created: sell 200 @ 20 identificador_6
>>> market buy 150
Order created: buy 150 @ market identificador_7
Trade, price: 10.5, qty: 100
Trade, price: 20, qty: 50
>>> book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
100 @ 9.99          | 50 @ 20
200 @ 9.98          | 200 @ 20
```

No `market buy 150`, a venda a 10.5 executa primeiro por ter o melhor preço, e entre as duas
vendas a 20 a ordem 5 (que chegou antes) é preenchida antes da ordem 6.

Como biblioteca:

```python
from decimal import Decimal
from matching_engine import Lado, MotorDeCasamento, TipoOrdem, visualizar_livro

motor = MotorDeCasamento(ativo="PETR4")
venda = motor.enviar_ordem(TipoOrdem.LIMITE, Lado.VENDA, 100, Decimal("38.50")).ordem
resultado = motor.enviar_ordem(TipoOrdem.MERCADO, Lado.COMPRA, 40)
print(resultado.negocios)
motor.alterar_ordem(venda.id, preco=Decimal("38.40"), quantidade=80)
print(visualizar_livro(motor))
motor.cancelar_ordem(venda.id)
```

## Estrutura

- `ordem.py`: `Lado`, `Ordem`, `Negocio` e status.
- `livro.py`: livro de ofertas; níveis de preço ordenados, cada um com uma fila FIFO.
- `motor.py`: validação, casamento, alteração e cancelamento.
- `visualizacao.py`: `visualizar_livro`, o livro em duas colunas, uma ordem por linha.
- `cli.py`: terminal interativo.

## Desenvolvimento

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy
```
