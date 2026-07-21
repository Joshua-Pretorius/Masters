# Operator Runbook

## Canonical mount layout

- `/data/raw`
- `/data/processed`
- `/data/shapefiles`
- `/data/biophysical`
- `/data/patches`
- `/data/stacks`
- `/data/logs`
- `/data/manifests`
- `/job`

## Build

```bash
docker build -t sar-server-pipeline -f docker/Dockerfile .
```

## Compose setup

1. Copy `.env.example` to `.env`.
2. Set `DATA_ROOT` and `JOB_DIR` for the server.
3. Pull the SNAP base image used by the pipeline build.

```bash
docker pull mundialis/esa-snap:latest
docker compose build
```

## Run one stage

```bash
docker run --rm \
  -v /srv/sar-data:/data \
  -v /srv/jobs:/job \
  sar-server-pipeline \
  patch_extract --manifest /job/job.yaml
```

Compose equivalent:

```bash
docker compose run --rm pipeline patch_extract --manifest /job/job.yaml
```

## Run all stages

```bash
docker run --rm \
  -v /srv/sar-data:/data \
  -v /srv/jobs:/job \
  sar-server-pipeline \
  run_all --manifest /job/job.yaml
```

Compose default:

```bash
docker compose run --rm pipeline
```

Override the manifest path if needed:

```bash
JOB_MANIFEST=/job/other-job.yaml docker compose run --rm pipeline
```

## Outputs

- Scene outputs under `processed_root`
- Patch rasters and catalogs under `patches_root`
- Final stacked patches and dataset manifest under `stacks_root`
- Stage status markers under `manifests_root/<run_id>/stages`

## SLC stage source

`slc_process` defaults to the vendored neutral Sentinel-1 SLC processor bundled under `vendor/`.
If you need to override that entrypoint, set `stages.slc_process.processor_script` in the manifest.

## SNAP runtime

The pipeline image imports SNAP from `mundialis/esa-snap:latest` during its multi-stage build. No host SNAP
installation or SNAP bind mount is required. The image exports `SNAP_GPT=/usr/local/snap/bin/gpt` and runs
`gpt -h` while building so an unusable SNAP runtime fails the build immediately. The Python runtime is pinned
to Debian Bullseye so SNAP uses Java 11 rather than an incompatible newer default JRE.

To use another compatible SNAP image, pass it as the `SNAP_IMAGE` build argument. If that image installs GPT
at another path, update `SNAP_GPT` in the Dockerfile and the optional manifest override together.
