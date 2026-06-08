# ============================================================
# bot.py — Motor principal de trading ScalpBot
# ============================================================

import time
import json
import os
from datetime import datetime, date

import config
import indicadores as ind_mod
import sinais as sig_mod
import risco as risk_mod
import protecao as prot_mod
import telegram_notif as tg

# Importação condicional da Binance
try:
    from binance.client import Client
    from binance.enums import (
        FUTURE_ORDER_TYPE_MARKET,
        FUTURE_ORDER_TYPE_STOP_MARKET,
        FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
        SIDE_BUY,
        SIDE_SELL,
    )
    from binance.exceptions import BinanceAPIException
    BINANCE_OK = True
except ImportError:
    BINANCE_OK = False
    print("[BOT] AVISO: python-binance não instalado. Rode: pip install python-binance")

# Importação condicional do Telegram
try:
    import requests as req_lib
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


LOG_ARQUIVO = "scalp.log"


class ScalpBot:
    """Motor principal do bot de scalping BTC/USDT Futures."""

    def __init__(self):
        self.log("=" * 55)
        self.log("  🤖 ScalpBot iniciando...")
        self.log("=" * 55)
        self._trades_hoje: list = []

        # Conecta à Binance
        if BINANCE_OK:
            if config.USAR_TESTNET:
                self.client = Client(
                    config.API_KEY,
                    config.API_SECRET,
                    testnet=True,
                )
                self.log("Conectado ao TESTNET da Binance Futures")
            else:
                self.client = Client(config.API_KEY, config.API_SECRET)
                self.log("⚠️ Conectado à conta REAL da Binance Futures")
        else:
            self.client = None
            self.log("MODO SEM BINANCE: ordens não serão enviadas")

        # Estado da posição
        self.posicao_aberta: dict | None = None
        self.trailing: risk_mod.TrailingStop | None = None

        # Histórico e proteção
        self.historico = risk_mod.carregar_historico()
        self.estado_prot = prot_mod.carregar_estado()

        # Banca
        self.banca_atual = config.BANCA_USDT
        self.banca_inicio_dia = self.banca_atual
        self._data_inicio_dia = date.today()

        # Configura futures (alavancagem + margem cruzada)
        self._configurar_futures()

        self.log(f"Banca inicial: ${self.banca_atual:.2f} USDT")
        self.log(f"Símbolo: {config.SYMBOL} | Timeframe: {config.TIMEFRAME}")
        self.log(f"Alavancagem: {config.ALAVANCAGEM}x | Modo teste: {config.MODO_TESTE}")

    # ── Configuração ─────────────────────────────────────────

    def _configurar_futures(self):
        """Define alavancagem e tipo de margem no contrato."""
        if not self.client:
            return
        try:
            self.client.futures_change_leverage(
                symbol=config.SYMBOL,
                leverage=config.ALAVANCAGEM,
            )
            self.client.futures_change_margin_type(
                symbol=config.SYMBOL,
                marginType="CROSSED",
            )
            self.log(f"Futures configurado: {config.ALAVANCAGEM}x — Margem CRUZADA")
        except BinanceAPIException as e:
            # Código -4046 = margem já está no modo desejado (ignorar)
            if e.code != -4046:
                self.log(f"[AVISO] Erro ao configurar futures: {e.code} — {e.message}")

    # ── Utilitários de dados ─────────────────────────────────

    def get_preco(self) -> float:
        """Retorna o preço atual do par."""
        if not self.client:
            return 0.0
        try:
            ticker = self.client.futures_symbol_ticker(symbol=config.SYMBOL)
            return float(ticker["price"])
        except BinanceAPIException as e:
            self.log(f"[ERRO] get_preco: {e.code} — {e.message}")
            return 0.0

    def get_candles(self) -> list:
        """Baixa os últimos N candles do timeframe configurado."""
        if not self.client:
            return []
        try:
            candles = self.client.futures_klines(
                symbol=config.SYMBOL,
                interval=config.TIMEFRAME,
                limit=config.CANDLES_N,
            )
            return candles
        except BinanceAPIException as e:
            self.log(f"[ERRO] get_candles: {e.code} — {e.message}")
            return []

    def get_saldo(self) -> float:
        """Retorna saldo USDT disponível na conta futures."""
        if not self.client:
            return self.banca_atual
        try:
            saldos = self.client.futures_account_balance()
            for s in saldos:
                if s["asset"] == "USDT":
                    return float(s["balance"])
        except BinanceAPIException as e:
            self.log(f"[ERRO] get_saldo: {e.code} — {e.message}")
        return self.banca_atual

    def get_volume_24h(self) -> float:
        """Retorna o volume de 24h do par."""
        if not self.client:
            return 0.0
        try:
            stats = self.client.futures_ticker(symbol=config.SYMBOL)
            return float(stats["quoteVolume"])
        except BinanceAPIException as e:
            self.log(f"[ERRO] get_volume_24h: {e.code} — {e.message}")
            return 0.0

    # ── Log e alertas ─────────────────────────────────────────

    def log(self, msg: str):
        """Registra mensagem no terminal e no arquivo de log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] {msg}"
        print(linha)
        try:
            with open(LOG_ARQUIVO, "a", encoding="utf-8") as f:
                f.write(linha + "\n")
        except Exception:
            pass   # log em arquivo falhou, continua

    def alerta(self, msg: str):
        """Loga e envia mensagem simples ao Telegram (fallback)."""
        self.log(f"📢 {msg}")
        if REQUESTS_OK and config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID:
            try:
                url = (
                    f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"
                    f"/sendMessage"
                )
                req_lib.post(
                    url,
                    json={"chat_id": config.TELEGRAM_CHAT_ID, "text": msg},
                    timeout=10,
                )
            except Exception as e:
                self.log(f"[AVISO] Telegram falhou: {e}")

    # ── Abertura de posição ──────────────────────────────────

    def abrir_posicao(self, direcao: str, niveis: dict, tamanho: dict):
        """
        Abre uma posição no mercado e envia ordens de SL e TP.
        """
        qty  = tamanho["quantidade_btc"]
        side = SIDE_BUY if direcao == "long" else SIDE_SELL

        self.log("-" * 45)
        self.log(f"🚀 ABRINDO {direcao.upper()} | Qtd: {qty} BTC")
        self.log(f"   Entrada: ${niveis['entrada']:,.2f}")
        self.log(f"   SL:      ${niveis['stop_loss']:,.2f}")
        self.log(f"   TP:      ${niveis['take_profit']:,.2f}")
        self.log(f"   Capital: ${tamanho['capital_usdt']:.2f} | Alavancado: ${tamanho['capital_alavancado']:.2f}")
        self.log(f"   Kelly: {tamanho['kelly_frac']*100:.1f}% | WR: {tamanho['win_rate']*100:.1f}%")

        # Registra a posição (mesmo em modo teste real)
        self.posicao_aberta = {
            "direcao":    direcao,
            "preco_entrada": niveis["entrada"],
            "stop_loss":  niveis["stop_loss"],
            "take_profit": niveis["take_profit"],
            "quantidade": qty,
            "capital":    tamanho["capital_usdt"],
            "aberta_em":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Inicializa trailing stop
        self.trailing = risk_mod.TrailingStop(
            entrada  = niveis["entrada"],
            direcao  = direcao,
            gatilho  = niveis["trailing_gatilho"],
        )

        if not config.MODO_TESTE and self.client:
            try:
                # 1) Ordem MARKET (entrada)
                self.client.futures_create_order(
                    symbol=config.SYMBOL,
                    side=side,
                    type=FUTURE_ORDER_TYPE_MARKET,
                    quantity=qty,
                )
                # 2) Stop Loss
                sl_side = SIDE_SELL if direcao == "long" else SIDE_BUY
                self.client.futures_create_order(
                    symbol=config.SYMBOL,
                    side=sl_side,
                    type=FUTURE_ORDER_TYPE_STOP_MARKET,
                    stopPrice=niveis["stop_loss"],
                    closePosition=True,
                )
                # 3) Take Profit
                self.client.futures_create_order(
                    symbol=config.SYMBOL,
                    side=sl_side,
                    type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                    stopPrice=niveis["take_profit"],
                    closePosition=True,
                )
                self.log("Ordens enviadas com sucesso à Binance")
            except BinanceAPIException as e:
                self.log(f"[ERRO CRÍTICO] Falha ao enviar ordem: {e.code} — {e.message}")
                self.alerta(f"❌ Erro ao abrir posição: {e.message}")
                self.posicao_aberta = None
                self.trailing = None
                return
        else:
            self.log("(Modo teste/testnet — posição simulada)")

        # Notificação rica ao Telegram
        tg.posicao_aberta(
            direcao   = direcao,
            entrada   = niveis["entrada"],
            sl        = niveis["stop_loss"],
            tp        = niveis["take_profit"],
            quantidade= qty,
            capital   = tamanho["capital_usdt"],
        )

    # ── Fechamento de posição ────────────────────────────────

    def fechar_posicao(self, preco: float, motivo: str):
        """
        Fecha a posição atual, calcula resultado e salva no histórico.
        """
        if not self.posicao_aberta:
            return

        pos     = self.posicao_aberta
        dir_pos = pos["direcao"]
        entrada = pos["preco_entrada"]
        qty     = pos["quantidade"]
        capital = pos["capital"]

        # Calcula lucro real
        if dir_pos == "long":
            pct   = (preco - entrada) / entrada
        else:
            pct   = (entrada - preco) / entrada

        lucro_bruto = capital * config.ALAVANCAGEM * pct
        lucro_usdt  = round(lucro_bruto, 4)
        lucro_pct   = round(pct * 100, 2)

        emoji = "✅" if lucro_usdt > 0 else "❌"

        self.log("-" * 45)
        self.log(f"{emoji} FECHANDO {dir_pos.upper()} | Motivo: {motivo}")
        self.log(f"   Entrada: ${entrada:,.2f} | Saída: ${preco:,.2f}")
        self.log(f"   Resultado: {lucro_pct:+.2f}% | ${lucro_usdt:+.2f}")

        # Envia ordem de fechamento (mercado real)
        if not config.MODO_TESTE and self.client:
            try:
                close_side = SIDE_SELL if dir_pos == "long" else SIDE_BUY
                self.client.futures_create_order(
                    symbol=config.SYMBOL,
                    side=close_side,
                    type=FUTURE_ORDER_TYPE_MARKET,
                    quantity=qty,
                    reduceOnly=True,
                )
                # Cancela ordens abertas (SL e TP)
                self.client.futures_cancel_all_open_orders(symbol=config.SYMBOL)
            except BinanceAPIException as e:
                self.log(f"[ERRO] Falha ao fechar posição: {e.code} — {e.message}")

        # Salva no histórico
        trade = {
            "data_hora":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "direcao":     dir_pos,
            "preco_entrada": entrada,
            "preco_saida": preco,
            "quantidade":  qty,
            "capital":     capital,
            "lucro_usdt":  lucro_usdt,
            "lucro_pct":   lucro_pct,
            "motivo":      motivo,
        }
        risk_mod.salvar_trade(trade)
        self.historico.append(trade)

        # Atualiza banca
        self.banca_atual = round(self.banca_atual + lucro_usdt, 4)
        self.log(f"   Banca atualizada: ${self.banca_atual:.2f}")

        # Salva trade do dia para resumo
        self._trades_hoje.append(trade)

        # Notificação rica ao Telegram
        if lucro_usdt > 0:
            tg.posicao_fechada_win(
                direcao     = dir_pos,
                entrada     = entrada,
                saida       = preco,
                lucro_usdt  = lucro_usdt,
                lucro_pct   = lucro_pct,
                motivo      = motivo,
                banca       = self.banca_atual,
                trades_hoje = len(self._trades_hoje),
            )
        else:
            tg.posicao_fechada_loss(
                direcao     = dir_pos,
                entrada     = entrada,
                saida       = preco,
                perda_usdt  = lucro_usdt,
                perda_pct   = lucro_pct,
                motivo      = motivo,
                banca       = self.banca_atual,
                trades_hoje = len(self._trades_hoje),
            )

        # Reseta estado
        self.posicao_aberta = None
        self.trailing = None

    # ── Loop principal ───────────────────────────────────────

    def rodar(self):
        """Loop principal infinito do bot."""
        self.log("▶️  Bot iniciado — loop principal rodando")
        modo = "TESTNET" if config.USAR_TESTNET else "REAL ⚠️"
        tg.bot_iniciado(self.banca_atual, modo)

        try:
            while True:
                try:
                    agora = datetime.now()

                    # ── 1. Virada de mês ─────────────────────
                    self.estado_prot = prot_mod.verificar_virada_mes(
                        self.estado_prot, self.banca_atual
                    )

                    # ── 2. Reset início de dia ────────────────
                    if date.today() != self._data_inicio_dia:
                        self._data_inicio_dia = date.today()
                        self.banca_inicio_dia = self.banca_atual
                        self.log(f"📅 Novo dia — banca início: ${self.banca_inicio_dia:.2f}")

                    # ── POSIÇÃO ABERTA: monitora TP/SL/trailing
                    if self.posicao_aberta:
                        preco_atual = self.get_preco()
                        if preco_atual <= 0:
                            time.sleep(config.CICLO_SEGUNDOS)
                            continue

                        pos = self.posicao_aberta

                        # Verifica TP
                        if pos["direcao"] == "long" and preco_atual >= pos["take_profit"]:
                            self.fechar_posicao(preco_atual, "Take Profit atingido")
                        elif pos["direcao"] == "short" and preco_atual <= pos["take_profit"]:
                            self.fechar_posicao(preco_atual, "Take Profit atingido")

                        # Verifica SL
                        elif pos["direcao"] == "long" and preco_atual <= pos["stop_loss"]:
                            self.fechar_posicao(preco_atual, "Stop Loss atingido")
                        elif pos["direcao"] == "short" and preco_atual >= pos["stop_loss"]:
                            self.fechar_posicao(preco_atual, "Stop Loss atingido")

                        # Verifica Trailing
                        elif self.trailing:
                            resultado_trail = self.trailing.atualizar(preco_atual)
                            if resultado_trail == -1:
                                self.fechar_posicao(preco_atual, "Trailing Stop ativado")
                            elif resultado_trail is not None:
                                self.log(
                                    f"🔄 Trailing atualizado: novo stop = ${resultado_trail:,.2f}"
                                )

                        time.sleep(config.CICLO_SEGUNDOS)
                        continue

                    # ── SEM POSIÇÃO ABERTA ────────────────────

                    # 6. Stop global
                    banca_inicial = config.BANCA_USDT
                    if banca_inicial > 0:
                        queda = (banca_inicial - self.banca_atual) / banca_inicial
                        if queda >= config.STOP_GLOBAL_PCT:
                            tg.stop_global_ativado(self.banca_atual, queda * 100)
                            self.log(f"🛑 STOP GLOBAL ativado! Banca caiu {queda*100:.1f}%. Bot encerrado.")
                            return

                    # 7. Hibernação mensal
                    hibernando, motivo_hib = prot_mod.checar_hibernacao(
                        self.estado_prot, self.banca_atual
                    )
                    if hibernando:
                        self.log(f"😴 Hibernando: {motivo_hib}")
                        tg.hibernacao_ativada(motivo_hib)
                        time.sleep(config.CICLO_SEGUNDOS * 60)  # aguarda 1 hora
                        continue

                    # 8. Pode operar hoje?
                    pode, motivo_dia = risk_mod.pode_operar_hoje(
                        self.banca_atual,
                        self.banca_inicio_dia,
                        self.historico,
                    )
                    if not pode:
                        self.log(f"⏸️ {motivo_dia}")
                        time.sleep(config.CICLO_SEGUNDOS)
                        continue

                    # 9. Baixa candles e calcula indicadores
                    candles = self.get_candles()
                    if len(candles) < 60:
                        self.log("⏳ Candles insuficientes, aguardando...")
                        time.sleep(config.CICLO_SEGUNDOS)
                        continue

                    ind = ind_mod.calcular_todos(candles)

                    # 10. Avalia sinal
                    sinal = sig_mod.avaliar_sinal(ind)

                    self.log(
                        f"📊 Score — LONG: {sinal['score_long']} | "
                        f"SHORT: {sinal['score_short']} | "
                        f"RSI: {sinal['rsi']:.1f} | "
                        f"Sinal: {sinal['direcao'] or 'nenhum'}"
                    )

                    # 11. Sinal válido → abre posição
                    if sinal["direcao"]:
                        banca_op = prot_mod.banca_operacional(
                            self.estado_prot, self.banca_atual
                        )
                        niveis = sig_mod.calcular_niveis(
                            sinal["close"], sinal["direcao"], sinal["atr"]
                        )
                        tamanho = risk_mod.calcular_tamanho_posicao(
                            banca_op, sinal["close"], self.historico
                        )

                        if tamanho["quantidade_btc"] > 0:
                            self.abrir_posicao(
                                sinal["direcao"], niveis, tamanho
                            )
                        else:
                            self.log("⚠️ Tamanho calculado = 0, saldo insuficiente")
                    else:
                        self.log(f"🔍 Aguardando sinal (score mínimo: {config.SCORE_MINIMO})")

                except BinanceAPIException as e:
                    self.log(
                        f"[BINANCE API] Código: {e.code} — {e.message}"
                    )
                    time.sleep(30)

                except ConnectionError as e:
                    self.log(f"[CONEXÃO] Erro de rede: {e} — tentando em 30s")
                    time.sleep(30)

                except Exception as e:
                    self.log(f"[ERRO GENÉRICO] {type(e).__name__}: {e}")
                    time.sleep(30)

                # 13. Aguarda próximo ciclo
                time.sleep(config.CICLO_SEGUNDOS)

        except KeyboardInterrupt:
            self.log("⛔ Interrupção pelo usuário (Ctrl+C)")
            if self.posicao_aberta:
                preco = self.get_preco()
                if preco > 0:
                    self.fechar_posicao(preco, "Encerramento manual")
            tg.bot_encerrado(
                motivo        = "Encerrado manualmente (Ctrl+C)",
                banca_final   = self.banca_atual,
                banca_inicial = config.BANCA_USDT,
            )
            # Envia resumo do dia se houver trades
            if self._trades_hoje:
                tg.resumo_diario(
                    banca_inicio = self.banca_inicio_dia,
                    banca_atual  = self.banca_atual,
                    trades       = self._trades_hoje,
                )
