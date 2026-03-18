# Backend for Render

Что важно:

1. В `requirements.txt` НЕ должно быть строки `3.12.7`.
2. Версия Python фиксируется через файл `.python-version` и/или переменную `PYTHON_VERSION`.
3. Для Render:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Обязательные переменные окружения:
   - `FRONTEND_ORIGINS=https://hr-methodology-analytics.netlify.app`
   - `PUBLIC_API_BASE_URL=https://hr-backend-oxbn.onrender.com`

Если сервис уже создан вручную, Render может не подхватить `render.yaml` автоматически. Тогда проверьте команды и переменные в UI Render.
