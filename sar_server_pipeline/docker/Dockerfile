FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    SNAP_HOME=/opt/snap \
    SNAP_GPT=/opt/snap/bin/gpt \
    PATH=/opt/snap/bin:${PATH}
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gdal-bin libgdal-dev libproj-dev build-essential default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/snap

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY pipeline /app/pipeline
COPY stages /app/stages
COPY docker/snap_graphs /app/docker/snap_graphs
COPY vendor /app/vendor

ENTRYPOINT ["python", "-m", "pipeline"]
