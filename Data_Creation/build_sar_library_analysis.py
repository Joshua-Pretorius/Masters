#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import rasterio as rio


GHANA_SCENE_ID = "before_20181030T181758"
GHANA_CLASSES = {"plastic", "ship", "wake", "slick", "calm_water"}
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CREATION_ROOT = REPO_ROOT / "Data_Creation"
DEFAULT_LIBRARY_CSV = DATA_CREATION_ROOT / "Library" / "sar_patch_library.csv"
DEFAULT_INVENTORY_CSV = DATA_CREATION_ROOT / "Library" / "sar_patch_inventory.csv"
DEFAULT_PATCHES_ROOT = DATA_CREATION_ROOT / "Patches"
DEFAULT_ANALYSIS_ROOT = DATA_CREATION_ROOT / "Library" / "Analysis"
SUMMARY_FEATURES = [
    "vv_db_mean",
    "vh_db_mean",
    "vv_vh_ratio_db_mean",
    "vv_glcm_mean_mean",
    "vv_glcm_entropy_mean",
    "decomp_entropy_mean",
    "decomp_alpha_mean",
]


def load_library_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def is_valid_number(value: str | None) -> bool:
    if value is None or value == "":
        return False
    try:
        parsed = float(value)
    except ValueError:
        return False
    return math.isfinite(parsed)


def row_has_required_features(row: Mapping[str, str], required_features: Sequence[str]) -> bool:
    return all(is_valid_number(row.get(feature)) for feature in required_features)


def filter_valid_plastic_rows(rows: Sequence[Mapping[str, str]], required_features: Sequence[str]) -> list[dict[str, str]]:
    return [
        dict(row)
        for row in rows
        if row.get("normalized_class_label") == "plastic"
        and row.get("extraction_status") == "ok"
        and row_has_required_features(row, required_features)
    ]


def filter_valid_ghana_rows(rows: Sequence[Mapping[str, str]], required_features: Sequence[str]) -> list[dict[str, str]]:
    return [
        dict(row)
        for row in rows
        if row.get("scene_id") == GHANA_SCENE_ID
        and row.get("normalized_class_label") in GHANA_CLASSES
        and row.get("extraction_status") == "ok"
        and row_has_required_features(row, required_features)
    ]


def build_plastic_vs_other_labels(rows: Sequence[Mapping[str, str]]) -> np.ndarray:
    return np.array(
        [1 if row.get("normalized_class_label") == "plastic" else 0 for row in rows],
        dtype="int32",
    )


def compute_effect_size_ranking(
    matrix: np.ndarray,
    labels: np.ndarray,
    feature_names: Sequence[str],
) -> list[dict[str, float | str]]:
    rankings: list[dict[str, float | str]] = []
    positive = labels == 1
    negative = labels == 0
    for index, feature_name in enumerate(feature_names):
        pos_values = matrix[positive, index]
        neg_values = matrix[negative, index]
        pos_mean = float(np.mean(pos_values))
        neg_mean = float(np.mean(neg_values))
        pos_std = float(np.std(pos_values))
        neg_std = float(np.std(neg_values))
        pooled = math.sqrt((pos_std ** 2 + neg_std ** 2) / 2.0) if (pos_std or neg_std) else 0.0
        effect_size = abs(pos_mean - neg_mean) / pooled if pooled else 0.0
        rankings.append(
            {
                "feature_name": feature_name,
                "effect_size": effect_size,
            }
        )
    rankings.sort(key=lambda item: float(item["effect_size"]), reverse=True)
    return rankings


def draw_bar_chart(labels: Sequence[str], values: Sequence[int], title: str, out_path: Path) -> None:
    width = 900
    height = 600
    margin_left = 100
    margin_right = 40
    margin_top = 80
    margin_bottom = 140
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    title_font = ImageFont.load_default()
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom
    max_value = max(values) if values else 1
    draw.line((margin_left, margin_top, margin_left, margin_top + chart_height), fill="black", width=2)
    draw.line((margin_left, margin_top + chart_height, margin_left + chart_width, margin_top + chart_height), fill="black", width=2)
    draw.text((margin_left, 20), title, fill="black", font=title_font)
    if values:
        slot_width = chart_width / max(len(values), 1)
        bar_width = max(20, int(slot_width * 0.6))
        for index, (label, value) in enumerate(zip(labels, values)):
            x_center = margin_left + int((index + 0.5) * slot_width)
            bar_height = int((value / max_value) * (chart_height - 20)) if max_value else 0
            x0 = x_center - bar_width // 2
            y0 = margin_top + chart_height - bar_height
            x1 = x_center + bar_width // 2
            y1 = margin_top + chart_height
            draw.rectangle((x0, y0, x1, y1), fill="#2a6f97", outline="black")
            draw.text((x_center - 8, y0 - 18), str(value), fill="black", font=font)
            draw.text((x_center - (len(label) * 3), margin_top + chart_height + 10), label, fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def write_feature_importance_csv(out_path: Path, ranking: Sequence[Mapping[str, object]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["feature_name", "effect_size"])
        writer.writeheader()
        for row in ranking:
            writer.writerow(
                {
                    "feature_name": row.get("feature_name"),
                    "effect_size": row.get("effect_size"),
                }
            )


def plot_class_counts(rows: Sequence[Mapping[str, str]], out_path: Path) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        label = row.get("normalized_class_label", "")
        counts[label] = counts.get(label, 0) + 1
    labels = list(counts.keys())
    values = [counts[label] for label in labels]
    draw_bar_chart(labels, values, "Class Counts", out_path)


def rows_to_feature_matrix(rows: Sequence[Mapping[str, str]], feature_names: Sequence[str]) -> np.ndarray:
    return np.array(
        [[float(row[feature_name]) for feature_name in feature_names] for row in rows],
        dtype="float32",
    )


def write_run_note(out_path: Path, lines: Iterable[str]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_placeholder_image(out_path: Path, title: str, message: str) -> None:
    img = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((40, 40), title, fill="black", font=font)
    draw.text((40, 100), message, fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def feature_ranges(rows: Sequence[Mapping[str, str]], feature_names: Sequence[str]) -> dict[str, tuple[float, float]]:
    ranges: dict[str, tuple[float, float]] = {}
    for feature_name in feature_names:
        values = np.array([float(row[feature_name]) for row in rows], dtype="float32")
        ranges[feature_name] = (float(np.min(values)), float(np.max(values)))
    return ranges


def draw_histogram_grid(rows: Sequence[Mapping[str, str]], feature_names: Sequence[str], title: str, out_path: Path) -> None:
    if not rows:
        create_placeholder_image(out_path, title, "No valid rows available")
        return
    width = 1200
    height = 800
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((30, 20), title, fill="black", font=font)
    cols = 3
    rows_n = max(1, math.ceil(len(feature_names) / cols))
    ranges = feature_ranges(rows, feature_names)
    panel_w = (width - 80) // cols
    panel_h = (height - 80) // rows_n
    for idx, feature_name in enumerate(feature_names):
        row_idx = idx // cols
        col_idx = idx % cols
        x0 = 30 + col_idx * panel_w
        y0 = 60 + row_idx * panel_h
        x1 = x0 + panel_w - 20
        y1 = y0 + panel_h - 30
        draw.rectangle((x0, y0, x1, y1), outline="black", width=1)
        values = np.array([float(row[feature_name]) for row in rows], dtype="float32")
        hist, _ = np.histogram(values, bins=min(8, max(3, len(values))))
        max_bin = int(hist.max()) if hist.size else 1
        inner_w = x1 - x0 - 30
        inner_h = y1 - y0 - 40
        slot_w = inner_w / max(len(hist), 1)
        for j, count in enumerate(hist):
            bar_h = int((count / max_bin) * inner_h) if max_bin else 0
            bx0 = x0 + 20 + int(j * slot_w)
            bx1 = x0 + 20 + int((j + 1) * slot_w) - 4
            by0 = y1 - 20 - bar_h
            by1 = y1 - 20
            draw.rectangle((bx0, by0, bx1, by1), fill="#2a6f97", outline="black")
        lo, hi = ranges[feature_name]
        draw.text((x0 + 10, y0 + 8), feature_name, fill="black", font=font)
        draw.text((x0 + 10, y1 - 16), f"{lo:.2f} to {hi:.2f}", fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def percentile(values: np.ndarray, p: float) -> float:
    return float(np.percentile(values, p))


def draw_boxplot_grid(rows: Sequence[Mapping[str, str]], feature_names: Sequence[str], title: str, out_path: Path) -> None:
    if not rows:
        create_placeholder_image(out_path, title, "No valid rows available")
        return
    width = 1200
    height = 800
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((30, 20), title, fill="black", font=font)
    cols = 3
    rows_n = max(1, math.ceil(len(feature_names) / cols))
    ranges = feature_ranges(rows, feature_names)
    panel_w = (width - 80) // cols
    panel_h = (height - 80) // rows_n
    for idx, feature_name in enumerate(feature_names):
        row_idx = idx // cols
        col_idx = idx % cols
        x0 = 30 + col_idx * panel_w
        y0 = 60 + row_idx * panel_h
        x1 = x0 + panel_w - 20
        y1 = y0 + panel_h - 30
        draw.rectangle((x0, y0, x1, y1), outline="black", width=1)
        values = np.array([float(row[feature_name]) for row in rows], dtype="float32")
        lo, hi = ranges[feature_name]
        if hi == lo:
            hi = lo + 1.0
        q1 = percentile(values, 25)
        med = percentile(values, 50)
        q3 = percentile(values, 75)
        mn = float(np.min(values))
        mx = float(np.max(values))

        def map_y(value: float) -> int:
            frac = (value - lo) / (hi - lo)
            return y1 - 25 - int(frac * (y1 - y0 - 50))

        center = (x0 + x1) // 2
        box_half = 40
        draw.line((center, map_y(mn), center, map_y(mx)), fill="black", width=2)
        draw.rectangle((center - box_half, map_y(q3), center + box_half, map_y(q1)), outline="#2a6f97", width=2)
        draw.line((center - box_half, map_y(med), center + box_half, map_y(med)), fill="#2a6f97", width=2)
        draw.text((x0 + 10, y0 + 8), feature_name, fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def normalize_patch_for_display(image_path: Path) -> Image.Image:
    with rio.open(image_path) as src:
        arr = src.read(1).astype("float32")
    finite = np.isfinite(arr)
    if not finite.any():
        arr = np.zeros_like(arr, dtype="float32")
    else:
        vals = arr[finite]
        lo = float(np.percentile(vals, 2))
        hi = float(np.percentile(vals, 98))
        if hi <= lo:
            hi = lo + 1.0
        arr = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
        arr[~finite] = 0.0
    img = Image.fromarray((arr * 255).astype("uint8"), mode="L")
    return img.convert("RGB")


def write_montage(rows: Sequence[Mapping[str, str]], out_path: Path, examples_csv: Path, limit: int = 12) -> None:
    selected = list(rows[:limit])
    if not selected:
        create_placeholder_image(out_path, "Plastic Patch Montage", "No valid plastic patches available")
        write_feature_importance_csv(examples_csv, [])
        return
    thumb_size = 160
    cols = 4
    rows_n = max(1, math.ceil(len(selected) / cols))
    canvas = Image.new("RGB", (cols * thumb_size + 40, rows_n * (thumb_size + 30) + 40), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((20, 10), "Plastic Patch Montage", fill="black", font=font)
    examples_csv.parent.mkdir(parents=True, exist_ok=True)
    with examples_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "image_path", "scene_id", "normalized_class_label"])
        writer.writeheader()
        for idx, row in enumerate(selected):
            patch = normalize_patch_for_display(Path(row["image_path"])).resize((thumb_size, thumb_size))
            x = 20 + (idx % cols) * thumb_size
            y = 40 + (idx // cols) * (thumb_size + 30)
            canvas.paste(patch, (x, y))
            draw.text((x, y + thumb_size + 4), row.get("sample_id", ""), fill="black", font=font)
            writer.writerow(
                {
                    "sample_id": row.get("sample_id", ""),
                    "image_path": row.get("image_path", ""),
                    "scene_id": row.get("scene_id", ""),
                    "normalized_class_label": row.get("normalized_class_label", ""),
                }
            )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def plot_feature_importance(ranking: Sequence[Mapping[str, object]], out_path: Path) -> None:
    top = list(ranking[:10])
    labels = [str(item["feature_name"]) for item in top]
    values = [float(item["effect_size"]) for item in top]
    draw_bar_chart(labels, [max(1, int(v * 100)) for v in values], "Plastic vs Other Feature Importance", out_path)


def plot_pairplot_subset(rows: Sequence[Mapping[str, str]], feature_names: Sequence[str], out_path: Path) -> None:
    if len(rows) < 2:
        create_placeholder_image(out_path, "Ghana Feature Pairplot", "Insufficient rows")
        return
    features = list(feature_names[:3])
    colors = {
        "plastic": "#2a9d8f",
        "ship": "#e76f51",
        "wake": "#264653",
        "slick": "#f4a261",
        "calm_water": "#457b9d",
    }
    width = 900
    height = 900
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((20, 10), "Ghana Feature Pairplot Subset", fill="black", font=font)
    panel = 250
    margins = 60
    ranges = feature_ranges(rows, features)
    for i, y_feature in enumerate(features):
        for j, x_feature in enumerate(features):
            x0 = margins + j * panel
            y0 = margins + i * panel
            x1 = x0 + panel - 20
            y1 = y0 + panel - 20
            draw.rectangle((x0, y0, x1, y1), outline="black")
            x_lo, x_hi = ranges[x_feature]
            y_lo, y_hi = ranges[y_feature]
            if x_hi == x_lo:
                x_hi = x_lo + 1.0
            if y_hi == y_lo:
                y_hi = y_lo + 1.0
            for row in rows:
                xv = float(row[x_feature])
                yv = float(row[y_feature])
                px = x0 + 10 + int(((xv - x_lo) / (x_hi - x_lo)) * (x1 - x0 - 20))
                py = y1 - 10 - int(((yv - y_lo) / (y_hi - y_lo)) * (y1 - y0 - 20))
                draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=colors.get(row["normalized_class_label"], "black"))
            draw.text((x0 + 4, y0 + 4), f"{x_feature} / {y_feature}", fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def plot_plastic_vs_other_violin(rows: Sequence[Mapping[str, str]], feature_names: Sequence[str], out_path: Path) -> None:
    if not rows:
        create_placeholder_image(out_path, "Plastic vs Other", "No Ghana rows available")
        return
    groups = {"plastic": [], "other": []}
    for row in rows:
        key = "plastic" if row["normalized_class_label"] == "plastic" else "other"
        groups[key].append(row)
    width = 1200
    height = 800
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((20, 10), "Ghana Plastic vs Other", fill="black", font=font)
    cols = 3
    rows_n = max(1, math.ceil(len(feature_names) / cols))
    panel_w = (width - 80) // cols
    panel_h = (height - 80) // rows_n
    all_ranges = feature_ranges(rows, feature_names)
    for idx, feature_name in enumerate(feature_names):
        row_idx = idx // cols
        col_idx = idx % cols
        x0 = 30 + col_idx * panel_w
        y0 = 60 + row_idx * panel_h
        x1 = x0 + panel_w - 20
        y1 = y0 + panel_h - 30
        draw.rectangle((x0, y0, x1, y1), outline="black")
        lo, hi = all_ranges[feature_name]
        if hi == lo:
            hi = lo + 1.0
        for group_idx, group_name in enumerate(("plastic", "other")):
            values = np.array([float(row[feature_name]) for row in groups[group_name]], dtype="float32")
            if values.size == 0:
                continue
            center = x0 + 60 + group_idx * 120
            for p in range(10, 91, 10):
                value = float(np.percentile(values, p))
                frac = (value - lo) / (hi - lo)
                y = y1 - 20 - int(frac * (y1 - y0 - 40))
                width_px = 4 + int(min(p, 100 - p) * 0.6)
                draw.line((center - width_px, y, center + width_px, y), fill="#2a6f97", width=2)
            draw.text((center - 20, y1 - 12), group_name, fill="black", font=font)
        draw.text((x0 + 10, y0 + 8), feature_name, fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def write_rows_csv(out_path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def run_analysis(library_csv: Path, inventory_csv: Path, patches_root: Path, analysis_root: Path) -> None:
    del inventory_csv, patches_root
    analysis_root.mkdir(parents=True, exist_ok=True)
    rows = load_library_rows(library_csv)
    plastic_rows = filter_valid_plastic_rows(rows, SUMMARY_FEATURES)
    ghana_rows = filter_valid_ghana_rows(rows, SUMMARY_FEATURES)

    draw_histogram_grid(plastic_rows, SUMMARY_FEATURES, "Plastic Feature Distributions", analysis_root / "plastic_feature_distributions.png")
    draw_boxplot_grid(plastic_rows, SUMMARY_FEATURES, "Plastic Feature Boxplots", analysis_root / "plastic_feature_boxplots.png")
    write_montage(
        plastic_rows,
        analysis_root / "plastic_patch_montage.png",
        analysis_root / "plastic_patch_montage_examples.csv",
    )

    plot_class_counts(ghana_rows, analysis_root / "ghana_class_counts.png")
    draw_boxplot_grid(ghana_rows, SUMMARY_FEATURES, "Ghana Feature Boxplots By Class", analysis_root / "ghana_feature_boxplots_by_class.png")
    plot_pairplot_subset(ghana_rows, SUMMARY_FEATURES[:3], analysis_root / "ghana_feature_pairplot_subset.png")
    plot_plastic_vs_other_violin(ghana_rows, SUMMARY_FEATURES[:6], analysis_root / "ghana_plastic_vs_other_violinplots.png")

    if ghana_rows:
        matrix = rows_to_feature_matrix(ghana_rows, SUMMARY_FEATURES)
        labels = build_plastic_vs_other_labels(ghana_rows)
        ranking = compute_effect_size_ranking(matrix, labels, SUMMARY_FEATURES)
    else:
        ranking = []
    write_feature_importance_csv(analysis_root / "ghana_plastic_vs_other_feature_importance.csv", ranking)
    plot_feature_importance(ranking, analysis_root / "ghana_plastic_vs_other_feature_importance.png")

    write_run_note(
        analysis_root / "analysis_run_note.md",
        [
            "# Analysis Run Note",
            f"- library_csv: {library_csv}",
            f"- plastic_valid_rows: {len(plastic_rows)}",
            f"- ghana_valid_rows: {len(ghana_rows)}",
            f"- ghana_classes: {', '.join(sorted({row['normalized_class_label'] for row in ghana_rows})) if ghana_rows else 'none'}",
            f"- summary_features: {', '.join(SUMMARY_FEATURES)}",
            f"- dropped_plastic_rows: {sum(1 for row in rows if row.get('normalized_class_label') == 'plastic') - len(plastic_rows)}",
            f"- dropped_ghana_rows: {sum(1 for row in rows if row.get('scene_id') == GHANA_SCENE_ID and row.get('normalized_class_label') in GHANA_CLASSES) - len(ghana_rows)}",
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate graphics and feature rankings from the SAR patch library.")
    parser.add_argument("--library-csv", type=Path, default=DEFAULT_LIBRARY_CSV)
    parser.add_argument("--inventory-csv", type=Path, default=DEFAULT_INVENTORY_CSV)
    parser.add_argument("--patches-root", type=Path, default=DEFAULT_PATCHES_ROOT)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_analysis(
        library_csv=args.library_csv,
        inventory_csv=args.inventory_csv,
        patches_root=args.patches_root,
        analysis_root=args.analysis_root,
    )


if __name__ == "__main__":
    main()
