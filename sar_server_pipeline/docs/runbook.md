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
2. Set `DATA_ROOT`, `JOB_DIR`, and `SNAP_HOST_DIR` for the server.
3. Confirm the mounted SNAP GPT binary will be available at `/opt/snap/bin/gpt`.

```bash
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

## SNAP on the host

The image does not install SNAP itself. Compose mounts the host SNAP installation from `SNAP_HOST_DIR`
to `/opt/snap` in the container and exports `SNAP_GPT=/opt/snap/bin/gpt`.

If the server SNAP install exposes `gpt` at a different location, either:

- change `SNAP_GPT` in `.env`, or
- set `stages.slc_process.gpt` in the manifest to the in-container path.
