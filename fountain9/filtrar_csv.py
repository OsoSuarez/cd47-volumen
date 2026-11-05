"""Filtra los CSV descargados de Fountain9 y genera el Excel de volumen futuro.

Lee los dos CSV más recientes de descargas/, elimina filas con
Replenishment(Allocation) Quantity for Plan Duration Editable == 0,
combina secos + RyC y guarda descargas/volumen_futuro_YYYY_MM_DD.xlsx.

Uso:
    python fountain9/filtrar_csv.py
"""
import pathlib
import sys
from datetime import date

import pandas as pd

OUT = pathlib.Path("descargas")
COL_FILTRO = "Replenishment(Allocation) Quantity for Plan Duration Editable"
HOY = date.today().strftime("%Y_%m_%d")


def leer_csv(path: pathlib.Path) -> pd.DataFrame:
    print(f"  leyendo {path.name} ({path.stat().st_size // 1_000_000} MB)...")
    df = pd.read_csv(path, low_memory=False)
    total = len(df)
    df = df[df[COL_FILTRO].fillna(0) != 0]
    print(f"  {total:,} filas → {len(df):,} filas con cantidad > 0 ({total - len(df):,} eliminadas)")
    return df


def main():
    csvs = sorted(OUT.glob("All - Fixed Schedule Replenishment Plan *.csv"),
                  key=lambda p: p.stat().st_mtime)
    if len(csvs) < 2:
        sys.exit(f"ERROR: se esperaban 2 CSV en {OUT}/, se encontraron {len(csvs)}")

    # Los dos más recientes (el último es RyC, el anteúltimo es Secos)
    secos_path, ryc_path = csvs[-2], csvs[-1]
    print(f"Secos: {secos_path.name}")
    print(f"RyC:   {ryc_path.name}")

    print("\nFiltrando...")
    df_secos = leer_csv(secos_path)
    df_secos["Tipo"] = "Secos"

    df_ryc = leer_csv(ryc_path)
    df_ryc["Tipo"] = "RyC"

    df = pd.concat([df_secos, df_ryc], ignore_index=True)
    print(f"\nTotal combinado: {len(df):,} filas")

    destino = OUT / f"volumen_futuro_{HOY}.xlsx"
    print(f"\nGenerando {destino.name}...")
    with pd.ExcelWriter(destino, engine="openpyxl") as writer:
        df_secos.to_excel(writer, sheet_name="Secos", index=False)
        df_ryc.to_excel(writer, sheet_name="RyC", index=False)
        df.to_excel(writer, sheet_name="Combinado", index=False)

    size_mb = destino.stat().st_size / 1_000_000
    print(f"LISTO: {destino} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
