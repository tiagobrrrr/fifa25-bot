import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix
from threading import Thread, Event, Lock
import time
import datetime
import pytz

from models import db, Player, Team, Match, FinishedMatchArchive
from web_scraper import FIFA25Scraper
from data_analyzer import DataAnalyzer
from email_service import EmailService
from telegram_service import TelegramNotifier

app = Flask(__name__, template_folder="templates")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///fifa25_bot.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SESSION_SECRET", "fifa25-bot-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
db.init_app(app)

# Logging
if not os.path.exists("logs"):
    os.makedirs("logs")

handler = RotatingFileHandler("logs/fifa25_bot.log", maxBytes=5_000_000, backupCount=5)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")

scraper = FIFA25Scraper()
analyzer = DataAnalyzer()
email_service = EmailService()
telegram_notifier = TelegramNotifier()

stop_event = Event()
SCAN_INTERVAL_SECONDS = int(os.environ.get("SCAN_INTERVAL", 30))
last_scan = None

_worker_started = False
_worker_lock = Lock()


# ---------------------------
#   Persistência
# ---------------------------
def persist_match_if_new(m):
    try:
        ts = None
        if m.get("timestamp"):
            try:
                ts = datetime.datetime.fromisoformat(m["timestamp"])
            except:
                ts = None

        date_val = ts.date() if ts else datetime.date.today()
        time_val = ts.time() if ts else None

        existing = Match.query.filter_by(match_id=m["match_id"], player=m.get("player_left")).first()
        if existing:
            changed = False
            if existing.status != m.get("status"):
                existing.status = m.get("status")
                changed = True
            if changed:
                db.session.commit()
            return existing

        left = Match(
            match_id=m["match_id"],
            player=m["player_left"],
            team=m["team_left"],
            opponent=m["team_right"],
            goals=m.get("goals_left"),
            goals_against=m.get("goals_right"),
            win=(m.get("goals_left") is not None and m.get("goals_left") > m.get("goals_right"))
                if m.get("goals_left") is not None else None,
            league=m.get("league"),
            stadium=m.get("stadium"),
            date=date_val,
            time=time_val,
            status=m.get("status", "planned")
        )

        right = Match(
            match_id=m["match_id"],
            player=m["player_right"],
            team=m["team_right"],
            opponent=m["team_left"],
            goals=m.get("goals_right"),
            goals_against=m.get("goals_left"),
            win=(m.get("goals_right") is not None and m.get("goals_right") > m.get("goals_left"))
                if m.get("goals_right") is not None else None,
            league=m.get("league"),
            stadium=m.get("stadium"),
            date=date_val,
            time=time_val,
            status=m.get("status", "planned")
        )

        db.session.add_all([left, right])
        db.session.commit()

        if m.get("status", "").lower() in ("finished", "final"):
            a1 = FinishedMatchArchive(
                match_id=m["match_id"],
                player=left.player,
                team=left.team,
                opponent=left.opponent,
                goals=left.goals,
                goals_againant=left.goals_against,
                win=left.win,
                league=left.league,
                stadium=left.stadium,
                date=left.date,
                time=left.time
            )

            a2 = FinishedMatchArchive(
                match_id=m["match_id"],
                player=right.player,
                team=right.team,
                opponent=right.opponent,
                goals=right.goals,
                goals_againant=right.goals_against,
                win=right.win,
                league=right.league,
                stadium=right.stadium,
                date=right.date,
                time=right.time
            )

            db.session.add_all([a1, a2])
            db.session.commit()

        app.logger.info(f"Saved match {m['match_id']}")
        return left

    except Exception as e:
        app.logger.exception(f"Error persisting match: {e}")
        db.session.rollback()
        return None


# ---------------------------
#   LOOP DO BOT (SCRAPER)
# ---------------------------
def scan_and_persist():
    global last_scan
    try:
        app.logger.info("Scanning for matches...")
        matches = scraper.get_live_matches() + scraper.get_recent_matches()
        last_scan = datetime.datetime.now(BRAZIL_TZ)

        app.logger.info(f"Found {len(matches)} matches")

        players = {p.username for p in Player.query.all()}
        teams = {t.name for t in Team.query.all()}

        for m in matches:
            if players:
                if not (m.get("player_left") in players or m.get("player_right") in players):
                    continue
            persist_match_if_new(m)

        return True

    except Exception as e:
        app.logger.exception(f"Error scanning: {e}")
        try:
            telegram_notifier.send(f"❌ Bot scanning error: {e}")
        except:
            pass
        return False


def background_worker():
    app.logger.info("Background worker started")
    while not stop_event.is_set():
        ok = scan_and_persist()
        sleep_time = SCAN_INTERVAL_SECONDS if ok else max(60, SCAN_INTERVAL_SECONDS * 2)
        stop_event.wait(sleep_time)

    app.logger.info("Background worker stopped")
    try:
        telegram_notifier.send("⚠️ Bot parado.")
    except:
        pass


def start_worker_once():
    global _worker_started
    if os.environ.get("RUN_SCRAPER", "true").lower() not in ("1", "true", "yes"):
        app.logger.info("Scraper desativado via RUN_SCRAPER")
        return

    with _worker_lock:
        if not _worker_started:
            Thread(target=background_worker, daemon=True).start()
            _worker_started = True
            app.logger.info("Background worker iniciado")


# ---------------------------
#   SETUP COMPATÍVEL COM FLASK 3
# ---------------------------
@app.before_request
def setup_once():
    if not hasattr(app, "_setup_done"):
        app._setup_done = True
        db.create_all()
        start_worker_once()


# ---------------------------
#   ROTAS DO FLASK
# ---------------------------
@app.route("/")
def dashboard():
    today = datetime.date.today()
    rows = Match.query.filter(Match.date == today).all()

    matches_data = [{
        "match_id": r.match_id,
        "player": r.player,
        "team": r.team,
        "opponent": r.opponent,
        "goals": r.goals,
        "goals_against": r.goals_against,
        "win": r.win,
        "league": r.league,
        "stadium": r.stadium,
        "date": r.date.isoformat(),
        "time": r.time.isoformat() if r.time else None,
        "status": r.status
    } for r in rows]

    stats = analyzer.get_daily_stats(matches_data)

    return render_template("dashboard.html", matches=matches_data, stats=stats, last_scan=last_scan)


@app.route("/api/live")
def api_live():
    rows = Match.query.filter(Match.status.in_(["Live", "Started", "live", "started"])).all()
    data = [{
        "match_id": r.match_id,
        "player": r.player,
        "team": r.team,
        "opponent": r.opponent,
        "goals": r.goals,
        "status": r.status
    } for r in rows]

    return jsonify({"matches": data})


@app.route("/players")
def players_page():
    players = Player.query.order_by(Player.username).all()
    return render_template("players.html", players=players)


@app.route("/players/add", methods=["POST"])
def players_add():
    username = request.form.get("username")
    display = request.form.get("display_name")

    if not username:
        flash("username obrigatório", "error")
        return redirect(url_for("players_page"))

    if Player.query.filter_by(username=username).first():
        flash("Jogador já existe", "warning")
        return redirect(url_for("players_page"))

    db.session.add(Player(username=username, display_name=display))
    db.session.commit()

    flash("Jogador adicionado", "success")
    return redirect(url_for("players_page"))


@app.route("/players/delete/<int:id>", methods=["POST"])
def players_delete(id):
    obj = Player.query.get(id)
    if obj:
        db.session.delete(obj)
        db.session.commit()
    return redirect(url_for("players_page"))


@app.route("/matches")
def matches_page():
    page = int(request.args.get("page", 1))
    per = 200

    rows = Match.query.order_by(Match.date.desc(), Match.time.desc()) \
                      .limit(per).offset((page - 1) * per).all()

    return render_template("matches.html", matches=rows, page=page)


@app.route("/admin/shutdown", methods=["POST"])
def admin_shutdown():
    stop_event.set()
    flash("Bot será finalizado", "info")
    return redirect(url_for("dashboard"))


@app.route("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
