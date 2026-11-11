FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /policy
COPY deploy/privacy/server.py /policy/server.py
COPY deploy/privacy/default-policy.html /policy/privacy.html
COPY web/public/static/public/policy.css /policy/policy.css
USER 10001:10001
EXPOSE 8000
CMD ["python", "/policy/server.py"]
