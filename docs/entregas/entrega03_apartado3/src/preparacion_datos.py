"""
Entrega 02 — Datos y preparación
Pipeline reproducible Bronze -> Silver -> Gold para el AVM (valoración automática de vivienda).

Fuente: paquete idealista18 (Rey-Blanco, Arbués, López y Páez, 2024), anuncios reales de
idealista.com en 2018 enriquecidos con Catastro. Licencia ODbL. Ciudad: Madrid.

Uso (desde la raíz del repositorio):
    python src/preparacion_datos.py            # descarga (si falta), limpia y genera Gold
    python src/preparacion_datos.py --offline  # no descarga: usa data/raw tal cual

Salidas:
    data/raw/       Madrid_Sale.rda, Madrid_Polygons.rda   (Bronze, sin modificar)
    data/silver/    viviendas_silver.parquet
    data/gold/      viviendas_gold.parquet + informe_calidad.json
    data/sample/    muestras pequeñas (Bronze y Gold) que sí se suben al repo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, SILVER, GOLD, SAMPLE = (ROOT / "data" / d for d in ("raw", "silver", "gold", "sample"))

# Versión fijada del repositorio de origen: garantiza que todos descargan exactamente los mismos bytes
COMMIT = "e9ef80618f8a9cc28f672ac138f298bbd519918e"
URL = "https://raw.githubusercontent.com/paezha/idealista18/{commit}/data/{name}"
FICHEROS = {
    "Madrid_Sale.rda": "c50e281ee699a8a523a5505dd64eb1d5aa0e3ba712092355850ed6d9f0d38a20",
    "Madrid_Polygons.rda": "3c10d0eaccd52029150d12fb1c9b25031dedf9bbaba9237380401125ca83acba",
}

# Códigos oficiales de distrito del Ayuntamiento de Madrid (aparecen dentro de LOCATIONID)
DISTRITOS = {
    "01": "Centro", "02": "Arganzuela", "03": "Retiro", "04": "Salamanca", "05": "Chamartín",
    "06": "Tetuán", "07": "Chamberí", "08": "Fuencarral-El Pardo", "09": "Moncloa-Aravaca",
    "10": "Latina", "11": "Carabanchel", "12": "Usera", "13": "Puente de Vallecas",
    "14": "Moratalaz", "15": "Ciudad Lineal", "16": "Hortaleza", "17": "Villaverde",
    "18": "Villa de Vallecas", "19": "Vicálvaro", "20": "San Blas-Canillejas", "21": "Barajas",
}

# Reglas de plausibilidad (documentadas en docs/entregas/02_datos_y_preparacion.md)
REGLAS = {
    "superficie_m2": (25, 600),
    "habitaciones": (0, 10),
    "banos": (1, 8),
    "anio_construccion_catastro": (1800, 2018),
}

informe: dict = {}


# ----------------------------------------------------------------------------------------
# BRONZE: adquisición reproducible, sin tocar el dato
# ----------------------------------------------------------------------------------------
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def descargar_bronze(offline: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for nombre, hash_esperado in FICHEROS.items():
        destino = RAW / nombre
        if not destino.exists():
            if offline:
                raise FileNotFoundError(f"Falta {destino} y se pidió --offline")
            print(f"Descargando {nombre} (commit {COMMIT[:7]})…")
            urllib.request.urlretrieve(URL.format(commit=COMMIT, name=nombre), destino)
        if sha256(destino) != hash_esperado:
            raise ValueError(f"{nombre}: el checksum no coincide; el fichero no es el esperado")
    print("Bronze OK: ficheros presentes y verificados por SHA-256")


def leer_bronze() -> tuple[pd.DataFrame, pd.DataFrame]:
    import rdata  # lector de ficheros .rda de R en Python puro

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ventas = rdata.read_rda(str(RAW / "Madrid_Sale.rda"))["Madrid_Sale"]
        barrios = rdata.read_rda(str(RAW / "Madrid_Polygons.rda"), default_encoding="utf8")["Madrid_Polygons"]
    return ventas, barrios


# ----------------------------------------------------------------------------------------
# SILVER: tipos, nombres, duplicados, inconsistencias, unión espacial con barrios
# ----------------------------------------------------------------------------------------
RENOMBRAR = {
    "ASSETID": "id_vivienda", "PERIOD": "periodo", "PRICE": "precio_eur", "UNITPRICE": "precio_m2",
    "CONSTRUCTEDAREA": "superficie_m2", "ROOMNUMBER": "habitaciones", "BATHNUMBER": "banos",
    "HASTERRACE": "terraza", "HASLIFT": "ascensor", "HASAIRCONDITIONING": "aire_acondicionado",
    "AMENITYID": "equipamiento", "HASPARKINGSPACE": "parking",
    "HASNORTHORIENTATION": "orient_norte", "HASSOUTHORIENTATION": "orient_sur",
    "HASEASTORIENTATION": "orient_este", "HASWESTORIENTATION": "orient_oeste",
    "HASBOXROOM": "trastero", "HASWARDROBE": "armarios", "HASSWIMMINGPOOL": "piscina",
    "HASDOORMAN": "portero", "HASGARDEN": "jardin", "ISDUPLEX": "duplex", "ISSTUDIO": "estudio",
    "ISINTOPFLOOR": "ultima_planta", "FLOORCLEAN": "planta", "FLATLOCATIONID": "exterior_interior",
    "CADCONSTRUCTIONYEAR": "anio_construccion_catastro", "CADMAXBUILDINGFLOOR": "plantas_edificio",
    "CADDWELLINGCOUNT": "viviendas_edificio", "CADASTRALQUALITYID": "calidad_catastral",
    "DISTANCE_TO_CITY_CENTER": "dist_centro_km", "DISTANCE_TO_METRO": "dist_metro_km",
    "DISTANCE_TO_CASTELLANA": "dist_castellana_km", "LONGITUDE": "lon", "LATITUDE": "lat",
}

BINARIAS = ["terraza", "ascensor", "aire_acondicionado", "parking", "orient_norte", "orient_sur",
            "orient_este", "orient_oeste", "trastero", "armarios", "piscina", "portero", "jardin",
            "duplex", "estudio", "ultima_planta"]


def paso(nombre: str, df: pd.DataFrame) -> pd.DataFrame:
    informe.setdefault("pasos_silver", []).append({"paso": nombre, "filas": int(len(df))})
    print(f"  {nombre:<55} {len(df):>7,} filas")
    return df


def asignar_barrio(df: pd.DataFrame, barrios: pd.DataFrame) -> pd.DataFrame:
    """Punto-en-polígono: cada vivienda recibe el barrio en el que caen sus coordenadas."""
    from shapely import STRtree, points
    from shapely.geometry import MultiPolygon, Polygon

    def a_poligono(geom):  # rdata devuelve el MULTIPOLYGON de sf como listas anidadas de arrays
        return MultiPolygon([Polygon(p[0], p[1:]) for p in geom])

    polys = [a_poligono(g) for g in barrios["geometry"]]
    arbol = STRtree(polys)
    pts = points(df["lon"].to_numpy(), df["lat"].to_numpy())
    idx_pt, idx_poly = arbol.query(pts, predicate="within")
    asignado = pd.Series(-1, index=range(len(df)))
    asignado.iloc[idx_pt] = idx_poly  # los barrios no se solapan: como mucho uno por punto

    ids = barrios["LOCATIONID"].astype(str).to_numpy()
    nombres = barrios["LOCATIONNAME"].astype(str).to_numpy()
    ok = asignado.to_numpy() >= 0
    df = df.copy()
    df["barrio_id"] = np.where(ok, ids[asignado.clip(lower=0)], None)
    df["barrio"] = np.where(ok, nombres[asignado.clip(lower=0)], None)
    # LOCATIONID = 0-EU-ES-28-07-001-079-<distrito>-<barrio>; 079 = municipio de Madrid (INE 28079)
    df["distrito_cod"] = df["barrio_id"].str.split("-").str[-2]
    df["distrito"] = df["distrito_cod"].map(DISTRITOS)
    informe["fuera_de_barrios"] = int((~ok).sum())
    return df


def construir_silver(ventas: pd.DataFrame, barrios: pd.DataFrame) -> pd.DataFrame:
    informe["bronze_filas"] = int(len(ventas))
    informe["bronze_columnas"] = int(ventas.shape[1])
    print("Silver:")
    df = paso("Bronze leído", ventas)

    # 1) Columnas: se descartan las redundantes o inservibles (motivo en el documento)
    descartar = {
        "geometry": "duplica LONGITUDE/LATITUDE",
        "CONSTRUCTIONYEAR": "año declarado por el anunciante: 59% nulos y valores imposibles; se usa el catastral",
        "ISPARKINGSPACEINCLUDEDINPRICE": "idéntica a HASPARKINGSPACE en todas las filas",
        "PARKINGSPACEPRICE": "valor de relleno (1) en el 98% de filas y extremos sin sentido",
        "BUILTTYPEID_1": "se condensa en 'estado'", "BUILTTYPEID_2": "se condensa en 'estado'",
        "BUILTTYPEID_3": "se condensa en 'estado'",
    }
    informe["columnas_descartadas"] = descartar
    estado = np.select(
        [ventas["BUILTTYPEID_1"] == 1, ventas["BUILTTYPEID_2"] == 1, ventas["BUILTTYPEID_3"] == 1],
        ["obra_nueva", "a_reformar", "buen_estado"], default=None)
    df = ventas.drop(columns=list(descartar)).rename(columns=RENOMBRAR)
    df["estado"] = pd.Categorical(estado, categories=["obra_nueva", "buen_estado", "a_reformar"])

    # 2) Tipos y formatos
    df["id_vivienda"] = df["id_vivienda"].astype(str)
    df["periodo"] = df["periodo"].astype(int)
    df["fecha_trimestre"] = pd.to_datetime(df["periodo"].astype(str), format="%Y%m").dt.to_period("Q").astype(str)
    df[BINARIAS] = df[BINARIAS].astype("int8")
    df["equipamiento"] = df["equipamiento"].map(
        {1: "sin_cocina_ni_muebles", 2: "cocina_sin_muebles", 3: "cocina_y_muebles"}).astype("category")
    df["exterior_interior"] = df["exterior_interior"].map({1: "exterior", 2: "interior"}).fillna("desconocido").astype("category")
    df["precio_eur"] = df["precio_eur"].round().astype(int)

    # 3) Duplicados: una misma vivienda reaparece en varios trimestres -> se conserva el anuncio más reciente
    df = df.sort_values(["id_vivienda", "periodo"])
    df["n_apariciones"] = df.groupby("id_vivienda")["periodo"].transform("size").astype("int8")
    df = paso("Tras corregir tipos y columnas", df)
    df = df.drop_duplicates("id_vivienda", keep="last")
    df = paso("Una fila por vivienda (último trimestre)", df)

    # 4) Nulos
    df = df.dropna(subset=["calidad_catastral"])
    df = paso("Sin nulo en calidad catastral", df)
    df["planta_desconocida"] = df["planta"].isna().astype("int8")  # el nulo se imputa en la fase ML

    # 5) Inconsistencias y valores no plausibles
    for col, (lo, hi) in REGLAS.items():
        df = df[df[col].between(lo, hi)]
        df = paso(f"{col} en [{lo}, {hi}]", df)
    df = df[~((df["estudio"] == 1) & (df["habitaciones"] > 1))]
    df = paso("Estudio con <= 1 habitación", df)

    # 6) Unión espacial: barrio y distrito oficiales; fuera del término municipal = coordenada errónea
    df = asignar_barrio(df.reset_index(drop=True), barrios)
    df = df[df["barrio"].notna()]
    df = paso("Coordenadas dentro de un barrio de Madrid", df)

    # 7) Variables derivadas simples (sin usar el precio, para no filtrar la variable objetivo)
    df["antiguedad_anios"] = (2018 - df["anio_construccion_catastro"]).astype(int)
    df["calidad_catastral"] = df["calidad_catastral"].astype(int)
    return df.reset_index(drop=True)


# ----------------------------------------------------------------------------------------
# GOLD: tabla final que consume la fase de Machine Learning
# ----------------------------------------------------------------------------------------
COLUMNAS_GOLD = [
    # identificación y tiempo
    "id_vivienda", "fecha_trimestre", "n_apariciones",
    # objetivo
    "precio_eur", "log_precio", "precio_m2",
    # características físicas
    "superficie_m2", "habitaciones", "banos", "planta", "planta_desconocida", "exterior_interior",
    "estado", "equipamiento", "terraza", "ascensor", "aire_acondicionado", "parking", "trastero",
    "armarios", "piscina", "portero", "jardin", "duplex", "estudio", "ultima_planta",
    "orient_norte", "orient_sur", "orient_este", "orient_oeste",
    # edificio (Catastro)
    "anio_construccion_catastro", "antiguedad_anios", "plantas_edificio", "viviendas_edificio",
    "calidad_catastral",
    # localización
    "distrito", "barrio", "barrio_id", "lat", "lon", "dist_centro_km", "dist_metro_km",
    "dist_castellana_km",
]


def construir_gold(silver: pd.DataFrame) -> pd.DataFrame:
    gold = silver.copy()
    gold["log_precio"] = np.log(gold["precio_eur"])
    gold = gold[COLUMNAS_GOLD]

    # Comprobaciones mínimas de contrato: si fallan, el pipeline se detiene
    assert gold["id_vivienda"].is_unique, "id_vivienda debe ser único"
    assert gold["precio_eur"].gt(0).all()
    obligatorias = [c for c in COLUMNAS_GOLD if c != "planta"]
    nulos = gold[obligatorias].isna().sum()
    assert nulos.sum() == 0, f"Nulos inesperados: {nulos[nulos > 0].to_dict()}"
    assert np.allclose(gold["precio_m2"], gold["precio_eur"] / gold["superficie_m2"], rtol=0.01)

    informe["gold_filas"] = int(len(gold))
    informe["gold_columnas"] = int(gold.shape[1])
    informe["gold_barrios"] = int(gold["barrio"].nunique())
    informe["gold_distritos"] = int(gold["distrito"].nunique())
    informe["nulos_planta"] = int(gold["planta"].isna().sum())
    informe["precio_eur"] = gold["precio_eur"].describe().round(0).to_dict()
    informe["precio_m2"] = gold["precio_m2"].describe().round(0).to_dict()
    informe["filas_por_trimestre"] = gold["fecha_trimestre"].value_counts().sort_index().to_dict()
    return gold


def guardar(ventas: pd.DataFrame, silver: pd.DataFrame, gold: pd.DataFrame) -> None:
    for d in (SILVER, GOLD, SAMPLE):
        d.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(SILVER / "viviendas_silver.parquet", index=False)
    gold.to_parquet(GOLD / "viviendas_gold.parquet", index=False)
    # Muestras pequeñas para el repositorio (los ficheros completos quedan fuera por .gitignore)
    ventas.drop(columns="geometry").sample(200, random_state=42).to_csv(
        SAMPLE / "bronze_madrid_muestra.csv", index=False)
    gold.sample(500, random_state=42).to_csv(SAMPLE / "gold_madrid_muestra.csv", index=False)
    with open(GOLD / "informe_calidad.json", "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2, default=str)


def main(offline: bool = False) -> pd.DataFrame:
    descargar_bronze(offline)
    ventas, barrios = leer_bronze()
    silver = construir_silver(ventas, barrios)
    gold = construir_gold(silver)
    guardar(ventas, silver, gold)
    print(f"Gold: {len(gold):,} viviendas x {gold.shape[1]} columnas -> data/gold/viviendas_gold.parquet")
    return gold


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="no descargar; usar data/raw existente")
    main(ap.parse_args().offline)
