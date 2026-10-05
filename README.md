# matching-engine

[![CI](https://github.com/MattHenri/matching-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/MattHenri/matching-engine/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-0E7490)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-0E7490)](LICENSE)
![Status: estudo](https://img.shields.io/badge/status-projeto%20de%20estudo-0E7490)

Motor de casamento de ordens (matching engine) para um único ativo, com prioridade preço-tempo, escrito em Python puro e sem dependências.

<!-- TODO: gravar um GIF curto do terminal (ex.: com asciinema + agg ou ScreenToGif) rodando a sessão de exemplo abaixo e colocar aqui. -->

## O problema

Toda bolsa tem, no centro, um motor que recebe ordens de compra e venda, decide quem negocia com quem e a que preço, e mantém o livro de ofertas com o que sobrou. Este projeto implementa esse núcleo de forma pequena e legível, para estudar as regras de casamento e garantir com testes que elas nunca são violadas.

Tudo fica em memória: ordens, livro e negócios somem quando o processo termina.

## Regras de casamento

- **Prioridade preço-tempo**: o melhor preço é executado primeiro; no mesmo preço, a ordem que chegou antes.
- **Preço do negócio**: o da ordem que já estava no livro (passiva).
- **Ordem limitada**: executa o que cruzar com o livro; o restante fica no livro.
- **Ordem a mercado**: executa contra o que houver no livro; o restante é cancelado.
- **Cancelamento** de ordens limitadas abertas ou parcialmente executadas.
- Preços em `Decimal`, múltiplos do tick (padrão `0.01`). Quantidades inteiras e positivas.

## Como rodar

Requer [uv](https://docs.astral.sh/uv/) e Python 3.12+.

```bash
uv sync
uv run matching-engine
```

Comandos: `compra <qtd> [preço]`, `venda <qtd> [preço]` (sem preço, a ordem é a mercado), `cancelar <id>`, `livro`, `negocios`, `ajuda` e `sair`.

```
> venda 100 10.50
ordem 1 (venda, limite): aberta, executada 0/100
> venda 50 10.52
ordem 2 (venda, limite): aberta, executada 0/50
> compra 200 10.48
ordem 3 (compra, limite): aberta, executada 0/200
> compra 120
ordem 4 (compra, mercado): executada, executada 120/120
  negócio #1: 100 @ 10.50
  negócio #2: 20 @ 10.52
> livro
livro ATIVO
  VENDA       10.52       30 (1)
  ---------- spread 0.04
  COMPRA      10.48      200 (1)
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

## Stack

- Python 3.12, só biblioteca padrão
- pytest e [Hypothesis](https://hypothesis.readthedocs.io/) (testes baseados em propriedades)
- ruff (lint e formatação) e mypy em modo `strict`
- uv para ambiente e empacotamento; GitHub Actions para CI

## Decisões técnicas

- **`Decimal` em vez de `float`**: preço com erro de arredondamento quebra a comparação de níveis e a validação do tick.
- **Livro em níveis de preço com fila FIFO**: cada lado guarda um `dict` de preço → `deque` de ordens e uma lista de preços ordenada (`bisect.insort`) do melhor para o pior. Consultar a melhor ordem é O(1); criar ou remover um nível é O(n) no número de níveis, aceitável para um ativo.
- **ID sequencial como prioridade de tempo**: dispensa relógio e torna o comportamento determinístico e fácil de testar.
- **Motor separado da interface**: `motor.py` não sabe nada do terminal; `cli.py` só traduz comandos, o que permite usar o motor como biblioteca.
- **Testes de propriedade**: o Hypothesis gera sequências aleatórias de ordens e cancelamentos e verifica invariantes a cada passo, como livro nunca cruzado, quantidade negociada igual nos dois lados, nenhuma ordem executada além do total e negócios sempre dentro do limite de preço de cada ordem.

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

## Próximos passos

- Ordens com validade (ex.: IOC e FOK) e alteração de preço/quantidade.
- Vários ativos, cada um com seu livro.
- Benchmark de throughput (ordens por segundo).

## Licença

[MIT](LICENSE)
