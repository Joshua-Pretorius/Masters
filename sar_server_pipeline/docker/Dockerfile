ARG SNAP_IMAGE=mundialis/esa-snap:latest

FROM ${SNAP_IMAGE} AS snap-runtime

# SNAP 9 in the Mundialis image is compatible with Java 11. Pin Bullseye so
# default-jre-headless cannot silently advance to Java 21 on a future rebuild.
FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    JAVA_HOME=/usr/lib/jvm/default-java \
    SNAP_HOME=/usr/local/snap \
    SNAP_GPT=/usr/local/snap/bin/gpt \
    PATH=/usr/local/snap/bin:${PATH}
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-jre-headless \
        fontconfig \
        fonts-dejavu-core \
        gdal-bin \
        libgdal-dev \
        libgfortran5 \
        libproj-dev \
        libxi6 \
        libxrender1 \
        libxtst6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=snap-runtime /usr/local/snap /usr/local/snap
COPY --from=snap-runtime /root/.snap /root/.snap

# Fail the image build if GPT exits unsuccessfully or reports a loader failure.
RUN set -eu; \
    test -x "${SNAP_GPT}"; \
    gpt_log="$(mktemp)"; \
    if ! "${SNAP_GPT}" -h >"${gpt_log}" 2>&1; then \
        cat "${gpt_log}"; \
        exit 1; \
    fi; \
    if grep -Eq "SEVERE:|UnsatisfiedLinkError|NoClassDefFoundError" "${gpt_log}"; then \
        cat "${gpt_log}"; \
        exit 1; \
    fi; \
    rm -f "${gpt_log}"

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY pipeline /app/pipeline
COPY stages /app/stages
COPY docker/snap_graphs /app/docker/snap_graphs
COPY vendor /app/vendor

ENTRYPOINT ["python", "-m", "pipeline"]
