FROM python:3

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT 8080
ENV FLASK_APP app.py

WORKDIR /app
COPY . /app

RUN pip install --no-cache -r requirements.txt

CMD ["flask", "run", "-h", "0.0.0.0", "-p", "8080"]

