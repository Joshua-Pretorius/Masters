ARG SNAP_IMAGE=mundialis/esa-snap:latest

# Keep SNAP in its native Mundialis/Alpine runtime.  The previous image used
# python:3.11-slim-bullseye and copied /usr/local/snap into it; GPT started but
# could hang while writing BEAM-DIMAP products.  This image deliberately uses
# the runtime that completed the calibration smoke test successfully.
FROM ${SNAP_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    SNAP_HOME=/usr/local/snap \
    SNAP_GPT=/usr/local/snap/bin/gpt \
    PATH=/usr/local/snap/bin:${PATH}
WORKDIR /app

RUN apk add --no-cache \
        build-base \
        fontconfig \
        gdal \
        gdal-dev \
        geos \
        geos-dev \
        libgfortran \
        libxi \
        libxrender \
        libxtst \
        proj \
        proj-dev \
        py3-pip \
        python3-dev

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
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY pipeline /app/pipeline
COPY stages /app/stages
COPY docker/snap_graphs /app/docker/snap_graphs
COPY vendor /app/vendor

ENTRYPOINT ["python3", "-m", "pipeline"]
