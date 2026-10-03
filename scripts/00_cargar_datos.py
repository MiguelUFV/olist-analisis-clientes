"""
Fase 0 - Cargar los 9 CSV de Olist en una base de datos SQLite.

Ejecutar desde la carpeta del proyecto:
    python scripts/00_cargar_datos.py

No se limpia nada aquí: los datos entran tal cual vienen (eso es la fase 2).
"""
import sqlite3
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")          # carpeta con los CSV originales
DB = Path("data/olist.db")      # base de datos que vamos a crear

# Conexión a la base de datos (si el archivo no existe, SQLite lo crea)
con = sqlite3.connect(DB)

for csv in sorted(RAW.glob("*.csv")):
    # Nombre de tabla corto: "olist_orders_dataset.csv" -> "orders"
    tabla = csv.stem.replace("olist_", "").replace("_dataset", "")

    # dtype=str en los códigos postales para no perder los ceros a la izquierda
    df = pd.read_csv(csv, dtype={
        "customer_zip_code_prefix": str,
        "seller_zip_code_prefix": str,
        "geolocation_zip_code_prefix": str,
    })

    # if_exists="replace": si la tabla ya existe la borra y la vuelve a crear,
    # así el script se puede ejecutar las veces que haga falta
    df.to_sql(tabla, con, if_exists="replace", index=False)

    print(f"{tabla:<35} {len(df):>9,} filas  {df.shape[1]:>2} columnas")

con.close()
