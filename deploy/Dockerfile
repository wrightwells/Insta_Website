# Development image. Pin the base digest after registry/platform verification
# before producing a production artifact.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY config /app/config
COPY domain /app/domain
COPY web /app/web
COPY locales /app/locales
COPY manage.py /app/manage.py
RUN useradd --uid 10001 --create-home app && mkdir /app/private-media /app/staticfiles /var/lib/contact-mail /var/lib/site-policy && chmod 700 /var/lib/contact-mail /var/lib/site-policy && chown app:app /app/private-media /app/staticfiles /var/lib/contact-mail /var/lib/site-policy
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "/dev/null"]
