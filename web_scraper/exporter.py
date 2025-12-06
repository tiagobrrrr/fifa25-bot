# web_scraper/exporter.py
import pandas as pd
import os
from datetime import datetime

OUTPUT_DIR = "stadiums_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def export_single_workbook_by_stadium(stadium_dict: dict, prefix: str = "stadiums_report"):
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.xlsx"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for stadium, matches in stadium_dict.items():
            sheet = stadium[:31]  # limite de nome da aba
            df = pd.DataFrame(matches)

            cols = [
                "match_id", "stadium", "league", "match_time",
                "team1", "player1", "team2", "player2", "score", "status"
            ]
            df = df[[c for c in cols if c in df.columns]]

            df.to_excel(writer, sheet_name=sheet, index=False)

    return filepath

