FROM python:3.11-slim

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script and cron configuration
COPY daily_stats.py .
COPY crontab /etc/cron.d/daily-stats

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/daily-stats

# Apply cron job
RUN crontab /etc/cron.d/daily-stats

# Create log file
RUN touch /var/log/daily_stats.log

# Make script executable
RUN chmod +x daily_stats.py

# Run cron in foreground
CMD ["cron", "-f"]