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

### Ordem pegged

Uma ordem pegged não tem preço fixo: ela acompanha o **bid** (melhor preço de compra) ou o
**offer** (melhor preço de venda), e o motor atualiza o preço dela sempre que a referência
muda.

- **Só peg bid buy e peg offer sell.** Uma venda atrelada ao bid (ou compra atrelada ao offer)
  cruzaria o livro na hora e seria, na prática, uma ordem a mercado; essas combinações são
  rejeitadas.
- **A referência é o melhor preço entre as ordens limit do lado**, não do livro todo. Se a
  pegged contasse, ela acompanharia a si mesma (e outras pegged).
- **Ao mudar de preço, a pegged mantém a prioridade da chegada original.** É o que o exemplo
  do enunciado mostra: depois do `limit buy 10.1 300`, a pegged de 150 (que chegou antes)
  fica na frente dela a 10.1. Para isso, cada lado do livro é ordenado por preço e, no
  mesmo preço, por um número de prioridade dado na chegada.
- **A reprecificação acontece ao fim de cada operação.** Uma ordem agressora executa contra o
  livro como ele estava quando ela chegou; só depois as pegged se ajustam.
- **Sem referência no envio, a ordem é rejeitada.** Se a referência some depois (não sobra
  nenhuma limit no lado), a pegged fica no último preço até aparecer uma nova referência.
- **Ela nunca agride o livro**: fica sempre no melhor preço do próprio lado, que é pior que o
  melhor preço do outro. Executa só como passiva.
- Só a quantidade pode ser alterada (o preço vem da referência), com a mesma regra de
  prioridade das outras ordens.

## Uso

```bash
uv sync
uv run matching-engine
```

Comandos:

```
limit <buy|sell> <price> <qty>                  ordem limitada
market <buy|sell> <qty>                         ordem a mercado
peg bid buy <qty>                               compra que acompanha o bid
peg offer sell <qty>                            venda que acompanha o offer
cancel order <id>                               cancela uma ordem aberta
change order <id> [price <price>] [qty <qty>]   altera preço, quantidade ou ambos
book (ou print book)                            mostra o livro
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

Ordem pegged (exemplo do enunciado):

```
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
200 @ 10            | 100 @ 10.5
100 @ 9.99          |
>>> peg bid buy 150
Order created: buy 150 @ 10 (peg bid) identificador_4
>>> limit buy 10.1 300
Order created: buy 300 @ 10.1 identificador_5
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
150 @ 10.1          | 100 @ 10.5
300 @ 10.1          |
200 @ 10            |
100 @ 9.99          |
```

Como biblioteca:

```python
from decimal import Decimal
from matching_engine import MotorDeCasamento
from matching_engine.cli import mostrar_livro

motor = MotorDeCasamento()
venda, _ = motor.enviar_limit("sell", 100, Decimal("38.50"))
compra, negocios = motor.enviar_market("buy", 40)
print(negocios)
motor.alterar(venda.id, preco=Decimal("38.40"), quantidade=80)
print(mostrar_livro(motor))
motor.cancelar(venda.id)
```

## Estrutura

- `ordem.py`: as classes `Ordem` e `Negocio`, que só guardam dados.
- `motor.py`: as regras. O livro são duas listas (`compras` e `vendas`), sempre ordenadas
  por preço e, no mesmo preço, por ordem de chegada. Aqui ficam a validação, o casamento,
  as ordens peg, a alteração e o cancelamento.
- `cli.py`: o terminal. Lê os comandos, chama o motor e formata a resposta, incluindo a
  tabela do livro (`mostrar_livro`).

## Desenvolvimento

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy
```
