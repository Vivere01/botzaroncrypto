# ============================================================
# config.py — Todas as configurações centralizadas do bot
# ============================================================
import os

# ── API Binance Futures (Carregamento Seguro) ────────────────
# RECOMENDADO: Defina essas chaves como variáveis de ambiente em seu sistema
# ou utilize um arquivo local `.env` (não versionado) para evitar expor suas chaves públicas no GitHub.
API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USAR_TESTNET = True   # True = testnet | False = conta real

# ── Telegram (opcional, deixe em branco para desativar) ──────
TELEGRAM_TOKEN   = ""
TELEGRAM_CHAT_ID = ""

# ── Par e timeframe ──────────────────────────────────────────
SYMBOL     = "BTCUSDT"
TIMEFRAME  = "15m"
CANDLES_N  = 200

# ── Banca ────────────────────────────────────────────────────
BANCA_BRL  = 1000
BRL_USDT   = 5.70
BANCA_USDT = round(BANCA_BRL / BRL_USDT, 2)   # ≈ 175.44

# ── Meta: 2 % ao dia com ratio 1:2 ──────────────────────────
ALAVANCAGEM          = 5
PORCENTO_POR_TRADE   = 0.20      # 20 % da banca operacional por trade
MAX_TRADES_ABERTOS   = 1
STOP_LOSS_PCT        = 0.010     # -1 %
TAKE_PROFIT_PCT      = 0.020     # +2 %
TRAILING_STOP_PCT    = 0.008     # recua 0.8 % a partir do pico
TRAILING_ATIVA_EM    = 0.012     # ativa trailing a partir de +1.2 %

# ── Limites diários ──────────────────────────────────────────
MAX_PERDA_DIARIA  = 0.010    # para o dia se perder 1 % da banca
MAX_TRADES_DIA    = 4
STOP_GLOBAL_PCT   = 0.20     # encerra tudo se banca cair 20 %

# ── Score mínimo para entrar (0-100) ────────────────────────
SCORE_MINIMO       = 75
SCORE_MINIMO_SHORT = 75

# ── Indicadores técnicos ─────────────────────────────────────
EMA_RAPIDA   = 9
EMA_MEDIA    = 21
EMA_LENTA    = 50
MACD_FAST    = 12
MACD_SLOW    = 26
MACD_SIGNAL  = 9
RSI_PERIODO  = 14
RSI_NEUTRO_MIN      = 45
RSI_NEUTRO_MAX      = 55
RSI_SOBRECOMPRADO   = 70
RSI_SOBREVENDIDO    = 30
ATR_PERIODO    = 14
ATR_MULT_SL    = 1.5
BB_PERIODO     = 20
BB_STD         = 2.0
BB_SQUEEZE_THRESH = 0.015
VOLUME_MEDIA   = 20
VOLUME_MULT    = 1.5

# ── Proteção de capital ──────────────────────────────────────
PERDA_MAX_MES           = 0.03   # hiberna se mês cair 3 %
LUCRO_RESERVA_PCT       = 0.50   # guarda 50 % do lucro acima de 5 %/mês
LUCRO_GATILHO_RESERVA   = 0.05   # gatilho de 5 % para reserva

# ── Ciclo principal ──────────────────────────────────────────
CICLO_SEGUNDOS = 60

# ── Modo de operação ─────────────────────────────────────────
# Se USAR_TESTNET = True, as ordens vão para o testnet (saldo fictício)
# Se False, cuidado: ordens reais com dinheiro real!
MODO_TESTE = USAR_TESTNET
