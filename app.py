import os
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup

# =====================================================================================
# CONFIG
# =====================================================================================

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "defaultsecret")

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))
RUN_SCRAPER = os.getenv("RUN_SCRAPER", "true").lower() == "true"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(level=logging.INFO)

# =====================================================================================
# MODELS
# =====================================================================================

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(100))
    team2 = db.Column(db.String(100))
    score = db.Column(db.String(20))
    status = db.Column(db.String(20))
    league = db.Column(db.String(100))
    stadium = db.Column(db.String(100))
    match_time = db.Column(db.String(100))


# =====================================================================================
# SCRAPER
# =====================================================================================

def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Token ou chat_id não configurado.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

    if r.status_code != 200:
        print("[TELEGRAM] Falha:", r.text)
    else:
        print("[TELEGRAM] Mensagem enviada!")


def scrape_matches():
    """
    Coleta partidas do site football.esportsbattle.com
    """
    print("[SCRAPER] Buscando partidas...")

    url = "https://football.esportsbattle.com/en"

    try:
        html = requests.get(url, timeout=10).text
    except:
        print("[SCRAPER] ERRO ao acessar o site.")
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="match-card")

    matches = []

    for card in cards:
        team1 = card.find("div", class_="team-1").text.strip() if card.find("div", class_="team-1") else "?"
        team2 = card.find("div", class_="team-2").text.strip() if card.find("div", class_="team-2") else "?"
        score = card.find("div", class_="score").text.strip() if card.find("div", class_="score") else "vs"
        status = "LIVE" if "live" in card.get("class", []) else "Finished"

        league = card.find("div", class_="league").text.strip() if card.find("div", class_="league") else "-"
        stadium = card.find("div", class_="stadium").text.strip() if card.find("div", class_="stadium") else "-"
        match_time = card.find("div", class_="time").text.strip() if card.find("div", class_="time") else "-"

        matches.append({
            "team1": team1,
            "team2": team2,
            "score": score,
            "status": status,
            "league": league,
            "stadium": stadium,
            "match_time": match_time,
        })

    print(f"[SCRAPER] {len(matches)} partidas encontradas.")
    return matches


# =====================================================================================
# PERSISTÊNCIA COM CONTEXTO DO FLASK
# =====================================================================================

def scan_and_save():
    """
    Função chamada pelo scheduler.  
    Agora ela roda **dentro do contexto da aplicação**, evitando o erro:
    "Working outside of application context".
    """
    with app.app_context():

        try:
            print("[SCAN] Iniciando varredura de partidas...")

            matches = scrape_matches()

            # limpa a tabela antes de inserir novos dados
            Match.query.delete()

            for m in matches:
                row = Match(
                    team1=m["team1"],
                    team2=m["team2"],
                    score=m["score"],
                    status=m["status"],
                    league=m["league"],
                    stadium=m["stadium"],
                    match_time=m["match_time"]
                )
                db.session.add(row)

            db.session.commit()

            send_telegram(f"⏱️ Bot atualizado — {len(matches)} partidas encontradas.")

            print("[SCAN] Finalizado.")

        except Exception as e:
            print("[SCAN] ERRO:", e)


# =====================================================================================
# SCHEDULER
# =====================================================================================

scheduler = BackgroundScheduler()

if RUN_SCRAPER:
    scheduler.add_job(scan_and_save, "interval", seconds=SCAN_INTERVAL)
    scheduler.start()
    print(f"[SCHEDULER] Ativado. Intervalo: {SCAN_INTERVAL}s")
else:
    print("[SCHEDULER] Desativado.")


# =====================================================================================
# ROTAS
# =====================================================================================

@app.route("/")
def dashboard():
    with app.app_context():
        matches = Match.query.all()

    stats = {
        "total": len(matches),
        "live": len([m for m in matches if m.status == "LIVE"])
    }

    return render_template("dashboard.html", matches=matches, stats=stats, last_scan=datetime.utcnow())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pwd = request.form.get("password")
        if pwd == "admin123":  # você pode usar variável de ambiente depois
            session["logged"] = True
            return redirect("/")
        return "Senha incorreta"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =====================================================================================
# START
# =====================================================================================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=10000)
