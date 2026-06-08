# ============================================================
# protecao.py — High Water Mark + Hibernação mensal
# Três camadas de proteção de capital
# ============================================================

import json
import os
from datetime import datetime
import config

ESTADO_ARQUIVO = "estado_protecao.json"


# ── Utilitários ───────────────────────────────────────────────

def _mes_atual() -> str:
    return datetime.now().strftime("%Y-%m")


def _ano_atual() -> int:
    return datetime.now().year


def _agora_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Carregar / salvar estado ─────────────────────────────────

def carregar_estado() -> dict:
    """Carrega estado de proteção do arquivo JSON."""
    if not os.path.exists(ESTADO_ARQUIVO):
        return _estado_inicial()
    try:
        with open(ESTADO_ARQUIVO, "r", encoding="utf-8") as f:
            estado = json.load(f)
        # Garante campos novos em versões antigas do arquivo
        for chave, valor in _estado_inicial().items():
            if chave not in estado:
                estado[chave] = valor
        return estado
    except Exception:
        return _estado_inicial()


def salvar_estado(estado: dict) -> None:
    """Persiste estado de proteção no arquivo JSON."""
    estado["ultima_atualizacao"] = _agora_str()
    try:
        with open(ESTADO_ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[PROTEÇÃO] Aviso: erro ao salvar estado — {e}")


def _estado_inicial() -> dict:
    """Estado padrão ao inicializar o bot pela primeira vez."""
    banca = config.BANCA_USDT
    return {
        "high_water_mark":    banca,
        "reserva_trancada":   0.0,
        "banca_inicio_mes":   banca,
        "banca_inicio_ano":   banca,
        "mes_atual":          _mes_atual(),
        "ano_atual":          _ano_atual(),
        "hibernando":         False,
        "historico_mensal":   [],
        "ultima_atualizacao": _agora_str(),
    }


# ── Virada de mês ────────────────────────────────────────────

def verificar_virada_mes(estado: dict, banca_atual: float) -> dict:
    """
    Detecta mudança de mês, fecha o mês anterior e abre o novo.
    Também detecta virada de ano.
    Retorna estado atualizado.
    """
    mes_agora = _mes_atual()
    ano_agora = _ano_atual()

    if estado["mes_atual"] == mes_agora:
        return estado   # mesmo mês, nada a fazer

    # ── Fecha o mês anterior ─────────────────────────────────
    banca_inicio = estado["banca_inicio_mes"]
    lucro_mes    = banca_atual - banca_inicio
    lucro_pct    = (lucro_mes / banca_inicio) if banca_inicio > 0 else 0.0

    # Calcula reserva: 50 % do lucro que exceder 5 %
    nova_reserva = 0.0
    if lucro_pct >= config.LUCRO_GATILHO_RESERVA:
        excesso     = banca_atual - banca_inicio * (1 + config.LUCRO_GATILHO_RESERVA)
        nova_reserva = excesso * config.LUCRO_RESERVA_PCT
        estado["reserva_trancada"] = round(
            estado["reserva_trancada"] + nova_reserva, 4
        )

    # Atualiza High Water Mark
    if banca_atual > estado["high_water_mark"]:
        estado["high_water_mark"] = banca_atual

    # Registra no histórico
    registro_mes = {
        "mes":          estado["mes_atual"],
        "banca_inicio": round(banca_inicio, 4),
        "banca_fim":    round(banca_atual, 4),
        "lucro_usdt":   round(lucro_mes, 4),
        "lucro_pct":    round(lucro_pct * 100, 2),
        "reserva_nova": round(nova_reserva, 4),
        "reserva_total": round(estado["reserva_trancada"], 4),
    }
    estado["historico_mensal"].append(registro_mes)

    msg = (
        f"[PROTEÇÃO] 📅 Fechamento do mês {estado['mes_atual']}: "
        f"Lucro {lucro_pct*100:.2f}% | "
        f"Reserva nova: ${nova_reserva:.2f} | "
        f"Total reserva: ${estado['reserva_trancada']:.2f}"
    )
    print(msg)

    # Virada de ano
    if estado["ano_atual"] != ano_agora:
        lucro_ano = banca_atual - estado["banca_inicio_ano"]
        pct_ano   = (lucro_ano / estado["banca_inicio_ano"]) * 100 if estado["banca_inicio_ano"] > 0 else 0
        print(
            f"[PROTEÇÃO] 🎆 Ano {estado['ano_atual']} encerrado. "
            f"Resultado anual: {pct_ano:.2f}%"
        )
        estado["banca_inicio_ano"] = banca_atual
        estado["ano_atual"]        = ano_agora

    # Abre o novo mês
    estado["mes_atual"]       = mes_agora
    estado["banca_inicio_mes"] = banca_atual
    estado["hibernando"]      = False   # acorda para o novo mês

    salvar_estado(estado)
    return estado


# ── Hibernação ────────────────────────────────────────────────

def checar_hibernacao(estado: dict, banca_atual: float) -> tuple:
    """
    Verifica se o bot deve hibernar.
    Retorna (hibernando: bool, motivo: str).
    """
    if estado["hibernando"]:
        return True, "Bot em hibernação (perda mensal atingiu limite)"

    banca_inicio = estado["banca_inicio_mes"]
    if banca_inicio <= 0:
        return False, "Operando normalmente"

    perda_mes = (banca_inicio - banca_atual) / banca_inicio
    if perda_mes >= config.PERDA_MAX_MES:
        estado["hibernando"] = True
        salvar_estado(estado)
        motivo = (
            f"Hibernação ativada: perda de {perda_mes*100:.2f}% "
            f"no mês (limite {config.PERDA_MAX_MES*100:.1f}%)"
        )
        print(f"[PROTEÇÃO] 🔴 {motivo}")
        return True, motivo

    return False, "Operando normalmente"


# ── High Water Mark ───────────────────────────────────────────

def checar_high_water_mark(estado: dict, banca_atual: float) -> tuple:
    """
    Atualiza o HWM se banca subiu.
    Retorna (hwm_atual: float, quanto_abaixo: float).
    """
    if banca_atual > estado["high_water_mark"]:
        estado["high_water_mark"] = banca_atual
        salvar_estado(estado)

    hwm      = estado["high_water_mark"]
    abaixo   = max(0.0, hwm - banca_atual)
    return hwm, round(abaixo, 4)


# ── Banca operacional ─────────────────────────────────────────

def banca_operacional(estado: dict, banca_atual: float) -> float:
    """
    Retorna a banca disponível para operar (descontando reserva trancada).
    Nunca menor que zero.
    """
    operacional = banca_atual - estado["reserva_trancada"]
    return max(0.0, round(operacional, 4))


# ── Status textual ────────────────────────────────────────────

def status_protecao(estado: dict, banca_atual: float) -> str:
    """
    Retorna string formatada com todas as métricas de proteção.
    """
    hwm, abaixo  = checar_high_water_mark(estado, banca_atual)
    operacional  = banca_operacional(estado, banca_atual)
    hibernando, _ = checar_hibernacao(estado, banca_atual)

    banca_inicio = estado["banca_inicio_mes"]
    lucro_mes    = banca_atual - banca_inicio
    pct_mes      = (lucro_mes / banca_inicio * 100) if banca_inicio > 0 else 0.0

    status = (
        f"\n{'='*50}\n"
        f"  PROTEÇÃO DE CAPITAL\n"
        f"{'='*50}\n"
        f"  Banca atual:       ${banca_atual:.2f}\n"
        f"  Banca operacional: ${operacional:.2f}\n"
        f"  Reserva trancada:  ${estado['reserva_trancada']:.2f}\n"
        f"  High Water Mark:   ${hwm:.2f} ({abaixo:.2f} abaixo)\n"
        f"  Resultado do mês:  {pct_mes:+.2f}%\n"
        f"  Mês atual:         {estado['mes_atual']}\n"
        f"  Hibernando:        {'🔴 SIM' if hibernando else '🟢 NÃO'}\n"
        f"{'='*50}"
    )
    return status


# ── Relatório de proteção ─────────────────────────────────────

def relatorio_protecao():
    """Imprime o histórico mensal completo com emojis."""
    estado = carregar_estado()
    historico = estado.get("historico_mensal", [])

    print("\n" + "=" * 55)
    print("  📊 RELATÓRIO DE PROTEÇÃO DE CAPITAL")
    print("=" * 55)
    print(f"  High Water Mark:  ${estado['high_water_mark']:.2f}")
    print(f"  Reserva Trancada: ${estado['reserva_trancada']:.2f}")
    print(f"  Hibernando:       {'🔴 SIM' if estado['hibernando'] else '🟢 NÃO'}")
    print("-" * 55)
    print(f"  {'Mês':<10} {'Início':>8} {'Fim':>8} {'Lucro':>8} {'%':>7} {'Reserva':>9}")
    print("-" * 55)

    for m in historico:
        emoji = "✅" if m["lucro_pct"] >= 0 else "❌"
        print(
            f"  {m['mes']:<10} "
            f"${m['banca_inicio']:>7.2f} "
            f"${m['banca_fim']:>7.2f} "
            f"${m['lucro_usdt']:>+7.2f} "
            f"{m['lucro_pct']:>+6.2f}% "
            f"${m['reserva_nova']:>8.2f} {emoji}"
        )

    if not historico:
        print("  Nenhum mês encerrado ainda.")

    print("=" * 55 + "\n")
