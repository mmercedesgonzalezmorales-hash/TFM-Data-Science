"""
Entrega 03 · Machine Learning — Apartado 3: baseline y selección de modelos

Idea: entrenar un modelo SOLO con datos anteriores a la norma (hasta 2023T4) que prevea la renta y los
contratos de alquiler de cada municipio en los trimestres siguientes, "como si no hubiera ley".
Después (src/evaluacion.py) se compara esa previsión con lo que pasó de verdad.

Este script elige el modelo de previsión con backtests en los que tampoco se ve el futuro: se hace como si
estuviéramos en 2021T2, 2021T4, 2022T2 o 2022T4, se entrena solo con lo anterior y se predicen los
trimestres siguientes hasta 2023T4 (todos todavía sin ley).

Entrada: el Gold de la Entrega 02 (data/gold/panel_municipio_trimestre.parquet), muestra principal.
Uso (desde la raíz del repositorio):
    python src/preparacion_datos.py   # Entrega 02: genera el Gold
    python src/modelado.py            # este apartado

Salidas:
    results/03_backtest_detalle.csv   error de cada modelo por variable, corte y horizonte
    results/03_backtest_resumen.csv   resumen por modelo y variable
    results/03_resultados.json        modelo elegido para cada variable y configuración
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold" / "panel_municipio_trimestre.parquet"
OUT = ROOT / "results"
SEED = 42
# Muestra de municipios (Entrega 02): la principal, o la alternativa elegida solo con datos de 2019T1–2023T4
MUESTRA = "muestra_principal"

VARIABLES = {"log_renta": "Renta media", "log_contratos": "Contratos nuevos"}
CORTE_FINAL = pd.Period("2023Q4", "Q")  # último trimestre completo antes de la ola 1 (16/03/2024)
CORTES_BACKTEST = [pd.Period(p, "Q") for p in ["2021Q2", "2021Q4", "2022Q2", "2022Q4"]]
H_MAX = 10           # 2023T4 + 10 = 2026T2, último trimestre del Gold
VENTANA = 8          # trimestres de historia que mira el modelo en cada origen
PRIMER_ORIGEN = pd.Period("2020Q4", "Q")  # primer origen con 8 trimestres de historia (desde 2019T1)


# --------------------------------------------------------------------------------------------- Datos
def cargar() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.PeriodIndex]:
    """Muestra (MUESTRA) en formato ancho: una fila por municipio, una columna por trimestre."""
    g = pd.read_parquet(GOLD)
    g = g[g[MUESTRA]].copy()
    g["periodo_q"] = pd.PeriodIndex(g["periodo"], freq="Q")
    # 2026T1: la fuente no publica la renta en casi ningún municipio (ver Entrega 02). Se trata como dato ausente.
    g.loc[g["trimestre_anomalo_fuente"], "log_renta"] = np.nan
    trimestres = pd.period_range(g["periodo_q"].min(), g["periodo_q"].max(), freq="Q")
    series = {v: g.pivot(index="codigo_ine", columns="periodo_q", values=v).reindex(columns=trimestres)
              for v in VARIABLES}
    info = (g.drop_duplicates("codigo_ine").set_index("codigo_ine")
            [["municipio", "ola", "grupo", "fecha_efectos"]].copy())
    info["provincia"] = info.index.str[:2].map({"08": "Barcelona", "17": "Girona", "25": "Lleida", "43": "Tarragona"})
    # Peso de cada municipio = contratos medios de 2023 (antes de la ley): pesa más donde hay más alquileres
    c23 = g[g["anio"] == 2023].groupby("codigo_ine")["contratos"].mean()
    info["peso"] = c23.reindex(info.index).astype(float)
    return info, series, trimestres


def pesos_en(series: dict, corte: pd.Period) -> pd.Series:
    """Peso de cada municipio con lo que se sabía en `corte`: contratos medios de los 4 trimestres
    que terminan en el corte. Así un backtest de 2021 no usa información de 2023."""
    c = np.expm1(series["log_contratos"].loc[:, corte - 3: corte])
    return c.mean(axis=1).fillna(0)


# --------------------------------------------------------------------------------------------- Variables
def _pendiente(m: np.ndarray) -> np.ndarray:
    """Pendiente por trimestre de cada fila (ignora huecos)."""
    x = np.arange(m.shape[1], dtype=float)
    out = np.full(m.shape[0], np.nan)
    for i, fila in enumerate(m):
        ok = ~np.isnan(fila)
        if ok.sum() >= 4:
            out[i] = np.polyfit(x[ok], fila[ok], 1)[0]
    return out


def resumen_origen(series: dict, trimestres: pd.PeriodIndex, origen: pd.Period) -> pd.DataFrame:
    """Todo lo que se sabe de cada municipio en el trimestre `origen` (sin mirar después)."""
    t0 = trimestres.get_loc(origen)
    f = pd.DataFrame(index=series["log_renta"].index)
    for v, corto in [("log_renta", "r"), ("log_contratos", "c")]:
        m = series[v].to_numpy()[:, t0 - VENTANA + 1: t0 + 1]
        f[f"base_{corto}"] = np.nanmean(m[:, -4:], axis=1)        # nivel medio del último año
        f[f"var_anual_{corto}"] = f[f"base_{corto}"] - np.nanmean(m[:, :4], axis=1)
        f[f"pendiente_{corto}"] = _pendiente(m)
        f[f"volatilidad_{corto}"] = np.nanstd(np.diff(m, axis=1), axis=1)
        f[f"huecos_{corto}"] = np.isnan(m).sum(axis=1)
        # Momento del mercado catalán en ese origen (mediana de todos los municipios): común a todos
        f[f"mercado_var_anual_{corto}"] = np.nanmedian(f[f"var_anual_{corto}"])
    f["provincia"] = f.index.str[:2]
    return f


def filas(series: dict, trimestres: pd.PeriodIndex, origen: pd.Period, variable: str,
          h_max: int, limite: pd.Period | None) -> pd.DataFrame:
    """Una fila por municipio y horizonte h: variables en el origen y objetivo = valor(origen+h) - nivel base.
    `limite` = último trimestre objetivo permitido (no se crean filas con objetivo posterior)."""
    f = resumen_origen(series, trimestres, origen)
    f = f[f["huecos_r"] <= 2]  # al menos 6 de 8 trimestres con dato
    base = f["base_r" if variable == "log_renta" else "base_c"]
    out = []
    for h in range(1, h_max + 1):
        q = origen + h
        if q > trimestres[-1] or (limite is not None and q > limite):
            break
        d = f.copy()
        d["h"] = h
        d["trimestre_objetivo"] = q.quarter
        d["ley_2020_en_objetivo"] = int(pd.Period("2020Q4", "Q") <= q <= pd.Period("2022Q1", "Q"))
        d["origen"] = str(origen)
        d["periodo_objetivo"] = str(q)
        d["real"] = series[variable][q].reindex(d.index).to_numpy()
        d["base"] = base.to_numpy()
        d["objetivo"] = d["real"] - d["base"]
        out.append(d)
    return pd.concat(out) if out else pd.DataFrame()


def conjunto_entrenamiento(series, trimestres, variable, corte: pd.Period) -> pd.DataFrame:
    """Todos los orígenes posibles con objetivo <= corte. Nada posterior al corte entra en el modelo."""
    partes = [filas(series, trimestres, o, variable, H_MAX, corte)
              for o in pd.period_range(PRIMER_ORIGEN, corte - 1, freq="Q")]
    d = pd.concat([p for p in partes if len(p)])
    return d[d["objetivo"].notna()]


# --------------------------------------------------------------------------------------------- Modelos
NUM = ["h", "var_anual_r", "pendiente_r", "volatilidad_r", "base_r", "var_anual_c", "pendiente_c",
       "volatilidad_c", "base_c", "mercado_var_anual_r", "mercado_var_anual_c", "ley_2020_en_objetivo"]
CAT = ["provincia", "trimestre_objetivo"]


def _con_interacciones(d: pd.DataFrame) -> pd.DataFrame:
    X = d[NUM + CAT].copy()
    # La previsión de un cambio crece con el horizonte: tendencia × h, cambio anual × h, mercado × h
    for c in ["pendiente_r", "var_anual_r", "pendiente_c", "var_anual_c", "mercado_var_anual_r", "mercado_var_anual_c"]:
        X[f"{c}_x_h"] = X[c] * X["h"]
    X[NUM] = X[NUM].fillna(0)
    return X


class Persistencia:
    """B0: sin cambios. Prevé que cada municipio sigue en su nivel medio del último año."""
    nombre = "B0 · Persistencia"

    def fit(self, d, variable):
        return self

    def predict(self, d):
        return np.zeros(len(d))


class TendenciaPropia:
    """B1: prolonga en línea recta la tendencia de los últimos 8 trimestres de cada municipio.
    Es lo que haría un analista con una hoja de cálculo."""
    nombre = "B1 · Tendencia propia"

    def fit(self, d, variable):
        self.col = "pendiente_r" if variable == "log_renta" else "pendiente_c"
        return self

    def predict(self, d):
        # El nivel base es la media de los 4 últimos trimestres (centrada 1,5 trimestres antes del origen)
        return (d[self.col].fillna(0) * (d["h"] + 1.5)).to_numpy()


class Ridge:
    """M1: regresión lineal regularizada con todas las variables del origen e interacciones con el horizonte."""
    nombre = "M1 · Ridge"

    def fit(self, d, variable):
        X = _con_interacciones(d)
        num = [c for c in X.columns if c not in CAT]
        pre = ColumnTransformer([("num", StandardScaler(), num),
                                 ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])
        self.m = make_pipeline(pre, RidgeCV(alphas=np.logspace(-2, 4, 13))).fit(X, d["objetivo"])
        return self

    def predict(self, d):
        return self.m.predict(_con_interacciones(d))


class GBM:
    """M2: LightGBM con las mismas variables. Puede captar relaciones no lineales
    (p. ej. que los municipios que más subieron frenen más, o estacionalidad distinta por provincia)."""
    nombre = "M2 · LightGBM"

    def fit(self, d, variable):
        X = _con_interacciones(d)
        for c in CAT:
            X[c] = X[c].astype("category")
        self.cats = {c: X[c].cat.categories for c in CAT}
        self.m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=50,
                                   subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                                   random_state=SEED, verbose=-1).fit(X, d["objetivo"])
        return self

    def predict(self, d):
        X = _con_interacciones(d)
        for c in CAT:
            X[c] = pd.Categorical(X[c], categories=self.cats[c])
        return self.m.predict(X)


MODELOS = [Persistencia, TendenciaPropia, Ridge, GBM]


# --------------------------------------------------------------------------------------------- Métricas
def error_agregado(d: pd.DataFrame, pred: np.ndarray, info: pd.DataFrame, pesos: pd.Series) -> pd.DataFrame:
    """Error del conjunto de un grupo en cada trimestre: media ponderada por contratos de (real - previsto).
    Es el error que importa para el efecto de la ley, porque el efecto se mide sobre el grupo.
    `pesos` = contratos de cada municipio conocidos en el corte (ver pesos_en)."""
    t = d.assign(err=d["objetivo"].to_numpy() - pred, peso=pesos.reindex(d.index).to_numpy(),
                 grupo=info["grupo"].reindex(d.index).to_numpy())
    t = t[t["err"].notna()]
    return (t.groupby(["grupo", "periodo_objetivo"])
             .apply(lambda x: np.average(x["err"], weights=x["peso"])).rename("err").reset_index())


def backtest(info, series, trimestres) -> pd.DataFrame:
    """Para cada corte: entrena con objetivos <= corte y predice desde el corte hasta 2023T4."""
    detalle = []
    for variable in VARIABLES:
        for corte in CORTES_BACKTEST:
            entreno = conjunto_entrenamiento(series, trimestres, variable, corte)
            prueba = filas(series, trimestres, corte, variable, H_MAX, CORTE_FINAL)
            prueba = prueba[prueba["objetivo"].notna()]
            pesos = pesos_en(series, corte)
            for Modelo in MODELOS:
                m = Modelo().fit(entreno, variable)
                p = m.predict(prueba)
                e = prueba["objetivo"].to_numpy() - p
                agg = error_agregado(prueba, p, info, pesos)
                for h in sorted(prueba["h"].unique()):
                    k = prueba["h"].to_numpy() == h
                    q = str(corte + h)
                    a = agg[agg["periodo_objetivo"] == q].set_index("grupo")["err"]
                    detalle.append({
                        "variable": variable, "corte": str(corte), "h": int(h), "modelo": m.nombre,
                        "n_municipios": int(k.sum()),
                        # error típico de un municipio (en %, mediana de |real/previsto - 1|)
                        "error_municipio_mediano_pct": float(np.median(np.abs(np.expm1(e[k]))) * 100),
                        # error del grupo agregado (lo que se usará para medir el efecto), en %
                        **{f"error_grupo_{g.split(' ')[0]}{g.split(' ')[1] if g.startswith('ola') else ''}_pct":
                           float(np.expm1(a.get(g, np.nan)) * 100) for g in info["grupo"].unique()},
                    })
    return pd.DataFrame(detalle)


def main():
    OUT.mkdir(exist_ok=True)
    info, series, trimestres = cargar()
    print(f"Muestra principal: {len(info)} municipios · {info['grupo'].value_counts().to_dict()}")
    det = backtest(info, series, trimestres)
    det.round(3).to_csv(OUT / "03_backtest_detalle.csv", index=False)

    gcols = [c for c in det.columns if c.startswith("error_grupo")]
    res = det.assign(**{c: det[c].abs() for c in gcols}).groupby(["variable", "modelo"])[
        ["error_municipio_mediano_pct"] + gcols].mean()
    res["error_grupos_medio_pct"] = res[gcols].mean(axis=1)
    res.round(2).to_csv(OUT / "03_backtest_resumen.csv")
    print("\nBacktest (media sobre cortes 2021T2–2022T4 y horizontes hasta 2023T4):")
    print(res.round(2).to_string())

    # Elección: menor error del grupo agregado (es lo que se usa para medir el efecto); a igualdad, el más sencillo
    elegido = {}
    for v in VARIABLES:
        r = res.loc[v, "error_grupos_medio_pct"]
        mejor = r.min()
        elegido[v] = next(m.nombre for m in [M() for M in MODELOS] if r[m.nombre] - mejor < 0.25)
        print(f"Elegido para {VARIABLES[v]}: {elegido[v]}")
    json.dump({"modelo_elegido": elegido, "corte_final": str(CORTE_FINAL), "cortes_backtest": [str(c) for c in CORTES_BACKTEST],
               "criterio": "menor error medio del grupo agregado en el backtest; si otro más sencillo está a menos "
                           "de 0,25 puntos, se elige el más sencillo (orden: B0, B1, M1, M2)",
               "resumen": res.round(3).reset_index().to_dict(orient="records")},
              open(OUT / "03_resultados.json", "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
