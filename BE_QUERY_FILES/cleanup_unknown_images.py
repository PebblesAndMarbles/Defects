"""
Cleanup: UNKNOWN folder audit and manifest health check.

1. Cross-reference UNKNOWN/ files against the image manifest to check
   whether correctly-named counterparts exist on disk.
2. Remove UNKNOWN/ files where the correct counterpart exists.
3. Remove UNKNOWN/ files with no manifest entry (orphaned mis-named downloads).
4. Remove the UNKNOWN/ folder if empty after cleanup.
5. Report manifest health: broken LOCAL_IMAGE_FILE paths, UNKNOWN-pointing rows,
   and rows with no LOCAL_IMAGE_FILE.
"""

import sys
import os
import re
from pathlib import Path

import pandas as pd

WORKSPACE = Path(__file__).resolve().parent.parent
IMAGE_ROOT = WORKSPACE / "images" / "defects"
UNKNOWN_DIR = IMAGE_ROOT / "UNKNOWN"
MANIFEST_CSV = WORKSPACE / "outputs" / "defects" / "DEFECT_COORDINATES_EXTENDED_IMAGES.csv"

# ---------------------------------------------------------------------------
# 1. Inventory UNKNOWN folder
# ---------------------------------------------------------------------------
print("=" * 80)
print("STEP 1 — UNKNOWN folder inventory")
print("=" * 80)

if not UNKNOWN_DIR.exists():
    print("  UNKNOWN folder does not exist — nothing to do.")
    sys.exit(0)

unknown_files = list(UNKNOWN_DIR.glob("*.jpg")) + list(UNKNOWN_DIR.glob("*.png"))
print(f"  Found {len(unknown_files)} file(s) in UNKNOWN/")

# Parse defect_id and image_id from filename pattern:
# 000000_0000_UNK_UNKNOWN_UNK_UNKNOWN_{defect_id}_{image_id}.jpg
_pat = re.compile(r"_(\d+)_(\d+)\.\w+$")
unknown_keys = {}
for f in unknown_files:
    m = _pat.search(f.name)
    if m:
        did, iid = int(m.group(1)), int(m.group(2))
        unknown_keys[f] = (did, iid)
    else:
        unknown_keys[f] = None
        print(f"  WARNING: could not parse defect/image ID from: {f.name}")

# ---------------------------------------------------------------------------
# 2. Load manifest and cross-reference
# ---------------------------------------------------------------------------
print(f"\n{'=' * 80}")
print("STEP 2 — Cross-reference with manifest")
print("=" * 80)

manifest = pd.read_csv(MANIFEST_CSV, low_memory=False)
print(f"  Manifest loaded: {len(manifest)} rows")

# Build lookup: (defect_id, image_id) → LOCAL_IMAGE_FILE
def _norm(v):
    try:
        return int(float(v))
    except Exception:
        return None

manifest["_DID"] = manifest["DEFECT_ID"].apply(_norm)
manifest["_IID"] = manifest["IMAGE_ID"].apply(_norm)
lookup = {}
for _, row in manifest.iterrows():
    k = (row["_DID"], row["_IID"])
    if k[0] is not None and k[1] is not None:
        lookup[k] = row.get("LOCAL_IMAGE_FILE")

n_has_counterpart = 0
n_no_manifest = 0
n_counterpart_missing = 0
to_delete = []

print(f"\n  {'UNKNOWN file':<55}  {'Manifest counterpart'}")
print(f"  {'-'*54}  {'-'*60}")

for f, key in unknown_keys.items():
    if key is None:
        to_delete.append((f, "no_key"))
        continue
    did, iid = key
    correct_path = lookup.get((did, iid))
    if correct_path is None:
        n_no_manifest += 1
        to_delete.append((f, "no_manifest_entry"))
        print(f"  {f.name:<55}  [NO MANIFEST ENTRY — orphan]")
    elif correct_path and os.path.isfile(str(correct_path)):
        n_has_counterpart += 1
        to_delete.append((f, "counterpart_exists"))
        print(f"  {f.name:<55}  OK -> {Path(str(correct_path)).name}")
    else:
        n_counterpart_missing += 1
        to_delete.append((f, "counterpart_missing"))
        cname = Path(str(correct_path)).name if correct_path else "n/a"
        print(f"  {f.name:<55}  MANIFEST ENTRY EXISTS but file missing: {cname}")

print(f"\n  Summary:")
print(f"    Counterpart confirmed on disk:  {n_has_counterpart}")
print(f"    Manifest entry but file missing: {n_counterpart_missing}")
print(f"    No manifest entry (orphan):     {n_no_manifest}")

# ---------------------------------------------------------------------------
# 3. Delete UNKNOWN files
# ---------------------------------------------------------------------------
print(f"\n{'=' * 80}")
print("STEP 3 — Deleting UNKNOWN files")
print("=" * 80)

deleted = 0
kept = 0
for f, reason in to_delete:
    if reason == "counterpart_missing":
        # Keep — only correctly-named copy we have
        print(f"  KEPT (only copy): {f.name}")
        kept += 1
    else:
        f.unlink()
        deleted += 1

print(f"  Deleted: {deleted}   Kept (only copy): {kept}")

# Remove UNKNOWN dir if now empty
remaining = list(UNKNOWN_DIR.iterdir())
if not remaining:
    UNKNOWN_DIR.rmdir()
    print(f"  UNKNOWN/ folder removed (empty)")
else:
    print(f"  UNKNOWN/ folder kept — {len(remaining)} file(s) remaining")

# ---------------------------------------------------------------------------
# 4. Manifest health check
# ---------------------------------------------------------------------------
print(f"\n{'=' * 80}")
print("STEP 4 — Manifest health check")
print("=" * 80)

total = len(manifest)
has_local = manifest["LOCAL_IMAGE_FILE"].notna() & (manifest["LOCAL_IMAGE_FILE"].astype(str).str.strip() != "")
n_has_local = has_local.sum()
n_no_local = total - n_has_local

# Rows pointing to UNKNOWN folder
unknown_rows = manifest["LOCAL_IMAGE_FILE"].astype(str).str.contains("\\\\UNKNOWN\\\\", na=False)
n_unknown_rows = unknown_rows.sum()

# Rows where LOCAL_IMAGE_FILE is set but file doesn't exist
def _file_exists(v):
    if pd.isna(v) or str(v).strip() in ("", "nan"):
        return None  # not set
    return os.path.isfile(str(v))

print(f"  Checking {n_has_local} rows with LOCAL_IMAGE_FILE set (may take a moment)...")
exists_series = manifest.loc[has_local, "LOCAL_IMAGE_FILE"].apply(_file_exists)
n_broken = (exists_series == False).sum()
n_good   = (exists_series == True).sum()

print(f"\n  Total manifest rows:                {total}")
print(f"  Rows with LOCAL_IMAGE_FILE set:     {n_has_local}  ({n_has_local/total*100:.1f}%)")
print(f"    -> file confirmed on disk:        {n_good}")
print(f"    -> file NOT found (broken path):  {n_broken}")
print(f"  Rows with no LOCAL_IMAGE_FILE:      {n_no_local}")
print(f"  Rows pointing to UNKNOWN/ folder:   {n_unknown_rows}")

if n_broken > 0:
    print(f"\n  Sample broken paths:")
    broken_paths = manifest.loc[has_local][exists_series == False]["LOCAL_IMAGE_FILE"].head(5)
    for p in broken_paths:
        print(f"    {p}")

# Patch UNKNOWN-pointing manifest rows to null (they'll be re-resolved on next run)
if n_unknown_rows > 0:
    print(f"\n  Clearing {n_unknown_rows} UNKNOWN-pointing LOCAL_IMAGE_FILE entries in manifest...")
    manifest.loc[unknown_rows, "LOCAL_IMAGE_FILE"] = None
    manifest.drop(columns=["_DID", "_IID"], inplace=True, errors="ignore")
    manifest.to_csv(MANIFEST_CSV, index=False)
    print(f"  Manifest updated: {MANIFEST_CSV.name}")
else:
    manifest.drop(columns=["_DID", "_IID"], inplace=True, errors="ignore")
    print(f"  No UNKNOWN-pointing rows in manifest — no update needed.")

print(f"\n{'=' * 80}")
print("CLEANUP COMPLETE")
print("=" * 80)
