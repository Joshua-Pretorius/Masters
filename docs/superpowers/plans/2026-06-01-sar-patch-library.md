# SAR Patch Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new extraction stage that scans processed MERIA SLC scene directories, creates centroid-centered `256 x 256` SAR image patches and binary masks, and writes a per-geometry SAR feature library CSV.

**Architecture:** Add a standalone script in `D:\Masters\Data_Creation` that reuses the existing processed-scene folder conventions and manifest outputs from the MERIA SLC pipeline. Keep extraction, raster lookup, vector label normalization, mask generation, and CSV writing in focused helpers so the new stage can be tested without SNAP or network access.

**Tech Stack:** Python, `unittest`, `tempfile`, `rasterio`, `numpy`, shapefile DBF parsing for metadata discovery, existing `Data_Creation` test conventions

---

### Task 1: Add Red Tests For Discovery And Label Rules

**Files:**
- Create: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`

- [ ] **Step 1: Write the failing tests**

```python
class DiscoveryAndLabelTests(unittest.TestCase):
    def test_discover_digitized_layers_finds_standard_and_case_variant_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            standard = root / "processed_slc" / "Scene_A" / "digitised_patches" / "scene_a_digitised_patches.shp"
            case_variant = root / "processed_slc" / "Scene_B" / "Digitised_patches" / "scene_b_digitised_patches.shp"
            standard.parent.mkdir(parents=True)
            case_variant.parent.mkdir(parents=True)
            for shp_path in (standard, case_variant):
                shp_path.write_bytes(b"")

            results = MODULE.discover_digitized_layers((root / "processed_slc",))

        self.assertEqual([item.shapefile_path for item in results], [standard, case_variant])

    def test_resolve_feature_class_defaults_standard_digitised_patches_to_plastic(self) -> None:
        source = MODULE.LayerSource(
            dataset="meria_sa",
            scene_id="MERIA_SA_001_Durban_after_20190425T031055",
            scene_dir=Path("D:/scene"),
            shapefile_path=Path("D:/scene/digitised_patches/sample_digitised_patches.shp"),
            layer_kind="digitised_patches",
        )

        raw_label, normalized = MODULE.resolve_feature_class(source, {"patch_id": "patch-01"})

        self.assertIsNone(raw_label)
        self.assertEqual(normalized, "plastic")

    def test_resolve_feature_class_reads_and_normalizes_explicit_class_field(self) -> None:
        source = MODULE.LayerSource(
            dataset="meria_global",
            scene_id="91ea9edc-67b4-4211-8532-35deec4a3148_Ghana_before_20181030T181758",
            scene_dir=Path("D:/scene"),
            shapefile_path=Path("D:/scene/digitised_patches/sample_digitised_other_features.shp"),
            layer_kind="digitised_other_features",
        )

        raw_label, normalized = MODULE.resolve_feature_class(source, {"Class": " Calm Water "})

        self.assertEqual(raw_label, " Calm Water ")
        self.assertEqual(normalized, "calm_water")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.DiscoveryAndLabelTests -v"
```

Expected: `FAIL` because `build_sar_patch_library.py` and the tested symbols do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class LayerSource:
    dataset: str
    scene_id: str
    scene_dir: Path
    shapefile_path: Path
    layer_kind: str


def discover_digitized_layers(processed_roots: Iterable[Path]) -> list[LayerSource]:
    ...


def resolve_feature_class(source: LayerSource, properties: Mapping[str, object]) -> tuple[str | None, str]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.DiscoveryAndLabelTests -v"
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py D:\Masters\Data_Creation\build_sar_patch_library.py
git commit -m "feat: add patch layer discovery and label normalization"
```

### Task 2: Add Red Tests For Raster Lookup And Patch Window Construction

**Files:**
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`
- Modify: `D:\Masters\Data_Creation\build_sar_patch_library.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`

- [ ] **Step 1: Write the failing tests**

```python
class RasterLookupAndWindowTests(unittest.TestCase):
    def test_build_scene_raster_map_reads_existing_outputs_and_derives_vh_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_dir = Path(tmp_dir)
            manifest_path = scene_dir / "scene_slc_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "scene_id": "Scene_001",
                        "outputs": {
                            "vv": str(scene_dir / "scene_slc_native_vv.tif"),
                            "vh": str(scene_dir / "scene_slc_native_vh.tif"),
                            "vv_refined_lee_db": str(scene_dir / "scene_slc_utm_vv_refined_lee_db.tif"),
                            "vv_glcm_mean": str(scene_dir / "scene_slc_native_vv_glcm_mean.tif"),
                            "vv_glcm_std": str(scene_dir / "scene_slc_native_vv_glcm_std.tif"),
                            "vv_glcm_entropy": str(scene_dir / "scene_slc_native_vv_glcm_entropy.tif"),
                            "decomp_entropy": str(scene_dir / "scene_slc_native_decomp_entropy.tif"),
                            "decomp_anisotropy": str(scene_dir / "scene_slc_native_decomp_anisotropy.tif"),
                            "decomp_alpha": str(scene_dir / "scene_slc_native_decomp_alpha.tif"),
                        },
                    }
                ),
                encoding="utf-8",
            )

            raster_map = MODULE.build_scene_raster_map(manifest_path)

        self.assertEqual(raster_map["vv_db"].key, "vv_refined_lee_db")
        self.assertEqual(raster_map["vh_db"].key, "vh")
        self.assertEqual(raster_map["vv_glcm_mean"].key, "vv_glcm_mean")

    def test_centroid_window_is_fixed_256_by_256_and_marks_edge_overlap(self) -> None:
        transform = from_origin(0.0, 512.0, 10.0, 10.0)
        profile = {"width": 512, "height": 512, "transform": transform}

        window = MODULE.centroid_patch_window(profile, centroid_x=20.0, centroid_y=500.0, patch_size=256)

        self.assertEqual(window.width, 256)
        self.assertEqual(window.height, 256)
        self.assertTrue(window.touches_edge)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.RasterLookupAndWindowTests -v"
```

Expected: `FAIL` because raster-map and centroid-window helpers are missing.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class RasterBandSpec:
    name: str
    key: str
    path: Path
    mode: str


@dataclass(frozen=True)
class PatchWindow:
    row_off: int
    col_off: int
    width: int
    height: int
    touches_edge: bool


def build_scene_raster_map(manifest_path: Path) -> dict[str, RasterBandSpec]:
    ...


def centroid_patch_window(profile: Mapping[str, object], centroid_x: float, centroid_y: float, patch_size: int) -> PatchWindow:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.RasterLookupAndWindowTests -v"
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py D:\Masters\Data_Creation\build_sar_patch_library.py
git commit -m "feat: add raster lookup and patch window helpers"
```

### Task 3: Add Red Tests For Patch Extraction, Mask Rasterization, And Statistics

**Files:**
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`
- Modify: `D:\Masters\Data_Creation\build_sar_patch_library.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`

- [ ] **Step 1: Write the failing tests**

```python
class PatchExtractionTests(unittest.TestCase):
    def test_extract_patch_stack_pads_beyond_raster_bounds_with_nan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            raster_path = tmp / "vv_db.tif"
            write_raster(raster_path, np.arange(16, dtype="float32").reshape(4, 4), pixel_size=10.0)
            band = MODULE.RasterBandSpec(name="vv_db", key="vv_refined_lee_db", path=raster_path, mode="identity")
            profile = MODULE.load_reference_profile(raster_path)
            window = MODULE.PatchWindow(row_off=-1, col_off=-1, width=4, height=4, touches_edge=True)

            stack, out_profile = MODULE.extract_patch_stack({"vv_db": band}, profile, window)

        self.assertEqual(stack.shape, (1, 4, 4))
        self.assertTrue(np.isnan(stack[0, 0, 0]))
        self.assertEqual(out_profile["width"], 4)

    def test_rasterize_geometry_mask_aligns_with_patch_grid(self) -> None:
        profile = MODULE.patch_profile(from_origin(0.0, 40.0, 10.0, 10.0), width=4, height=4, count=1)
        geometry = {
            "type": "Polygon",
            "coordinates": [[(10.0, 30.0), (30.0, 30.0), (30.0, 10.0), (10.0, 10.0), (10.0, 30.0)]],
        }

        mask = MODULE.rasterize_feature_mask(geometry, profile)

        self.assertEqual(mask.shape, (4, 4))
        self.assertEqual(int(mask.sum()), 4)

    def test_compute_band_statistics_uses_labeled_pixels_only(self) -> None:
        stack = np.array([[[1.0, 2.0], [3.0, np.nan]]], dtype="float32")
        mask = np.array([[1, 0], [1, 0]], dtype="uint8")

        stats = MODULE.compute_band_statistics(stack, mask, ["vv_db"])

        self.assertEqual(stats["vv_db_valid_pixel_count"], 2)
        self.assertAlmostEqual(stats["vv_db_mean"], 2.0)
        self.assertAlmostEqual(stats["vv_db_min"], 1.0)
        self.assertAlmostEqual(stats["vv_db_max"], 3.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.PatchExtractionTests -v"
```

Expected: `FAIL` because patch extraction, mask rasterization, and statistics helpers are missing.

- [ ] **Step 3: Write minimal implementation**

```python
def load_reference_profile(raster_path: Path) -> dict[str, object]:
    ...


def patch_profile(transform: Affine, width: int, height: int, count: int) -> dict[str, object]:
    ...


def extract_patch_stack(raster_map: Mapping[str, RasterBandSpec], reference_profile: Mapping[str, object], window: PatchWindow) -> tuple[np.ndarray, dict[str, object]]:
    ...


def rasterize_feature_mask(geometry: Mapping[str, object], profile: Mapping[str, object]) -> np.ndarray:
    ...


def compute_band_statistics(stack: np.ndarray, mask: np.ndarray, band_names: Sequence[str]) -> dict[str, float | int]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.PatchExtractionTests -v"
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py D:\Masters\Data_Creation\build_sar_patch_library.py
git commit -m "feat: add patch extraction and summary statistics"
```

### Task 4: Add Red Tests For End-To-End Sample Writing And CSV Outputs

**Files:**
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`
- Modify: `D:\Masters\Data_Creation\build_sar_patch_library.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`

- [ ] **Step 1: Write the failing tests**

```python
class EndToEndExtractionTests(unittest.TestCase):
    def test_process_feature_writes_image_mask_and_library_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            patches_dir = tmp / "Patches"
            library_dir = tmp / "Library"
            scene_dir = tmp / "scene"
            manifest_path = scene_dir / "scene_slc_manifest.json"
            scene_dir.mkdir(parents=True)
            create_manifest_and_rasters(scene_dir, manifest_path)

            source = MODULE.LayerSource(
                dataset="meria_global",
                scene_id="Scene_001",
                scene_dir=scene_dir,
                shapefile_path=scene_dir / "digitised_patches" / "scene_digitised_patches.shp",
                layer_kind="digitised_patches",
            )
            feature = sample_feature_record()

            inventory_row, library_row = MODULE.process_feature(
                source=source,
                feature=feature,
                manifest_path=manifest_path,
                patches_root=patches_dir,
                library_root=library_dir,
                patch_size=256,
            )

        self.assertEqual(inventory_row["normalized_class_label"], "plastic")
        self.assertTrue(Path(inventory_row["image_path"]).exists())
        self.assertTrue(Path(inventory_row["mask_path"]).exists())
        self.assertIn("vv_db_mean", library_row)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.EndToEndExtractionTests -v"
```

Expected: `FAIL` because the orchestration and file writing path does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def process_feature(
    source: LayerSource,
    feature: Mapping[str, object],
    manifest_path: Path,
    patches_root: Path,
    library_root: Path,
    patch_size: int = 256,
) -> tuple[dict[str, object], dict[str, object]]:
    ...


def append_csv_row(csv_path: Path, fieldnames: Sequence[str], row: Mapping[str, object]) -> None:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.EndToEndExtractionTests -v"
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py D:\Masters\Data_Creation\build_sar_patch_library.py
git commit -m "feat: write SAR patch assets and library rows"
```

### Task 5: Add CLI Wiring And Full Verification

**Files:**
- Modify: `D:\Masters\Data_Creation\build_sar_patch_library.py`
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py`

- [ ] **Step 1: Write the failing test**

```python
class CommandLineTests(unittest.TestCase):
    def test_parse_args_uses_data_creation_patch_and_library_defaults(self) -> None:
        with mock.patch.object(sys, "argv", ["build_sar_patch_library.py"]):
            args = MODULE.parse_args()

        self.assertEqual(args.patch_size, 256)
        self.assertEqual(args.patches_root, MODULE.REPO_ROOT / "Data_Creation" / "Patches")
        self.assertEqual(args.library_root, MODULE.REPO_ROOT / "Data_Creation" / "Library")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_patch_library.CommandLineTests -v"
```

Expected: `FAIL` because the CLI defaults are not defined yet.

- [ ] **Step 3: Write minimal implementation**

```python
def parse_args() -> argparse.Namespace:
    ...


def main() -> None:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py -v"
```

Expected: `PASS`

- [ ] **Step 5: Run regression tests**

Run:
```powershell
& 'C:\windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Command "& 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest D:\Masters\Data_Creation\tests\test_process_meria_sa_slc_targets.py -v"
```

Expected: existing `process_meria_sa_slc_targets` tests remain green.

- [ ] **Step 6: Commit**

```bash
git add D:\Masters\Data_Creation\build_sar_patch_library.py D:\Masters\Data_Creation\tests\test_build_sar_patch_library.py
git commit -m "feat: add SAR patch library extraction CLI"
```
