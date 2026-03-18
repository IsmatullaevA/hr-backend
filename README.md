Render-stable backend.

Что изменено:
- данные из Google Sheets читаются через requests + retry + timeout;
- добавлен in-memory cache;
- добавлен fallback на последний успешный cache-файл;
- /api/trainers продолжает отдавать те же данные из той же таблицы.

Render settings:
- Build Command: pip install -r requirements.txt
- Start Command: gunicorn app:app --workers 1 --threads 4 --timeout 120
- Env:
  - PYTHON_VERSION=3.12.7
  - FRONTEND_ORIGINS=https://hr-methodology-analytics.netlify.app
  - PUBLIC_API_BASE_URL=https://hr-backend-oxbn.onrender.com
  - CACHE_TTL_SECONDS=300
  - STALE_CACHE_MAX_AGE_SECONDS=86400
  - SHEET_TIMEOUT_SECONDS=15
