FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN SECRET_KEY=build-only-dummy-key \
    DEBUG=False \
    DB_NAME=dummy \
    DB_USER=dummy \
    DB_PASSWORD=dummy \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p $PORT devduel.asgi:application"]