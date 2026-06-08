# ============================================================
# sinais.py — Lógica de entrada/saída de trades
# Estratégia: Momentum Breakout com 5 confirmações simultâneas
# ============================================================

import numpy as np
import config


def avaliar_sinal(ind: dict) -> dict:
    """
    Analisa o ÚLTIMO CANDLE FECHADO (índice -2, não -1) e
    retorna score LONG e SHORT com todos os detalhes.
    """
    i = -2   # último candle fechado

    # ── Extrai valores do índice correto ─────────────────────
    close     = float(ind["close"][i])
    volume    = float(ind["volume"][i])
    ema9_val  = float(ind["ema9"][i])
    ema21_val = float(ind["ema21"][i])
    ema50_val = float(ind["ema50"][i])
    rsi_val   = float(ind["rsi"][i])
    macd_line = float(ind["macd_line"][i])
    macd_sig  = float(ind["macd_sig"][i])
    macd_hist = float(ind["macd_hist"][i])
    macd_hist_ant = float(ind["macd_hist"][i - 1]) if i - 1 >= -len(ind["macd_hist"]) else macd_hist
    atr_val   = float(ind["atr"][i])
    bb_upper  = float(ind["bb_upper"][i])
    bb_lower  = float(ind["bb_lower"][i])
    bb_mid    = float(ind["bb_mid"][i])
    bb_larg   = float(ind["bb_largura"][i])
    vol_sma   = float(ind["vol_sma"][i])

    # Verifica se algum indicador crítico é NaN
    valores_criticos = [ema9_val, ema21_val, ema50_val, rsi_val,
                        macd_line, macd_sig, atr_val, bb_upper, vol_sma]
    if any(np.isnan(v) for v in valores_criticos):
        return _resultado_vazio(ind)

    vol_ratio = volume / vol_sma if vol_sma > 0 else 1.0
    bb_squeeze = bb_larg < config.BB_SQUEEZE_THRESH

    # ── SCORE LONG ───────────────────────────────────────────
    score_long = 0
    detalhes_long = {}

    # Condição 1 — TENDÊNCIA (25 + 5 bônus)
    tend_pts = 0
    if ema9_val > ema21_val > ema50_val:
        tend_pts += 25
    if close > ema9_val:
        tend_pts += 5
    score_long += tend_pts
    detalhes_long["tendencia"] = tend_pts

    # Condição 2 — MACD (30 + 5 bônus)
    macd_pts = 0
    if macd_line > macd_sig:
        macd_pts += 15
    if macd_hist > macd_hist_ant:    # histograma subindo
        macd_pts += 10
    if macd_line > 0:
        macd_pts += 5
    score_long += macd_pts
    detalhes_long["macd"] = macd_pts

    # Condição 3 — RSI (25 + 5 bônus)
    rsi_pts = 0
    if config.RSI_NEUTRO_MIN <= rsi_val <= config.RSI_SOBRECOMPRADO:
        rsi_pts += 20
        if 50 <= rsi_val <= 65:
            rsi_pts += 5
    score_long += rsi_pts
    detalhes_long["rsi"] = rsi_pts

    # Condição 4 — VOLUME (20 pts)
    vol_pts = 0
    if vol_ratio >= config.VOLUME_MULT:
        vol_pts += 20
    elif vol_ratio < 1.0:
        vol_pts += 5   # não penaliza totalmente
    score_long += vol_pts
    detalhes_long["volume"] = vol_pts

    # Condição 5 — BOLLINGER (20 pts)
    bb_pts = 0
    if bb_squeeze:
        bb_pts += 10
    if close >= bb_upper * 0.998:
        bb_pts += 10
    score_long += bb_pts
    detalhes_long["bollinger"] = bb_pts

    # ── SCORE SHORT ──────────────────────────────────────────
    score_short = 0
    detalhes_short = {}

    # Condição 1 — TENDÊNCIA inversa
    tend_s = 0
    if ema9_val < ema21_val < ema50_val:
        tend_s += 25
    if close < ema9_val:
        tend_s += 5
    score_short += tend_s
    detalhes_short["tendencia"] = tend_s

    # Condição 2 — MACD inverso
    macd_s = 0
    if macd_line < macd_sig:
        macd_s += 15
    if macd_hist < macd_hist_ant:    # histograma caindo
        macd_s += 10
    if macd_line < 0:
        macd_s += 5
    score_short += macd_s
    detalhes_short["macd"] = macd_s

    # Condição 3 — RSI inverso
    rsi_s = 0
    if config.RSI_SOBREVENDIDO <= rsi_val <= config.RSI_NEUTRO_MAX:
        rsi_s += 20
        if 35 <= rsi_val <= 50:
            rsi_s += 5
    score_short += rsi_s
    detalhes_short["rsi"] = rsi_s

    # Condição 4 — VOLUME (igual para short)
    vol_s = 0
    if vol_ratio >= config.VOLUME_MULT:
        vol_s += 20
    elif vol_ratio < 1.0:
        vol_s += 5
    score_short += vol_s
    detalhes_short["volume"] = vol_s

    # Condição 5 — BOLLINGER inverso
    bb_s = 0
    if bb_squeeze:
        bb_s += 10
    if close <= bb_lower * 1.002:
        bb_s += 10
    score_short += bb_s
    detalhes_short["bollinger"] = bb_s

    # ── DECISÃO ──────────────────────────────────────────────
    direcao = None
    score   = 0

    long_ok  = score_long  >= config.SCORE_MINIMO
    short_ok = score_short >= config.SCORE_MINIMO_SHORT

    if long_ok and (not short_ok or score_long >= score_short):
        direcao = "long"
        score   = score_long
    elif short_ok and (not long_ok or score_short > score_long):
        direcao = "short"
        score   = score_short

    return {
        "direcao":    direcao,
        "score":      score,
        "score_long":  score_long,
        "score_short": score_short,
        "atr":        atr_val,
        "close":      close,
        "rsi":        rsi_val,
        "ema9":       ema9_val,
        "ema21":      ema21_val,
        "ema50":      ema50_val,
        "bb_squeeze": bb_squeeze,
        "vol_ratio":  round(vol_ratio, 2),
        "detalhes": {
            "long":  detalhes_long,
            "short": detalhes_short,
        },
    }


def _resultado_vazio(ind: dict) -> dict:
    """Retorno padrão quando indicadores ainda não têm dados suficientes."""
    close = float(ind["close"][-1]) if len(ind["close"]) > 0 else 0.0
    return {
        "direcao":     None,
        "score":       0,
        "score_long":  0,
        "score_short": 0,
        "atr":         0.0,
        "close":       close,
        "rsi":         float("nan"),
        "ema9":        float("nan"),
        "ema21":       float("nan"),
        "ema50":       float("nan"),
        "bb_squeeze":  False,
        "vol_ratio":   0.0,
        "detalhes":    {"long": {}, "short": {}},
    }


def calcular_niveis(preco: float, direcao: str, atr_val: float) -> dict:
    """
    Calcula Stop Loss, Take Profit e Trailing Gatilho.
    SL = max(preco × STOP_LOSS_PCT, atr × ATR_MULT_SL)
    TP = SL × 2  → ratio 1:2
    """
    sl_por_pct = preco * config.STOP_LOSS_PCT
    sl_por_atr = atr_val * config.ATR_MULT_SL
    sl_distancia = max(sl_por_pct, sl_por_atr)
    tp_distancia = sl_distancia * 2.0

    if direcao == "long":
        stop_loss       = preco - sl_distancia
        take_profit     = preco + tp_distancia
        trailing_gatilho = preco * (1 + config.TRAILING_ATIVA_EM)
    else:   # short
        stop_loss       = preco + sl_distancia
        take_profit     = preco - tp_distancia
        trailing_gatilho = preco * (1 - config.TRAILING_ATIVA_EM)

    return {
        "entrada":          round(preco, 2),
        "stop_loss":        round(stop_loss, 2),
        "take_profit":      round(take_profit, 2),
        "trailing_gatilho": round(trailing_gatilho, 2),
        "sl_distancia":     round(sl_distancia, 2),
        "tp_distancia":     round(tp_distancia, 2),
        "ratio":            round(tp_distancia / sl_distancia, 2),
    }
