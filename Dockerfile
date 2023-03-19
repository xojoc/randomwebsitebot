FROM python:3.11-slim

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

ENV PYTHONUNBUFFERED 1
COPY ./requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /usr/src/app

ENTRYPOINT ["/usr/src/app/docker-entrypoint.sh"]
