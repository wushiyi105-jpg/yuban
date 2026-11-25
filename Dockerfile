FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8775

CMD ["python", "-m", "yuban", "serve", "--host", "0.0.0.0"]
