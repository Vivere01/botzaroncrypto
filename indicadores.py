# ============================================================
# indicadores.py — Cálculo de indicadores técnicos (sem ta-lib)
# ============================================================

import numpy as np
import config


def ema(values: np.ndarray, periodo: int) -> np.ndarray:
    """
    Calcula a Média Móvel Exponencial (EMA) clássica.
    Os primeiros `periodo - 1` valores são NaN.
    """
    resultado = np.full(len(values), np.nan)
    if len(values) < periodo:
        return resultado

    # Semente: média simples dos primeiros `periodo` valores
    resultado[periodo - 1] = np.mean(values[:periodo])
    k = 2.0 / (periodo + 1)

    for i in range(periodo, len(values)):
        resultado[i] = values[i] * k + resultado[i - 1] * (1 - k)

    return resultado


def rsi(closes: np.ndarray, periodo: int = 14) -> np.ndarray:
    """
    RSI de Wilder.
    Primeiros `periodo` valores são NaN.
    """
    resultado = np.full(len(closes), np.nan)
    if len(closes) < periodo + 1:
        return resultado

    deltas = np.diff(closes)
    ganhos = np.where(deltas > 0, deltas, 0.0)
    perdas = np.where(deltas < 0, -deltas, 0.0)

    # Médias iniciais (Wilder: SMA dos primeiros N)
    avg_ganho = np.mean(ganhos[:periodo])
    avg_perda = np.mean(perdas[:periodo])

    for i in range(periodo, len(closes)):
        idx = i - 1  # índice em deltas/ganhos/perdas (1 menor que closes)
        avg_ganho = (avg_ganho * (periodo - 1) + ganhos[idx]) / periodo
        avg_perda = (avg_perda * (periodo - 1) + perdas[idx]) / periodo

        if avg_perda == 0:
            resultado[i] = 100.0
        else:
            rs = avg_ganho / avg_perda
            resultado[i] = 100.0 - (100.0 / (1 + rs))

    return resultado


def macd(closes: np.ndarray,
         fast: int = None,
         slow: int = None,
         signal: int = None):
    """
    Calcula MACD line, Signal line e Histograma.
    Retorna tupla (macd_line, signal_line, histogram) como arrays numpy.
    """
    fast   = fast   or config.MACD_FAST
    slow   = slow   or config.MACD_SLOW
    signal = signal or config.MACD_SIGNAL

    ema_fast   = ema(closes, fast)
    ema_slow   = ema(closes, slow)
    macd_line  = ema_fast - ema_slow

    # Signal é a EMA do MACD (ignora NaN usando máscara)
    signal_line = np.full(len(macd_line), np.nan)
    validos = ~np.isnan(macd_line)
    if np.sum(validos) >= signal:
        idx_validos = np.where(validos)[0]
        sinal_arr = ema(macd_line[validos], signal)
        for j, idx in enumerate(idx_validos):
            signal_line[idx] = sinal_arr[j]

    histograma = macd_line - signal_line
    return macd_line, signal_line, histograma


def atr(highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        periodo: int = 14) -> np.ndarray:
    """
    Average True Range (ATR) de Wilder.
    """
    n = len(closes)
    resultado = np.full(n, np.nan)
    if n < 2:
        return resultado

    tr = np.full(n, np.nan)
    tr[0] = highs[0] - lows[0]   # sem candle anterior

    for i in range(1, n):
        hl  = highs[i] - lows[i]
        hcp = abs(highs[i] - closes[i - 1])
        lcp = abs(lows[i]  - closes[i - 1])
        tr[i] = max(hl, hcp, lcp)

    # Semente: SMA dos primeiros `periodo`
    if n < periodo:
        return resultado
    resultado[periodo - 1] = np.mean(tr[:periodo])

    for i in range(periodo, n):
        resultado[i] = (resultado[i - 1] * (periodo - 1) + tr[i]) / periodo

    return resultado


def bollinger(closes: np.ndarray,
              periodo: int = 20,
              std: float = 2.0):
    """
    Bandas de Bollinger.
    Retorna (upper, mid, lower) como arrays numpy.
    """
    n = len(closes)
    upper = np.full(n, np.nan)
    mid   = np.full(n, np.nan)
    lower = np.full(n, np.nan)

    for i in range(periodo - 1, n):
        janela = closes[i - periodo + 1: i + 1]
        m = np.mean(janela)
        s = np.std(janela, ddof=0)
        mid[i]   = m
        upper[i] = m + std * s
        lower[i] = m - std * s

    return upper, mid, lower


def volume_sma(volumes: np.ndarray, periodo: int = 20) -> np.ndarray:
    """
    Média Móvel Simples (SMA) do volume.
    """
    n = len(volumes)
    resultado = np.full(n, np.nan)
    for i in range(periodo - 1, n):
        resultado[i] = np.mean(volumes[i - periodo + 1: i + 1])
    return resultado


def calcular_todos(candles: list) -> dict:
    """
    Recebe lista de candles da Binance no formato:
      [timestamp, open, high, low, close, volume, ...]
    Retorna dict com todas as séries de indicadores.
    """
    closes  = np.array([float(c[4]) for c in candles])
    highs   = np.array([float(c[2]) for c in candles])
    lows    = np.array([float(c[3]) for c in candles])
    volumes = np.array([float(c[5]) for c in candles])

    ema9  = ema(closes, config.EMA_RAPIDA)
    ema21 = ema(closes, config.EMA_MEDIA)
    ema50 = ema(closes, config.EMA_LENTA)

    rsi_arr = rsi(closes, config.RSI_PERIODO)

    macd_line, macd_sig, macd_hist = macd(
        closes,
        fast=config.MACD_FAST,
        slow=config.MACD_SLOW,
        signal=config.MACD_SIGNAL,
    )

    atr_arr = atr(highs, lows, closes, config.ATR_PERIODO)

    bb_upper, bb_mid, bb_lower = bollinger(
        closes, config.BB_PERIODO, config.BB_STD
    )

    # Largura relativa das bandas
    with np.errstate(invalid="ignore", divide="ignore"):
        bb_largura = np.where(
            bb_mid != 0,
            (bb_upper - bb_lower) / bb_mid,
            np.nan,
        )

    vol_sma_arr = volume_sma(volumes, config.VOLUME_MEDIA)

    return {
        "close":     closes,
        "high":      highs,
        "low":       lows,
        "volume":    volumes,
        "ema9":      ema9,
        "ema21":     ema21,
        "ema50":     ema50,
        "rsi":       rsi_arr,
        "macd_line": macd_line,
        "macd_sig":  macd_sig,
        "macd_hist": macd_hist,
        "atr":       atr_arr,
        "bb_upper":  bb_upper,
        "bb_mid":    bb_mid,
        "bb_lower":  bb_lower,
        "bb_largura": bb_largura,
        "vol_sma":   vol_sma_arr,
    }
