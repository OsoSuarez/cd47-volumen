"""
Convierte los CSV filtrados (secos + RyC) al formato base.json del repo cd47-volumen
y los sube via GitHub CLI para que el workflow de Actions regenere el dashboard
con los datos del plan persistidos.

Formato base.json:
{
  "dates": ["2026-11-04", ...],           <- lista global de fechas
  "skus": {"1002": ["nombre", batch, "temp"], ...},
  "files": [
    {
      "file": "filtrado_secos_...",
      "rows": 60667,
      "whs": [3, 7, ...],
      "dates": ["2026-11-04", ...],
      "skus": [1002, ...],
      "recs": [wh_id, sku_id, date_idx_en_base_dates, qty, ...]  <- grupos de 4
    },
    { ... ryc ... }
  ]
}
"""

import csv
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime

DESCARGAS = pathlib.Path(__file__).parent.parent / "descargas"
REPO_URL   = "https://github.com/OsoSuarez/cd47-volumen.git"
BASE_API   = "https://raw.githubusercontent.com/OsoSuarez/cd47-volumen/main/base.json"

COL_WH    = "Warehouseid"
COL_SKU   = "SKU ID"
COL_NAME  = "SKU Name"
COL_DATE  = "Final Order Date"
COL_BATCH = "Batch Size"
COL_QTY   = "Replenishment(Allocation) Quantity for Plan Duration Editable"
COL_TEMP  = "Storage Type"


def find_filtrados():
    secos = sorted(DESCARGAS.glob("filtrado_secos_*.csv"), key=lambda p: p.stat().st_mtime)
    ryc   = sorted(DESCARGAS.glob("filtrado_ryc_*.csv"),   key=lambda p: p.stat().st_mtime)
    if not secos or not ryc:
        sys.exit(f"ERROR: No se encontraron filtrado_secos_*.csv o filtrado_ryc_*.csv en {DESCARGAS}")
    return secos[-1], ryc[-1]


def col_idx(header, *names):
    low = {n.lower() for n in names}
    for i, h in enumerate(header):
        if h.strip().lower() in low:
            return i
    return -1


def norm_date(v):
    v = str(v or "").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if m:
        return f"{m[1]}-{m[2].zfill(2)}-{m[3].zfill(2)}"
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", v)
    if m:
        y = m[3] if len(m[3]) == 4 else "20" + m[3]
        return f"{y}-{m[2].zfill(2)}-{m[1].zfill(2)}"
    return None


def parse_csv(path):
    """Lee un CSV filtrado y extrae registros.
    Retorna: (skus_dict, file_obj) donde file_obj tiene el formato base.json."""
    print(f"  Leyendo {path.name} ...", flush=True)
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]

    iwh   = col_idx(header, COL_WH)
    isku  = col_idx(header, COL_SKU)
    iname = col_idx(header, COL_NAME)
    idate = col_idx(header, COL_DATE)
    ibatch= col_idx(header, COL_BATCH)
    iqty  = col_idx(header, COL_QTY)
    itemp = col_idx(header, COL_TEMP, "Storage Type", "Slot Temperature", "Temperature")

    missing = []
    for name, idx in [("Warehouseid", iwh), ("SKU ID", isku), ("Final Order Date", idate), (COL_QTY, iqty)]:
        if idx < 0:
            missing.append(name)
    if missing:
        sys.exit(f"ERROR: Columnas faltantes en {path.name}: {missing}")

    skus_local = {}  # sku_id -> [name, batch, temp]
    recs_raw   = []  # list of (wh, sku_id, date_str, qty)
    dates_set  = set()
    whs_set    = set()
    skus_set   = set()
    rows = 0

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            def g(i):
                return row[i].strip() if 0 <= i < len(row) else ""

            qty_raw = g(iqty)
            try:
                qty = float(qty_raw.replace(",", ".")) if qty_raw else 0
            except ValueError:
                qty = 0
            if qty <= 0:
                continue

            sku_raw = re.sub(r"\D", "", g(isku))
            if not sku_raw:
                continue
            sku_id = int(sku_raw)

            wh_raw = re.sub(r"\D", "", g(iwh))
            if not wh_raw:
                continue
            wh_id = int(wh_raw)

            date_str = norm_date(g(idate))
            if not date_str:
                continue

            batch_raw = g(ibatch)
            try:
                batch = int(float(batch_raw)) if batch_raw else 1
            except ValueError:
                batch = 1

            name  = g(iname) if iname >= 0 else ""
            temp  = g(itemp) if itemp >= 0 else "room temperature"

            if sku_id not in skus_local:
                skus_local[sku_id] = [name, batch, temp]

            recs_raw.append((wh_id, sku_id, date_str, int(qty) if qty == int(qty) else qty))
            dates_set.add(date_str)
            whs_set.add(wh_id)
            skus_set.add(sku_id)
            rows += 1

    print(f"    → {rows:,} registros, {len(skus_set):,} SKUs, {len(whs_set)} tiendas, {len(dates_set)} fechas")
    return skus_local, recs_raw, sorted(dates_set), sorted(whs_set), sorted(skus_set), rows, path.name


def build_base_json(secos_path, ryc_path):
    """Construye el base.json completo combinando ambos CSV filtrados."""
    print("\nProcesando CSV filtrados...")

    # Leer ambos archivos
    secos_skus, secos_recs, secos_dates, secos_whs, secos_skulist, secos_rows, secos_name = parse_csv(secos_path)
    ryc_skus,   ryc_recs,   ryc_dates,   ryc_whs,   ryc_skulist,   ryc_rows,   ryc_name   = parse_csv(ryc_path)

    # Unir todas las fechas para el índice global
    all_dates = sorted(set(secos_dates) | set(ryc_dates))
    date_idx  = {d: i for i, d in enumerate(all_dates)}

    # Unir todos los SKUs
    all_skus = {}
    all_skus.update(secos_skus)
    all_skus.update(ryc_skus)

    # Construir file objects con recs comprimidos (grupos de 4)
    def make_file_obj(recs_raw, name, dates, whs, skus_list, rows):
        recs_flat = []
        for wh, sku_id, date_str, qty in recs_raw:
            recs_flat.extend([wh, sku_id, date_idx[date_str], qty])
        return {
            "file": name,
            "rows": rows,
            "whs":  whs,
            "dates": dates,
            "skus":  skus_list,
            "recs":  recs_flat,
        }

    secos_obj = make_file_obj(secos_recs, secos_name, secos_dates, secos_whs, secos_skulist, secos_rows)
    ryc_obj   = make_file_obj(ryc_recs,   ryc_name,   ryc_dates,   ryc_whs,   ryc_skulist,   ryc_rows)

    base = {
        "dates": all_dates,
        "skus":  {str(k): v for k, v in all_skus.items()},
        "files": [secos_obj, ryc_obj],
    }

    print(f"\nbase.json generado:")
    print(f"  Fechas globales: {len(all_dates)}")
    print(f"  SKUs totales: {len(all_skus):,}")
    print(f"  Archivos: {secos_name}, {ryc_name}")
    return base


def push_to_github(base_obj):
    """Hace commit del nuevo base.json al repo usando gh CLI."""
    import subprocess

    # Serializar
    json_str = json.dumps(base_obj, ensure_ascii=False, separators=(",", ":"))
    size_mb  = len(json_str.encode()) / 1_048_576
    print(f"\nbase.json: {size_mb:.1f} MB")

    # Clonar repo en tmp
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="cd47_"))
    print(f"Clonando repo en {tmp_dir} ...")
    subprocess.run(["git", "clone", "https://github.com/OsoSuarez/cd47-volumen.git", str(tmp_dir)],
                   check=True, capture_output=True)

    # Escribir base.json
    target = tmp_dir / "base.json"
    target.write_text(json_str, encoding="utf-8")

    # Commit y push
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"plan: actualizar base.json con plan CD47 ({ts})\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01S124WGFBhrWr9RDLRhaY8p"
    subprocess.run(["git", "-C", str(tmp_dir), "config", "user.email", "jorge.suarez@rappi.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_dir), "config", "user.name",  "Jorge Suarez"], check=True)
    subprocess.run(["git", "-C", str(tmp_dir), "add", "base.json"], check=True)
    result = subprocess.run(["git", "-C", str(tmp_dir), "diff", "--cached", "--stat"],
                            capture_output=True, text=True)
    print(result.stdout)
    subprocess.run(["git", "-C", str(tmp_dir), "commit", "-m", msg], check=True)
    print("Haciendo push...")
    subprocess.run(["git", "-C", str(tmp_dir), "push"], check=True)
    print("✓ Push exitoso")

    # Disparar workflow via REST API (funciona sin GraphQL)
    print("\nDisparando workflow actualizar.yml ...")
    subprocess.run([
        "gh", "api",
        "/repos/OsoSuarez/cd47-volumen/actions/workflows/407418201/dispatches",
        "--method", "POST",
        "--field", "ref=main",
    ], check=True, capture_output=True)
    print("✓ Workflow disparado — el dashboard se regenerará en ~2 min")

    # Limpiar
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    secos_path, ryc_path = find_filtrados()
    print(f"Secos: {secos_path.name}")
    print(f"RyC:   {ryc_path.name}")

    base_obj = build_base_json(secos_path, ryc_path)
    push_to_github(base_obj)

    print(f"\n{'='*55}")
    print(f"Pipeline completo ✓  — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"El dashboard estará listo en: https://ososuarez.github.io/cd47-volumen/")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
