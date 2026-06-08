# ============================================================
# relatorio.py — Dashboard de performance mensal
# Execute: python relatorio.py
# ============================================================

import json
import os
import sys
import io
from datetime import datetime, date
from collections import defaultdict

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import config


def carregar_historico() -> list:
    if not os.path.exists("historico_trades.json"):
        return []
    try:
        with open("historico_trades.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def carregar_estado_prot() -> dict:
    if not os.path.exists("estado_protecao.json"):
        return {}
    try:
        with open("estado_protecao.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def barra_ascii(valor: float, max_abs: float, largura: int = 20) -> str:
    """Gera barra visual ASCII proporcional ao valor."""
    if max_abs == 0:
        return " " * largura
    frac = abs(valor) / max_abs
    n    = int(frac * largura)
    if valor >= 0:
        return "█" * n + "░" * (largura - n)
    else:
        return "▓" * n + "░" * (largura - n)


def calcular_drawdown(lucros_acumulados: list) -> float:
    """Calcula o drawdown máximo a partir da lista de banca acumulada."""
    pico = -float("inf")
    dd   = 0.0
    for v in lucros_acumulados:
        if v > pico:
            pico = v
        queda = pico - v
        if queda > dd:
            dd = queda
    return round(dd, 4)


def main():
    historico = carregar_historico()
    estado    = carregar_estado_prot()

    banca_inicial = config.BANCA_USDT

    print("\n" + "=" * 60)
    print("  📈 DASHBOARD DE PERFORMANCE — ScalpBot BTC/USDT")
    print("=" * 60)

    if not historico:
        print("\n  Nenhum trade registrado ainda.")
        print("=" * 60)
        return

    # ── 1. RESUMO GERAL ──────────────────────────────────────
    total_trades = len(historico)
    wins         = [t for t in historico if t.get("lucro_pct", 0) > 0]
    losses       = [t for t in historico if t.get("lucro_pct", 0) <= 0]
    win_rate     = len(wins) / total_trades * 100

    lucros_list  = [t.get("lucro_usdt", 0) for t in historico]
    lucro_total  = sum(lucros_list)
    banca_atual  = banca_inicial + lucro_total
    retorno_pct  = (lucro_total / banca_inicial) * 100 if banca_inicial > 0 else 0

    # Profit Factor
    soma_wins   = sum(abs(t.get("lucro_usdt", 0)) for t in wins)
    soma_losses = sum(abs(t.get("lucro_usdt", 0)) for t in losses)
    profit_factor = (soma_wins / soma_losses) if soma_losses > 0 else float("inf")

    # Drawdown máximo
    banca_acum   = []
    acum = banca_inicial
    for t in historico:
        acum += t.get("lucro_usdt", 0)
        banca_acum.append(acum)
    dd_max = calcular_drawdown(banca_acum)

    print(f"\n  {'Total de trades:':<25} {total_trades}")
    print(f"  {'Win Rate:':<25} {win_rate:.1f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  {'Lucro total:':<25} ${lucro_total:+.2f} USDT")
    print(f"  {'Banca inicial:':<25} ${banca_inicial:.2f}")
    print(f"  {'Banca atual:':<25} ${banca_atual:.2f}")
    print(f"  {'Retorno total:':<25} {retorno_pct:+.2f}%")
    print(f"  {'Profit Factor:':<25} {profit_factor:.2f}")
    print(f"  {'Drawdown máximo:':<25} ${dd_max:.2f}")

    # ── 2. RESULTADO DIA A DIA ────────────────────────────────
    print("\n" + "-" * 60)
    print("  📅 RESULTADO DIA A DIA")
    print("-" * 60)

    por_dia: dict = defaultdict(list)
    for t in historico:
        d = t.get("data_hora", "")[:10]
        por_dia[d].append(t.get("lucro_usdt", 0))

    dias_ordenados = sorted(por_dia.keys())
    valores_dias   = [sum(por_dia[d]) for d in dias_ordenados]
    max_abs_dia    = max((abs(v) for v in valores_dias), default=1)

    banca_acum_dia = banca_inicial
    print(f"  {'Data':<12} {'Lucro':>8} {'':20}  {'Banca':>9}")
    print("-" * 60)
    for d in dias_ordenados:
        lucro_d = sum(por_dia[d])
        trades_d = len(por_dia[d])
        banca_acum_dia += lucro_d
        barra = barra_ascii(lucro_d, max_abs_dia, 18)
        emoji = "✅" if lucro_d >= 0 else "❌"
        print(
            f"  {d:<12} ${lucro_d:>+7.2f}  {barra}  "
            f"${banca_acum_dia:>8.2f} {emoji} ({trades_d}t)"
        )

    # ── 3. RESULTADO MÊS A MÊS ───────────────────────────────
    print("\n" + "-" * 60)
    print("  📆 RESULTADO MÊS A MÊS")
    print("-" * 60)

    por_mes: dict = defaultdict(list)
    for t in historico:
        m = t.get("data_hora", "")[:7]
        por_mes[m].append(t.get("lucro_usdt", 0))

    meses_ordenados = sorted(por_mes.keys())
    print(f"  {'Mês':<10} {'Lucro':>9} {'%':>7} {'Trades':>7} {'Média/dia':>10}")
    print("-" * 60)

    for m in meses_ordenados:
        lucro_m  = sum(por_mes[m])
        trades_m = len(por_mes[m])
        pct_m    = (lucro_m / banca_inicial) * 100
        # Dias únicos no mês
        dias_mes = len(set(
            t.get("data_hora", "")[:10]
            for t in historico
            if t.get("data_hora", "").startswith(m)
        ))
        media_d  = lucro_m / dias_mes if dias_mes > 0 else 0
        emoji    = "✅" if lucro_m >= 0 else "❌"
        print(
            f"  {m:<10} ${lucro_m:>+8.2f} {pct_m:>+6.2f}% "
            f"{trades_m:>7} ${media_d:>+9.2f} {emoji}"
        )

    # ── 4. CURVA DA BANCA (ASCII) ────────────────────────────
    print("\n" + "-" * 60)
    print("  📈 CURVA DA BANCA")
    print("-" * 60)

    if len(banca_acum) > 1:
        max_b = max(banca_acum)
        min_b = min(banca_acum)
        escala = max_b - min_b if max_b != min_b else 1

        LINHAS = 10
        COLUNAS = min(len(banca_acum), 50)

        # Reamostra para 50 pontos
        passo = max(1, len(banca_acum) // COLUNAS)
        amostras = banca_acum[::passo][:COLUNAS]

        for linha in range(LINHAS, 0, -1):
            threshold = min_b + (linha / LINHAS) * escala
            row = ""
            for v in amostras:
                row += "█" if v >= threshold else " "
            label = f"${min_b + (linha/LINHAS)*escala:>8.2f} |"
            print(f"  {label} {row}")
        print(f"  {'':>9}+" + "-" * COLUNAS)
        print(f"  {'(início)':>9}  {'':>{COLUNAS//2}}(fim)")
    else:
        print("  Dados insuficientes para exibir curva.")

    # ── 5. PROTEÇÃO ──────────────────────────────────────────
    print("\n" + "-" * 60)
    print("  🛡️  PROTEÇÃO DE CAPITAL")
    print("-" * 60)

    if estado:
        hwm       = estado.get("high_water_mark", banca_inicial)
        reserva   = estado.get("reserva_trancada", 0.0)
        hibernando = estado.get("hibernando", False)
        meses_hib = sum(
            1 for m in estado.get("historico_mensal", [])
            if m.get("lucro_pct", 0) < 0
        )
        print(f"  High Water Mark:   ${hwm:.2f}")
        print(f"  Reserva Trancada:  ${reserva:.2f}")
        print(f"  Hibernando:        {'🔴 SIM' if hibernando else '🟢 NÃO'}")
        print(f"  Meses negativos:   {meses_hib}")
    else:
        print("  Estado de proteção não encontrado.")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
