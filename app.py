# =========================================================
# app.py — versão premium + corrigida + last_scan ajustado
# =========================================================

import os
import time
import logging
from math import ceil
from datetime import datetime
import pytz
from tempfile import NamedTemporaryFile

from flask import (
    Flask, render_template, request, redirect,
    session, send_file, flash, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

# Scraper e utilidades
from web_scraper.stadium_scraper import StadiumScraper
from web_scraper.exporter import export_single_workbook_by_stadium
from web_scraper.emailer import send_file_via_gmail

# =========================================================
# CONFIG
# =========================================================

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "default_secret_key")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Intervalo do scanner
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))

# Ativar/desativar o scheduler
RUN_SCRAPER = os.getenv("RUN_SCRAPER", "true").lower() == "true"

# Credenciais de e-mail
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT", GMAIL_USER)

logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# =========================================================
# MODELS
# =========================================================

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=True)

class Match(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    stadium = db.Column(db.String(150))
    league = db.Column(db.String(150))
    match_time = db.Column(db.String(100))
    team1 = db.Column(db.String(150))
    player1 = db.Column(db.String(150))
    team2 = db.Column(db.String(150))
    player2 = db.Column(db.String(150))
    score = db.Column(db.String(50))
    status = db.Column(db.String(50))
    match_id = db.Column(db.String(128))

# =========================================================
# DB INIT
# =========================================================

def ensure_db_ready_and_sync():
    """Garante que o banco está pronto e sincroniza tabelas."""
    with app.app_context():

        # Espera banco responder
        for attempt in range(30):
            try:
                db.session.execute(text("SELECT 1"))
                break
            except OperationalError:
                app.logger.info(f"[DB] Aguardando banco ({attempt+1}/30)...")
                time.sleep(1)
        else:
            app.logger.error("[DB] Banco não respondeu.")
            return

        # Remove tabelas antigas (não remove matches)
        try:
            db.create_all()
            app.logger.info("[DB] Tabelas OK.")
        except Exception as e:
            app.logger.error(f"[DB] Erro ao criar tabelas: {e}")

# Executa ao importar
ensure_db_ready_and_sync()

# =========================================================
# SCRAPER
# =========================================================

scraper = StadiumScraper(wait_seconds=int(os.getenv("SCRAPER_WAIT", 6)))

def scan_and_save():
    """Executa scraper e salva dados no DB."""
    with app.app_context():
        try:
            app.logger.info("[SCAN] Iniciando varredura...")
            html = scraper.fetch_page()
            locations_map, matches = scraper.parse(html)

            db.session.query(Match).delete()

            for m in matches:
                entry = Match(
                    stadium=m.get("stadium"),
                    league=m.get("league"),
                    match_time=m.get("match_time"),
                    team1=m.get("team1"),
                    player1=m.get("player1"),
                    team2=m.get("team2"),
                    player2=m.get("player2"),
                    score=m.get("score"),
                    status=m.get("status"),
                    match_id=m.get("match_id")
                )
                db.session.add(entry)

            db.session.commit()
            app.logger.info(f"[SCAN] OK — {len(matches)} partidas atualizadas.")

        except Exception as e:
            app.logger.exception(f"[SCAN] Erro: {e}")
            db.session.rollback()

# =========================================================
# EXPORT / E-MAIL
# =========================================================

def generate_and_get_workbook():
    """Gera o arquivo Excel agrupado por estádio."""
    with app.app_context():
        matches = Match.query.order_by(Match.id.desc()).all()

        grouped = {}
        for m in matches:
            st = m.stadium or "Unknown"
            grouped.setdefault(st, []).append({
                "match_id": m.match_id,
                "stadium": m.stadium,
                "league": m.league,
                "match_time": m.match_time,
                "team1": m.team1,
                "player1": m.player1,
                "team2": m.team2,
                "player2": m.player2,
                "score": m.score,
                "status": m.status
            })

        return export_single_workbook_by_stadium(grouped, prefix="weekly_stadiums")

def weekly_stadium_report():
    """Job semanal de envio por email."""
    app.logger.info("[REPORT] Gerando relatório semanal...")
    try:
        file = generate_and_get_workbook()
        send_file_via_gmail(
            file,
            "Relatório semanal — Partidas por Estádio",
            "Segue relatório semanal atualizado."
        )
    except Exception as e:
        app.logger.exception(f"[REPORT] Erro: {e}")

# =========================================================
# SCHEDULER
# =========================================================

scheduler = BackgroundScheduler()

if RUN_SCRAPER:
    scheduler.add_job(scan_and_save, "interval", seconds=SCAN_INTERVAL)
    scheduler.add_job(
        weekly_stadium_report,
        "cron",
        day_of_week="sun",
        hour=0,
        minute=5,
        timezone="America/Sao_Paulo"
    )
    scheduler.start()
    app.logger.info("[SCHEDULER] Ativo.")

# =========================================================
# ROTAS
# =========================================================

@app.route("/")
def dashboard():
    """Dashboard Premium"""
    try:
        matches = Match.query.order_by(Match.id.desc()).limit(200).all()

        sao_paulo = pytz.timezone("America/Sao_Paulo")
        last_scan = datetime.now(sao_paulo)

        stats = {
            "total": Match.query.count(),
            "live": Match.query.filter(Match.status.ilike("%live%")).count(),
        }

        # Converter para dict
        matches_list = [{
            "id": m.id,
            "stadium": m.stadium,
            "team1": m.team1,
            "team2": m.team2,
            "score": m.score,
            "league": m.league,
            "match_time": m.match_time,
            "status": m.status,
        } for m in matches]

        live = [
            m for m in matches_list
            if m["status"] and "live" in m["status"].lower()
        ]

        return render_template(
            "dashboard.html",
            matches=matches_list,
            stats=stats,
            last_scan=last_scan,
            live_matches=live
        )

    except Exception as e:
        app.logger.exception(f"[WEB] Dashboard erro: {e}")
        return "Erro interno", 500

@app.route("/matches")
def matches_page():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50

    all_matches = Match.query.order_by(Match.id.desc()).all()
    total = len(all_matches)

    matches = all_matches[(page-1)*per_page : page*per_page]
    total_pages = max(1, ceil(total / per_page))

    return render_template("matches.html", matches=matches, page=page, total_pages=total_pages)

@app.route("/players")
def players_page():
    q = request.args.get("q", "").strip()

    query = Player.query
    if q:
        query = query.filter(Player.username.ilike(f"%{q}%"))

    players = query.order_by(Player.id.asc()).all()

    return render_template("players.html", players=players, q=q)

@app.route("/reports")
def reports_page():
    matches = Match.query.all()
    stats = {
        "total": len(matches),
        "live": len([m for m in matches if m.status and "live" in m.status.lower()])
    }
    return render_template("reports.html", stats=stats)

@app.route("/health")
def health():
    return "ok", 200

# =========================================================
# LOCAL RUN
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
