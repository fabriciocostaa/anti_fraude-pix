FROM python:3.11-slim
WORKDIR /app
COPY mocks/server.py /app/server.py
COPY mocks/serasa.json /app/serasa.json
COPY mocks/dict.json /app/dict.json
USER nobody
CMD ["python", "server.py"]

