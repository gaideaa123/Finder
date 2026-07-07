FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Server varsayilanlari (fly.toml / env ile ezilebilir)
ENV HOST=0.0.0.0 \
    PORT=8080 \
    DATA_DIR=/data \
    AUTOSTART=1 \
    REQUIRE_EMAIL=1

EXPOSE 8080

# Tek process: arka plandaki auto-loop'un tek kopya calismasi icin onemli.
CMD ["python", "app.py"]
