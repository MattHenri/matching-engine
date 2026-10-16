"""Matching engine: recebe as ordens, monta o livro e gera os negócios."""

from decimal import Decimal

from matching_engine.ordem import Negocio, Ordem


class ErroDeOrdem(Exception):
    """Erro de ordem inválida. O terminal mostra a mensagem pro usuário."""


class MotorDeCasamento:
    def __init__(self, tick: Decimal = Decimal("0.01")) -> None:
        self.tick = tick  # menor variação de preço aceita
        self.compras: list[Ordem] = []  # sempre ordenadas: maior preço primeiro
        self.vendas: list[Ordem] = []  # sempre ordenadas: menor preço primeiro
        self.ordens: dict[int, Ordem] = {}  # todas as ordens que já chegaram, pelo id
        self.negocios: list[Negocio] = []
        self._contador_prioridade = 0

    # ---------- enviar ordens ----------

    def enviar_limit(
        self, lado: str, quantidade: int, preco: Decimal
    ) -> tuple[Ordem, list[Negocio]]:
        self._validar_quantidade(quantidade)
        self._validar_preco(preco)
        ordem = self._criar_ordem(lado, "limit", quantidade, preco)
        # se o preço já cruza o livro, executa (como numa bolsa de verdade)
        negocios = self._casar(ordem)
        if ordem.restante > 0:
            self._colocar_no_livro(ordem)  # o que sobrou fica esperando no livro
        self._atualizar_pegs()
        return ordem, negocios

    def enviar_market(self, lado: str, quantidade: int) -> tuple[Ordem, list[Negocio]]:
        self._validar_quantidade(quantidade)
        ordem = self._criar_ordem(lado, "market", quantidade, Decimal(0))
        negocios = self._casar(ordem)
        if ordem.restante > 0:
            ordem.cancelada = True  # market não fica no livro, o que sobrou é cancelado
        self._atualizar_pegs()
        return ordem, negocios

    def enviar_peg(
        self, referencia: str, lado: str, quantidade: int
    ) -> tuple[Ordem, list[Negocio]]:
        self._validar_quantidade(quantidade)
        # peg bid sell (ou peg offer buy) cruzaria o livro na hora, aí seria uma market
        if (referencia, lado) not in (("bid", "buy"), ("offer", "sell")):
            raise ErroDeOrdem(
                "só existe peg bid buy e peg offer sell (o contrário cruzaria o livro)"
            )
        preco = self._melhor_limit(lado)
        if preco is None:
            raise ErroDeOrdem(f"não há {referencia} no livro para acompanhar")
        ordem = self._criar_ordem(lado, "peg", quantidade, preco, referencia)
        self._colocar_no_livro(ordem)  # a peg nunca cruza, então vai direto pro livro
        return ordem, []

    # ---------- cancelar e alterar ----------

    def cancelar(self, id_ordem: int) -> Ordem:
        ordem = self._buscar_ordem_aberta(id_ordem)
        self._lado_do_livro(ordem.lado).remove(ordem)
        ordem.cancelada = True
        self._atualizar_pegs()
        return ordem

    def alterar(
        self, id_ordem: int, preco: Decimal | None = None, quantidade: int | None = None
    ) -> tuple[Ordem, list[Negocio]]:
        """Muda o preço e/ou a quantidade em aberto de uma ordem.

        Mudar o preço ou aumentar a quantidade faz a ordem ir pro fim da fila.
        Só diminuir a quantidade mantém o lugar dela.
        """
        if preco is None and quantidade is None:
            raise ErroDeOrdem("informe o novo preço, a nova quantidade ou os dois")
        if preco is not None:
            self._validar_preco(preco)
        if quantidade is not None:
            self._validar_quantidade(quantidade)
        ordem = self._buscar_ordem_aberta(id_ordem)
        if ordem.tipo == "peg" and preco is not None:
            raise ErroDeOrdem("o preço da peg segue a referência, só dá pra mudar a quantidade")

        novo_preco = ordem.preco if preco is None else preco
        nova_quantidade = ordem.restante if quantidade is None else quantidade
        perde_prioridade = novo_preco != ordem.preco or nova_quantidade > ordem.restante
        ordem.quantidade = ordem.executada + nova_quantidade  # o que já executou não muda

        if not perde_prioridade:
            return ordem, []

        # tira do livro e trata como se fosse uma ordem nova (pode até executar)
        self._lado_do_livro(ordem.lado).remove(ordem)
        ordem.preco = novo_preco
        ordem.prioridade = self._nova_prioridade()
        negocios = self._casar(ordem)
        if ordem.restante > 0:
            self._colocar_no_livro(ordem)
        self._atualizar_pegs()
        return ordem, negocios

    # ---------- consultas ----------

    def melhor_compra(self) -> Decimal | None:
        return self.compras[0].preco if self.compras else None

    def melhor_venda(self) -> Decimal | None:
        return self.vendas[0].preco if self.vendas else None

    # ---------- casamento ----------

    def _casar(self, ordem: Ordem) -> list[Negocio]:
        """Executa a ordem contra o outro lado do livro enquanto o preço permitir."""
        outro_lado = self.vendas if ordem.lado == "buy" else self.compras
        negocios = []

        while ordem.restante > 0 and outro_lado:
            melhor = outro_lado[0]  # a lista está ordenada, então a primeira é a melhor
            if not self._cruza(ordem, melhor.preco):
                break

            quantidade = min(ordem.restante, melhor.restante)
            ordem.executada += quantidade
            melhor.executada += quantidade
            if melhor.restante == 0:
                outro_lado.pop(0)

            if ordem.lado == "buy":
                compra, venda = ordem, melhor
            else:
                compra, venda = melhor, ordem
            # o negócio sai pelo preço de quem já estava no livro
            negocio = Negocio(
                id=len(self.negocios) + 1,
                preco=melhor.preco,
                quantidade=quantidade,
                id_compra=compra.id,
                id_venda=venda.id,
                agressor=ordem.lado,
            )
            self.negocios.append(negocio)
            negocios.append(negocio)

        return negocios

    def _cruza(self, ordem: Ordem, preco_do_livro: Decimal) -> bool:
        if ordem.tipo == "market":
            return True  # market aceita qualquer preço
        if ordem.lado == "buy":
            return ordem.preco >= preco_do_livro
        return ordem.preco <= preco_do_livro

    # ---------- livro ----------

    def _lado_do_livro(self, lado: str) -> list[Ordem]:
        return self.compras if lado == "buy" else self.vendas

    def _colocar_no_livro(self, ordem: Ordem) -> None:
        self._lado_do_livro(ordem.lado).append(ordem)
        self._ordenar_livro()

    def _ordenar_livro(self) -> None:
        # compra: maior preço primeiro; venda: menor preço primeiro
        # no mesmo preço, quem tem a prioridade menor (chegou antes) vem primeiro
        self.compras.sort(key=lambda o: (-o.preco, o.prioridade))
        self.vendas.sort(key=lambda o: (o.preco, o.prioridade))

    # ---------- peg ----------

    def _melhor_limit(self, lado: str) -> Decimal | None:
        # a referência da peg é a melhor limit do lado (as pegs não contam,
        # senão a peg ia seguir ela mesma)
        for ordem in self._lado_do_livro(lado):
            if ordem.tipo == "limit":
                return ordem.preco
        return None

    def _atualizar_pegs(self) -> None:
        # roda no fim de cada operação e coloca cada peg no preço da referência.
        # a peg mantém a prioridade de quando chegou (igual ao exemplo do enunciado).
        # se não sobrou nenhuma limit no lado, a peg fica no último preço.
        for lado in ("buy", "sell"):
            referencia = self._melhor_limit(lado)
            if referencia is None:
                continue
            for ordem in self._lado_do_livro(lado):
                if ordem.tipo == "peg":
                    ordem.preco = referencia
        self._ordenar_livro()

    # ---------- funções auxiliares ----------

    def _criar_ordem(
        self, lado: str, tipo: str, quantidade: int, preco: Decimal, referencia: str = ""
    ) -> Ordem:
        ordem = Ordem(
            id=len(self.ordens) + 1,
            lado=lado,
            tipo=tipo,
            quantidade=quantidade,
            preco=preco,
            prioridade=self._nova_prioridade(),
            referencia=referencia,
        )
        self.ordens[ordem.id] = ordem
        return ordem

    def _nova_prioridade(self) -> int:
        self._contador_prioridade += 1
        return self._contador_prioridade

    def _buscar_ordem_aberta(self, id_ordem: int) -> Ordem:
        if id_ordem not in self.ordens:
            raise ErroDeOrdem(f"ordem {id_ordem} não existe")
        ordem = self.ordens[id_ordem]
        if ordem.restante == 0:
            raise ErroDeOrdem(f"ordem {id_ordem} não está aberta ({ordem.status})")
        return ordem

    def _validar_quantidade(self, quantidade: int) -> None:
        # type() em vez de isinstance() pra não aceitar True/False (bool é um tipo de int)
        if type(quantidade) is not int or quantidade <= 0:
            raise ErroDeOrdem("quantidade deve ser um inteiro positivo")

    def _validar_preco(self, preco: Decimal) -> None:
        if not isinstance(preco, Decimal) or not preco.is_finite() or preco <= 0:
            raise ErroDeOrdem("preço deve ser positivo")
        if preco % self.tick != 0:
            raise ErroDeOrdem(f"preço {preco} não é múltiplo do tick {self.tick}")
