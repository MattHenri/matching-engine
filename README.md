# matching-engine

Matching engine simples para um único ativo. Tudo fica em memória: ordens, livro e negócios
somem quando o processo termina.

## Regras de casamento

- **Prioridade preço-tempo**: o melhor preço é executado primeiro; no mesmo preço, a ordem que
  chegou antes.
- **Preço do negócio**: o da ordem que já estava no livro (passiva).
- **Ordem limitada**: executa o que cruzar com o livro; o restante fica no livro.
- **Ordem a mercado**: executa contra o que houver no livro; o restante é cancelado.
- Preços em `Decimal`, múltiplos do tick (padrão `0.01`). Quantidades inteiras e positivas.

## Uso

```bash
uv sync
uv run matching-engine
```

```
> venda 100 10.50
ordem 1 (venda, limite): aberta, executada 0/100
> compra 30
ordem 2 (compra, mercado): executada, executada 30/30
  negócio #1: 30 @ 10.50
> livro
livro ATIVO
  VENDA       10.50       70 (1)
  ---------- spread -
```

Como biblioteca:

```python
from decimal import Decimal
from matching_engine import Lado, MotorDeCasamento

motor = MotorDeCasamento(ativo="PETR4")
motor.enviar_ordem_limitada(Lado.VENDA, 100, Decimal("38.50"))
resultado = motor.enviar_ordem_a_mercado(Lado.COMPRA, 40)
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
