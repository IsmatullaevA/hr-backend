import json
import logging
import os
import time
from io import StringIO
from pathlib import Path
from threading import Lock
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent
IMG_DIR = BASE_DIR / 'static' / 'img'
CACHE_FILE = BASE_DIR / 'trainers_cache.json'

app = Flask(__name__)
app.logger.setLevel(logging.INFO)


def get_allowed_origins():
    raw = os.getenv('FRONTEND_ORIGINS', '').strip()
    if not raw:
        return '*'
    origins = [item.strip() for item in raw.split(',') if item.strip()]
    return origins or '*'


CORS(
    app,
    resources={
        r"/api/*": {"origins": get_allowed_origins()},
        r"/img/*": {"origins": get_allowed_origins()},
        r"/healthz": {"origins": get_allowed_origins()},
    },
)

GOOGLE_SHEET_URL = os.getenv(
    'GOOGLE_SHEET_URL',
    'https://docs.google.com/spreadsheets/d/e/2PACX-1vRENIyeYE8Gbr05g_BYrQ5WmTWLG2Eh8ONj3OR3IlrPoQObv22ww8eBlghOiXXxbkZQFgJuBLQ66NpX/pub?gid=969100673&single=true&output=tsv',
)

SHEET_TIMEOUT_SECONDS = float(os.getenv('SHEET_TIMEOUT_SECONDS', '15'))
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '300'))
STALE_CACHE_MAX_AGE_SECONDS = int(os.getenv('STALE_CACHE_MAX_AGE_SECONDS', '86400'))

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
    23: 'Вводный модуль',
    24: 'Тематический модуль (проведение)',
    25: 'Завершение тренинга',
    26: 'Профессиональные качества тренера',
}

PHOTO_FILES = {
    'Темиров Жалолиддин': 'Жалолиддин.png',
    'Рустамов Сардор': 'Сардор.png',
    'Рахманкулова Шахнозабону': 'Шахноза.png',
    'Халимбоев Бехруз': 'Бехруз.png',
    'Бабаева Муборак': 'Муборак.png',
    'Гулямова Сабина': 'Сабина.png',
}

_cache_lock = Lock()
_cache_state = {
    'loaded_at': 0.0,
    'source': 'empty',
    'data': None,
}


def build_http_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(['GET']),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({'User-Agent': 'trainer-audit-api/1.0'})
    return session


HTTP = build_http_session()


def safe_text(value):
    if pd.isna(value):
        return ''
    text = str(value).strip()
    return '' if text.lower() in {'nan', 'none'} else text


def safe_number(value, default=np.nan):
    num = pd.to_numeric(value, errors='coerce')
    return float(num) if not pd.isna(num) else default


def compute_block_avg(row, cols):
    values = [safe_number(row.iloc[i]) for i in cols]
    values = [v for v in values if not np.isnan(v)]
    return float(np.mean(values)) if values else 0.0


def public_base_url():
    explicit = os.getenv('PUBLIC_API_BASE_URL', '').strip().rstrip('/')
    if explicit:
        return explicit
    return request.host_url.rstrip('/')


def photo_url_for(name):
    filename = PHOTO_FILES.get(name)
    if filename and (IMG_DIR / filename).exists():
        return f"{public_base_url()}/img/{quote(filename)}"
    return f"https://ui-avatars.com/api/?name={quote(name.replace(' ', '+'))}&background=random"


def write_cache_file(payload):
    try:
        CACHE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
            encoding='utf-8',
        )
    except Exception:
        app.logger.exception('Failed to write cache file')



def read_cache_file():
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
    except Exception:
        app.logger.exception('Failed to read cache file')
        return None



def cache_is_fresh(loaded_at: float) -> bool:
    return (time.time() - loaded_at) < CACHE_TTL_SECONDS



def cache_is_usable(loaded_at: float) -> bool:
    return (time.time() - loaded_at) < STALE_CACHE_MAX_AGE_SECONDS



def fetch_sheet_text() -> str:
    response = HTTP.get(GOOGLE_SHEET_URL, timeout=SHEET_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.content.decode('utf-8-sig')



def build_sessions_from_sheet_text(sheet_text: str):
    df = pd.read_csv(StringIO(sheet_text), sep='\t')

    while len(df.columns) < 27:
        df[f'empty_{len(df.columns)}'] = np.nan

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
                'label': COMMENT_LABELS.get(col_idx, f'Комментарий {col_idx + 1}'),
                'text': text,
            })

        sessions.append({
            'id': int(idx),
            'sessionId': f"{idx}-{name}".replace(' ', '_'),
            'name': name,
            'date': questionnaire_date or submitted_at,
            'questionnaireDate': questionnaire_date,
            'submittedAt': submitted_at,
            'topic': topic,
            'rater': rater,
            'photo': photo_url_for(name),
            'raw': raw,
            'minCrit': float(min_critical),
            'red': bool(min_critical == 1.0),
            'blocks': {
                'b1': compute_block_avg(row, B1),
                'b2': compute_block_avg(row, B2),
                'b3': compute_block_avg(row, B3),
                'b4': compute_block_avg(row, B4),
            },
            'comments': comments,
            'commentCount': sum(1 for item in comments if safe_text(item['text'])),
        })

    return sessions



def refresh_cache_from_sheet():
    sheet_text = fetch_sheet_text()
    sessions = build_sessions_from_sheet_text(sheet_text)
    payload = {
        'loaded_at': time.time(),
        'source': 'google_sheet',
        'data': sessions,
    }
    with _cache_lock:
        _cache_state.update(payload)
    write_cache_file(payload)
    app.logger.info('Sheet cache refreshed: %s records', len(sessions))
    return payload



def get_trainers_payload(force_refresh: bool = False):
    with _cache_lock:
        memory_payload = dict(_cache_state)

    if not force_refresh and memory_payload['data'] is not None and cache_is_fresh(memory_payload['loaded_at']):
        memory_payload['source'] = 'memory_cache'
        return memory_payload

    try:
        return refresh_cache_from_sheet()
    except Exception as exc:
        app.logger.exception('Failed to refresh from Google Sheets: %s', exc)

        # Fresh in-memory cache is best fallback.
        if memory_payload['data'] is not None and cache_is_usable(memory_payload['loaded_at']):
            memory_payload['source'] = 'memory_cache_stale'
            return memory_payload

        # File cache fallback survives process restarts within the same instance lifecycle.
        file_payload = read_cache_file()
        if file_payload and file_payload.get('data') is not None and cache_is_usable(float(file_payload.get('loaded_at', 0))):
            file_payload['source'] = 'file_cache_stale'
            with _cache_lock:
                _cache_state.update({
                    'loaded_at': float(file_payload.get('loaded_at', 0)),
                    'source': file_payload['source'],
                    'data': file_payload['data'],
                })
            return file_payload

        raise


@app.route('/healthz')
def healthz():
    return jsonify({'ok': True, 'cacheLoaded': _cache_state['data'] is not None})


@app.route('/')
def root():
    return jsonify({
        'service': 'trainer-audit-api',
        'status': 'ok',
        'endpoints': ['/api/trainers', '/healthz', '/img/<filename>'],
    })


@app.route('/img/<path:filename>')
def serve_img(filename):
    return send_from_directory(IMG_DIR, filename)


@app.route('/api/trainers')
def get_data():
    force_refresh = request.args.get('refresh') == '1'
    try:
        payload = get_trainers_payload(force_refresh=force_refresh)
        response = jsonify(payload['data'])
        response.headers['X-Data-Source'] = payload.get('source', 'unknown')
        response.headers['X-Cache-Loaded-At'] = str(int(payload.get('loaded_at', 0)))
        return response
    except Exception as error:
        app.logger.exception('Failed to load trainers data')
        return jsonify({
            'error': 'Не удалось загрузить данные из таблицы',
            'details': str(error),
        }), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)
