import os
import smtplib
from email.message import EmailMessage

class EmailService:

    def __init__(self):
        self.smtp_server = os.environ.get("EMAIL_SMTP_SERVER")
        self.smtp_port = os.environ.get("EMAIL_SMTP_PORT")
        self.email_user = os.environ.get("EMAIL_USER")
        self.email_password = os.environ.get("EMAIL_PASSWORD")

    # ===========================
    #   Enviar e-mail simples
    # ===========================
    def send_email(self, to_email: str, subject: str, body: str):
        if not self.smtp_server or not self.email_user:
            print("[EMAIL] Configurações de SMTP faltando.")
            return False

        msg = EmailMessage()
        msg["From"] = self.email_user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_server, int(self.smtp_port)) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            print("[EMAIL] E-mail enviado com sucesso.")
            return True

        except Exception as e:
            print(f"[EMAIL] Erro ao enviar e-mail: {e}")
            return False

    # ===========================
    #   Enviar relatório com anexo XLSX
    # ===========================
    def send_report(self, to_email: str, filepath: str):
        if not os.path.exists(filepath):
            print(f"[EMAIL] Arquivo não encontrado: {filepath}")
            return False

        msg = EmailMessage()
        msg["From"] = self.email_user
        msg["To"] = to_email
        msg["Subject"] = "Relatório Diário de Partidas — FIFA25"
        msg.set_content("Segue o relatório diário em anexo.")

        try:
            with open(filepath, "rb") as f:
                data = f.read()

            msg.add_attachment(
                data,
                maintype="application",
                subtype="xlsx",
                filename=os.path.basename(filepath)
            )

            with smtplib.SMTP(self.smtp_server, int(self.smtp_port)) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            print("[EMAIL] Relatório enviado com sucesso.")
            return True

        except Exception as e:
            print(f"[EMAIL] Erro ao enviar relatório: {e}")
            return False
