# ============================================================
# telegram_notif.py — Notificações ricas para o Telegram
# Chamado automaticamente pelo bot a cada evento relevante
# ============================================================

from datetime import datetime
import config

try:
    import requests as _req
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


# ── Envio base ────────────────────────────────────────────────

def _enviar(texto: str, parse_mode: str = "Markdown") -> bool:
    """Envia mensagem ao Telegram. Retorna True se OK."""
    if not _REQUESTS_OK:
        return False
    token    = config.TELEGRAM_TOKEN
    chat_id  = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False
    try:
        resp = _req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id":    chat_id,
                "text":       texto,
                "parse_mode": parse_mode,
            },
            timeout=10,
        )
        return resp.json().get("ok", False)
    except Exception:
        return False


# ── Helpers ───────────────────────────────────────────────────

def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def _barra_pct(pct: float, largura: int = 10) -> str:
    """Barra de progresso simples."""
    pct_abs = min(abs(pct), 100)
    n = int(pct_abs / 100 * largura)
    simbolo = "🟩" if pct >= 0 else "🟥"
    return simbolo * n + "⬜" * (largura - n)


# ── Eventos ───────────────────────────────────────────────────

def bot_iniciado(banca: float, modo: str):
    """Notifica que o bot foi iniciado."""
    texto = (
        "🤖 *ScalpBot BTC/USDT — INICIADO*\n"
        f"🕐 `{_agora()}`\n\n"
        f"💰 Banca inicial: `${banca:.2f} USDT`\n"
        f"⚙️ Modo: `{modo}`\n"
        f"📊 Par: `{config.SYMBOL}` | TF: `{config.TIMEFRAME}`\n"
        f"🔧 Alavancagem: `{config.ALAVANCAGEM}x`\n\n"
        "👁️ Monitorando o mercado..."
    )
    _enviar(texto)


def bot_encerrado(motivo: str, banca_final: float, banca_inicial: float):
    """Notifica encerramento do bot."""
    lucro     = banca_final - banca_inicial
    retorno   = (lucro / banca_inicial * 100) if banca_inicial > 0 else 0
    emoji     = "📈" if lucro >= 0 else "📉"
    texto = (
        f"🛑 *ScalpBot — ENCERRADO*\n"
        f"🕐 `{_agora()}`\n\n"
        f"📝 Motivo: _{motivo}_\n\n"
        f"{emoji} *Resultado da sessão:*\n"
        f"  Banca inicial: `${banca_inicial:.2f}`\n"
        f"  Banca final:   `${banca_final:.2f}`\n"
        f"  Lucro/Perda:   `${lucro:+.2f}` ({retorno:+.2f}%)\n"
    )
    _enviar(texto)


def posicao_aberta(direcao: str, entrada: float, sl: float, tp: float,
                   quantidade: float, capital: float, score: int = 0):
    """Notifica abertura de posição."""
    emoji_dir = "🟢 LONG 📈" if direcao.lower() == "long" else "🔴 SHORT 📉"
    risco_pct = abs(entrada - sl) / entrada * 100 * config.ALAVANCAGEM
    ganho_pct = abs(tp - entrada) / entrada * 100 * config.ALAVANCAGEM
    ratio     = ganho_pct / risco_pct if risco_pct > 0 else 0

    texto = (
        f"🚀 *POSIÇÃO ABERTA — {direcao.upper()}*\n"
        f"🕐 `{_agora()}`\n\n"
        f"📌 Direção:  *{emoji_dir}*\n"
        f"💵 Entrada:  `${entrada:,.2f}`\n"
        f"🛑 Stop Loss: `${sl:,.2f}` (-{risco_pct:.1f}%)\n"
        f"🎯 Take Profit: `${tp:,.2f}` (+{ganho_pct:.1f}%)\n\n"
        f"💼 Capital: `${capital:.2f}` | Qtd: `{quantidade} BTC`\n"
        f"⚖️  R:R = 1 : {ratio:.1f}\n"
        + (f"🧠 Score: `{score}/100`\n" if score else "")
    )
    _enviar(texto)


def posicao_fechada_win(direcao: str, entrada: float, saida: float,
                        lucro_usdt: float, lucro_pct: float,
                        motivo: str, banca: float, trades_hoje: int):
    """Notifica fechamento com LUCRO."""
    barra = _barra_pct(lucro_pct * config.ALAVANCAGEM)
    texto = (
        f"✅ *TRADE VENCEDOR — {direcao.upper()}*\n"
        f"🕐 `{_agora()}`\n\n"
        f"📈 {barra}\n\n"
        f"💵 Entrada: `${entrada:,.2f}`\n"
        f"💵 Saída:   `${saida:,.2f}`\n"
        f"📝 Motivo:  _{motivo}_\n\n"
        f"💰 *Resultado: +${lucro_usdt:.2f} USDT ({lucro_pct:+.2f}%)*\n"
        f"🏦 Banca atual: `${banca:.2f}`\n"
        f"📊 Trades hoje: `{trades_hoje}`\n"
    )
    _enviar(texto)


def posicao_fechada_loss(direcao: str, entrada: float, saida: float,
                         perda_usdt: float, perda_pct: float,
                         motivo: str, banca: float, trades_hoje: int):
    """Notifica fechamento com PERDA."""
    barra = _barra_pct(perda_pct)
    texto = (
        f"❌ *TRADE PERDEDOR — {direcao.upper()}*\n"
        f"🕐 `{_agora()}`\n\n"
        f"📉 {barra}\n\n"
        f"💵 Entrada: `${entrada:,.2f}`\n"
        f"💵 Saída:   `${saida:,.2f}`\n"
        f"📝 Motivo:  _{motivo}_\n\n"
        f"💸 *Resultado: ${perda_usdt:.2f} USDT ({perda_pct:.2f}%)*\n"
        f"🏦 Banca atual: `${banca:.2f}`\n"
        f"📊 Trades hoje: `{trades_hoje}`\n"
    )
    _enviar(texto)


def trailing_atualizado(novo_stop: float, preco_atual: float, direcao: str):
    """Notifica atualização do trailing stop."""
    texto = (
        f"🔄 *TRAILING STOP ATUALIZADO*\n"
        f"🕐 `{_agora()}`\n\n"
        f"📌 Direção: `{direcao.upper()}`\n"
        f"💹 Preço atual: `${preco_atual:,.2f}`\n"
        f"🛡️ Novo stop:   `${novo_stop:,.2f}`\n"
    )
    _enviar(texto)


def alerta_risco(mensagem: str, nivel: str = "AVISO"):
    """Envia alerta de risco crítico."""
    emoji = {"CRITICO": "🚨", "AVISO": "⚠️", "INFO": "ℹ️"}.get(nivel, "⚠️")
    texto = (
        f"{emoji} *ALERTA {nivel} — ScalpBot*\n"
        f"🕐 `{_agora()}`\n\n"
        f"{mensagem}"
    )
    _enviar(texto)


def resumo_diario(banca_inicio: float, banca_atual: float,
                  trades: list, data: str = None):
    """Envia resumo diário de performance."""
    if data is None:
        data = datetime.now().strftime("%d/%m/%Y")

    lucro      = banca_atual - banca_inicio
    retorno    = (lucro / banca_inicio * 100) if banca_inicio > 0 else 0
    wins       = [t for t in trades if t.get("lucro_usdt", 0) > 0]
    losses     = [t for t in trades if t.get("lucro_usdt", 0) <= 0]
    win_rate   = len(wins) / len(trades) * 100 if trades else 0
    emoji_day  = "✅" if lucro >= 0 else "❌"
    barra      = _barra_pct(retorno)

    texto = (
        f"📅 *RESUMO DIÁRIO — {data}*\n"
        f"{'─' * 28}\n\n"
        f"{barra}\n\n"
        f"📊 Trades:    `{len(trades)}` ({len(wins)}W / {len(losses)}L)\n"
        f"🎯 Win Rate:  `{win_rate:.1f}%`\n"
        f"💰 Lucro:     `${lucro:+.2f} USDT` ({retorno:+.2f}%)\n"
        f"🏦 Banca:     `${banca_atual:.2f} USDT`\n"
        f"\n{emoji_day} *{'DIA POSITIVO' if lucro >= 0 else 'DIA NEGATIVO'}*"
    )
    _enviar(texto)


def stop_global_ativado(banca: float, queda_pct: float):
    """Alerta crítico de stop global."""
    texto = (
        f"🚨 *STOP GLOBAL ATIVADO!*\n"
        f"🕐 `{_agora()}`\n\n"
        f"📉 A banca caiu `{queda_pct:.1f}%` — limite atingido!\n"
        f"🏦 Banca atual: `${banca:.2f} USDT`\n\n"
        f"⛔ *Bot encerrado automaticamente por proteção de capital.*"
    )
    _enviar(texto)


def hibernacao_ativada(motivo: str):
    """Notifica entrada em modo hibernação."""
    texto = (
        f"😴 *HIBERNAÇÃO ATIVADA*\n"
        f"🕐 `{_agora()}`\n\n"
        f"📝 Motivo: _{motivo}_\n\n"
        f"💤 O bot parou de operar para proteger a banca.\n"
        f"🔄 Será retomado no próximo ciclo de avaliação."
    )
    _enviar(texto)
