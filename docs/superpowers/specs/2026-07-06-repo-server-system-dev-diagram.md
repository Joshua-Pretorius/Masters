# Repository Server System Dev Diagram

This diagram is the simplified system-developer view of the server setup.

It focuses on:

- the workstation
- the host paths
- the Docker container
- the bind mounts
- the runtime dependencies
- the main data flow into and through the server

Related documents:

- `D:\Masters\docs\superpowers\specs\2026-07-06-repo-server-architecture-design.md`
- `D:\Masters\docs\superpowers\specs\2026-07-06-repo-server-architecture-one-shot-diagram.md`

## System Developer One-Shot View

```mermaid
flowchart LR
    subgraph WS["Your Workstation"]
        W1["Prep scripts
        scene matching
        shapefile prep
        biophysical prep"]
        W2["Write server job manifest
        job.yaml or job.json"]
    end

    subgraph DEP["External dependencies"]
        D1["Earthdata / ASF
        Sentinel-1 download"]
        D2["Copernicus Marine / CDS
        currents, waves, wind"]
        D3["Credentials
        EDL_USER / EDL_PASS
        Copernicus Marine creds
        .cdsapirc"]
        D4["Host SNAP install
        gpt binary"]
    end

    subgraph HOST["Host machine paths"]
        H1["${DATA_ROOT}"]
        H1A["raw
        match CSVs
        points CSVs
        raw slc"]
        H1B["processed
        scene tifs
        *_slc_manifest.json"]
        H1C["shapefiles
        scene feature files"]
        H1D["biophysical
        scene band rasters"]
        H1E["patches
        images masks inventory"]
        H1F["stacks
        stack tifs channels catalog"]
        H1G["manifests
        stage markers"]
        H2["${JOB_DIR}
        job manifest files"]
        H3["${SNAP_HOST_DIR}
        mounted SNAP folder"]
    end

    subgraph CTR["Docker container: sar-server-pipeline"]
        C1["/data"]
        C2["/job"]
        C3["/opt/snap"]
        C4["python -m pipeline
        run_all --manifest ${JOB_MANIFEST:-/job/job.yaml}"]
        S1["slc_process"]
        S2["patch_extract"]
        S3["patch_stack"]
    end

    subgraph OUT["Server outputs"]
        O1["Processed scenes"]
        O2["Patch dataset"]
        O3["Stack dataset"]
        O4["Run audit trail"]
    end

    W1 --> H1A
    W1 --> H1B
    W1 --> H1C
    W1 --> H1D
    W2 --> H2

    D1 --> W1
    D2 --> W1
    D3 --> W1
    D3 --> C4
    D4 --> H3

    H1 --> H1A
    H1 --> H1B
    H1 --> H1C
    H1 --> H1D
    H1 --> H1E
    H1 --> H1F
    H1 --> H1G

    H1 -->|bind mount| C1
    H2 -->|bind mount| C2
    H3 -->|read-only bind mount| C3

    C2 -->|reads manifest| C4
    C3 -->|SNAP GPT| S1
    C1 -->|reads and writes data| S1
    C1 -->|reads shapefiles and scenes| S2
    C1 -->|reads patches and biophysical rasters| S3

    C4 --> S1
    C4 --> S2
    C4 --> S3

    S1 --> H1B
    S1 --> H1G
    S2 --> H1E
    S2 --> H1G
    S3 --> H1F
    S3 --> H1G

    H1B --> O1
    H1E --> O2
    H1F --> O3
    H1G --> O4
```
