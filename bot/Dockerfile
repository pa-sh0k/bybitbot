FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8001

CMD ["python", "-m", "app.main"]