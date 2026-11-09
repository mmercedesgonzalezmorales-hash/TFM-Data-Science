"""
Entrega 03 — Machine Learning · Apartado 3: baseline y selección de modelos

Parte del Gold de la Entrega 02 (data/gold/viviendas_gold.parquet, generado con
`python src/preparacion_datos.py`) y compara, con validación cruzada sobre el periodo de
entrenamiento, dos referencias sencillas y dos alternativas de ML para estimar el precio de
oferta de una vivienda en Madrid.

Uso (desde la raíz del repositorio):
    python src/modelado.py

Salidas:
    results/03_comparacion_cv.csv     métricas por modelo y fold
    results/03_resumen_cv.csv         media y desviación por modelo
    results/03_validacion_temporal_T3.csv   entrena T1–T2, valida T3
    results/03_resultados.json        resumen legible + configuración usada
"""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold" / "viviendas_gold.parquet"
OUT = ROOT / "results"
SEED = 42

# ---------------------------------------------------------------------------
# Variables (ver apartado 2): solo lo que el usuario conoce al pedir la valoración
# ---------------------------------------------------------------------------
OBJETIVO = "log_precio"  # se modela log(precio); las métricas se dan en euros

NUMERICAS = [
    "superficie_m2", "habitaciones", "banos", "planta", "antiguedad_anios",
    "plantas_edificio", "viviendas_edificio", "calidad_catastral",
    "lat", "lon", "dist_centro_km", "dist_metro_km", "dist_castellana_km",
]
BINARIAS = [
    "planta_desconocida", "terraza", "ascensor", "aire_acondicionado", "parking", "trastero",
    "armarios", "piscina", "portero", "jardin", "duplex", "estudio", "ultima_planta",
    "orient_norte", "orient_sur", "orient_este", "orient_oeste",
]
CATEGORICAS = ["exterior_interior", "estado", "equipamiento", "distrito", "barrio"]

# Excluidas a propósito:
#   precio_eur, precio_m2           -> son el objetivo expresado de otra forma (fuga directa)
#   n_apariciones                   -> cuántos trimestres estuvo publicado: solo se sabe a posteriori
#   id_vivienda, barrio_id          -> identificadores (barrio ya entra por nombre)
#   anio_construccion_catastro      -> redundante con antiguedad_anios
#   fecha_trimestre                 -> se usa para separar entrenamiento y test, no como entrada


def cargar() -> tuple[pd.DataFrame, pd.DataFrame]:
    g = pd.read_parquet(GOLD)
    for c in NUMERICAS:
        g[c] = g[c].astype("float64")  # Int32 con nulos -> float con NaN
    for c in CATEGORICAS:
        g[c] = g[c].astype(str)
    # Separación temporal: T1–T3 2018 para entrenar y seleccionar; T4 se reserva para el apartado 4
    entreno = g[g.fecha_trimestre < "2018Q4"].reset_index(drop=True)
    test = g[g.fecha_trimestre == "2018Q4"].reset_index(drop=True)
    return entreno, test


# ---------------------------------------------------------------------------
# Métricas en euros (lo que entiende el usuario del producto)
# ---------------------------------------------------------------------------
def metricas(real: np.ndarray, pred: np.ndarray) -> dict:
    ape = np.abs(pred - real) / real
    return {
        "MAE_eur": float(np.mean(np.abs(pred - real))),
        "MdAPE_pct": float(np.median(ape) * 100),
        "MAPE_pct": float(np.mean(ape) * 100),
        "dentro_10pct": float(np.mean(ape <= 0.10) * 100),
        "dentro_20pct": float(np.mean(ape <= 0.20) * 100),
        "R2_log": float(1 - np.sum((np.log(real) - np.log(pred)) ** 2)
                        / np.sum((np.log(real) - np.log(real).mean()) ** 2)),
    }


# ---------------------------------------------------------------------------
# Modelos. Todos siguen la misma interfaz: ajustar(train) -> predecir(df) en euros
# ---------------------------------------------------------------------------
class MedianaGlobal:
    """B0: a todas las viviendas les asigna la mediana de precio del entrenamiento."""
    nombre = "B0 · Mediana global"

    def fit(self, df):
        self.m = df.precio_eur.median()
        return self

    def predict(self, df):
        return np.full(len(df), self.m)


class EurM2Barrio:
    """B1: mediana de €/m² del barrio × superficie. Es la regla del tasador (método de comparación).
    Si el barrio tiene menos de 10 anuncios en entrenamiento usa la del distrito, y si no, la global."""
    nombre = "B1 · €/m² del barrio × m²"

    def fit(self, df, min_n=10):
        b = df.groupby("barrio").precio_m2.agg(["median", "size"])
        self.barrio = b.loc[b["size"] >= min_n, "median"]
        self.distrito = df.groupby("distrito").precio_m2.median()
        self.glob = df.precio_m2.median()
        return self

    def predict(self, df):
        eur_m2 = df.barrio.map(self.barrio).fillna(df.distrito.map(self.distrito)).fillna(self.glob)
        return (eur_m2 * df.superficie_m2).to_numpy()


class Ridge:
    """M1: regresión lineal regularizada sobre log(precio). One-hot de categóricas (barrio incluido),
    log(superficie) e imputación de nulos con la mediana. Interpretable y rápida."""
    nombre = "M1 · Regresión Ridge (log)"

    def _X(self, df):
        X = df[NUMERICAS + BINARIAS + CATEGORICAS].copy()
        X["log_superficie"] = np.log(X.superficie_m2)
        return X

    def fit(self, df):
        X = self._X(df)
        self.medianas = X[NUMERICAS].median()
        X[NUMERICAS] = X[NUMERICAS].fillna(self.medianas)
        num = NUMERICAS + ["log_superficie"]
        pre = ColumnTransformer([
            ("num", StandardScaler(), num),
            ("bin", "passthrough", BINARIAS),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10), CATEGORICAS),
        ])
        self.modelo = make_pipeline(pre, RidgeCV(alphas=np.logspace(-2, 3, 12)))
        self.modelo.fit(X, df[OBJETIVO])
        return self

    def predict(self, df):
        X = self._X(df)
        X[NUMERICAS] = X[NUMERICAS].fillna(self.medianas)
        return np.exp(self.modelo.predict(X))


class GBM:
    """M2: gradient boosting (LightGBM) sobre log(precio). Capta no linealidades e interacciones
    (p. ej. el valor de un ascensor depende de la planta) y usa lat/lon directamente."""

    def __init__(self, nombre="M2 · LightGBM (log)", **params):
        self.nombre = nombre
        self.params = dict(n_estimators=1500, learning_rate=0.03, num_leaves=63,
                           min_child_samples=20, subsample=0.8, subsample_freq=1,
                           colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1)
        self.params.update(params)

    def _X(self, df):
        X = df[NUMERICAS + BINARIAS + CATEGORICAS].copy()
        for c in CATEGORICAS:
            X[c] = pd.Categorical(X[c], categories=self.cats[c])
        return X

    def fit(self, df):
        self.cats = {c: sorted(df[c].unique()) for c in CATEGORICAS}
        self.modelo = lgb.LGBMRegressor(**self.params).fit(self._X(df), df[OBJETIVO])
        return self

    def predict(self, df):
        return np.exp(self.modelo.predict(self._X(df)))


# Ajuste ligero de LightGBM: tres configuraciones de menos a más capacidad, elegidas por CV
CONFIGS_GBM = {
    "M2a · LightGBM pequeño": dict(num_leaves=15, n_estimators=800, min_child_samples=50),
    "M2b · LightGBM medio": dict(num_leaves=63, n_estimators=1500),
    "M2c · LightGBM grande": dict(num_leaves=255, n_estimators=2500, learning_rate=0.02,
                                  min_child_samples=10),
}


def candidatos():
    yield MedianaGlobal()
    yield EurM2Barrio()
    yield Ridge()
    for nombre, p in CONFIGS_GBM.items():
        yield GBM(nombre=nombre, **p)


# Casi 3 de cada 10 anuncios comparten barrio, m², habitaciones, baños, planta y año con otro:
# es la misma vivienda republicada (otra agencia u otro trimestre) con distinto id. Si una copia
# cae en entrenamiento y otra en validación, el modelo "se la sabe" y la métrica sale optimista.
CLAVE_VIVIENDA = ["barrio", "superficie_m2", "habitaciones", "banos", "planta", "antiguedad_anios"]


def grupos(df: pd.DataFrame) -> np.ndarray:
    return pd.MultiIndex.from_frame(df[CLAVE_VIVIENDA].astype(str)).factorize()[0]


def _copia(modelo):
    m = type(modelo).__new__(type(modelo))
    m.__dict__.update(modelo.__dict__)
    return m


def validar(entreno: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """CV agrupada de 5 folds sobre T1–T3: todas las copias de una vivienda caen en el mismo fold.
    Todo lo que se aprende de los datos (medianas por barrio, escalado, imputación, categorías)
    se calcula dentro de cada fold, solo con su parte de entrenamiento."""
    filas = []
    folds = list(GroupKFold(k, shuffle=True, random_state=SEED).split(entreno, groups=grupos(entreno)))
    for modelo in candidatos():
        t0 = time.time()
        for i, (tr, va) in enumerate(folds):
            m = _copia(modelo)
            m.fit(entreno.iloc[tr])
            r = metricas(entreno.precio_eur.iloc[va].to_numpy(), m.predict(entreno.iloc[va]))
            filas.append({"modelo": modelo.nombre, "fold": i + 1, **r})
        print(f"  {modelo.nombre:32s} {time.time() - t0:6.1f}s")
    return pd.DataFrame(filas)


def comprobar_temporal(entreno: pd.DataFrame) -> pd.DataFrame:
    """Segunda comprobación, más exigente: entrenar con T1–T2 y validar en T3 (sin tocar T4).
    Imita el uso real: el modelo valora anuncios posteriores a los que vio."""
    a, b = entreno[entreno.fecha_trimestre < "2018Q3"], entreno[entreno.fecha_trimestre == "2018Q3"]
    filas = []
    for modelo in candidatos():
        m = _copia(modelo).fit(a)
        filas.append({"modelo": modelo.nombre, **metricas(b.precio_eur.to_numpy(), m.predict(b))})
    return pd.DataFrame(filas).set_index("modelo")


def main():
    OUT.mkdir(exist_ok=True)
    entreno, test = cargar()
    print(f"Entrenamiento (T1–T3 2018): {len(entreno):,} viviendas · Test reservado (T4): {len(test):,}")
    cv = validar(entreno)
    cv.to_csv(OUT / "03_comparacion_cv.csv", index=False)
    orden = list(dict.fromkeys(cv.modelo))
    resumen = cv.drop(columns="fold").groupby("modelo").agg(["mean", "std"]).loc[orden]
    resumen.columns = [f"{a}_{b}" for a, b in resumen.columns]
    resumen.round(3).to_csv(OUT / "03_resumen_cv.csv")

    cols = ["MAE_eur", "MdAPE_pct", "MAPE_pct", "dentro_10pct", "dentro_20pct", "R2_log"]
    tabla = cv.groupby("modelo")[cols].mean().loc[orden]
    print("\nValidación cruzada (media de 5 folds):")
    print(tabla.round(2).to_string())

    temporal = comprobar_temporal(entreno)
    temporal.round(3).to_csv(OUT / "03_validacion_temporal_T3.csv")
    print("\nComprobación temporal (entrena T1–T2, valida T3):")
    print(temporal[cols].round(2).to_string())

    # Regla de selección: la configuración más sencilla cuyo MdAPE en CV esté a menos de
    # 0,5 puntos de la mejor y que también sea de las mejores en la comprobación temporal
    gbm = [n for n in orden if "LightGBM" in n]
    mejor = tabla.loc[gbm, "MdAPE_pct"].min()
    elegido = next(n for n in gbm if tabla.loc[n, "MdAPE_pct"] - mejor < 0.5
                   and temporal.loc[n, "MdAPE_pct"] - temporal.loc[gbm, "MdAPE_pct"].min() < 0.5)
    json.dump({
        "gold": str(GOLD.relative_to(ROOT)),
        "objetivo": OBJETIVO,
        "entradas": {"numericas": NUMERICAS, "binarias": BINARIAS, "categoricas": CATEGORICAS},
        "separacion": "Entrenamiento y selección: 2018 T1–T3 con GroupKFold(5, shuffle, seed=42) "
                      "agrupando copias de la misma vivienda; comprobación temporal T1–T2 -> T3. "
                      "Test reservado: 2018 T4 (apartado 4).",
        "n_entreno": len(entreno), "n_test_reservado": len(test),
        "cv_media": tabla.round(3).reset_index().to_dict(orient="records"),
        "temporal_T3": temporal[cols].round(3).reset_index().to_dict(orient="records"),
        "configuracion_gbm_elegida": elegido,
    }, open(OUT / "03_resultados.json", "w"), ensure_ascii=False, indent=2)
    print(f"\nConfiguración de LightGBM elegida por CV: {elegido}")


if __name__ == "__main__":
    main()
