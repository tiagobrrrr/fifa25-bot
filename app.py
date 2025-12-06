# app.py - Versão A completa
# - Sem Telegram
# - Correções SSL/SQLAlchemy para Render
# - Scraper tolerante
# - TRUNCATE seguro com retry
# - Envio semanal de relatório via Gmail (XLSX)

import os
import time
import logging
from math import ceil
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
import smtplib
import ssl

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email import encoders

from flask import Flask, render_template, request, redirect, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
from bs4 import BeautifulSoup
import pandas as pd
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

# Optional timezone handling
try:
    import pytz
    TZ = pytz.timezone("America/Sao_Paulo")
except Exception:
    TZ = None

# ==============================================================================
# Basic config
# ==============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "default_secret_key")

# DATABASE URL fix for older "postgres://" prefix
raw_db_url = os.getenv("DATABASE_URL", "")
if raw_db_url and raw_db_url.startswith("postgres://"):
    safe_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
else:
    safe_db_url = raw_db_url or "sqlite:///local.db"

app.config["SQLALCHEMY_DATABASE_URI"] = safe_db_url
# Engine options to stabilize Postgres connections on Render
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    # ensure SSL mode and connection health checks
    "connect_args": {"sslmode": "require"} if safe_db_url.startswith("postgresql://") else {},
    "pool_pre_ping": True,
    "pool_recycle": 280,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30,
}

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Scraper / scheduler config
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))  # seconds
RUN_SCRAPER = os.getenv("RUN_SCRAPER", "true").lower() == "true"

# Gmail envs (for weekly report)
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT")

WEEKLY_REPORT_DAY = os.getenv("WEEKLY_REPORT_DAY", "sun")  # mon,tue,wed,thu,fri,sat,sun
WEEKLY_REPORT_HOUR = int(os.getenv("WEEKLY_REPORT_HOUR", 0))
WEEKLY_REPORT_MINUTE = int(os.getenv("WEEKLY_REPORT_MINUTE", 5))

# ==============================================================================
# Models
# ==============================================================================

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=True)

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
    # created_at for history (optional)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==============================================================================
# DB bootstrap / ensure ready
# ==============================================================================

def ensure_db_ready_and_sync():
    with app.app_context():
        for attempt in range(30):
            try:
                db.session.execute(text("SELECT 1"))
                break
            except OperationalError:
                logger.info(f"[DB] Banco indisponível, aguardando... ({attempt+1}/30)")
                time.sleep(1)
        else:
            logger.error("[DB] Banco não respondeu a tempo. Abortando criação de tabelas.")
            return

        try:
            db.session.execute(text("DROP TABLE IF EXISTS match CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS matches CASCADE"))
            db.session.commit()
            logger.info("[DB] Tabelas antigas removidas (se existiam).")
        except Exception as e:
            logger.warning("[DB] Não foi possível remover tabelas antigas: %s", e)
            db.session.rollback()

        try:
            db.create_all()
            logger.info("[DB] Tabelas criadas/verificadas.")
        except Exception as e:
            logger.error("[DB] Erro ao criar tabelas: %s", e)

ensure_db_ready_and_sync()

# ==============================================================================
# Scraper (tolerant)
# ==============================================================================

SCRAPER_SESSION = requests.Session()
SCRAPER_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})

def scrape_matches():
    url = "https://football.esportsbattle.com/en"
    logger.info("[SCRAPER] Iniciando scrape em %s", url)
    try:
        r = SCRAPER_SESSION.get(url, timeout=12)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        logger.warning("[SCRAPER] Falha ao acessar site: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")

    # tolerant selectors
    cards = soup.find_all("div", class_="match-card")
    if not cards:
        cards = soup.find_all("div", class_="match__card")
    if not cards:
        cards = soup.select("[data-match], .card.match")

    matches = []
    for card in cards:
        def safe_selector(css_selector, default="-"):
            try:
                el = card.select_one(css_selector)
                return el.get_text(strip=True) if el else default
            except Exception:
                return default

        team1 = safe_selector(".team-1") or safe_selector(".team1") or safe_selector(".team.home")
        team2 = safe_selector(".team-2") or safe_selector(".team2") or safe_selector(".team.away")
        score = safe_selector(".score") or safe_selector(".match-score") or safe_selector(".result")
        status = "LIVE" if "live" in (card.get("class") or []) else (safe_selector(".status") or safe_selector(".match-status") or "Finished")
        league = safe_selector(".league") or safe_selector(".competition")
        stadium = safe_selector(".stadium") or safe_selector(".venue")
        match_time = safe_selector(".time") or safe_selector(".match-time") or safe_selector(".date")

        matches.append({
            "team1": team1,
            "team2": team2,
            "score": score,
            "status": status,
            "league": league,
            "stadium": stadium,
            "match_time": match_time
        })

    logger.info("[SCRAPER] Encontradas %d partidas", len(matches))
    return matches

# ==============================================================================
# Safe DB write: TRUNCATE + insert with retries
# ==============================================================================

def _safe_db_truncate_and_insert(items):
    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        attempts += 1
        try:
            db.session.execute(text("TRUNCATE TABLE matches RESTART IDENTITY"))
            for it in items:
                db.session.add(Match(**it))
            db.session.commit()
            return True
        except OperationalError as oe:
            logger.warning("[DB] OperationalError ao gravar (attempt %d/%d): %s", attempts, max_attempts, oe)
            db.session.rollback()
            try:
                db.engine.dispose()
            except Exception:
                pass
            time.sleep(1 + attempts)
        except Exception as e:
            logger.exception("[DB] Erro inesperado ao gravar no DB: %s", e)
            db.session.rollback()
            return False
    logger.error("[DB] Falha ao gravar após %d tentativas", max_attempts)
    return False

# ==============================================================================
# Scan & save job
# ==============================================================================

def scan_and_save():
    with app.app_context():
        try:
            logger.info("[SCAN] Execução iniciada.")
            items = scrape_matches()
            items_copy = list(items)
            ok = _safe_db_truncate_and_insert(items_copy)
            if ok:
                logger.info("[SCAN] Salvo %d partidas.", len(items_copy))
            else:
                logger.warning("[SCAN] Não foi possível salvar as partidas.")
        except Exception as e:
            logger.exception("[SCAN] Erro durante scan_and_save: %s", e)
            try:
                db.session.rollback()
            except Exception:
                pass

# ==============================================================================
# Weekly report via Gmail (XLSX attachment)
# ==============================================================================

def _generate_xlsx_from_matches(matches):
    df = pd.DataFrame([{
        "ID": m.id,
        "team1": m.team1,
        "team2": m.team2,
        "score": m.score,
        "status": m.status,
        "league": m.league,
        "stadium": m.stadium,
        "match_time": m.match_time,
        "created_at": m.created_at
    } for m in matches])

    # temporary file
    tmp = NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_name = tmp.name
    tmp.close()
    df.to_excel(tmp_name, index=False)
    return tmp_name

def send_email_with_attachment(subject: str, body: str, attachment_path: str,
                               sender: str, password: str, recipient: str):
    if not sender or not password or not recipient:
        logger.error("[EMAIL] Configuração de e-mail incompleta. Verifique GMAIL_USER/GMAIL_APP_PASSWORD/REPORT_RECIPIENT.")
        return False

    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    try:
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            message.attach(part)
    except Exception as e:
        logger.exception("[EMAIL] Falha ao anexar arquivo: %s", e)
        return False

    try:
        context = ssl.create_default_context()
        # Gmail SSL SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, message.as_string())
        logger.info("[EMAIL] Email enviado para %s", recipient)
        return True
    except Exception as e:
        logger.exception("[EMAIL] Erro ao enviar e-mail: %s", e)
        return False

def send_weekly_report():
    """
    Coleta partidas da semana (últimos 7 dias com base no campo created_at),
    gera XLSX e envia por Gmail para REPORT_RECIPIENT.
    """
    if not REPORT_RECIPIENT:
        logger.warning("[WEEKLY] REPORT_RECIPIENT não configurado, pulando envio.")
        return

    with app.app_context():
        # buscar partidas criadas nos últimos 7 dias
        now = datetime.utcnow()
        since = now - timedelta(days=7)
        matches = Match.query.filter(Match.created_at >= since).order_by(Match.id.desc()).all()
        logger.info("[WEEKLY] Encontradas %d partidas nos últimos 7 dias.", len(matches))

        if not matches:
            logger.info("[WEEKLY] Nenhuma partida encontrada na semana — criando XLSX vazio e enviando mesmo assim.")
        tmp_xlsx = _generate_xlsx_from_matches(matches)
        subject = f"Relatório semanal - {now.date().isoformat()}"
        body = f"Relatório de partidas coletadas entre {since.isoformat()} e {now.isoformat()}.\nTotal: {len(matches)} partidas."

        success = send_email_with_attachment(subject, body, tmp_xlsx, GMAIL_USER, GMAIL_APP_PASSWORD, REPORT_RECIPIENT)

        # opcional: remover/limpar dados após envio — NÃO removo automaticamente para histórico.
        try:
            os.remove(tmp_xlsx)
        except Exception:
            pass

        if success:
            logger.info("[WEEKLY] Relatório semanal enviado com sucesso.")
        else:
            logger.warning("[WEEKLY] Falha ao enviar relatório semanal.")

# ==============================================================================
# Scheduler
# ==============================================================================

scheduler = BackgroundScheduler()

if RUN_SCRAPER:
    scheduler.add_job(scan_and_save, "interval", seconds=SCAN_INTERVAL,
                      id="scan_and_save", replace_existing=True, max_instances=1, coalesce=False)
    logger.info("[SCHEDULER] Scraper agendado (intervalo %ds).", SCAN_INTERVAL)
else:
    logger.info("[SCHEDULER] Scraper desabilitado por configuração.")

# weekly cron job: uses user's timezone if pytz available
if TZ:
    trigger = CronTrigger(day_of_week=WEEKLY_REPORT_DAY, hour=WEEKLY_REPORT_HOUR, minute=WEEKLY_REPORT_MINUTE, timezone=TZ)
else:
    # fallback to server timezone (likely UTC)
    trigger = CronTrigger(day_of_week=WEEKLY_REPORT_DAY, hour=WEEKLY_REPORT_HOUR, minute=WEEKLY_REPORT_MINUTE)

scheduler.add_job(send_weekly_report, trigger, id="weekly_report", replace_existing=True, max_instances=1)
scheduler.start()
logger.info("[SCHEDULER] Weekly report agendado: day=%s hour=%d minute=%d (tz=%s)", WEEKLY_REPORT_DAY, WEEKLY_REPORT_HOUR, WEEKLY_REPORT_MINUTE, TZ.zone if TZ else "server")

# ==============================================================================
# Routes (dashboard, players, reports)
# ==============================================================================

@app.route("/")
def dashboard():
    try:
        matches = Match.query.order_by(Match.id.desc()).limit(200).all()
    except OperationalError as oe:
        logger.exception("[ROUTE /] OperationalError ao consultar DB: %s", oe)
        # attempt to recover by disposing engine and returning empty
        try:
            db.engine.dispose()
        except Exception:
            pass
        matches = []
    stats = {
        "total": Match.query.count() if db.session else 0,
        "live": Match.query.filter(Match.status.ilike("live")).count() if db.session else 0
    }
    return render_template("dashboard.html", matches=matches, stats=stats, last_scan=datetime.utcnow())

@app.route("/matches")
def matches_page():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    all_matches = Match.query.order_by(Match.id.desc()).all()
    start = (page - 1) * per_page
    matches = all_matches[start:start + per_page]
    total = len(all_matches)
    total_pages = max(1, ceil(total / per_page))
    return render_template("matches.html", matches=matches, page=page, total_pages=total_pages)

@app.route("/players")
def players_page():
    q = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 10

    query = Player.query
    if q:
        ilike = f"%{q}%"
        query = query.filter((Player.username.ilike(ilike)) | (Player.display_name.ilike(ilike)))

    all_players = query.order_by(Player.id.asc()).all()
    total = len(all_players)
    total_pages = max(1, ceil(total / per_page))
    start = (page - 1) * per_page
    players = all_players[start:start + per_page]

    window = 5
    first = max(1, page - window // 2)
    last = min(total_pages, first + window - 1)
    page_numbers = list(range(first, last + 1))

    return render_template("players.html",
                           players=players,
                           page=page,
                           total_pages=total_pages,
                           page_numbers=page_numbers,
                           q=q)

@app.route("/players/add", methods=["POST"])
def players_add():
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip() or None
    if not username:
        flash("Username é obrigatório.", "error")
        return redirect("/players")

    if Player.query.filter_by(username=username).first():
        flash("Jogador já existe.", "error")
        return redirect("/players")

    db.session.add(Player(username=username, display_name=display_name))
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
        "match_time": m.match_time,
        "created_at": m.created_at
    } for m in matches])

    with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_name = tmp.name
    df.to_excel(tmp_name, index=False)
    return send_file(tmp_name, as_attachment=True, download_name="relatorio_matches.xlsx")

@app.route("/health")
def health():
    return "ok", 200

# ==============================================================================
# Run (local)
# ==============================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)), debug=False)
