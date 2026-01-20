import smtplib
import os
from email.message import EmailMessage

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

def send_email_with_attachment(file_path):
    if not all([EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_TO]):
        return

    msg = EmailMessage()
    msg["Subject"] = "📊 FIFA25 – Relatório Semanal"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    msg.set_content(
        "Segue em anexo o relatório semanal do FIFA25 Bot.\n\n"
        "Partidas separadas por location.\n"
        "Horários em UTC.\n\n"
        "Bot automático 24/7."
    )

    with open(file_path, "rb") as f:
        file_data = f.read()

    file_name = file_path.split("/")[-1]

    msg.add_attachment(
        file_data,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_name
    )

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
