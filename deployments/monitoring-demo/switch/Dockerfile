FROM python:3.12-alpine

WORKDIR /app
COPY exporter.py .

ENV SWITCH_PORT=9101
EXPOSE 9101

CMD ["python3", "/app/exporter.py"]
