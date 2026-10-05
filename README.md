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

## Uso

```bash
uv sync
uv run matching-engine
```

Entrada:

```
limit <buy|sell> <price> <qty>
market <buy|sell> <qty>
```

Cada negócio realizado gera uma linha `Trade, price: <preço>, qty: <quantidade>`, seguida do
estado da ordem enviada (o id serve para `cancelar <id>`):

```
> limit buy 10 100
ordem 1: aberta, executada 0/100
> limit buy 10 200
ordem 2: aberta, executada 0/200
> limit sell 20 100
ordem 3: aberta, executada 0/100
> market sell 150
Trade, price: 10, qty: 100
Trade, price: 10, qty: 50
ordem 4: executada, executada 150/150
> limit buy 25 150
Trade, price: 20, qty: 100
ordem 5: parcialmente_executada, executada 100/150
> livro
livro ATIVO
  ---------- spread -
  BUY          25       50 (1)
  BUY          10      150 (1)
```

Outros comandos: `cancelar <id>`, `livro`, `negocios`, `ajuda`, `sair`.

Como biblioteca:

```python
from decimal import Decimal
from matching_engine import Lado, MotorDeCasamento, TipoOrdem

motor = MotorDeCasamento(ativo="PETR4")
motor.enviar_ordem(TipoOrdem.LIMITE, Lado.VENDA, 100, Decimal("38.50"))
resultado = motor.enviar_ordem(TipoOrdem.MERCADO, Lado.COMPRA, 40)
print(resultado.negocios)
print(motor.profundidade())
```

## Estrutura

- `ordem.py`: `Lado`, `Ordem`, `Negocio` e status.
- `livro.py`: livro de ofertas; níveis de preço ordenados, cada um com uma fila FIFO.
- `motor.py`: validação, casamento e cancelamento.
- `cli.py`: terminal interativo.

## Desenvolvimento

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy
```
