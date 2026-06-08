# ============================================================
# bot_autonomo.py — Script lançado pelo watchdog
# Sem menus, sem interação — apenas roda o bot
# Exit code 1 em caso de erro crítico (watchdog detecta e reinicia)
# ============================================================

import sys

try:
    from bot import ScalpBot
    bot = ScalpBot()
    bot.rodar()
except Exception as e:
    print(f"[AUTÔNOMO] Erro crítico: {type(e).__name__}: {e}")
    sys.exit(1)
