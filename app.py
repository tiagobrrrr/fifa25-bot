# app.py - Versão completa e final (com display_name no Player)
import os
import time
import logging
from math import ceil
from datetime import datetime
from tempfile import NamedTemporaryFile

from flask import Flask, render_template, request, redirect, session, send_file, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup
import pandas as pd
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

# =====================================================================================
# CONFIG
# =====================================================================================

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "default_secret_key")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))  # default 30s
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
    display_name = db.Column(db.String(100), nullable=True)  # opção A

class Match(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(100))
    team2 = db.Column(db.String(100))
    score = db.Column(db.String(50))
    status = db.Column(db.String(50))
    league = db.Column(db.String(100))
    stadium = db.Column(db.String(100))
    match_time = db.Column(db.String(100))

# =====================================================================================
# DATABASE BOOTSTRAP (espera banco e corrige schema)
# =====================================================================================

def ensure_db_ready_and_sync():
    """
    Aguarda o DB ficar disponível, remove tabelas antigas e cria as tabelas atuais.
    Funciona bem no Render (onde o banco pode demorar alguns segundos para subir).
    """
    with app.app_context():
        # 1) esperar banco ficar disponível
        for attempt in range(30):
            try:
                # test simple query
                db.session.execute(text("SELECT 1"))
                break
            except OperationalError:
                app.logger.info(f"[DB] Banco indisponível, aguardando... ({attempt+1}/30)")
                time.sleep(1)
        else:
            app.logger.error("[DB] Banco não respondeu a tempo. Continuando sem criar tabelas.")
            return

        # 2) remover eventuais tabelas antigas/problemáticas
        try:
            db.session.execute(text("DROP TABLE IF EXISTS match CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS matches CASCADE"))
            db.session.commit()
            app.logger.info("[DB] Tabelas antigas (se existiam) removidas.")
        except Exception as e:
            app.logger.warning("[DB] Aviso ao remover tabelas antigas: %s", e)
            db.session.rollback()

        # 3) criar todas as tabelas definidas nos modelos
        try:
            db.create_all()
            app.logger.info("[DB] Tabelas criadas/verificadas com sucesso.")
        except Exception as e:
            app.logger.error("[DB] Erro ao criar tabelas: %s", e)

# executar na importação (assim roda no Render independentemente de __main__)
ensure_db_ready_and_sync()

# =====================================================================================
# TELEGRAM UTILS
# =====================================================================================

def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.debug("[TELEGRAM] Token/chat_id não configurado. Ignorando envio.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=8)
        if r.status_code != 200:
            app.logger.warning("[TELEGRAM] Falha ao enviar: %s", r.text)
    except Exception as e:
        app.logger.warning("[TELEGRAM] Exceção ao enviar mensagem: %s", e)

# =====================================================================================
# SCRAPER
# =====================================================================================

def scrape_matches():
    """
    Coleta as partidas do site alvo. Retorna lista de dicts compatíveis com Match model.
    """
    url = "https://football.esportsbattle.com/en"
    app.logger.info("[SCRAPER] Iniciando scrape em %s", url)
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        app.logger.warning("[SCRAPER] Falha ao acessar site: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="match-card")
    matches = []

    for card in cards:
        def safe_find_text(sel, cls=None):
            try:
                el = card.find(sel, cls) if cls else card.find(sel)
                return el.text.strip() if el and el.text else "-"
            except Exception:
                return "-"

        team1 = safe_find_text("div", "team-1")
        team2 = safe_find_text("div", "team-2")
        score = safe_find_text("div", "score")
        status = "LIVE" if "live" in card.get("class", []) else safe_find_text("div", "status") or "Finished"
        league = safe_find_text("div", "league")
        stadium = safe_find_text("div", "stadium")
        match_time = safe_find_text("div", "time")

        matches.append({
            "team1": team1,
            "team2": team2,
            "score": score,
            "status": status,
            "league": league,
            "stadium": stadium,
            "match_time": match_time
        })

    app.logger.info("[SCRAPER] Encontradas %d partidas", len(matches))
    return matches

# =====================================================================================
# SCAN & SAVE
# =====================================================================================

def scan_and_save():
    with app.app_context():
        try:
            app.logger.info("[SCAN] Execução do scanner iniciada.")
            items = scrape_matches()
            # limpar e inserir (simples)
            db.session.query(Match).delete()
            for it in items:
                db.session.add(Match(**it))
            db.session.commit()
            send_telegram(f"🔄 Atualização: {len(items)} partidas coletadas.")
            app.logger.info("[SCAN] Concluído com %d partidas", len(items))
        except Exception as e:
            app.logger.exception("[SCAN] Erro durante scan_and_save: %s", e)
            db.session.rollback()

# =====================================================================================
# SCHEDULER
# =====================================================================================

scheduler = BackgroundScheduler()
if RUN_SCRAPER:
    scheduler.add_job(scan_and_save, "interval", seconds=SCAN_INTERVAL, id="scan_and_save")
    scheduler.start()
    app.logger.info("[SCHEDULER] Ativo — intervalo %ds", SCAN_INTERVAL)
else:
    app.logger.info("[SCHEDULER] Desativado por configuração.")

# =====================================================================================
# ROTAS PRINCIPAIS
# =====================================================================================

@app.route("/")
def dashboard():
    with app.app_context():
        matches = Match.query.order_by(Match.id.desc()).limit(200).all()
    stats = {
        "total": len(Match.query.all()),
        "live": len([m for m in Match.query.all() if m.status and m.status.lower() == "live"])
    }
    return render_template("dashboard.html", matches=matches, stats=stats, last_scan=datetime.utcnow())

# -------------------------
# Matches page (paginação simples)
# -------------------------
@app.route("/matches")
def matches_page():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    all_matches = Match.query.order_by(Match.id.desc()).all()
    start = (page-1)*per_page
    matches = all_matches[start:start+per_page]
    total = len(all_matches)
    total_pages = max(1, ceil(total / per_page))
    return render_template("matches.html", matches=matches, page=page, total_pages=total_pages)

# -------------------------
# Players: list, search, pagination
# -------------------------
@app.route("/players")
def players_page():
    q = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 10

    query = Player.query
    if q:
        ilike = f"%{q}%"
        # search in username or display_name
        query = query.filter(
            (Player.username.ilike(ilike)) | (Player.display_name.ilike(ilike))
        )

    all_players = query.order_by(Player.id.asc()).all()
    total = len(all_players)
    total_pages = max(1, ceil(total / per_page))
    start = (page-1)*per_page
    players = all_players[start:start+per_page]

    # pagination window
    window = 5
    first = max(1, page - window//2)
    last = min(total_pages, first + window - 1)
    page_numbers = list(range(first, last+1))

    return render_template("players.html",
                           players=players,
                           page=page,
                           total_pages=total_pages,
                           page_numbers=page_numbers,
                           q=q)

# -------------------------
# Players add/delete
# -------------------------
@app.route("/players/add", methods=["POST"])
def players_add():
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip() or None
    if not username:
        flash("Username é obrigatório.", "error")
        return redirect("/players")

    existing = Player.query.filter_by(username=username).first()
    if existing:
        flash("Jogador já existe.", "error")
        return redirect("/players")

    p = Player(username=username, display_name=display_name)
    db.session.add(p)
    db.session.commit()
    flash("Jogador adicionado.", "success")
    return redirect("/players")

@app.route("/players/delete/<int:pid>", methods=["POST"])
def players_delete(pid):
    p = Player.query.get(pid)
    if not p:
        flash("Jogador não encontrado.", "error")
        return redirect("/players")
    db.session.delete(p)
    db.session.commit()
    flash("Jogador removido.", "success")
    return redirect("/players")

# -------------------------
# Reports: page + export
# -------------------------
@app.route("/reports")
def reports_page():
    matches = Match.query.order_by(Match.id.desc()).all()
    stats = {
        "total": len(matches),
        "live": len([m for m in matches if m.status and m.status.lower() == "live"])
    }
    return render_template("reports.html", stats=stats)

@app.route("/reports/export", methods=["POST"])
def export_report():
    matches = Match.query.order_by(Match.id.desc()).all()
    df = pd.DataFrame([{
        "ID": m.id,
        "team1": m.team1,
        "team2": m.team2,
        "score": m.score,
        "status": m.status,
        "league": m.league,
        "stadium": m.stadium,
        "match_time": m.match_time
    } for m in matches])

    # write to temporary file then send
    with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_name = tmp.name
    df.to_excel(tmp_name, index=False)
    return send_file(tmp_name, as_attachment=True, download_name="relatorio_matches.xlsx")

# =====================================================================================
# UTIL (opcional)
# =====================================================================================

@app.route("/health")
def health():
    return "ok", 200

# =====================================================================================
# START (LOCAL)
# =====================================================================================

if __name__ == "__main__":
    # local debug server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)), debug=False)
