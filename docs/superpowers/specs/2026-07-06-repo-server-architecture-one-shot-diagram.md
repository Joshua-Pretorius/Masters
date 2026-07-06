# Repository Server Architecture One-Shot Diagram

This is a standalone combined view of the repository architecture. It compresses the research workflow, server runtime, bind mounts, storage layout, and external dependencies into one Mermaid diagram.

Source companion document:

- `D:\Masters\docs\superpowers\specs\2026-07-06-repo-server-architecture-design.md`

## Combined Diagram

```mermaid
flowchart TB
    subgraph EXT["External Services and Credentials"]
        E1["Planet timing lookups
        local JSON and source metadata"]
        E2["Copernicus Data Space
        Sentinel-1 scene search"]
        E3["Earthdata / ASF
        Sentinel-1 SLC ZIP download"]
        E4["Copernicus Marine
        currents and waves"]
        E5["CDS / ERA5
        wind reanalysis"]
        E6["Runtime credentials
        EDL_USER / EDL_PASS
        Copernicus Marine credentials
        .cdsapirc"]
    end

    subgraph RW["Research Workstation and Repo Scripts"]
        R1["Observation curation
        Data_Creation observation sets"]
        R2["Scene matching
        build_meria_sa_s1_slc_matches.py
        build_meria_global_s1_slc_matches.py"]
        R3["SLC preprocessing
        process_meria_sa_slc_targets.py
        process_global_slc_targets.py
        process_sa_slc_targets.py"]
        R4["Drift and forcing workflows
        fetch_drift_forcing.py
        run_planet_to_sar_opendrift.py
        process_drift_slc.py"]
        R5["Digitisation and feature prep
        build_meria_digitising_shapefiles.py
        build_meria_digitisation_tracker.py"]
        R6["Job preparation
        write job.yaml or job.json"]
    end

    subgraph HOST["Host Machine Layout"]
        H1["${DATA_ROOT}
        durable dataset root"]
        H1A["raw
        match CSVs
        points CSVs
        raw slc"]
        H1B["processed
        scene GeoTIFFs
        *_slc_manifest.json"]
        H1C["shapefiles
        scene feature folders"]
        H1D["biophysical
        scene band rasters
        uo vo swh"]
        H1E["patches
        image chips
        masks
        inventories"]
        H1F["stacks
        stack rasters
        channel json
        catalogs"]
        H1G["manifests
        run_id
        stage markers"]
        H2["${JOB_DIR}
        job manifest files
        setup notes"]
        H3["${SNAP_HOST_DIR}
        host SNAP install
        gpt binary"]
    end

    subgraph CTR["Docker Container: sar-server-pipeline"]
        C1["/data
        mounted dataset root"]
        C2["/job
        mounted job root"]
        C3["/opt/snap
        mounted read-only SNAP root"]
        C4["python -m pipeline
        run_all --manifest ${JOB_MANIFEST:-/job/job.yaml}"]

        subgraph STG["Manifest-Driven Stages"]
            S1["slc_process
            optional vendored SLC processor"]
            S2["patch_extract
            patch rasters
            masks
            sar_patch_inventory.csv
            sar_patch_library.csv"]
            S3["patch_stack
            SAR plus biophysical channel stack"]
        end
    end

    subgraph OUT["Final Consumable Outputs"]
        O1["Training-ready patch products"]
        O2["Training-ready stack products"]
        O3["Audit trail
        stage markers
        catalogs
        manifests"]
    end

    R1 --> R2
    R2 --> R3
    R2 --> R5
    R3 --> R6
    R4 --> R6
    R5 --> R6

    E1 --> R2
    E2 --> R2
    E3 --> R3
    E4 --> R4
    E5 --> R4
    E6 --> R3
    E6 --> R4
    E6 --> C4

    R2 --> H1A
    R3 --> H1B
    R4 --> H1D
    R5 --> H1C
    R6 --> H2

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

    C2 --> C4
    C3 --> S1
    C1 --> S1
    C1 --> S2
    C1 --> S3
    C4 --> S1
    C4 --> S2
    C4 --> S3

    S1 --> H1B
    S1 --> H1G
    S2 --> H1E
    S2 --> H1G
    S3 --> H1F
    S3 --> H1G

    H1E --> O1
    H1F --> O2
    H1G --> O3
```
