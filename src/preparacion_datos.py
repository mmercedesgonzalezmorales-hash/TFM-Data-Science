"""
Entrega 02 · Pipeline Bronze -> Silver -> Gold

Pregunta del proyecto: ¿qué efecto tuvo la declaración de zonas de mercado residencial
tensionado (Ley 12/2023) sobre la renta del alquiler y los contratos nuevos registrados en Cataluña?

Fuentes:
  - Incasòl / Generalitat de Catalunya: registro de fianzas de alquiler por municipio
    (dataset qww9-bvhh, "Preu mitjà del lloguer d'habitatges per municipi"). Reutilización
    libre con atribución según las condiciones de uso del portal de datos abiertos de la Generalitat.
  - BOE: relación de municipios declarados zona tensionada (BOE-A-2024-5214 y BOE-A-2024-20576),
    transcrita en data/referencia/municipios_tensionados.csv.

Uso (desde la raíz del repositorio):
    python src/preparacion_datos.py            # descarga el CSV si falta y genera Silver y Gold
    python src/preparacion_datos.py --offline  # no descarga: usa data/raw tal cual

Salidas:
    data/raw/      incasol_fianzas_municipi.csv + bronze_metadata.json   (Bronze, sin modificar)
    data/silver/   fianzas_trimestral.parquet, fianzas_anual.parquet
    data/gold/     panel_municipio_trimestre.parquet + informe_calidad.json
    data/sample/   muestras pequeñas (Bronze y Gold) que sí se suben al repo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.request
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, SILVER, GOLD, SAMPLE, REF = (ROOT / "data" / d for d in ("raw", "silver", "gold", "sample", "referencia"))

URL = "https://analisi.transparenciacatalunya.cat/api/v3/views/qww9-bvhh/export.csv?accessType=DOWNLOAD"
FICHERO_RAW = RAW / "incasol_fianzas_municipi.csv"
# Hash de la instantánea usada en esta entrega (descargada el 15/11/2026, datos hasta 2026 T2).
# La fuente se actualiza cada trimestre: un hash distinto no es un error, solo una versión más nueva.
SHA256_REFERENCIA = "602427170c393b4763e0118c48c1c5d52281d3eeea117750666fee8d7b6857a7"

TRIMESTRES = {"gener-març": 1, "abril-juny": 2, "juliol-setembre": 3, "octubre-desembre": 4}
ANUAL = "gener-desembre"
# Periodos acumulados (gener-juny, gener-setembre) que se descartan: se pueden reconstruir con los trimestres.

PRIMER_TRIMESTRE = pd.Period("2019Q1", "Q")  # desde 2019 la fuente es trimestral

# Ley catalana 11/2020 de contención de rentas: en vigor 22/09/2020, anulada por el Tribunal Constitucional
# (STC 37/2022, de 10 de marzo). Se marca el periodo para poder controlarlo en la fase de modelado.
LEY_CATALANA_2020 = (pd.Period("2020Q4", "Q"), pd.Period("2022Q1", "Q"))

UMBRAL_COBERTURA = 0.9  # % mínimo de trimestres con renta para entrar en la muestra
# Muestra alternativa: la cobertura se calcula solo con trimestres anteriores a la medida, para que lo que
# ocurre después (posible efecto de la ley) no influya en qué municipios entran.
FIN_PRE_TRATAMIENTO = pd.Period("2023Q4", "Q")


# --------------------------------------------------------------------------------------------- Bronze
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def descargar_bronze(offline: bool = False) -> dict:
    """Descarga el CSV tal cual (si no existe) y registra su huella. Nunca lo modifica."""
    RAW.mkdir(parents=True, exist_ok=True)
    if not FICHERO_RAW.exists():
        if offline:
            raise FileNotFoundError(
                f"Falta {FICHERO_RAW}. Descárgalo desde {URL} o ejecuta sin --offline."
            )
        print(f"Descargando {URL} ...")
        urllib.request.urlretrieve(URL, FICHERO_RAW)
    huella = sha256(FICHERO_RAW)
    if huella != SHA256_REFERENCIA:
        warnings.warn(
            "El CSV no coincide con la instantánea de referencia de esta entrega "
            "(probablemente es una actualización trimestral posterior). Las cifras pueden variar ligeramente."
        )
    meta = {
        "fuente": "Incasòl - Registre de fiances de lloguer d'habitatges per municipi",
        "url": URL,
        "licencia": "Condiciones de uso del portal de datos abiertos de la Generalitat (reutilización libre citando la fuente)",
        "atribucion": "Departament de Territori, Habitatge i Transició Ecològica - Incasòl",
        "fichero": FICHERO_RAW.name,
        "sha256": huella,
        "coincide_con_referencia": huella == SHA256_REFERENCIA,
        "bytes": FICHERO_RAW.stat().st_size,
        "registrado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (RAW / "bronze_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def leer_bronze() -> pd.DataFrame:
    # Todo como texto: los números vienen en formato español y se convierten en Silver.
    return pd.read_csv(FICHERO_RAW, dtype=str, keep_default_na=False, na_values=[""])


# --------------------------------------------------------------------------------------------- Silver
COLUMNAS = {
    "Àmbit territorial": "ambito",
    "Codi territorial": "codigo_ine",
    "Nom territori": "municipio_fuente",
    "Any": "anio",
    "Període": "periodo",
    "Habitatges": "contratos",
    "Renda": "renta_media",
    "Tram de preus": "tramo_renta",
}


def numero_es(s: pd.Series) -> pd.Series:
    """'30.789' -> 30789 ; '1.134,61' -> 1134.61 (punto = miles, coma = decimales)."""
    limpio = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(limpio, errors="coerce")


def clave_nombre(nombre: str) -> str:
    """Clave para cruzar nombres del BOE ('la Bisbal d'Empordà') con los del Incasòl ('Bisbal d'Empordà, la')."""
    m = re.match(r"^(.*), (el|la|les|l'|els|es)$", nombre.strip(), flags=re.I)
    if m:
        art = m.group(2)
        nombre = f"{art}{'' if art.endswith(chr(39)) else ' '}{m.group(1)}"
    s = unicodedata.normalize("NFKD", nombre.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\b(el|la|les|l'|els|es)\b ?", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def a_silver(bronze: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    log: dict = {"filas_bronze": len(bronze)}
    df = bronze.rename(columns=COLUMNAS)
    assert set(COLUMNAS.values()) <= set(df.columns), "Cambió el esquema de la fuente"

    log["ambitos"] = df["ambito"].value_counts().to_dict()
    df = df[df["ambito"] == "Municipi"].copy()

    # Tipos y formatos
    df["codigo_ine"] = df["codigo_ine"].str.zfill(5)
    df["anio"] = df["anio"].astype(int)
    df["contratos"] = numero_es(df["contratos"]).astype("Int64")
    df["renta_media"] = numero_es(df["renta_media"])
    df["renta_disponible"] = df["renta_media"].notna()
    log["filas_sin_renta"] = int((~df["renta_disponible"]).sum())

    # Duplicados exactos y por clave
    log["duplicados_exactos"] = int(df.duplicated().sum())
    df = df.drop_duplicates()
    clave = ["codigo_ine", "anio", "periodo"]
    log["duplicados_clave"] = int(df.duplicated(clave).sum())
    assert log["duplicados_clave"] == 0

    # Un nombre canónico por código (algunos municipios cambian de nombre: 'Palamós' -> 'Palamós i Sant Joan')
    ultimo = df.sort_values("anio").groupby("codigo_ine")["municipio_fuente"].last()
    df["municipio"] = df["codigo_ine"].map(ultimo)
    log["municipios_con_cambio_de_nombre"] = int(df.groupby("codigo_ine")["municipio_fuente"].nunique().gt(1).sum())

    # Reglas de plausibilidad
    malas = (df["contratos"] < 0) | (df["renta_media"] <= 0) | (df["renta_media"] > 10_000)
    log["filas_implausibles"] = int(malas.sum())
    df = df[~malas]

    cols = ["codigo_ine", "municipio", "anio", "contratos", "renta_media", "renta_disponible", "tramo_renta"]

    anual = df[df["periodo"] == ANUAL][cols].reset_index(drop=True)

    trim = df[df["periodo"].isin(TRIMESTRES)].copy()
    trim["trimestre"] = trim["periodo"].map(TRIMESTRES)
    trim["periodo_q"] = pd.PeriodIndex.from_fields(year=trim["anio"], quarter=trim["trimestre"], freq="Q")
    trim = trim[trim["periodo_q"] >= PRIMER_TRIMESTRE]
    trim = trim[cols[:3] + ["trimestre", "periodo_q"] + cols[3:]].reset_index(drop=True)
    log["descartadas_periodos_acumulados"] = int((~df["periodo"].isin(list(TRIMESTRES) + [ANUAL])).sum())

    # Coherencia: la suma de contratos trimestrales debe igualar al dato anual
    suma = trim.groupby(["codigo_ine", "anio"])["contratos"].sum()
    comp = anual.set_index(["codigo_ine", "anio"])["contratos"].to_frame("anual").join(suma.rename("suma_trim"), how="inner")
    completos = trim.groupby(["codigo_ine", "anio"]).size().eq(4)
    comp = comp[completos.reindex(comp.index, fill_value=False)]
    log["coherencia_anual_vs_trimestral"] = {
        "municipio_anio_comparados": len(comp),
        "coinciden_exactamente_pct": round(float((comp["anual"] == comp["suma_trim"]).mean() * 100), 2),
        "diferencia_mediana_pct": round(float(((comp["suma_trim"] - comp["anual"]).abs() / comp["anual"]).median() * 100), 2),
    }
    return trim, anual, log


def tratamiento(municipios: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cruza la lista del BOE (por nombre) con los códigos INE del Incasòl."""
    ref = pd.read_csv(REF / "municipios_tensionados.csv")
    ref["clave"] = ref["municipio_boe"].map(clave_nombre)
    nombres = municipios[["codigo_ine", "municipio_fuente"]].drop_duplicates()
    nombres["clave"] = nombres["municipio_fuente"].map(clave_nombre)
    ambiguas = nombres.groupby("clave")["codigo_ine"].nunique().gt(1)
    assert not ambiguas.any(), f"Nombres ambiguos: {ambiguas[ambiguas].index.tolist()}"
    m = ref.merge(nombres.drop_duplicates("clave"), on="clave", how="left")
    sin = m[m["codigo_ine"].isna()]["municipio_boe"].tolist()
    assert not sin, f"Municipios del BOE sin código: {sin}"
    out = m[["codigo_ine", "ola", "fecha_efectos"]].drop_duplicates("codigo_ine")
    out["fecha_efectos"] = pd.to_datetime(out["fecha_efectos"])
    return out, {"municipios_tensionados_cruzados": len(out), "ola_1": int((out.ola == 1).sum()), "ola_2": int((out.ola == 2).sum())}


# --------------------------------------------------------------------------------------------- Gold
def a_gold(trim: pd.DataFrame, trat: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Panel equilibrado municipio x trimestre (2019T1 - último trimestre disponible)."""
    ultimo_q = trim["periodo_q"].max()
    trimestres = pd.period_range(PRIMER_TRIMESTRE, ultimo_q, freq="Q")
    municipios = trim[["codigo_ine", "municipio"]].drop_duplicates("codigo_ine")
    rejilla = municipios.merge(pd.DataFrame({"periodo_q": trimestres}), how="cross")
    g = rejilla.merge(trim.drop(columns=["municipio"]), on=["codigo_ine", "periodo_q"], how="left")
    g["anio"] = g["periodo_q"].dt.year
    g["trimestre"] = g["periodo_q"].dt.quarter
    g["fila_en_fuente"] = g["contratos"].notna()
    g["renta_disponible"] = g["renta_media"].notna()

    # Tratamiento
    g = g.merge(trat, on="codigo_ine", how="left")
    g["ola"] = g["ola"].fillna(0).astype(int)
    g["grupo"] = g["ola"].map({0: "control (no tensionado)", 1: "ola 1 (mar-2024)", 2: "ola 2 (oct-2024)"})
    # Primer trimestre tratado = primer trimestre que empieza después de la entrada en vigor
    # (ola 1: 16/03/2024 -> 2024T2; ola 2: 10/10/2024 -> 2025T1). El trimestre de entrada se marca como transición.
    q_efecto = g["fecha_efectos"].dt.to_period("Q")
    g["primer_trimestre_tratado"] = q_efecto + 1
    g["trimestre_transicion"] = g["periodo_q"] == q_efecto
    # Fracción del trimestre con la medida vigente (0 = nada, 1 = todo el trimestre)
    inicio_q, fin_q = g["periodo_q"].dt.start_time, g["periodo_q"].dt.end_time.dt.normalize()
    dias_q = (fin_q - inicio_q).dt.days + 1
    dias_vigente = (fin_q - g["fecha_efectos"].clip(lower=inicio_q)).dt.days + 1
    g["fraccion_trimestre_vigente"] = (dias_vigente.clip(lower=0) / dias_q).where(g["ola"] > 0, 0.0).fillna(0.0).clip(upper=1).round(3)
    g["post"] = (g["ola"] > 0) & (g["periodo_q"] >= g["primer_trimestre_tratado"])
    g["trimestres_desde_tratamiento"] = np.where(
        g["ola"] > 0,
        (g["periodo_q"].astype("int64") - g["primer_trimestre_tratado"].astype("int64")),
        np.nan,
    )
    g["periodo_ley_catalana_2020"] = g["periodo_q"].between(*LEY_CATALANA_2020)
    g["log_renta"] = np.log(g["renta_media"])
    g["log_contratos"] = np.log1p(g["contratos"].astype(float))

    # Anomalía de la fuente: en 2026T1 falta la renta en ~90 % de los municipios que sí la tienen el resto de
    # trimestres (en la descarga de referencia). Se marca y no cuenta para decidir la muestra.
    cobertura_q = g.groupby("periodo_q")["renta_disponible"].mean()
    anomalos = cobertura_q[cobertura_q < 0.5 * cobertura_q.median()].index
    g["trimestre_anomalo_fuente"] = g["periodo_q"].isin(anomalos)

    # Muestra principal: renta disponible en al menos el 90 % de los trimestres no anómalos.
    # Por debajo, la serie es demasiado irregular (municipios con muy pocos contratos, renta suprimida por secreto).
    cobertura = g[~g["trimestre_anomalo_fuente"]].groupby("codigo_ine")["renta_disponible"].mean()
    g["cobertura_renta"] = g["codigo_ine"].map(cobertura).round(3)
    g["muestra_principal"] = g["cobertura_renta"] >= UMBRAL_COBERTURA

    # Muestra alternativa (comparación de robustez): misma regla, pero mirando solo 2019T1-2023T4
    pre = g[g["periodo_q"] <= FIN_PRE_TRATAMIENTO].groupby("codigo_ine")["renta_disponible"].mean()
    g["cobertura_renta_pre"] = g["codigo_ine"].map(pre).round(3)
    g["muestra_pre_tratamiento"] = g["cobertura_renta_pre"] >= UMBRAL_COBERTURA

    # Renta no publicada: la fuente da la fila (hay contratos) pero suprime la media por secreto estadístico
    g["renta_no_publicada"] = g["fila_en_fuente"] & ~g["renta_disponible"]

    g["fecha_trimestre"] = g["periodo_q"].dt.start_time
    g["periodo"] = g["periodo_q"].astype(str)
    cols = [
        "codigo_ine", "municipio", "periodo", "fecha_trimestre", "anio", "trimestre",
        "contratos", "renta_media", "tramo_renta", "fila_en_fuente", "renta_disponible", "renta_no_publicada",
        "log_renta", "log_contratos",
        "ola", "grupo", "fecha_efectos", "trimestre_transicion", "fraccion_trimestre_vigente", "post",
        "trimestres_desde_tratamiento",
        "periodo_ley_catalana_2020", "trimestre_anomalo_fuente", "cobertura_renta", "muestra_principal",
        "cobertura_renta_pre", "muestra_pre_tratamiento",
    ]
    g = g[cols].sort_values(["codigo_ine", "periodo"]).reset_index(drop=True)

    pm = g[g["muestra_principal"]].drop_duplicates("codigo_ine")
    resumen = {
        "filas": len(g),
        "municipios": int(g["codigo_ine"].nunique()),
        "trimestres": len(trimestres),
        "rango": f"{trimestres[0]} - {trimestres[-1]}",
        "filas_sin_dato_en_fuente_pct": round(float((~g["fila_en_fuente"]).mean() * 100), 1),
        "filas_sin_renta_pct": round(float((~g["renta_disponible"]).mean() * 100), 1),
        "filas_renta_no_publicada": int(g["renta_no_publicada"].sum()),
        "filas_trimestre_transicion": int(g["trimestre_transicion"].sum()),
        "fraccion_vigente_transicion": g.loc[g["trimestre_transicion"]].groupby("ola")["fraccion_trimestre_vigente"].first().to_dict(),
        "municipios_por_grupo": g.drop_duplicates("codigo_ine")["grupo"].value_counts().to_dict(),
        "trimestres_anomalos_fuente": [str(q) for q in anomalos],
        "umbral_cobertura_renta": UMBRAL_COBERTURA,
        "muestra_principal_por_grupo": pm["grupo"].value_counts().to_dict(),
        "muestra_principal_filas": int(g["muestra_principal"].sum()),
        "muestra_principal_pct_contratos": round(float(g.loc[g["muestra_principal"], "contratos"].sum() / g["contratos"].sum() * 100), 1),
        "muestra_pre_tratamiento_por_grupo": g[g["muestra_pre_tratamiento"]].drop_duplicates("codigo_ine")["grupo"].value_counts().to_dict(),
        "comparacion_muestras": comparar_muestras(g),
    }
    return g, resumen


def comparar_muestras(g: pd.DataFrame) -> dict:
    """Qué municipios entran en una muestra y no en la otra, por grupo."""
    m = g.drop_duplicates("codigo_ine")
    out = {}
    for grupo, d in m.groupby("grupo"):
        out[grupo] = {
            "en_ambas": int((d["muestra_principal"] & d["muestra_pre_tratamiento"]).sum()),
            "solo_principal": int((d["muestra_principal"] & ~d["muestra_pre_tratamiento"]).sum()),
            "solo_pre_tratamiento": int((~d["muestra_principal"] & d["muestra_pre_tratamiento"]).sum()),
        }
    return out


# --------------------------------------------------------------------------------------------- Muestras
def guardar_muestras(bronze: pd.DataFrame, gold: pd.DataFrame) -> None:
    SAMPLE.mkdir(parents=True, exist_ok=True)
    bronze.head(300).to_csv(SAMPLE / "bronze_muestra.csv", index=False)
    # Barcelona y Girona (ola 1) + los 3 municipios con más contratos de la ola 2 y del control (muestra principal)
    tam = gold[gold["muestra_principal"]].groupby(["grupo", "codigo_ine"])["contratos"].sum().reset_index()
    ejemplo = ["08019", "17079"]
    for grupo in ["ola 2 (oct-2024)", "control (no tensionado)"]:
        ejemplo += tam[tam["grupo"] == grupo].nlargest(3, "contratos")["codigo_ine"].tolist()
    gm = gold[gold["codigo_ine"].isin(ejemplo)].copy()
    gm["fecha_efectos"] = gm["fecha_efectos"].dt.date
    gm.to_csv(SAMPLE / "gold_muestra.csv", index=False)


def main(offline: bool = False) -> dict:
    meta = descargar_bronze(offline)
    bronze = leer_bronze()
    trim, anual, log = a_silver(bronze)
    trat, log_t = tratamiento(bronze.rename(columns=COLUMNAS).assign(codigo_ine=lambda d: d["codigo_ine"].str.zfill(5)))
    log.update(log_t)

    SILVER.mkdir(parents=True, exist_ok=True)
    trim.assign(periodo_q=trim["periodo_q"].astype(str)).to_parquet(SILVER / "fianzas_trimestral.parquet", index=False)
    anual.to_parquet(SILVER / "fianzas_anual.parquet", index=False)

    gold, resumen = a_gold(trim, trat)
    GOLD.mkdir(parents=True, exist_ok=True)
    gold.to_parquet(GOLD / "panel_municipio_trimestre.parquet", index=False)

    informe = {"bronze": meta, "silver": log, "gold": resumen}
    (GOLD / "informe_calidad.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False, default=str))
    guardar_muestras(bronze, gold)
    return informe


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="no descargar; usar data/raw tal cual")
    args = ap.parse_args()
    print(json.dumps(main(args.offline), indent=2, ensure_ascii=False, default=str))
