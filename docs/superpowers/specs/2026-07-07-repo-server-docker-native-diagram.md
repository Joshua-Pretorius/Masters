# Repository Server Docker-Native Diagram

This is a standalone Docker-native view of the system.

It intentionally describes the setup in terms of:

- your workstation
- Docker Compose
- the `pipeline` service
- the `sar-server-pipeline` image
- container bind mounts
- runtime environment variables
- host-side outputs written by the container

Related documents:

- `D:\Masters\docs\superpowers\specs\2026-07-06-repo-server-architecture-design.md`
- `D:\Masters\docs\superpowers\specs\2026-07-06-repo-server-system-dev-diagram.md`

## Docker-Native System Graph

```mermaid
flowchart LR
    subgraph WS["Your Workstation"]
        W1["Prepare data
        match CSVs
        points CSVs
        shapefiles
        biophysical rasters"]
        W2["Prepare Docker job
        compose env values
        job.yaml or job.json"]
        W3["Run Docker command
        docker compose run --rm pipeline"]
    end

    subgraph DEP["Runtime dependencies"]
        D1["Earthdata / ASF
        used when slc_process downloads SLC"]
        D2["Host SNAP install
        GPT binary"]
        D3["Credentials and env vars
        EDL_USER
        EDL_PASS
        SNAP_GPT
        JOB_MANIFEST"]
    end

    subgraph HOST["Docker host paths"]
        H1["${DATA_ROOT}
        dataset root"]
        H1A["/raw
        csvs
        raw slc"]
        H1B["/processed
        scene tifs
        scene manifests"]
        H1C["/shapefiles
        scene feature folders"]
        H1D["/biophysical
        scene band rasters"]
        H1E["/patches
        patch outputs"]
        H1F["/stacks
        stack outputs"]
        H1G["/manifests
        stage markers"]
        H2["${JOB_DIR}
        manifest files"]
        H3["${SNAP_HOST_DIR}
        SNAP install"]
    end

    subgraph DC["Docker Compose"]
        C0["service: pipeline
        image: sar-server-pipeline"]
        C1["bind mount
        ${DATA_ROOT} -> /data"]
        C2["bind mount
        ${JOB_DIR} -> /job"]
        C3["read-only bind mount
        ${SNAP_HOST_DIR} -> /opt/snap"]
    end

    subgraph CTR["Single container run"]
        R0["python -m pipeline
        run_all --manifest ${JOB_MANIFEST:-/job/job.yaml}"]
        R1["slc_process"]
        R2["patch_extract"]
        R3["patch_stack"]
    end

    subgraph OUT["Host-visible outputs"]
        O1["Processed scenes"]
        O2["Patch dataset"]
        O3["Stack dataset"]
        O4["Run audit trail"]
    end

    W1 --> H1
    W2 --> H2
    W3 --> C0

    D1 --> R1
    D2 --> H3
    D3 --> C0
    D3 --> R0

    H1 --> H1A
    H1 --> H1B
    H1 --> H1C
    H1 --> H1D
    H1 --> H1E
    H1 --> H1F
    H1 --> H1G

    H1 --> C1
    H2 --> C2
    H3 --> C3

    C0 --> C1
    C0 --> C2
    C0 --> C3
    C0 --> R0

    C1 --> R1
    C1 --> R2
    C1 --> R3
    C2 --> R0
    C3 --> R1

    R0 --> R1
    R0 --> R2
    R0 --> R3

    R1 --> H1B
    R1 --> H1G
    R2 --> H1E
    R2 --> H1G
    R3 --> H1F
    R3 --> H1G

    H1B --> O1
    H1E --> O2
    H1F --> O3
    H1G --> O4
```
