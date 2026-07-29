# snap_utils.py
from __future__ import annotations
import logging, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import re
import xml.etree.ElementTree as ET

# -------------------- logging --------------------
def setup_logging(verbosity: int = 1) -> None:
    level = logging.WARNING if verbosity <= 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=level)

# -------------------- gpt path --------------------
def _wsl_to_windows_path(path_str: str) -> str | None:
    match = re.match(r"^/mnt/([A-Za-z])/(.*)$", path_str)
    if not match:
        return None
    drive, rest = match.groups()
    return f"{drive.upper()}:\\{rest.replace('/', chr(92))}"


def _wsl_path_from_windows(path_str: str) -> str | None:
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", path_str)
    if not match:
        return None
    drive, rest = match.groups()
    return f"/mnt/{drive.lower()}/{rest.replace(chr(92), '/')}"


def uses_windows_paths(gpt_bin: str) -> bool:
    if os.name == "nt":
        return False
    lower = gpt_bin.lower()
    return lower.endswith(".exe") or bool(re.match(r"^[A-Za-z]:[\\/]", gpt_bin))


def snap_path(path_like: str | Path, windows_paths: bool = False) -> str:
    path_str = str(path_like)
    if windows_paths:
        return _wsl_to_windows_path(path_str) or path_str
    return path_str


def resolve_local_path(path_like: str | Path) -> Path:
    path_str = str(path_like)
    direct = Path(path_str)
    if direct.exists():
        return direct
    alternates = [_wsl_path_from_windows(path_str), _wsl_to_windows_path(path_str)]
    for alt in alternates:
        if alt:
            candidate = Path(alt)
            if candidate.exists():
                return candidate
    return direct


def _resolve_executable(candidate: str | None) -> str | None:
    if not candidate:
        return None
    resolved = shutil.which(candidate)
    if resolved:
        return resolved
    for path_str in (candidate, _wsl_path_from_windows(candidate)):
        if path_str and Path(path_str).exists():
            return path_str
    return None


def find_gpt(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.getenv("SNAP_GPT"),
        os.getenv("GPT_BIN"),
        "gpt.exe",
        "gpt",
        "/mnt/c/Program Files/esa-snap/bin/gpt.exe",
        "/mnt/c/Program Files/snap/bin/gpt.exe",
        r"C:\Program Files\esa-snap\bin\gpt.exe",
        r"C:\Program Files\snap\bin\gpt.exe",
    ]
    for cand in candidates:
        resolved = _resolve_executable(cand)
        if resolved:
            return resolved
    raise FileNotFoundError(
        "SNAP 'gpt' not found. Pass --gpt or set SNAP_GPT/GPT_BIN. "
        "Checked PATH plus standard SNAP locations for both 'esa-snap' and 'snap'."
    )

# -------------------- xml helpers --------------------
def _write_tmp(tree: ET.ElementTree, base_dir: Path | None = None) -> Path:
    tmp_dir = Path(tempfile.gettempdir()) if base_dir is None else base_dir / ".snap_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, p = tempfile.mkstemp(prefix="snap_", suffix=".xml", dir=tmp_dir)
    os.close(fd)  # avoid leaking a handle
    tmp = Path(p)
    tree.write(tmp, encoding="UTF-8", xml_declaration=True)
    return tmp

def patch_graph_io(src_graph: Path, in_file: Path, out_file: Path, windows_paths: bool = False) -> Path:
    """Set first Read.file and first Write.file in a SNAP graph."""
    tree = ET.parse(src_graph); root = tree.getroot()

    def set_param(op_name: str, param: str, value: str) -> bool:
        for node in root.iter("node"):
            op = node.find("operator")
            if op is not None and op.text == op_name:
                params = node.find("parameters") or ET.SubElement(node, "parameters")
                tgt = next((p for p in params if p.tag == param or p.attrib.get("name") == param), None)
                if tgt is None: tgt = ET.SubElement(params, param)
                tgt.text = value
                return True
        return False

    if not set_param("Read", "file", snap_path(in_file, windows_paths)):
        raise RuntimeError(f"No 'Read' operator in {src_graph}")
    if not set_param("Write", "file", snap_path(out_file, windows_paths)):
        raise RuntimeError(f"No 'Write' operator in {src_graph}")
    return _write_tmp(tree, base_dir=src_graph.parent)

def patch_graph_params(src_graph: Path, updates: list[dict]) -> Path:
    """
    updates: [{"op": "TOPSAR-Split", "param": "subswath", "value": "IW1"}, ...]
             if value=None the parameter is removed (let SNAP default)
    """
    tree = ET.parse(src_graph); root = tree.getroot()

    def set_param(op_name: str, param: str, value: str | None) -> bool:
        for node in root.iter("node"):
            op = node.find("operator")
            if op is not None and op.text == op_name:
                params = node.find("parameters") or ET.SubElement(node, "parameters")
                tgt = next((p for p in params if p.tag == param or p.attrib.get("name") == param), None)
                if value is None:
                    if tgt is not None: params.remove(tgt)
                else:
                    if tgt is None: tgt = ET.SubElement(params, param)
                    tgt.text = value
                return True
        return False

    for u in updates:
        ok = set_param(u["op"], u["param"], u.get("value"))
        if not ok:
            raise RuntimeError(f"Operator '{u['op']}' not found while setting '{u['param']}' in {src_graph}")
    return _write_tmp(tree, base_dir=src_graph.parent)

def graph_has_operator(src_graph: Path, operator_name: str) -> bool:
    """Return True if a graph contains an operator with this exact name."""
    tree = ET.parse(src_graph); root = tree.getroot()
    for node in root.iter("node"):
        op = node.find("operator")
        if op is not None and op.text == operator_name:
            return True
    return False

# -------------------- runner --------------------
def run_graph(
    gpt_bin: str,
    graph_xml: Path,
    cache_gb: int = 8,
    workers: int = 1,
    extra_args: list[str] | None = None,
) -> None:
    cmd = [gpt_bin, snap_path(graph_xml, uses_windows_paths(gpt_bin)), "-c", f"{cache_gb}G", "-q", str(workers)]
    # Keep full-scene operators such as C2 generation from requesting very
    # large JAI rasters, and release cached tiles as output rows complete.
    cmd.extend(["-x", "-Dsnap.jai.defaultTileSize=256"])
    if extra_args:
        cmd.extend(extra_args)
    logging.info("SNAP: %s", " ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"gpt failed ({proc.returncode}). See output above.")
    if graph_xml.name.startswith("snap_") and graph_xml.exists():
        graph_xml.unlink()

# -------------------- fs --------------------
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

# -------------------- exporter --------------------
def export_to_geotiff(
    gpt_bin: str,
    in_path: Path,
    out_tif: Path,
    cache_gb: int = 8,
    workers: int = 1,
    windows_paths: bool | None = None,
):
    """Atomically export a SNAP product to a tiled GeoTIFF-BigTIFF."""
    if windows_paths is None:
        windows_paths = uses_windows_paths(gpt_bin)
    partial_tif = out_tif.with_name(f"{out_tif.stem}.partial{out_tif.suffix}")
    partial_sidecar = Path(f"{partial_tif}.aux.xml")
    for stale_path in (partial_tif, partial_sidecar):
        if stale_path.exists():
            stale_path.unlink()

    root = ET.Element("graph", {"id": "ExportToGTiff"})
    ET.SubElement(root, "version").text = "1.0"

    n_read = ET.SubElement(root, "node", {"id": "Read"})
    ET.SubElement(n_read, "operator").text = "Read"
    ET.SubElement(n_read, "sources")
    p = ET.SubElement(n_read, "parameters", {"class": "com.bc.ceres.binding.dom.XppDomElement"})
    ET.SubElement(p, "file").text = snap_path(in_path, windows_paths)

    n_write = ET.SubElement(root, "node", {"id": "Write"})
    ET.SubElement(n_write, "operator").text = "Write"
    s = ET.SubElement(n_write, "sources")
    ET.SubElement(s, "sourceProduct", {"refid": "Read"})
    p2 = ET.SubElement(n_write, "parameters", {"class": "com.bc.ceres.binding.dom.XppDomElement"})
    ET.SubElement(p2, "file").text = snap_path(partial_tif, windows_paths)
    ET.SubElement(p2, "formatName").text = "GeoTIFF-BigTIFF"

    tmp = _write_tmp(ET.ElementTree(root), base_dir=out_tif.parent)
    # Full-swath texture products can be very large. Explicit BigTIFF tiles keep
    # the writer from trying to allocate an oversized float DataBuffer.
    try:
        run_graph(
            gpt_bin,
            tmp,
            cache_gb=cache_gb,
            workers=workers,
            extra_args=[
                "-Dsnap.dataio.bigtiff.tiling.width=512",
                "-Dsnap.dataio.bigtiff.tiling.height=512",
            ],
        )
        if not partial_tif.exists():
            raise RuntimeError(f"SNAP reported success but did not create {partial_tif}")
        partial_tif.replace(out_tif)
        if partial_sidecar.exists():
            partial_sidecar.replace(Path(f"{out_tif}.aux.xml"))
    except Exception:
        for failed_path in (partial_tif, partial_sidecar):
            if failed_path.exists():
                failed_path.unlink()
        raise
