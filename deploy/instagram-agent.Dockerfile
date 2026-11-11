FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY agent/instagram_poc/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
COPY agent/__init__.py agent/credentials.py /app/agent/
COPY agent/instagram_poc /app/agent/instagram_poc
RUN useradd --uid 10001 --create-home app && mkdir -p /var/lib/instagram/data /var/lib/instagram/key /run/instagram-control && chown -R app:app /var/lib/instagram /run/instagram-control && chmod 700 /var/lib/instagram/data /var/lib/instagram/key /run/instagram-control
USER app
CMD ["python", "-m", "agent.instagram_poc.bridge", "--host", "0.0.0.0", "--data-dir", "/var/lib/instagram/data", "--key-dir", "/var/lib/instagram/key", "--control-dir", "/run/instagram-control"]
