import os
import requests

class TelegramNotifier:

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    # ===========================
    #   Enviar mensagem
    # ===========================
    def send(self, message: str):
        if not self.token or not self.chat_id:
            print("[TELEGRAM] Token ou Chat ID não configurados.")
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            r = requests.post(url, data=payload, timeout=10)
            if r.status_code == 200:
                print("[TELEGRAM] Mensagem enviada com sucesso.")
                return True
            else:
                print(f"[TELEGRAM] Falha ao enviar mensagem: {r.text}")
        except Exception as e:
            print(f"[TELEGRAM] Erro: {e}")

        return False
