import pandas as pd


def normalize_players(matches):
    players = {}

    for m in matches:
        ph = m.player_home
        pa = m.player_away
        sh = m.score_home
        sa = m.score_away

        for p in [ph, pa]:
            if p not in players:
                players[p] = {
                    "player": p,
                    "jogos": 0,
                    "vitorias": 0,
                    "derrotas": 0,
                    "empates": 0,
                    "gols_feitos": 0,
                    "gols_sofridos": 0,
                }

        players[ph]["jogos"] += 1
        players[pa]["jogos"] += 1

        players[ph]["gols_feitos"] += sh
        players[ph]["gols_sofridos"] += sa
        players[pa]["gols_feitos"] += sa
        players[pa]["gols_sofridos"] += sh

        if sh > sa:
            players[ph]["vitorias"] += 1
            players[pa]["derrotas"] += 1
        elif sh < sa:
            players[pa]["vitorias"] += 1
            players[ph]["derrotas"] += 1
        else:
            players[ph]["empates"] += 1
            players[pa]["empates"] += 1

    return pd.DataFrame(players.values())


def export_players_history(matches, output_path="players_history.xlsx"):
    df = normalize_players(matches)

    df = df.sort_values(
        by=["vitorias", "gols_feitos"],
        ascending=False
    )

    df.to_excel(output_path, index=False)
    return output_path
