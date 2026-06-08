# ============================================================
# main.py — Menu interativo com diagnóstico e teste de conexão
# ============================================================

import sys
import os
import io

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import config

# Importação condicional da Binance
try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    BINANCE_OK = True
except ImportError:
    BINANCE_OK = False


def limpar():
    os.system("cls" if os.name == "nt" else "clear")


def cabecalho():
    print("\n" + "=" * 55)
    print("  🤖  ScalpBot — BTC/USDT Futures Automatizado")
    print(f"  Modo: {'TESTNET 🟡' if config.USAR_TESTNET else 'REAL 🔴'}")
    print(f"  Banca: ${config.BANCA_USDT:.2f} USDT  |  Alavancagem: {config.ALAVANCAGEM}x")
    print("=" * 55)


def menu_principal():
    print()
    print("  [1] Iniciar bot (via watchdog 24/7)")
    print("  [2] Diagnóstico de mercado (sem operar)")
    print("  [3] Dashboard de performance")
    print("  [4] Teste de conexão Binance")
    print("  [5] Sair")
    print()
    return input("  Escolha uma opção: ").strip()


# ── Opção 1: Iniciar bot ─────────────────────────────────────

def iniciar_bot():
    print("\n  Iniciando bot via watchdog...")
    print("  O watchdog mantém o bot vivo 24/7 e reinicia automaticamente.")
    print("  Para parar, pressione Ctrl+C neste terminal.\n")
    try:
        import watchdog
        watchdog.main()
    except KeyboardInterrupt:
        print("\n  Bot encerrado pelo usuário.")


# ── Opção 2: Diagnóstico ─────────────────────────────────────

def diagnostico():
    print("\n  📊 DIAGNÓSTICO DE MERCADO")
    print("  Conectando à Binance e baixando candles...")

    if not BINANCE_OK:
        print("  ❌ python-binance não instalado.")
        return

    try:
        if config.USAR_TESTNET:
            client = Client(config.API_KEY, config.API_SECRET, testnet=True)
        else:
            client = Client(config.API_KEY, config.API_SECRET)

        candles = client.futures_klines(
            symbol=config.SYMBOL,
            interval=config.TIMEFRAME,
            limit=config.CANDLES_N,
        )
        print(f"  ✅ {len(candles)} candles recebidos ({config.SYMBOL} {config.TIMEFRAME})")

    except BinanceAPIException as e:
        print(f"  ❌ Erro Binance: {e.code} — {e.message}")
        return
    except Exception as e:
        print(f"  ❌ Erro de conexão: {e}")
        return

    import indicadores as ind_mod
    import sinais as sig_mod

    ind   = ind_mod.calcular_todos(candles)
    sinal = sig_mod.avaliar_sinal(ind)

    import numpy as np
    i = -2  # último candle fechado

    def fmt(v):
        return f"{v:.4f}" if not np.isnan(v) else "N/A"

    print("\n" + "-" * 50)
    print("  INDICADORES (último candle fechado)")
    print("-" * 50)
    print(f"  Close:   ${float(ind['close'][i]):,.2f}")
    print(f"  EMA 9:   ${float(ind['ema9'][i]):,.2f}")
    print(f"  EMA 21:  ${float(ind['ema21'][i]):,.2f}")
    print(f"  EMA 50:  ${float(ind['ema50'][i]):,.2f}")
    print(f"  RSI:     {fmt(ind['rsi'][i])}")
    print(f"  MACD:    {fmt(ind['macd_line'][i])}  | Sinal: {fmt(ind['macd_sig'][i])}")
    print(f"  ATR:     ${float(ind['atr'][i]):.2f}")
    print(f"  BB Sup:  ${float(ind['bb_upper'][i]):,.2f}")
    print(f"  BB Inf:  ${float(ind['bb_lower'][i]):,.2f}")
    print(f"  BB Larg: {fmt(ind['bb_largura'][i])}")
    print(f"  Vol/SMA: {sinal['vol_ratio']:.2f}x")
    print(f"  Squeeze: {'✅ SIM' if sinal['bb_squeeze'] else '❌ NÃO'}")

    print("\n" + "-" * 50)
    print("  SCORES")
    print("-" * 50)
    print(f"  Score LONG:  {sinal['score_long']:>3}/100")
    print(f"  Score SHORT: {sinal['score_short']:>3}/100")
    print(f"  Score mín.:  {config.SCORE_MINIMO}")

    if sinal["direcao"]:
        niveis = sig_mod.calcular_niveis(
            sinal["close"], sinal["direcao"], sinal["atr"]
        )
        emoji = "🟢" if sinal["direcao"] == "long" else "🔴"
        print(f"\n  {emoji} SINAL: {sinal['direcao'].upper()} (score {sinal['score']})")
        print(f"  Entrada:  ${niveis['entrada']:,.2f}")
        print(f"  Stop:     ${niveis['stop_loss']:,.2f}")
        print(f"  Take:     ${niveis['take_profit']:,.2f}")
        print(f"  Ratio:    1:{niveis['ratio']:.1f}")
    else:
        print(f"\n  ⚪ SEM SINAL — score insuficiente")

    print("-" * 50)


# ── Opção 4: Teste de conexão ─────────────────────────────────

def testar_conexao():
    print("\n  🔌 TESTE DE CONEXÃO BINANCE")
    print("-" * 40)

    if not BINANCE_OK:
        print("  ❌ python-binance não instalado.")
        print("  Execute: pip install python-binance")
        return

    # Testa API key
    try:
        if config.USAR_TESTNET:
            client = Client(config.API_KEY, config.API_SECRET, testnet=True)
            print("  Conectando ao TESTNET...")
        else:
            client = Client(config.API_KEY, config.API_SECRET)
            print("  Conectando à conta REAL...")

        # Preço atual
        ticker = client.futures_symbol_ticker(symbol=config.SYMBOL)
        preco  = float(ticker["price"])
        print(f"  ✅ Conexão OK")
        print(f"  Preço atual {config.SYMBOL}: ${preco:,.2f}")

        # Saldo
        saldos = client.futures_account_balance()
        for s in saldos:
            if s["asset"] == "USDT":
                print(f"  Saldo USDT disponível: ${float(s['balance']):,.2f}")
                break

        # Testa configuração de alavancagem
        try:
            client.futures_change_leverage(
                symbol=config.SYMBOL,
                leverage=config.ALAVANCAGEM,
            )
            print(f"  ✅ Alavancagem {config.ALAVANCAGEM}x configurada")
        except BinanceAPIException as e:
            print(f"  ⚠️  Alavancagem: {e.message}")

    except BinanceAPIException as e:
        print(f"  ❌ Erro Binance: {e.code} — {e.message}")
    except Exception as e:
        print(f"  ❌ Erro de conexão: {e}")

    print("-" * 40)


# ── Loop do menu ─────────────────────────────────────────────

def main():
    while True:
        limpar()
        cabecalho()
        opcao = menu_principal()

        if opcao == "1":
            iniciar_bot()
            input("\n  Pressione Enter para continuar...")

        elif opcao == "2":
            diagnostico()
            input("\n  Pressione Enter para continuar...")

        elif opcao == "3":
            import relatorio
            relatorio.main()
            input("  Pressione Enter para continuar...")

        elif opcao == "4":
            testar_conexao()
            input("\n  Pressione Enter para continuar...")

        elif opcao == "5":
            print("\n  Até logo! 👋\n")
            sys.exit(0)

        else:
            print("\n  Opção inválida.")
            input("  Pressione Enter para continuar...")


if __name__ == "__main__":
    main()
