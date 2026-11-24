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
    controlar(path.name, total, df)
    return df


def controlar(nombre, total, df):
    """Avisos de sanidad: el plan puede venir cortado o con pocos dias."""
    if total % 1000 == 0 or len(df) % 1000 == 0:
        print(f"  !! AVISO {nombre}: cantidad de filas redonda ({total:,} / {len(df):,}). "
              f"Probable corte en la descarga de Fountain9: revisar que el plan este completo.")
    col = next((c for c in df.columns if c.strip().lower() == "final order date"), None)
    if col:
        dias = sorted(pd.to_datetime(df[col], errors="coerce").dropna().dt.date.unique())
        print(f"  dias en el plan: {len(dias)} ({dias[0]} -> {dias[-1]})" if dias else "  sin fechas")
        if len(dias) < 5:
            print(f"  !! AVISO {nombre}: solo {len(dias)} dias de plan (se esperan ~7).")
        for i in range(1, len(dias)):
            if (dias[i] - dias[i - 1]).days > 1:
                print(f"  !! AVISO {nombre}: salto de fechas {dias[i-1]} -> {dias[i]}")


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
    # Se ignora el prefijo plan_1_/plan_2_ (puede venir cruzado): se toman los 2 planes mas nuevos
    # por la fecha/hora del nombre y el MAS GRANDE es Secos, el mas chico es RyC.
    import re
    def clave(p):
        m = re.search(r"(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})", p.name)
        return m.group(1) if m else ""
    csvs = [c for c in OUT.glob("*Fixed Schedule Replenishment Plan*.csv") if not c.name.startswith("filtrado_")]
    porplan = {}
    for c in csvs:
        k = clave(c)
        if k and (k not in porplan or c.stat().st_size > porplan[k].stat().st_size):
            porplan[k] = c
    ult = sorted(porplan)[-2:]
    if len(ult) < 2:
        sys.exit(f"ERROR: se esperaban 2 planes distintos en {OUT}/, se encontraron {len(ult)}")
    a, b = porplan[ult[0]], porplan[ult[1]]
    # Los dos planes tienen que ser de la MISMA corrida (se crean con minutos de diferencia).
    # Si no, uno es de una corrida anterior (ej. el de frio de ayer) y se mezclaria un plan viejo.
    fa = datetime.strptime(ult[0], "%Y_%m_%d_%H_%M_%S")
    fb = datetime.strptime(ult[1], "%Y_%m_%d_%H_%M_%S")
    dif_min = (fb - fa).total_seconds() / 60
    if dif_min > 30:
        sys.exit(f"ERROR: los 2 planes mas nuevos son de corridas distintas ({ult[0]} y {ult[1]}, {dif_min:.0f} min de diferencia). "
                 f"Falto descargar uno de los dos planes de hoy. Revisar run_planes.py / Fountain9 y volver a bajar.")
    secos_path, ryc_path = (a, b) if a.stat().st_size >= b.stat().st_size else (b, a)
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
