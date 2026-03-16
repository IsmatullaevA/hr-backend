from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRENIyeYE8Gbr05g_BYrQ5WmTWLG2Eh8ONj3OR3IlrPoQObv22ww8eBlghOiXXxbkZQFgJuBLQ66NpX/pub?gid=969100673&single=true&output=tsv"

# Маппинг всех 18 критериев (индексы колонок F-W)
B1, B2, B3, B4 = [5,6,7,8], [9,10,11,12,13,14,15,16], [17,18], [19,20,21,22]
CRITICAL = [14, 21, 22] 

PHOTOS = {
    "Темиров Жалолиддин": "./img/Жалолиддин.png",
    "Рустамов Сардор": "./img/Сардор.png",
    "Рахманкулова Шахнозабону": "./img/Шахноза.png",
    "Халимбоев Бехруз": "./img/Бехруз.png",
    "Бабаева Муборак": "./img/Муборак.png",
    "Гулямова Сабина": "./img/Сабина.png"
}

@app.route('/api/trainers')
def get_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, sep='\t')
        
        while len(df.columns) < 23:
            df[f"empty_{len(df.columns)}"] = np.nan
            
        df = df.dropna(subset=[df.columns[2]])
        
        trainers = []
        for idx, row in df.iterrows():
            name = str(row.iloc[2]).strip()
            date_str = str(row.iloc[0]) # Дата заполнения
            
            raw = [float(pd.to_numeric(row.iloc[i], errors='coerce')) if not np.isnan(pd.to_numeric(row.iloc[i], errors='coerce')) else 0.0 for i in range(5, 23)]
            
            def avg(cols): 
                m = np.nanmean([pd.to_numeric(row.iloc[i], errors='coerce') for i in cols])
                return float(m) if not np.isnan(m) else 0.0
            
            crit_vals = [pd.to_numeric(row.iloc[i], errors='coerce') for i in CRITICAL]
            min_c = np.nanmin(crit_vals) if not np.isnan(crit_vals).all() else 5.0

            fallback = f"https://ui-avatars.com/api/?name={name.replace(' ','+')}&background=random"

            trainers.append({
                "id": idx, "date": date_str, "name": name, "photo": PHOTOS.get(name, fallback),
                "raw": raw, "minCrit": float(min_c), "red": bool(min_c == 1.0),
                "blocks": {"b1": avg(B1), "b2": avg(B2), "b3": avg(B3), "b4": avg(B4)}
            })
            
        return jsonify(trainers)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)