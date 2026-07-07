FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite kalici volume'de dursun (restart'ta dedup hafizasi silinmesin)
ENV DB_FILE=/data/finder_crm.db

# Headless email-only autopilot (DM YOK). Loglar stdout'a.
CMD ["python", "-u", "worker.py"]
