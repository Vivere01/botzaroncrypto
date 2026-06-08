# ============================================================
# watchdog.py — Guarda-cão 24/7 com relatórios automáticos
# ============================================================

import subprocess
import sys
import io
import os
import time
import json
from datetime import datetime, date

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import config

# Tenta importar requests para Telegram
try:
    import requests as req_lib
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

LOG_WATCHDOG   = "watchdog.log"
LOG_BOT        = "scalp.log"
MAX_REINICIALIZACOES = 5
INTERVALO_CHECK      = 60       # segundos entre verificações
LIMITE_INATIVIDADE   = 30 * 60  # 30 minutos sem log = alerta


def log_wdg(msg: str):
    """Log do watchdog com timestamp."""
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{ts}] [WDG] {msg}"
    print(linha)
    try:
        with open(LOG_WATCHDOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass


def enviar_telegram(msg: str):
    """Envia mensagem ao Telegram se configurado."""
    if not REQUESTS_OK or not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
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
        log_wdg(f"Telegram falhou: {e}")


# ── Relatórios ────────────────────────────────────────────────

def carregar_historico() -> list:
    """Carrega historico_trades.json."""
    try:
        with open("historico_trades.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def filtrar_por_data(historico: list, data_str: str) -> list:
    """Filtra trades de uma data específica (YYYY-MM-DD)."""
    return [t for t in historico if t.get("data_hora", "").startswith(data_str)]


def filtrar_por_mes(historico: list, mes_str: str) -> list:
    """Filtra trades de um mês específico (YYYY-MM)."""
    return [t for t in historico if t.get("data_hora", "").startswith(mes_str)]


def gerar_relatorio_diario(data: date) -> str:
    """Gera relatório do dia anterior como string."""
    historico = carregar_historico()
    trades    = filtrar_por_data(historico, data.isoformat())

    if not trades:
        return f"📊 Relatório {data.isoformat()}: Nenhum trade realizado hoje."

    wins   = [t for t in trades if t.get("lucro_pct", 0) > 0]
    losses = [t for t in trades if t.get("lucro_pct", 0) <= 0]
    lucros = [t.get("lucro_usdt", 0) for t in trades]
    lucro_total = sum(lucros)

    melhor = max(trades, key=lambda t: t.get("lucro_usdt", 0))
    pior   = min(trades, key=lambda t: t.get("lucro_usdt", 0))

    emoji = "✅" if lucro_total >= 0 else "❌"

    return (
        f"{emoji} Relatório Diário — {data.isoformat()}\n"
        f"Trades: {len(trades)} | Win Rate: {len(wins)/len(trades)*100:.1f}%\n"
        f"Wins: {len(wins)} | Losses: {len(losses)}\n"
        f"Lucro do dia: ${lucro_total:+.2f} USDT\n"
        f"Melhor trade: ${melhor.get('lucro_usdt', 0):+.2f} ({melhor.get('direcao','?').upper()})\n"
        f"Pior trade:   ${pior.get('lucro_usdt', 0):+.2f} ({pior.get('direcao','?').upper()})"
    )


def gerar_relatorio_mensal(mes_str: str) -> str:
    """Gera relatório mensal como string."""
    historico = carregar_historico()
    trades    = filtrar_por_mes(historico, mes_str)

    if not trades:
        return f"📊 Relatório Mensal {mes_str}: Nenhum trade realizado."

    wins        = [t for t in trades if t.get("lucro_pct", 0) > 0]
    lucros      = [t.get("lucro_usdt", 0) for t in trades]
    lucro_total = sum(lucros)

    melhor = max(trades, key=lambda t: t.get("lucro_usdt", 0))
    pior   = min(trades, key=lambda t: t.get("lucro_usdt", 0))

    banca_atual   = config.BANCA_USDT + lucro_total
    retorno_pct   = (lucro_total / config.BANCA_USDT) * 100

    # Agrupa por dia
    dias: dict = {}
    for t in trades:
        d = t.get("data_hora", "")[:10]
        dias.setdefault(d, []).append(t.get("lucro_usdt", 0))

    linhas_dias = "\n".join(
        f"  {d}: ${sum(v):+.2f} ({len(v)} trades)"
        for d, v in sorted(dias.items())
    )

    emoji = "✅" if lucro_total >= 0 else "❌"

    return (
        f"{emoji} Relatório Mensal — {mes_str}\n"
        f"Total trades: {len(trades)} | Win Rate: {len(wins)/len(trades)*100:.1f}%\n"
        f"Lucro total: ${lucro_total:+.2f} | Retorno: {retorno_pct:+.2f}%\n"
        f"Banca atual: ${banca_atual:.2f}\n"
        f"Melhor trade: ${melhor.get('lucro_usdt',0):+.2f}\n"
        f"Pior trade:   ${pior.get('lucro_usdt',0):+.2f}\n"
        f"\nResultado por dia:\n{linhas_dias}"
    )


# ── Heartbeat ────────────────────────────────────────────────

def checar_heartbeat():
    """Verifica se o bot está ativo (log atualizado nos últimos 30 min)."""
    if not os.path.exists(LOG_BOT):
        return
    mtime = os.path.getmtime(LOG_BOT)
    agora = time.time()
    if agora - mtime > LIMITE_INATIVIDADE:
        msg = (
            f"⚠️ Heartbeat: bot sem atividade há mais de "
            f"{int((agora-mtime)/60)} minutos"
        )
        log_wdg(msg)
        enviar_telegram(msg)


# ── Stop global ───────────────────────────────────────────────

def checar_stop_global() -> bool:
    """
    Verifica se a banca caiu abaixo do limite de stop global.
    Retorna True se deve parar tudo.
    """
    historico = carregar_historico()
    lucro_total = sum(t.get("lucro_usdt", 0) for t in historico)
    banca_atual = config.BANCA_USDT + lucro_total

    if banca_atual < config.BANCA_USDT * (1 - config.STOP_GLOBAL_PCT):
        msg = (
            f"🛑 STOP GLOBAL: banca atual ${banca_atual:.2f} "
            f"abaixo do limite ${config.BANCA_USDT * (1-config.STOP_GLOBAL_PCT):.2f}. "
            f"Watchdog encerrando tudo."
        )
        log_wdg(msg)
        enviar_telegram(msg)
        return True
    return False


# ── Loop principal do watchdog ───────────────────────────────

def main():
    log_wdg("🐕 Watchdog iniciado")
    enviar_telegram("🐕 Watchdog iniciado — monitorando o ScalpBot 24/7")

    processo   = None
    reinicializacoes_hoje = 0
    data_reset = date.today()
    ultimo_relatorio_diario = None
    ultimo_relatorio_mensal = None

    while True:
        agora = datetime.now()
        hoje  = date.today()

        # ── Reset diário de reinicializações ──────────────────
        if hoje != data_reset:
            reinicializacoes_hoje = 0
            data_reset = hoje

        # ── Relatório diário às 00:00 ─────────────────────────
        if agora.hour == 0 and agora.minute < 2:
            ontem = date.fromordinal(hoje.toordinal() - 1)
            if ultimo_relatorio_diario != ontem.isoformat():
                rel = gerar_relatorio_diario(ontem)
                log_wdg(rel)
                enviar_telegram(rel)
                ultimo_relatorio_diario = ontem.isoformat()

        # ── Relatório mensal no dia 1 às 00:00 ───────────────
        if agora.day == 1 and agora.hour == 0 and agora.minute < 2:
            mes_anterior = f"{agora.year}-{agora.month-1:02d}" if agora.month > 1 \
                else f"{agora.year-1}-12"
            if ultimo_relatorio_mensal != mes_anterior:
                rel = gerar_relatorio_mensal(mes_anterior)
                log_wdg(rel)
                enviar_telegram(rel)
                ultimo_relatorio_mensal = mes_anterior

        # ── Stop global ───────────────────────────────────────
        if checar_stop_global():
            if processo and processo.poll() is None:
                processo.terminate()
            log_wdg("🛑 Stop global ativado. Watchdog encerrado.")
            break

        # ── Heartbeat ─────────────────────────────────────────
        checar_heartbeat()

        # ── Verifica processo bot ─────────────────────────────
        if processo is None or processo.poll() is not None:
            codigo = processo.poll() if processo else "N/A"

            if processo is not None:
                log_wdg(f"⚠️ Bot encerrou com código {codigo}")
                reinicializacoes_hoje += 1

            if reinicializacoes_hoje > MAX_REINICIALIZACOES:
                msg = (
                    f"🚨 ALERTA CRÍTICO: Bot reiniciado "
                    f"{reinicializacoes_hoje}x hoje. "
                    f"Watchdog pausando para intervenção manual."
                )
                log_wdg(msg)
                enviar_telegram(msg)
                time.sleep(3600)   # pausa 1 hora para intervenção
                reinicializacoes_hoje = 0
                continue

            # Aguarda 15s antes de reiniciar
            if processo is not None:
                log_wdg(f"🔄 Reiniciando bot em 15s... (tentativa {reinicializacoes_hoje})")
                time.sleep(15)

            # Inicia bot_autonomo.py
            log_wdg("▶️ Iniciando bot_autonomo.py")
            try:
                processo = subprocess.Popen(
                    [sys.executable, "bot_autonomo.py"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                enviar_telegram(
                    f"▶️ Bot reiniciado (tentativa {reinicializacoes_hoje})"
                )
            except Exception as e:
                log_wdg(f"[ERRO] Não foi possível iniciar o bot: {e}")
                time.sleep(30)
                continue

        time.sleep(INTERVALO_CHECK)


if __name__ == "__main__":
    main()
