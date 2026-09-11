FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/backend
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd --system app && useradd --system --gid app --create-home app && chown app:app /app
COPY --chown=app:app backend backend
COPY --chown=app:app src src
USER app
EXPOSE 8000
CMD ["gunicorn", "stocksense.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]

FROM base AS development
USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY --chown=app:app tests tests
COPY --chown=app:app scripts scripts
COPY --chown=app:app pyproject.toml ./
USER app
CMD ["python", "backend/manage.py", "runserver", "0.0.0.0:8000"]
