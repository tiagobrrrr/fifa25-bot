import pandas as pd
from datetime import datetime, timedelta
from models import Match, db

def generate_weekly_excel():
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    matches = (
        db.session.query(Match)
        .filter(Match.created_at >= start_date)
        .all()
    )

    if not matches:
        return None

    data = []
    for m in matches:
        data.append({
            "Location": m.location,
            "League": m.league,
            "Home Team": m.home_team,
            "Away Team": m.away_team,
            "Score": f"{m.home_score} - {m.away_score}",
            "Status": m.status,
            "Match Time (UTC)": m.match_time,
            "Collected At (UTC)": m.created_at
        })

    df = pd.DataFrame(data)

    file_path = f"/tmp/fifa25_report_{end_date.date()}.xlsx"

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        for location, group in df.groupby("Location"):
            group.to_excel(
                writer,
                sheet_name=location[:31],
                index=False
            )

    return file_path
