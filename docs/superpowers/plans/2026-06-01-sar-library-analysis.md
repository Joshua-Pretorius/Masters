# SAR Library Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a graphics and feature-ranking analysis pack from the current SAR patch library, with descriptive plastic visuals across valid rows and Ghana-only class-separation outputs.

**Architecture:** Add a standalone analysis script in `D:\Masters\Data_Creation` that reads the existing patch library CSVs with the standard library, filters valid rows, generates PNG graphics with `matplotlib`, renders montages from existing patch GeoTIFFs, computes simple numeric separability rankings with `numpy`, and writes all outputs into `D:\Masters\Data_Creation\Library\Analysis`. Keep the analysis logic in focused helpers so tests can validate filtering, ranking, and output creation without depending on the real large dataset.

**Tech Stack:** Python, `unittest`, `csv`, `numpy`, `matplotlib`, `PIL`, `rasterio`

---

### Task 1: Add Red Tests For CSV Loading And Row Filtering

**Files:**
- Create: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`

- [ ] **Step 1: Write the failing tests**

```python
class LibraryFilteringTests(unittest.TestCase):
    def test_load_library_rows_reads_csv_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "library.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "scene_id,normalized_class_label,extraction_status,vv_db_mean,vh_db_mean,image_path",
                        "before_20181030T181758,plastic,ok,1.5,0.5,D:/patch1.tif",
                        "before_20181030T181758,ship,ok,2.0,0.7,D:/patch2.tif",
                    ]
                ),
                encoding="utf-8",
            )

            rows = MODULE.load_library_rows(csv_path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["normalized_class_label"], "plastic")

    def test_filter_valid_plastic_rows_keeps_only_ok_rows_with_numeric_features(self) -> None:
        rows = [
            {"normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "1.2", "vh_db_mean": "0.3"},
            {"normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "nan", "vh_db_mean": "0.4"},
            {"normalized_class_label": "ship", "extraction_status": "ok", "vv_db_mean": "1.4", "vh_db_mean": "0.5"},
        ]

        filtered = MODULE.filter_valid_plastic_rows(rows, ["vv_db_mean", "vh_db_mean"])

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["normalized_class_label"], "plastic")

    def test_filter_valid_ghana_rows_keeps_expected_classes_only(self) -> None:
        rows = [
            {"scene_id": "before_20181030T181758", "normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "1.0"},
            {"scene_id": "before_20181030T181758", "normalized_class_label": "ship", "extraction_status": "ok", "vv_db_mean": "2.0"},
            {"scene_id": "before_20181012T054431", "normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "3.0"},
        ]

        filtered = MODULE.filter_valid_ghana_rows(rows, ["vv_db_mean"])

        self.assertEqual(len(filtered), 2)
        self.assertEqual({row["normalized_class_label"] for row in filtered}, {"plastic", "ship"})
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.LibraryFilteringTests -v
```

Expected: `FAIL` because `build_sar_library_analysis.py` and the filtering helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def load_library_rows(csv_path: Path) -> list[dict[str, str]]:
    ...


def filter_valid_plastic_rows(rows: Sequence[Mapping[str, str]], required_features: Sequence[str]) -> list[dict[str, str]]:
    ...


def filter_valid_ghana_rows(rows: Sequence[Mapping[str, str]], required_features: Sequence[str]) -> list[dict[str, str]]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.LibraryFilteringTests -v
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py D:\Masters\Data_Creation\build_sar_library_analysis.py
git commit -m "feat: add SAR library analysis row filtering"
```

### Task 2: Add Red Tests For Feature Ranking

**Files:**
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`
- Modify: `D:\Masters\Data_Creation\build_sar_library_analysis.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`

- [ ] **Step 1: Write the failing tests**

```python
class FeatureRankingTests(unittest.TestCase):
    def test_build_plastic_vs_other_labels_marks_plastic_as_one(self) -> None:
        rows = [
            {"normalized_class_label": "plastic"},
            {"normalized_class_label": "ship"},
            {"normalized_class_label": "wake"},
        ]

        labels = MODULE.build_plastic_vs_other_labels(rows)

        np.testing.assert_array_equal(labels, np.array([1, 0, 0], dtype="int32"))

    def test_compute_effect_size_ranking_orders_more_separable_feature_first(self) -> None:
        matrix = np.array(
            [
                [10.0, 1.0],
                [11.0, 1.1],
                [2.0, 1.2],
                [3.0, 1.1],
            ],
            dtype="float32",
        )
        labels = np.array([1, 1, 0, 0], dtype="int32")
        feature_names = ["strong_feature", "weak_feature"]

        ranking = MODULE.compute_effect_size_ranking(matrix, labels, feature_names)

        self.assertEqual(ranking[0]["feature_name"], "strong_feature")
        self.assertGreater(ranking[0]["effect_size"], ranking[1]["effect_size"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.FeatureRankingTests -v
```

Expected: `FAIL` because ranking helpers are missing.

- [ ] **Step 3: Write minimal implementation**

```python
def build_plastic_vs_other_labels(rows: Sequence[Mapping[str, str]]) -> np.ndarray:
    ...


def compute_effect_size_ranking(matrix: np.ndarray, labels: np.ndarray, feature_names: Sequence[str]) -> list[dict[str, float | str]]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.FeatureRankingTests -v
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py D:\Masters\Data_Creation\build_sar_library_analysis.py
git commit -m "feat: add SAR library feature ranking"
```

### Task 3: Add Red Tests For Plot And Table Output Generation

**Files:**
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`
- Modify: `D:\Masters\Data_Creation\build_sar_library_analysis.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`

- [ ] **Step 1: Write the failing tests**

```python
class OutputGenerationTests(unittest.TestCase):
    def test_write_feature_importance_csv_creates_expected_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "importance.csv"
            ranking = [
                {"feature_name": "vv_db_mean", "effect_size": 1.5},
                {"feature_name": "vh_db_mean", "effect_size": 0.5},
            ]

            MODULE.write_feature_importance_csv(out_path, ranking)

            text = out_path.read_text(encoding="utf-8")

        self.assertIn("feature_name,effect_size", text)
        self.assertIn("vv_db_mean", text)

    def test_plot_class_counts_creates_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "class_counts.png"
            rows = [
                {"normalized_class_label": "plastic"},
                {"normalized_class_label": "plastic"},
                {"normalized_class_label": "ship"},
            ]

            MODULE.plot_class_counts(rows, out_path)

            self.assertTrue(out_path.exists())
            self.assertGreater(out_path.stat().st_size, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.OutputGenerationTests -v
```

Expected: `FAIL` because file-writing and plotting helpers are missing.

- [ ] **Step 3: Write minimal implementation**

```python
def write_feature_importance_csv(out_path: Path, ranking: Sequence[Mapping[str, object]]) -> None:
    ...


def plot_class_counts(rows: Sequence[Mapping[str, str]], out_path: Path) -> None:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.OutputGenerationTests -v
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py D:\Masters\Data_Creation\build_sar_library_analysis.py
git commit -m "feat: add SAR library analysis output writers"
```

### Task 4: Add Red Tests For End-To-End Analysis Pack Generation

**Files:**
- Modify: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`
- Modify: `D:\Masters\Data_Creation\build_sar_library_analysis.py`
- Test: `D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py`

- [ ] **Step 1: Write the failing test**

```python
class EndToEndAnalysisTests(unittest.TestCase):
    def test_run_analysis_writes_key_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            library_csv = tmp / "sar_patch_library.csv"
            inventory_csv = tmp / "sar_patch_inventory.csv"
            patches_root = tmp / "Patches"
            analysis_root = tmp / "Analysis"
            create_analysis_fixture(library_csv, inventory_csv, patches_root)

            MODULE.run_analysis(
                library_csv=library_csv,
                inventory_csv=inventory_csv,
                patches_root=patches_root,
                analysis_root=analysis_root,
            )

        self.assertTrue((analysis_root / "ghana_class_counts.png").exists())
        self.assertTrue((analysis_root / "ghana_plastic_vs_other_feature_importance.csv").exists())
        self.assertTrue((analysis_root / "analysis_run_note.md").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.EndToEndAnalysisTests -v
```

Expected: `FAIL` because the end-to-end analysis orchestration does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def run_analysis(library_csv: Path, inventory_csv: Path, patches_root: Path, analysis_root: Path) -> None:
    ...


def parse_args() -> argparse.Namespace:
    ...


def main() -> None:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest Data_Creation.tests.test_build_sar_library_analysis.EndToEndAnalysisTests -v
```

Expected: `PASS`

- [ ] **Step 5: Run full analysis test file**

Run:
```powershell
$env:PROJ_LIB='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\proj_data'; $env:GDAL_DATA='C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\Lib\site-packages\rasterio\gdal_data'; & 'C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311\python.exe' -m unittest D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py -v
```

Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add D:\Masters\Data_Creation\tests\test_build_sar_library_analysis.py D:\Masters\Data_Creation\build_sar_library_analysis.py
git commit -m "feat: add SAR library graphics and feature analysis"
```
