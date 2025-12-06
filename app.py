# app.py - Versão final substituindo scraper por StadiumScraper
import os
import time
import logging
from math import ceil
from datetime import datetime
from tempfile import NamedTemporaryFile

from flask import Flask, render_template, request, redirect, session, send_file, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

# import do novo scraper/exporter/emailer
from web_scraper.stadium_scraper import StadiumScraper
from web_scraper.exporter import export_single_workbook_by_stadium
from web_scraper.emailer import send_file_via_gmail

# =========================================================
# CONFIGURAÇÃO
# =========================================================
app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "default_secret_key")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# scanner interval (segundos)
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))

# Scheduler on/off
RUN_SCRAPER = os.getenv("RUN_SCRAPER", "true").lower() == "true"

# Gmail env vars (para relatório semanal)
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT", GMAIL_USER)

# logging
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
    match_id = db.Column(db.String(128), unique=False)  # optional unique identifier from scraper

# =========================================================
# DATABASE BOOTSTRAP (espera banco e corrige schema)
# =========================================================
def ensure_db_ready_and_sync():
    """
    Aguarda o DB ficar disponível, remove tabelas antigas e cria as tabelas atuais.
    """
    with app.app_context():
        # 1) esperar banco ficar disponível
        for attempt in range(30):
            try:
                db.session.execute(text("SELECT 1"))
                break
            except OperationalError:
                app.logger.info(f"[DB] Banco indisponível, aguardando... ({attempt+1}/30)")
                time.sleep(1)
        else:
            app.logger.error("[DB] Banco não respondeu a tempo. Continuando sem criar tabelas.")
            return

        # 2) remover eventuais tabelas antigas/problemáticas (mantém matches)
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

# =========================================================
# SCRAPER: usa StadiumScraper em vez do antigo scrape_matches()
# =========================================================
scraper = StadiumScraper(wait_seconds=int(os.getenv("SCRAPER_WAIT", 6)))

def scan_and_save():
    """
    Executa o scraper (Selenium), salva resultados no banco de dados.
    Substitui o scraper antigo.
    """
    with app.app_context():
        try:
            app.logger.info("[SCAN] Execução do scanner iniciada.")
            # pegar HTML e parse pelo scraper
            locations_map, matches = scraper.parse(scraper.fetch_page())

            # limpar tabela e inserir resultados novos (simples)
            db.session.query(Match).delete()
            for m in matches:
                mm = Match(
                    stadium = m.get("stadium"),
                    league = m.get("league"),
                    match_time = m.get("match_time"),
                    team1 = m.get("team1"),
                    player1 = m.get("player1"),
                    team2 = m.get("team2"),
                    player2 = m.get("player2"),
                    score = m.get("score"),
                    status = m.get("status"),
                    match_id = m.get("match_id")
                )
                db.session.add(mm)
            db.session.commit()
            app.logger.info("[SCAN] Concluído com %d partidas", len(matches))
        except Exception as e:
            app.logger.exception("[SCAN] Erro durante scan_and_save: %s", e)
            db.session.rollback()

# =========================================================
# EXPORT & EMAIL (manual endpoint + weekly job)
# =========================================================
def generate_and_get_workbook():
    """
    Lê os matches do DB, agrupa por stadium, gera workbook com uma aba por estádio.
    Retorna path do arquivo gerado.
    """
    with app.app_context():
        matches = Match.query.order_by(Match.id.desc()).all()
        # agrupar
        stadiums = {}
        for m in matches:
            name = m.stadium or "Unknown"
            stadiums.setdefault(name, []).append({
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
        # export
        path = export_single_workbook_by_stadium(stadiums, prefix="weekly_stadiums")
        return path

def weekly_stadium_report():
    """
    Job semanal: gera o workbook e envia por email (Gmail).
    """
    app.logger.info("[REPORT] Iniciando relatório semanal por estádio...")
    try:
        # geramos a planilha a partir do DB (mais rápido e consistente)
        workbook_path = generate_and_get_workbook()
        subj = "Relatório semanal - partidas por estádio"
        body = "Segue em anexo o relatório semanal com uma aba por estádio."
        send_file_via_gmail(workbook_path, subj, body)
        app.logger.info("[REPORT] Email enviado com sucesso.")
    except Exception as e:
        app.logger.exception("[REPORT] Falha ao gerar/enviar relatório: %s", e)

# =========================================================
# SCHEDULER
# =========================================================
scheduler = BackgroundScheduler()
if RUN_SCRAPER:
    # job contínuo de scraping
    scheduler.add_job(scan_and_save, "interval", seconds=SCAN_INTERVAL, id="scan_and_save")
    # job semanal (domingo 00:05 America/Sao_Paulo)
    scheduler.add_job(weekly_stadium_report, "cron", day_of_week="sun", hour=0, minute=5, timezone="America/Sao_Paulo", id="weekly_stadium_report")
    scheduler.start()
    app.logger.info("[SCHEDULER] Ativo — intervalo %ds", SCAN_INTERVAL)
else:
    app.logger.info("[SCHEDULER] Desativado por configuração.")

# =========================================================
# ROTAS PRINCIPAIS
# =========================================================
@app.route("/")
def dashboard():
    # carregar últimas 200 partidas
    try:
        matches = Match.query.order_by(Match.id.desc()).limit(200).all()
        # estatísticas
        total = Match.query.count()
        live = Match.query.filter(Match.status.ilike("%live%")).count()
        stats = {"total": total, "live": live}
        # por segurança, passar matches como lista de dicts para Jinja
        matches_list = [{
            "id": m.id,
            "stadium": m.stadium,
            "team1": m.team1,
            "team2": m.team2,
            "score": m.score,
            "league": m.league,
            "match_time": m.match_time,
            "status": m.status
        } for m in matches]
        # precompute live matches to avoid jinja list-comprehension issues in templates
        live_matches = [m for m in matches_list if m.get("status") and "live" in m.get("status", "").lower()]

        return render_template("dashboard.html", matches=matches_list, stats=stats, last_scan=datetime.utcnow(), live_matches=live_matches)
    except Exception as e:
        app.logger.exception("[WEB] Erro ao renderizar dashboard: %s", e)
        return "Erro interno", 500

# Matches page (paginação simples)
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

# Players page
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
    start = (page-1)*per_page
    players = all_players[start:start+per_page]

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

# Players add/delete
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

# Reports page
@app.route("/reports")
def reports_page():
    matches = Match.query.order_by(Match.id.desc()).all()
    stats = {"total": len(matches), "live": len([m for m in matches if m.status and "live" in (m.status or "").lower()])}
    return render_template("reports.html", stats=stats)

# Export current DB to excel (existing behaviour)
@app.route("/reports/export", methods=["POST"])
def export_report():
    matches = Match.query.order_by(Match.id.desc()).all()
    df = []
    for m in matches:
        df.append({
            "ID": m.id,
            "stadium": m.stadium,
            "team1": m.team1,
            "team2": m.team2,
            "score": m.score,
            "status": m.status,
            "league": m.league,
            "match_time": m.match_time
        })
    import pandas as pd
    df = pd.DataFrame(df)

    with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_name = tmp.name
    df.to_excel(tmp_name, index=False)
    return send_file(tmp_name, as_attachment=True, download_name="relatorio_matches.xlsx")

# Manual endpoint to generate stadium workbook now and return path (for testing)
@app.route("/export_stadiums")
def export_stadiums_now():
    try:
        path = generate_and_get_workbook()
        return jsonify({"status": "ok", "path": path})
    except Exception as e:
        app.logger.exception("[EXPORT] Falha ao gerar export: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# Health
@app.route("/health")
def health():
    return "ok", 200

# =========================================================
# START (LOCAL)
# =========================================================
if __name__ == "__main__":
    # local debug server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)), debug=False)
