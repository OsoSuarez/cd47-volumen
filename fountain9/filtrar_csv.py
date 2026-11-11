"""Filtra los CSV descargados de Fountain9 y los prepara para subir al dashboard.

Lee los dos CSV más recientes de descargas/, elimina filas con
Replenishment(Allocation) Quantity for Plan Duration Editable == 0,
guarda los CSV filtrados y si alguno supera 300 MB genera un Excel como respaldo.

Uso:
    python fountain9/filtrar_csv.py
"""
import pathlib
import sys
from datetime import datetime

import pandas as pd

OUT = pathlib.Path("descargas")
COL_FILTRO = "Replenishment(Allocation) Quantity for Plan Duration Editable"
AHORA = datetime.now().strftime("%Y_%m_%d_%H_%M")
LIMITE_MB = 300
DASHBOARD_URL = "https://ososuarez.github.io/cd47-volumen/"


def leer_csv(path: pathlib.Path) -> pd.DataFrame:
    print(f"  leyendo {path.name} ({path.stat().st_size // 1_000_000} MB)...")
    df = pd.read_csv(path, low_memory=False)
    total = len(df)
    df = df[df[COL_FILTRO].fillna(0) != 0].copy()
    print(f"  {total:,} filas -> {len(df):,} con cantidad > 0 ({total - len(df):,} eliminadas)")
    return df


def guardar_csv_filtrado(df: pd.DataFrame, nombre: str):
    destino = OUT / f"filtrado_{nombre}_{AHORA}.csv"
    df.to_csv(destino, index=False)
    size_mb = destino.stat().st_size / 1_000_000
    print(f"  guardado: {destino.name} ({size_mb:.1f} MB)")
    return destino, size_mb


def main():
    # run_planes.py guarda los planes como "plan_1_All - Fixed Schedule..." y
    # "plan_2_All - Fixed Schedule...". El glob viejo exigia que el nombre
    # EMPEZARA con "All - ", asi que no los encontraba y filtraba planes viejos.
    def mas_nuevo(patron):
        hits = sorted(OUT.glob(patron), key=lambda p: p.stat().st_mtime)
        return hits[-1] if hits else None

    secos_path = mas_nuevo("plan_1_*Fixed Schedule Replenishment Plan*.csv")
    ryc_path   = mas_nuevo("plan_2_*Fixed Schedule Replenishment Plan*.csv")

    if not (secos_path and ryc_path):
        # Respaldo: nombres viejos, los dos mas recientes por fecha de modificacion.
        csvs = sorted(OUT.glob("*Fixed Schedule Replenishment Plan*.csv"),
                      key=lambda p: p.stat().st_mtime)
        csvs = [c for c in csvs if not c.name.startswith("filtrado_")]
        if len(csvs) < 2:
            sys.exit(f"ERROR: se esperaban 2 CSV de plan en {OUT}/, se encontraron {len(csvs)}")
        secos_path, ryc_path = csvs[-2], csvs[-1]
    print(f"Secos: {secos_path.name}")
    print(f"RyC:   {ryc_path.name}")

    print("\nFiltrando...")
    df_secos = leer_csv(secos_path)
    df_ryc = leer_csv(ryc_path)
    print(f"\nTotal combinado: {len(df_secos) + len(df_ryc):,} filas")

    print("\nGuardando CSV filtrados...")
    secos_out, secos_mb = guardar_csv_filtrado(df_secos, "secos")
    ryc_out, ryc_mb = guardar_csv_filtrado(df_ryc, "ryc")

    if secos_mb > LIMITE_MB or ryc_mb > LIMITE_MB:
        print(f"\nAVISO: archivo supera {LIMITE_MB} MB, generando Excel como respaldo...")
        destino_xlsx = OUT / f"volumen_futuro_{AHORA}.xlsx"
        df_secos["Tipo"] = "Secos"
        df_ryc["Tipo"] = "RyC"
        df_combinado = pd.concat([df_secos, df_ryc], ignore_index=True)
        with pd.ExcelWriter(destino_xlsx, engine="openpyxl") as writer:
            df_secos.to_excel(writer, sheet_name="Secos", index=False)
            df_ryc.to_excel(writer, sheet_name="RyC", index=False)
            df_combinado.to_excel(writer, sheet_name="Combinado", index=False)
        print(f"Excel: {destino_xlsx.name} ({destino_xlsx.stat().st_size // 1_000_000} MB)")

    print(f"\nListos para subir al dashboard:")
    print(f"  {secos_out.name} ({secos_mb:.1f} MB)")
    print(f"  {ryc_out.name} ({ryc_mb:.1f} MB)")
    print(f"SECOS_PATH={secos_out.resolve()}")
    print(f"RYC_PATH={ryc_out.resolve()}")
    print("LISTO_PARA_UPLOAD")


if __name__ == "__main__":
    main()
