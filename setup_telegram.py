# ============================================================
# setup_telegram.py -- Descobre o CHAT_ID e testa o bot
# Execute: python setup_telegram.py
# ============================================================
import sys
import io

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests
import json

TOKEN = "8900382876:AAFXWSBl_7EVTpCaSi_6fkkUxz7KWM0wCbo"
BASE  = f"https://api.telegram.org/bot{TOKEN}"


def get_updates():
    """Busca as últimas mensagens recebidas pelo bot."""
    resp = requests.get(f"{BASE}/getUpdates", timeout=10)
    return resp.json()


def send_test(chat_id: str):
    """Envia mensagem de teste ao chat_id informado."""
    msg = (
        "✅ *ScalpBot conectado com sucesso!*\n\n"
        "🤖 O bot está configurado e pronto para enviar alertas.\n\n"
        "📊 Você receberá notificações de:\n"
        "• 🚀 Abertura de posições (LONG/SHORT)\n"
        "• ✅ Operações vencedoras (TP atingido)\n"
        "• ❌ Operações perdedoras (SL atingido)\n"
        "• 🔄 Trailing Stop ativado\n"
        "• 📈 Resumo diário de performance\n"
        "• 🛑 Alertas críticos de risco"
    )
    resp = requests.post(
        f"{BASE}/sendMessage",
        json={
            "chat_id":    chat_id,
            "text":       msg,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )
    return resp.json()


def main():
    print("=" * 55)
    print("  🤖 SETUP DO TELEGRAM — ScalpBot")
    print("=" * 55)

    print("\n📡 Buscando mensagens recebidas pelo bot...")
    data = get_updates()

    if not data.get("ok"):
        print(f"\n❌ Erro ao conectar: {data}")
        return

    updates = data.get("result", [])

    if not updates:
        print("\n⚠️  Nenhuma mensagem encontrada!")
        print("\n👉 COMO OBTER SEU CHAT_ID:")
        print("   1. Abra o Telegram")
        print("   2. Pesquise por: @Karonfuturebot")
        print("   3. Envie qualquer mensagem (ex: /start ou 'oi')")
        print("   4. Execute este script novamente")
        return

    # Extrai chat_ids únicos
    chats = {}
    for upd in updates:
        msg = upd.get("message", {})
        chat = msg.get("chat", {})
        if chat:
            cid  = chat.get("id")
            nome = chat.get("first_name", "") + " " + chat.get("last_name", "")
            user = chat.get("username", "")
            chats[cid] = {"nome": nome.strip(), "user": user}

    print(f"\n✅ Encontrados {len(chats)} chat(s):\n")
    for i, (cid, info) in enumerate(chats.items(), 1):
        print(f"  [{i}] Nome: {info['nome']} | @{info['user']} | ID: {cid}")

    print()
    chat_ids = list(chats.keys())

    if len(chat_ids) == 1:
        chat_id = str(chat_ids[0])
        info    = chats[chat_ids[0]]
    else:
        escolha = input("Digite o número do chat desejado: ").strip()
        idx = int(escolha) - 1
        chat_id = str(chat_ids[idx])
        info    = chats[chat_ids[idx]]

    print(f"\n📋 Chat selecionado: {info['nome']} | ID: {chat_id}")

    # Envia mensagem de teste
    print("\n📤 Enviando mensagem de teste...")
    resultado = send_test(chat_id)

    if resultado.get("ok"):
        print("✅ Mensagem enviada com sucesso!")
    else:
        print(f"❌ Erro: {resultado}")
        return

    # Salva o chat_id no config.py
    print(f"\n📝 Atualizando config.py com CHAT_ID = {chat_id} ...")

    with open("config.py", "r", encoding="utf-8") as f:
        conteudo = f.read()

    # Substitui as linhas do Telegram
    conteudo = conteudo.replace(
        'TELEGRAM_TOKEN   = ""',
        f'TELEGRAM_TOKEN   = "{TOKEN}"'
    )
    conteudo = conteudo.replace(
        'TELEGRAM_CHAT_ID = ""',
        f'TELEGRAM_CHAT_ID = "{chat_id}"'
    )

    with open("config.py", "w", encoding="utf-8") as f:
        f.write(conteudo)

    print("✅ config.py atualizado!")
    print("\n" + "=" * 55)
    print("  🎉 CONFIGURAÇÃO CONCLUÍDA!")
    print("=" * 55)
    print(f"\n  TOKEN   : {TOKEN[:20]}...")
    print(f"  CHAT_ID : {chat_id}")
    print("\n  O ScalpBot irá enviar alertas para o seu Telegram.")
    print("  Execute: python main.py\n")


if __name__ == "__main__":
    main()
