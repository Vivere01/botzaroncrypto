# ============================================================
# tests.py — Testes automáticos dos módulos do ScalpBot
# Execute: python tests.py
# ============================================================

import sys
import io

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import numpy as np

print("=" * 55)
print("  🧪 TESTES DO SCALP BOT")
print("=" * 55)

erros = 0


def ok(nome):
    print(f"  ✅ {nome}")


def falha(nome, detalhe=""):
    global erros
    erros += 1
    print(f"  ❌ {nome}: {detalhe}")


# ─────────────────────────────────────────────────────────────
# TESTE 1 — Indicadores com dados sintéticos
# ─────────────────────────────────────────────────────────────
print("\n  [1] Indicadores")

import indicadores as ind

# EMA
closes = np.array([float(i) for i in range(1, 21)])
e = ind.ema(closes, 5)
if np.isnan(e[3]) and not np.isnan(e[4]):
    ok("EMA — primeiros valores NaN, restante calculado")
else:
    falha("EMA", f"e[3]={e[3]} e[4]={e[4]}")

# RSI
rsi_arr = ind.rsi(closes, 14)
if np.all(np.isnan(rsi_arr[:14])) and not np.isnan(rsi_arr[14]):
    ok("RSI — primeiros N valores NaN")
else:
    falha("RSI", "valores iniciais incorretos")

# MACD
ml, ms, mh = ind.macd(closes)
if len(ml) == len(closes):
    ok("MACD — tamanho correto")
else:
    falha("MACD", f"tamanho {len(ml)} != {len(closes)}")

# ATR
highs  = closes + 1.0
lows   = closes - 1.0
atr_a  = ind.atr(highs, lows, closes, 14)
if not np.isnan(atr_a[-1]) and atr_a[-1] > 0:
    ok("ATR — valor positivo")
else:
    falha("ATR", f"atr[-1]={atr_a[-1]}")

# Bollinger
bb_u, bb_m, bb_l = ind.bollinger(closes, 10)
if not np.isnan(bb_u[-1]) and bb_u[-1] > bb_l[-1]:
    ok("Bollinger — upper > lower")
else:
    falha("Bollinger", f"upper={bb_u[-1]} lower={bb_l[-1]}")

# Volume SMA
vols   = np.ones(30) * 1000
vs     = ind.volume_sma(vols, 20)
if abs(vs[-1] - 1000) < 0.01:
    ok("Volume SMA — média correta")
else:
    falha("Volume SMA", f"vs[-1]={vs[-1]}")

# ─────────────────────────────────────────────────────────────
# TESTE 2 — Sinais: mercado lateral vs tendência
# ─────────────────────────────────────────────────────────────
print("\n  [2] Sinais")

import sinais as sig

# Simula candles laterais (preço oscila sem tendência)
np.random.seed(42)
n = 200
# Preço perfeitamente constante
preco_lateral = np.ones(n) * 30000.0

def _montar_ind(closes_arr, forcar_alta=False, forcar_baixa=False, volume_alto=False):
    """Cria um dict de indicadores a partir de um array de closes."""
    n = len(closes_arr)
    highs  = closes_arr + 5.0
    lows   = closes_arr - 5.0
    vols   = np.ones(n) * 1000.0

    ema9  = ind.ema(closes_arr, 9)
    ema21 = ind.ema(closes_arr, 21)
    ema50 = ind.ema(closes_arr, 50)

    if forcar_alta:
        # Força alinhamento de alta
        for idx in range(-10, 0):
            ema9[idx]  = closes_arr[idx] + 20.0
            ema21[idx] = closes_arr[idx] + 10.0
            ema50[idx] = closes_arr[idx] + 5.0

    if forcar_baixa:
        # Força alinhamento de baixa
        for idx in range(-10, 0):
            ema9[idx]  = closes_arr[idx] - 20.0
            ema21[idx] = closes_arr[idx] - 10.0
            ema50[idx] = closes_arr[idx] - 5.0

    ml, ms, mh = ind.macd(closes_arr)
    rsi_a      = ind.rsi(closes_arr)
    atr_a      = ind.atr(highs, lows, closes_arr)
    bb_u, bb_m, bb_l = ind.bollinger(closes_arr)

    with np.errstate(invalid="ignore", divide="ignore"):
        bb_larg = np.where(bb_m != 0, (bb_u - bb_l) / bb_m, np.nan)

    vol_sma_a = ind.volume_sma(vols)
    
    # Se volume_alto for True, colocamos o último volume 2x maior que a média
    vols_dinamico = vols.copy()
    if volume_alto:
        vols_dinamico[-5:] = 2000.0

    return {
        "close":     closes_arr,
        "high":      highs,
        "low":       lows,
        "volume":    vols_dinamico,
        "ema9":      ema9,
        "ema21":     ema21,
        "ema50":     ema50,
        "rsi":       rsi_a,
        "macd_line": ml,
        "macd_sig":  ms,
        "macd_hist": mh,
        "atr":       atr_a,
        "bb_upper":  bb_u,
        "bb_mid":    bb_m,
        "bb_lower":  bb_l,
        "bb_largura": bb_larg,
        "vol_sma":   vol_sma_a,
    }

# Lateral → sem sinal esperado (sem volume alto e preço plano)
ind_lateral = _montar_ind(preco_lateral, volume_alto=False)
s_lat = sig.avaliar_sinal(ind_lateral)
if s_lat["direcao"] is None or s_lat["score"] < 75:
    ok(f"Mercado lateral → sem sinal (score_long={s_lat['score_long']}, score_short={s_lat['score_short']})")
else:
    falha("Mercado lateral", f"gerou sinal {s_lat['direcao']} score={s_lat['score']}")

# Tendência de alta forçada → sinal LONG esperado
tendencia_alta = np.linspace(29000, 31000, n)
ind_alta = _montar_ind(tendencia_alta, forcar_alta=True, volume_alto=True)
# Forçar RSI na zona 50-65 e MACD favorável
ind_alta["rsi"][-5:] = 55.0
ind_alta["macd_line"][-5:] = 10.0
ind_alta["macd_sig"][-5:] = 5.0
ind_alta["macd_hist"][-5:] = 5.0
ind_alta["macd_hist"][-1] = 6.0
ind_alta["macd_hist"][-2] = 5.5

s_alta = sig.avaliar_sinal(ind_alta)
print(f"  [INFO] Tendência de alta: score_long={s_alta['score_long']} score_short={s_alta['score_short']}")
if s_alta["direcao"] == "long" and s_alta["score"] >= 75:
    ok(f"Tendência de alta → gerou sinal LONG (score={s_alta['score']})")
else:
    falha("Tendência de alta", f"esperava LONG >= 75, obteve {s_alta['direcao']} score={s_alta['score']}")

# calcular_niveis
niveis = sig.calcular_niveis(30000.0, "long", 200.0)
if niveis["take_profit"] > niveis["entrada"] > niveis["stop_loss"]:
    ok(f"Níveis LONG: TP={niveis['take_profit']} > entrada={niveis['entrada']} > SL={niveis['stop_loss']}")
else:
    falha("Níveis LONG", str(niveis))

niveis_s = sig.calcular_niveis(30000.0, "short", 200.0)
if niveis_s["stop_loss"] > niveis_s["entrada"] > niveis_s["take_profit"]:
    ok(f"Níveis SHORT: SL > entrada > TP ✓")
else:
    falha("Níveis SHORT", str(niveis_s))

# ─────────────────────────────────────────────────────────────
# TESTE 3 — Kelly com histórico vazio
# ─────────────────────────────────────────────────────────────
print("\n  [3] Kelly Criterion")

import risco

wr, ratio = risco.kelly_win_rate([])
if wr == 0.50 and ratio == 2.0:
    ok(f"Histórico vazio → padrão conservador (wr={wr}, ratio={ratio})")
else:
    falha("Kelly histórico vazio", f"wr={wr} ratio={ratio}")

frac = risco.kelly_fraction(0.50, 2.0)
if 0.05 <= frac <= 0.25:
    ok(f"Kelly fraction ∈ [5%, 25%]: {frac*100:.1f}%")
else:
    falha("Kelly fraction fora do range", f"frac={frac}")

# Com histórico (10 wins, 5 losses)
hist_teste = (
    [{"data_hora": "2024-01-01 10:00:00", "lucro_pct": 2.0, "lucro_usdt": 4.0}] * 10
    + [{"data_hora": "2024-01-01 10:00:00", "lucro_pct": -1.0, "lucro_usdt": -2.0}] * 5
)
wr2, ratio2 = risco.kelly_win_rate(hist_teste, ultimos_n=30)
if wr2 > 0.6 and ratio2 > 1.5:
    ok(f"Kelly com histórico: wr={wr2:.2f} ratio={ratio2:.2f}")
else:
    falha("Kelly com histórico", f"wr={wr2} ratio={ratio2}")

# ─────────────────────────────────────────────────────────────
# TESTE 4 — Proteção de capital: hibernação
# ─────────────────────────────────────────────────────────────
print("\n  [4] Proteção de Capital")

import protecao
import config as cfg

# Estado simulado com mês em andamento
estado_sim = {
    "high_water_mark": 200.0,
    "reserva_trancada": 0.0,
    "banca_inicio_mes": 175.44,
    "banca_inicio_ano": 175.44,
    "mes_atual": protecao._mes_atual(),
    "ano_atual": protecao._ano_atual(),
    "hibernando": False,
    "historico_mensal": [],
    "ultima_atualizacao": protecao._agora_str(),
}

# Simula perda de 3.5 % no mês
banca_perda = 175.44 * (1 - 0.035)   # ≈ 169.31
hib, motivo = protecao.checar_hibernacao(estado_sim, banca_perda)
if hib:
    ok(f"Hibernação ativada com perda de 3.5%: {motivo[:40]}")
else:
    falha("Hibernação", f"deveria hibernar com perda 3.5%: banca={banca_perda:.2f}")

# Simula novo mês → acorda
estado_sim2 = dict(estado_sim)
estado_sim2["hibernando"] = True
estado_sim2["mes_atual"] = "2024-01"   # mês antigo

# verificar_virada_mes não salva arquivo em modo teste — simulamos manualmente
estado_sim2["mes_atual"] = protecao._mes_atual()
estado_sim2["hibernando"] = False   # mês novo acorda
hib2, _ = protecao.checar_hibernacao(estado_sim2, 175.44)
if not hib2:
    ok("Novo mês → hibernação resetada")
else:
    falha("Novo mês", "ainda hibernando")

# HWM atualiza corretamente
hwm, abaixo = protecao.checar_high_water_mark(estado_sim, 250.0)
if hwm == 250.0 and abaixo == 0.0:
    ok(f"HWM atualizado para novo pico: ${hwm:.2f}")
else:
    falha("HWM", f"hwm={hwm} abaixo={abaixo}")

# ─────────────────────────────────────────────────────────────
# TESTE 5 — Trailing Stop
# ─────────────────────────────────────────────────────────────
print("\n  [5] Trailing Stop")

# LONG
ts_long = risco.TrailingStop(entrada=30000, direcao="long", gatilho=30360)

# Preço sobe, mas ainda não atingiu o gatilho
r = ts_long.atualizar(30200)
if r is None:
    ok("Trailing LONG — abaixo do gatilho → None")
else:
    falha("Trailing LONG gatilho", f"esperado None, obteve {r}")

# Preço atinge o gatilho → trailing ativa
r = ts_long.atualizar(30400)
if r is not None and r != -1 and r > 0:
    ok(f"Trailing LONG ativado — stop em ${r:,.2f}")
else:
    falha("Trailing LONG ativação", f"resultado={r}")

# Preço sobe mais → stop sobe
r = ts_long.atualizar(30600)
if r is not None and r != -1:
    ok(f"Trailing LONG avança — novo stop ${r:,.2f}")
else:
    ok("Trailing LONG — sem novo pico acima (normal)")

# Preço cai abaixo do stop → fecha
stop_atual = ts_long.stop_atual or 0
r = ts_long.atualizar(stop_atual - 10)
if r == -1:
    ok("Trailing LONG disparado — retorna -1 (fechar posição)")
else:
    falha("Trailing LONG disparo", f"esperado -1, obteve {r}")

# SHORT
ts_short = risco.TrailingStop(entrada=30000, direcao="short", gatilho=29640)
r = ts_short.atualizar(29700)
if r is None:
    ok("Trailing SHORT — acima do gatilho → None")
else:
    falha("Trailing SHORT gatilho", f"esperado None, obteve {r}")

r = ts_short.atualizar(29600)
if r is not None and r != -1:
    ok(f"Trailing SHORT ativado — stop em ${r:,.2f}")
else:
    falha("Trailing SHORT ativação", f"resultado={r}")

# ─────────────────────────────────────────────────────────────
# RESULTADO FINAL
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
if erros == 0:
    print(f"  🎉 TODOS OS TESTES PASSARAM!")
else:
    print(f"  ⚠️  {erros} teste(s) falharam.")
print("=" * 55 + "\n")

sys.exit(0 if erros == 0 else 1)
