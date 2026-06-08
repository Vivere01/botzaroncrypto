# ============================================================
# risco.py — Kelly Criterion + Position Sizing + Trailing Stop
# ============================================================

import json
import os
from datetime import datetime, date
import config

HISTORICO_ARQUIVO = "historico_trades.json"


# ── Persistência ─────────────────────────────────────────────

def salvar_trade(trade: dict) -> None:
    """Adiciona um trade ao arquivo de histórico JSON."""
    historico = carregar_historico()
    historico.append(trade)
    try:
        with open(HISTORICO_ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[RISCO] Aviso: não foi possível salvar trade — {e}")


def carregar_historico() -> list:
    """Carrega o histórico de trades do arquivo JSON."""
    if not os.path.exists(HISTORICO_ARQUIVO):
        return []
    try:
        with open(HISTORICO_ARQUIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


# ── Kelly Criterion ──────────────────────────────────────────

def kelly_win_rate(historico: list, ultimos_n: int = 30):
    """
    Calcula win rate e ratio médio a partir dos últimos N trades.
    Se histórico tiver menos de 5 trades: retorna padrão conservador.
    Retorna: (win_rate, avg_ratio)
    """
    trades = [t for t in historico if "lucro_pct" in t]
    trades = trades[-ultimos_n:]   # pega apenas os últimos N

    if len(trades) < 5:
        return 0.50, 2.0           # padrão conservador

    wins   = [t for t in trades if t["lucro_pct"] > 0]
    losses = [t for t in trades if t["lucro_pct"] <= 0]

    win_rate = len(wins) / len(trades) if trades else 0.5

    # Ratio médio: média do ganho / média da perda
    avg_ganho  = (sum(abs(t["lucro_pct"]) for t in wins)  / len(wins))  if wins   else config.TAKE_PROFIT_PCT
    avg_perda  = (sum(abs(t["lucro_pct"]) for t in losses) / len(losses)) if losses else config.STOP_LOSS_PCT
    avg_ratio  = avg_ganho / avg_perda if avg_perda > 0 else 2.0

    return round(win_rate, 4), round(avg_ratio, 4)


def kelly_fraction(win_rate: float, ratio: float) -> float:
    """
    Fórmula de Kelly: f = (p×b - q) / b
    Usa meio-Kelly (×0.5) por segurança.
    Limita resultado entre 5 % e 25 %.
    """
    p = win_rate
    q = 1.0 - p
    b = ratio

    if b <= 0:
        return 0.10   # fallback conservador

    kelly = (p * b - q) / b
    meio_kelly = kelly * 0.5      # segurança extra

    # Limita entre 5 % e 25 %
    frac = max(0.05, min(0.25, meio_kelly))
    return round(frac, 4)


def calcular_tamanho_posicao(banca: float,
                              preco: float,
                              historico: list) -> dict:
    """
    Calcula o tamanho da posição com Kelly Criterion.
    Retorna dict completo com capital, quantidade e métricas.
    """
    win_rate, ratio = kelly_win_rate(historico)
    kelly_frac      = kelly_fraction(win_rate, ratio)

    # Usa o menor entre kelly e o limite fixo do config
    frac_final = min(kelly_frac, config.PORCENTO_POR_TRADE)

    capital_usdt      = round(banca * frac_final, 2)
    capital_alavancado = round(capital_usdt * config.ALAVANCAGEM, 2)
    quantidade_btc     = round(capital_alavancado / preco, 6) if preco > 0 else 0
    margem_usdt        = capital_usdt  # margem = capital sem alavancagem

    return {
        "capital_usdt":      capital_usdt,
        "capital_alavancado": capital_alavancado,
        "quantidade_btc":    quantidade_btc,
        "margem_usdt":       margem_usdt,
        "win_rate":          win_rate,
        "ratio":             ratio,
        "kelly_frac":        kelly_frac,
        "frac_final":        frac_final,
    }


# ── Verificações diárias ─────────────────────────────────────

def stats_do_dia(historico: list) -> dict:
    """Filtra os trades de hoje e calcula estatísticas."""
    hoje = date.today().isoformat()
    trades_hoje = [
        t for t in historico
        if t.get("data_hora", "").startswith(hoje)
    ]

    wins_hoje  = [t for t in trades_hoje if t.get("lucro_pct", 0) > 0]
    lucro_dia  = sum(t.get("lucro_usdt", 0) for t in trades_hoje)

    return {
        "trades_hoje": len(trades_hoje),
        "wins_hoje":   len(wins_hoje),
        "lucro_dia":   round(lucro_dia, 4),
    }


def pode_operar_hoje(banca_atual: float,
                     banca_inicio_dia: float,
                     historico: list) -> tuple:
    """
    Verifica se o bot pode abrir novas posições.
    Retorna (pode_operar: bool, motivo: str).
    """
    stats = stats_do_dia(historico)

    # Limite de trades diários
    if stats["trades_hoje"] >= config.MAX_TRADES_DIA:
        return False, f"Limite de {config.MAX_TRADES_DIA} trades/dia atingido"

    # Stop diário por perda
    if banca_inicio_dia > 0:
        perda_dia = (banca_inicio_dia - banca_atual) / banca_inicio_dia
        if perda_dia >= config.MAX_PERDA_DIARIA:
            return False, (
                f"Stop diário: perda de {perda_dia*100:.2f}% "
                f"(limite {config.MAX_PERDA_DIARIA*100:.1f}%)"
            )

    # Stop global
    banca_inicial = config.BANCA_USDT
    if banca_inicial > 0:
        queda_total = (banca_inicial - banca_atual) / banca_inicial
        if queda_total >= config.STOP_GLOBAL_PCT:
            return False, (
                f"STOP GLOBAL ativado: banca caiu {queda_total*100:.2f}%"
            )

    return True, "Pode operar"


# ── Trailing Stop ─────────────────────────────────────────────

class TrailingStop:
    """
    Trailing Stop dinâmico.
    - Para LONG: stop sobe junto com o preço, nunca desce.
    - Para SHORT: stop desce junto com o preço, nunca sobe.
    """

    def __init__(self, entrada: float, direcao: str, gatilho: float):
        self.entrada   = entrada
        self.direcao   = direcao
        self.gatilho   = gatilho       # preço que ativa o trailing
        self.ativado   = False
        self.pico      = entrada       # pico mais alto (long) ou mais baixo (short)
        self.stop_atual = None

    def atualizar(self, preco_atual: float):
        """
        Atualiza o trailing stop.
        Retorna:
          - novo stop (float) se subiu/desceu
          - -1 se trailing foi atingido (fechar posição)
          - None se sem mudança relevante
        """
        if self.direcao == "long":
            # Verifica se o gatilho foi atingido
            if not self.ativado and preco_atual >= self.gatilho:
                self.ativado   = True
                self.pico      = preco_atual
                self.stop_atual = preco_atual * (1 - config.TRAILING_STOP_PCT)
                return self.stop_atual

            if not self.ativado:
                return None

            # Atualiza pico e stop se preço subiu
            if preco_atual > self.pico:
                self.pico       = preco_atual
                novo_stop       = preco_atual * (1 - config.TRAILING_STOP_PCT)
                if novo_stop > self.stop_atual:
                    self.stop_atual = novo_stop
                    return self.stop_atual

            # Verifica se preço caiu abaixo do stop
            if preco_atual <= self.stop_atual:
                return -1   # sinaliza fechamento

        else:  # short
            if not self.ativado and preco_atual <= self.gatilho:
                self.ativado    = True
                self.pico       = preco_atual
                self.stop_atual = preco_atual * (1 + config.TRAILING_STOP_PCT)
                return self.stop_atual

            if not self.ativado:
                return None

            if preco_atual < self.pico:
                self.pico       = preco_atual
                novo_stop       = preco_atual * (1 + config.TRAILING_STOP_PCT)
                if novo_stop < self.stop_atual:
                    self.stop_atual = novo_stop
                    return self.stop_atual

            if preco_atual >= self.stop_atual:
                return -1

        return None
