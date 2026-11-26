FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/mithu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY command-center ./command-center
COPY tests ./tests
COPY README.md README_COMMAND_CENTER.md ./
RUN useradd --create-home --uid 10001 mithu && chown -R mithu:mithu /srv/mithu
USER mithu
EXPOSE 8100
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8100}"]
