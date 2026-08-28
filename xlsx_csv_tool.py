#!/usr/bin/env python3
"""
xlsx_csv_tool.py

Convert XLSX files to CSV, optionally chop large CSVs into <=15MB
segments, and reassemble chopped segments (plus copy through any
plain CSVs) back into a final output directory.

Modes (mutually exclusive, exactly one required):
    --c     Convert XLSX -> CSV only.
    --cc    Convert XLSX -> CSV, then chop any CSV over the size
            threshold into numbered chunk files.
    --r     Reassemble: scan --s-dir for chunk files and whole CSVs,
            reassemble chunk sets into single files, copy whole CSVs
            as-is, write everything into --r-dir.

Usage:
    xlsx_csv_tool.py --c  --s-dir <dir> --r-dir <dir>
    xlsx_csv_tool.py --cc --s-dir <dir> --r-dir <dir>
    xlsx_csv_tool.py --r  --s-dir <dir> --r-dir <dir>

Chunk naming convention (produced by --cc, consumed by --r):
    <original_basename>.part<NNN>of<MMM>.csv
    e.g.  big_export.part001of004.csv

Each chunk is written as a fully valid, independently-openable CSV
(header row repeated in every chunk). On reassembly, the header is
kept only from part 001; parts are concatenated in numeric order.
"""

import argparse
import csv
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Dependency check / auto-install
#
# pandas and openpyxl are not part of the standard library, so a fresh
# macOS Python (or any machine without them) will fail with a raw
# ModuleNotFoundError before argparse even runs. This checks for both,
# and if either is missing, installs it into THIS interpreter
# (sys.executable) via pip before continuing. Using sys.executable
# rather than a bare "pip"/"pip3" matters on macOS specifically, since
# it's common to have several Pythons on PATH (system Python, Homebrew
# Python, a pyenv/venv Python) and a bare pip call can silently install
# into the wrong one.
# --------------------------------------------------------------------------
REQUIRED_PACKAGES = {
    "pandas": "pandas",
    "openpyxl": "openpyxl",  # required by pandas to read .xlsx
}


def ensure_dependencies() -> None:
    missing = []
    for module_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return

    print(f"[setup] missing required package(s): {', '.join(missing)}")
    print(f"[setup] installing via: {sys.executable} -m pip install {' '.join(missing)}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    except subprocess.CalledProcessError as exc:
        print(
            f"[error] automatic install failed: {exc}\n"
            f"        Install manually with:\n"
            f"        {sys.executable} -m pip install {' '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)
    print("[setup] install complete, continuing...")


ensure_dependencies()

import pandas as pd  # noqa: E402  (must come after ensure_dependencies)

CHUNK_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
CHUNK_RE = re.compile(r"^(?P<base>.+)\.part(?P<part>\d+)of(?P<total>\d+)\.csv$", re.IGNORECASE)


# --------------------------------------------------------------------------
# Conversion
# --------------------------------------------------------------------------

def convert_xlsx_to_csv(xlsx_path: Path, dest_dir: Path) -> Path:
    """Convert a single .xlsx file to .csv in dest_dir (first sheet only).

    Returns the path to the written CSV.
    """
    df = pd.read_excel(xlsx_path, sheet_name=0, dtype=str, engine="openpyxl")
    csv_path = dest_dir / (xlsx_path.stem + ".csv")
    df.to_csv(csv_path, index=False)
    return csv_path


def convert_all(source_dir: Path, dest_dir: Path) -> list[Path]:
    """Convert every .xlsx/.xls file in source_dir into dest_dir.

    Returns list of produced CSV paths.
    """
    produced = []
    xlsx_files = sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".xlsx", ".xls")
    )
    if not xlsx_files:
        print(f"[warn] no .xlsx/.xls files found in {source_dir}")
        return produced

    for xlsx_path in xlsx_files:
        try:
            csv_path = convert_xlsx_to_csv(xlsx_path, dest_dir)
            print(f"[convert] {xlsx_path.name} -> {csv_path.name}")
            produced.append(csv_path)
        except Exception as exc:
            print(f"[error] failed to convert {xlsx_path.name}: {exc}", file=sys.stderr)

    return produced


# --------------------------------------------------------------------------
# Chopping
# --------------------------------------------------------------------------

def chop_csv(csv_path: Path, dest_dir: Path, chunk_size: int = CHUNK_SIZE_BYTES) -> list[Path]:
    """Split csv_path into <=chunk_size chunks (row-boundary safe).

    Header row is repeated in every chunk. If the file is already
    under chunk_size, no chopping happens; the original is left in
    place (caller decides whether to also copy it).

    Returns list of chunk paths written (empty if no chop was needed).
    """
    if csv_path.stat().st_size <= chunk_size:
        return []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print(f"[warn] {csv_path.name} is empty, skipping chop")
            return []
        rows = list(reader)

    if not rows:
        return []

    # First pass: group rows into parts that respect the byte budget,
    # accounting for the header being repeated in every part. Size is
    # tracked incrementally (O(n)) rather than by re-encoding each
    # candidate batch (which is O(n^2) and far too slow on large files).
    base = csv_path.stem

    def row_csv_bytes(row: list[str]) -> int:
        buf = io.StringIO()
        csv.writer(buf).writerow(row)
        return len(buf.getvalue().encode("utf-8"))

    header_size = row_csv_bytes(header)

    parts_rows: list[list[list[str]]] = []
    current_rows: list[list[str]] = []
    current_size = header_size

    for row in rows:
        row_size = row_csv_bytes(row)
        if current_rows and (current_size + row_size) > chunk_size:
            parts_rows.append(current_rows)
            current_rows = [row]
            current_size = header_size + row_size
        else:
            current_rows.append(row)
            current_size += row_size
    if current_rows:
        parts_rows.append(current_rows)

    total = len(parts_rows)
    chunk_paths = []
    for idx, part_rows in enumerate(parts_rows, start=1):
        chunk_name = f"{base}.part{idx:03d}of{total:03d}.csv"
        chunk_path = dest_dir / chunk_name
        with open(chunk_path, "w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow(header)
            w.writerows(part_rows)
        print(f"[chop] {csv_path.name} -> {chunk_name} ({chunk_path.stat().st_size / 1_048_576:.2f} MB)")
        chunk_paths.append(chunk_path)

    return chunk_paths


def convert_and_chop(source_dir: Path, dest_dir: Path) -> None:
    produced = convert_all(source_dir, dest_dir)
    for csv_path in produced:
        chunk_paths = chop_csv(csv_path, dest_dir)
        if chunk_paths:
            # Remove the pre-chop whole file so dest_dir only holds
            # either chunks or small whole files, never both for the
            # same source.
            csv_path.unlink()
        else:
            print(f"[chop] {csv_path.name} is under 15MB, left whole")


# --------------------------------------------------------------------------
# Reassembly
# --------------------------------------------------------------------------

def reassemble(source_dir: Path, dest_dir: Path) -> None:
    """Reassemble chunk sets in source_dir and copy through whole CSVs,
    writing all results into dest_dir.
    """
    csv_files = sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() == ".csv")
    if not csv_files:
        print(f"[warn] no .csv files found in {source_dir}")
        return

    groups: dict[str, dict[int, Path]] = {}
    totals: dict[str, int] = {}
    whole_files: list[Path] = []

    for path in csv_files:
        m = CHUNK_RE.match(path.name)
        if m:
            base = m.group("base")
            part = int(m.group("part"))
            total = int(m.group("total"))
            groups.setdefault(base, {})[part] = path
            existing_total = totals.get(base)
            if existing_total is not None and existing_total != total:
                print(f"[error] conflicting total-part count for '{base}': "
                      f"{existing_total} vs {total} (from {path.name})", file=sys.stderr)
            totals[base] = total
        else:
            whole_files.append(path)

    # Reassemble chunk groups
    for base, parts in sorted(groups.items()):
        total = totals[base]
        missing = [i for i in range(1, total + 1) if i not in parts]
        if missing:
            print(f"[error] '{base}' is missing part(s) {missing} of {total} — skipping reassembly", file=sys.stderr)
            continue

        out_path = dest_dir / f"{base}.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            for idx in range(1, total + 1):
                chunk_path = parts[idx]
                with open(chunk_path, newline="", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if idx == 1 and header is not None:
                        writer.writerow(header)
                    for row in reader:
                        writer.writerow(row)
        print(f"[reassemble] {total} parts -> {out_path.name}")

    # Copy through whole (non-chunked) CSVs untouched
    for path in whole_files:
        dest_path = dest_dir / path.name
        shutil.copy2(path, dest_path)
        print(f"[copy] {path.name} -> {dest_path.name}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert XLSX to CSV, chop large CSVs into 15MB segments, and reassemble them."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--c", action="store_true", help="Convert XLSX -> CSV only.")
    mode.add_argument("--cc", action="store_true", help="Convert XLSX -> CSV, then chop files over 15MB.")
    mode.add_argument("--r", action="store_true", help="Reassemble chunked CSVs and copy through whole CSVs.")

    parser.add_argument("--s-dir", required=True, type=Path, help="Source directory.")
    parser.add_argument("--r-dir", required=True, type=Path, help="Result/output directory.")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    source_dir: Path = args.s_dir
    dest_dir: Path = args.r_dir

    if not source_dir.is_dir():
        print(f"[error] source dir does not exist: {source_dir}", file=sys.stderr)
        sys.exit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)

    if args.c:
        convert_all(source_dir, dest_dir)
    elif args.cc:
        convert_and_chop(source_dir, dest_dir)
    elif args.r:
        reassemble(source_dir, dest_dir)


if __name__ == "__main__":
    main()
