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

# set dummy SECRET_KEY only for collectstatic — Railway real one set via env vars
ENV SECRET_KEY=dummy-build-secret-not-used-in-production
ENV DEBUG=False
ENV ALLOWED_HOSTS=*

RUN python manage.py collectstatic --noinput || true

CMD daphne -b 0.0.0.0 -p ${PORT:-8000} devduel.asgi:application