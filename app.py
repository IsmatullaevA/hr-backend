from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRENIyeYE8Gbr05g_BYrQ5WmTWLG2Eh8ONj3OR3IlrPoQObv22ww8eBlghOiXXxbkZQFgJuBLQ66NpX/pub?gid=969100673&single=true&output=tsv"

TIMESTAMP_COL = 0
DATE_COL = 1
NAME_COL = 2
TOPIC_COL = 3
RATER_COL = 4

SCORES_START = 5
SCORES_END = 23
COMMENT_COLS = [23, 24, 25, 26]

B1 = [5, 6, 7, 8]
B2 = [9, 10, 11, 12, 13, 14, 15, 16]
B3 = [17, 18]
B4 = [19, 20, 21, 22]

CRITICAL = [14, 21, 22]

COMMENT_LABELS = {
    23: "Вводный модуль",
    24: "Тематический модуль (проведение)",
    25: "Завершение тренинга",
    26: "Профессиональные качества тренера",
}

PHOTOS = {
    "Темиров Жалолиддин": "./img/Жалолиддин.png",
    "Рустамов Сардор": "./img/Сардор.png",
    "Рахманкулова Шахнозабону": "./img/Шахноза.png",
    "Халимбоев Бехруз": "./img/Бехруз.png",
    "Бабаева Муборак": "./img/Муборак.png",
    "Гулямова Сабина": "./img/Сабина.png"
}


def safe_text(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def safe_number(value, default=np.nan):
    num = pd.to_numeric(value, errors="coerce")
    return float(num) if not pd.isna(num) else default


def compute_block_avg(row, cols):
    values = [safe_number(row.iloc[i]) for i in cols]
    values = [v for v in values if not np.isnan(v)]
    return float(np.mean(values)) if values else 0.0


@app.route("/api/trainers")
def get_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, sep="\t")

        while len(df.columns) < 27:
            df[f"empty_{len(df.columns)}"] = np.nan

        df = df.dropna(subset=[df.columns[NAME_COL]])

        sessions = []
        for idx, row in df.iterrows():
            name = safe_text(row.iloc[NAME_COL])
            if not name:
                continue

            questionnaire_date = safe_text(row.iloc[DATE_COL])
            submitted_at = safe_text(row.iloc[TIMESTAMP_COL])
            topic = safe_text(row.iloc[TOPIC_COL])
            rater = safe_text(row.iloc[RATER_COL])

            raw = []
            for i in range(SCORES_START, SCORES_END):
                raw.append(safe_number(row.iloc[i], default=0.0))

            crit_vals = [safe_number(row.iloc[i]) for i in CRITICAL]
            crit_vals = [v for v in crit_vals if not np.isnan(v)]
            min_critical = min(crit_vals) if crit_vals else 5.0

            comments = []
            for col_idx in COMMENT_COLS:
                text = safe_text(row.iloc[col_idx])
                comments.append({
                    "label": COMMENT_LABELS.get(col_idx, f"Комментарий {col_idx + 1}"),
                    "text": text
                })

            fallback = f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=random"

            sessions.append({
                "id": int(idx),
                "sessionId": f"{idx}-{name}".replace(" ", "_"),
                "name": name,
                "date": questionnaire_date or submitted_at,
                "questionnaireDate": questionnaire_date,
                "submittedAt": submitted_at,
                "topic": topic,
                "rater": rater,
                "photo": PHOTOS.get(name, fallback),
                "raw": raw,
                "minCrit": float(min_critical),
                "red": bool(min_critical == 1.0),
                "blocks": {
                    "b1": compute_block_avg(row, B1),
                    "b2": compute_block_avg(row, B2),
                    "b3": compute_block_avg(row, B3),
                    "b4": compute_block_avg(row, B4)
                },
                "comments": comments,
                "commentCount": sum(1 for item in comments if safe_text(item["text"]))
            })

        return jsonify(sessions)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
