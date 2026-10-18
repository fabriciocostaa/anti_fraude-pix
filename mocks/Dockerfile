FROM python:3.11-slim
WORKDIR /app
COPY mocks/server.py /app/server.py
COPY src/income_ranges.json /app/income_ranges.json
USER nobody
CMD ["python", "server.py"]
