import os
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup
from sqlalchemy.exc import OperationalError

# =====================================================================================
# CONFIG
# =====================================================================================

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "default_secret_key")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):  # Render usa formato antigo
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 60))
RUN_SCRAPER = os.getenv("RUN_SCRAPER", "true").lower() == "true"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(level=logging.INFO)


# =====================================================================================
# MODELOS
# =====================================================================================

class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(100))
    team2 = db.Column(db.String(100))
    score = db.Column(db.String(20))
    status = db.Column(db.String(20))
    league = db.Column(db.String(100))
    stadium = db.Column(db.String(100))
    match_time = db.Column(db.String(100))


# =====================================================================================
# BANCO – SOLUÇÃO DEFINITIVA PARA RENDER
# =====================================================================================

def force_fix_render_database():
    """
    Aguarda o banco online, remove tabelas antigas e recria 'matches'.
    Correção definitiva para: relation "matches" does not exist
    """

    print("\n[DB] Sincronizando banco do Render...")

    with app.app_context():

        # 1. Esperar banco ficar disponível
        for i in range(30):
            try:
                db.engine.execute("SELECT 1;")
                print("[DB] Banco online!")
                break
            except OperationalError:
                print(f"[DB] Banco indisponível, aguardando... ({i+1}/30)")
                time.sleep(1)
        else:
            print("[DB] ERRO: Banco não ficou disponível a tempo!")
            return

        # 2. Remover tabelas antigas ou corrompidas
        try:
            db.engine.execute("DROP TABLE IF EXISTS match CASCADE;")
            db.engine.execute("DROP TABLE IF EXISTS matches CASCADE;")
            print("[DB] Tabelas antigas removidas.")
        except Exception as e:
            print("[DB] Aviso ao tentar remover tabelas:", e)

        # 3. Recriar tabela final e correta
        try:
            db.create_all()
            print("[DB] Tabela 'matches' criada com sucesso!")
        except Exception as e:
            print("[DB] ERRO ao criar tabela:", e)

        print("[DB] Banco sincronizado.\n")


# =====================================================================================
# TELEGRAM
# =====================================================================================

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        )
        if r.status_code != 200:
            print("[TELEGRAM] ERRO:", r.text)
    except Exception as e:
        print("[TELEGRAM] Exceção:", e)


# =====================================================================================
# SCRAPER
# =====================================================================================

def scrape_matches():
    print("[SCRAPER] Coletando partidas...")

    try:
        html = requests.get("https://football.esportsbattle.com/en", timeout=15).text
    except Exception as e:
        print("[SCRAPER] Falha ao acessar o site:", e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="match-card")

    matches = []

    for card in cards:

        def safe(selector, cls):
            el = card.find(selector, cls)
            return el.text.strip() if el else "-"

        matches.append({
            "team1": safe("div", "team-1"),
            "team2": safe("div", "team-2"),
            "score": safe("div", "score"),
            "status": "LIVE" if "live" in card.get("class", []) else "Finished",
            "league": safe("div", "league"),
            "stadium": safe("div", "stadium"),
            "match_time": safe("div", "time"),
        })

    print(f"[SCRAPER] Total encontrado: {len(matches)} partidas.")
    return matches


# =====================================================================================
# SCAN + SAVE
# =====================================================================================

def scan_and_save():
    with app.app_context():

        try:
            print("[SCAN] Atualizando banco...")

            items = scrape_matches()

            Match.query.delete()

            for m in items:
                db.session.add(Match(**m))

            db.session.commit()

            send_telegram(f"🔄 Atualização concluída — {len(items)} partidas.")
            print("[SCAN] OK.")

        except Exception as e:
            print("[SCAN] ERRO:", e)


# =====================================================================================
# SCHEDULER
# =====================================================================================

scheduler = BackgroundScheduler()

if RUN_SCRAPER:
    scheduler.add_job(scan_and_save, "interval", seconds=SCAN_INTERVAL)
    scheduler.start()
    print(f"[SCHEDULER] Ativo — rodando a cada {SCAN_INTERVAL}s")
else:
    print("[SCHEDULER] Desativado")


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

    return render_template(
        "dashboard.html",
        matches=matches,
        stats=stats,
        last_scan=datetime.utcnow()
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == "admin123":
            session["logged"] = True
            return redirect("/")
        return "Senha incorreta."

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =====================================================================================
# START
# =====================================================================================

if __name__ == "__main__":
    force_fix_render_database()
    app.run(host="0.0.0.0", port=10000)
