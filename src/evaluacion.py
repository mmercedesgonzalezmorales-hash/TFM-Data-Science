"""
Entrega 03 · Machine Learning — Apartados 4 y 5: previsión congelada en 2023T4 y comparación con la realidad

1. Entrena el modelo elegido en el apartado 3 SOLO con datos hasta 2023T4 (antes de la ola 1).
2. Prevé, para cada municipio, la renta y los contratos de 2024T1 a 2026T2 "como si no hubiera ley".
3. Compara la previsión con lo que pasó de verdad:
     - efecto sin ajustar = real − previsto en los municipios tensionados
     - efecto ajustado    = (real − previsto en tensionados) − (real − previsto en los 29 de control)
     - contraste extra    = ola 1 frente a ola 2 en 2024T2–2024T3, cuando la ola 2 aún no tenía la ley
4. Mide cuánto "efecto" sale por puro ruido repitiendo lo mismo en los backtests anteriores a la ley (placebos)
   y la incertidumbre por la muestra de municipios (bootstrap).
5. Contraste con el método clásico (diferencias en diferencias con efectos fijos).
6. Genera la salida por municipio que consumirá el producto.

Uso (desde la raíz del repositorio):
    python src/evaluacion.py      # requiere haber ejecutado antes src/modelado.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modelado as M  # noqa: E402

OUT, FIG = M.OUT, M.OUT / "figuras"
CORTE = M.CORTE_FINAL
TRANSICION = {1: pd.Period("2024Q1", "Q"), 2: pd.Period("2024Q4", "Q")}   # trimestre de entrada en vigor
PRIMER_TRATADO = {1: pd.Period("2024Q2", "Q"), 2: pd.Period("2025Q1", "Q")}
GRUPOS = {0: "control", 1: "ola 1", 2: "ola 2"}
B = 2000
rng = np.random.default_rng(M.SEED)


def nombre_a_clase(nombre: str):
    return next(C for C in M.MODELOS if C.nombre == nombre)


def a_nivel(variable: str, x):
    return np.exp(x) if variable == "log_renta" else np.expm1(x)


# --------------------------------------------------------------------------------------------- Previsión
def prever(info, series, trimestres, variable, Modelo, corte=CORTE, limite=None):
    """Entrena con objetivos <= corte y prevé desde el corte. Devuelve una fila por municipio y trimestre.
    Los pesos de cada municipio son sus contratos de los 4 trimestres hasta el corte (en el corte final,
    2023T1–2023T4), así que tampoco usan información posterior."""
    entreno = M.conjunto_entrenamiento(series, trimestres, variable, corte)
    prueba = M.filas(series, trimestres, corte, variable, M.H_MAX, limite)
    m = Modelo().fit(entreno, variable)
    p = prueba.assign(previsto_log=prueba["base"] + m.predict(prueba))
    p["brecha"] = p["real"] - p["previsto_log"]          # log(real / previsto)
    p["ola"] = info["ola"].reindex(p.index).to_numpy()
    p["peso"] = M.pesos_en(series, corte).reindex(p.index).to_numpy()
    return p


def agregar(p: pd.DataFrame) -> pd.DataFrame:
    """Brecha media de cada grupo y trimestre, ponderada por contratos de 2023."""
    q = p[p["brecha"].notna()]
    return (q.groupby(["ola", "periodo_objetivo"])
             .apply(lambda x: np.average(x["brecha"], weights=x["peso"])).unstack(0))


def efectos(agr: pd.DataFrame) -> dict:
    """Efecto medio de cada ola en sus trimestres tratados (en log), sin ajustar y ajustado por el control."""
    out = {}
    for ola in (1, 2):
        post = [q for q in agr.index if pd.Period(q, "Q") >= PRIMER_TRATADO[ola]]
        out[f"ola{ola}_sin_ajustar"] = agr.loc[post, ola].mean()
        out[f"ola{ola}_ajustado_control"] = (agr.loc[post, ola] - agr.loc[post, 0]).mean()
    v = [q for q in agr.index if PRIMER_TRATADO[1] <= pd.Period(q, "Q") < TRANSICION[2]]
    out["ola1_ajustado_ola2"] = (agr.loc[v, 1] - agr.loc[v, 2]).mean() if v else np.nan
    return out


def bootstrap(p: pd.DataFrame) -> dict:
    """Remuestrea municipios dentro de cada grupo: ¿cuánto cambiaría el efecto con otra muestra de municipios?"""
    unidades = {o: p.index[p["ola"] == o].unique().to_numpy() for o in (0, 1, 2)}
    res = []
    for _ in range(B):
        idx = np.concatenate([rng.choice(u, len(u)) for u in unidades.values()])
        res.append(efectos(agregar(p.loc[idx])))
    r = pd.DataFrame(res)
    return {k: (float(r[k].quantile(0.025)), float(r[k].quantile(0.975))) for k in r.columns}


def placebos(info, series, trimestres, variable, Modelo) -> pd.DataFrame:
    """Mismo cálculo en los cortes del backtest (sin ley): el 'efecto' que sale debería ser 0.
    Ventana equivalente: los 6 trimestres siguientes al corte (sin pasar de 2023T4)."""
    filas = []
    for corte in M.CORTES_BACKTEST:
        p = prever(info, series, trimestres, variable, Modelo, corte, limite=M.CORTE_FINAL)
        p = p[p["h"].between(2, 7)]
        agr = agregar(p)
        filas.append({"corte": str(corte), "ola1_sin_ajustar": agr[1].mean(), "ola2_sin_ajustar": agr[2].mean(),
                      "ola1_ajustado_control": (agr[1] - agr[0]).mean(),
                      "ola2_ajustado_control": (agr[2] - agr[0]).mean(),
                      "ola1_ajustado_ola2": (agr[1] - agr[2]).mean()})
    return pd.DataFrame(filas)


def residuos_municipio(info, series, trimestres, variable, Modelo) -> pd.DataFrame:
    """Cuantiles 10 % / 90 % del error de un municipio por horizonte, sacados de los backtests (sin ley).
    Dan el rango probable de la previsión de cada municipio."""
    e = []
    for corte in M.CORTES_BACKTEST:
        p = prever(info, series, trimestres, variable, Modelo, corte, limite=M.CORTE_FINAL)
        e.append(p[["h", "brecha"]].dropna())
    e = pd.concat(e)
    q = e.groupby("h")["brecha"].quantile([0.1, 0.9]).unstack()
    # Horizontes sin backtest (más allá de lo observable antes de la ley): se usa el del mayor horizonte disponible
    return q.reindex(range(1, M.H_MAX + 1)).ffill()


# --------------------------------------------------------------------------------------------- Contraste clásico
def did_clasico(variable: str, muestra: str = "muestra_principal") -> dict:
    """Diferencias en diferencias con efectos fijos de municipio y trimestre (errores agrupados por municipio).
    Excluye los trimestres de transición y el trimestre anómalo de la fuente."""
    g = pd.read_parquet(M.GOLD)
    g = g[g[muestra] & ~g["trimestre_transicion"] & ~g["trimestre_anomalo_fuente"]].dropna(subset=[variable])
    g["tratado"] = g["post"].astype(int)
    r = smf.wls(f"{variable} ~ tratado + C(codigo_ine) + C(periodo)", data=g,
                weights=g.groupby("codigo_ine")["contratos"].transform("mean")).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(g["codigo_ine"])[0]})
    b, se = r.params["tratado"], r.bse["tratado"]
    return {"efecto_log": b, "ic95": (b - 1.96 * se, b + 1.96 * se), "p_valor": r.pvalues["tratado"]}


# --------------------------------------------------------------------------------------------- Gráficos
def grafico(variable, series, info, p, nombre_fichero):
    FIG.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=False)
    hist = series[variable]
    for ax, ola in zip(axes, (1, 2, 0)):
        u = info.index[info["ola"] == ola]
        w = info.loc[u, "peso"]
        real = hist.loc[u].apply(lambda col: np.average(col.dropna(), weights=w[col.dropna().index])
                                 if col.notna().any() else np.nan)
        pp = p[p["ola"] == ola].dropna(subset=["previsto_log"])
        prev = pp.groupby("periodo_objetivo").apply(lambda x: np.average(x["previsto_log"], weights=x["peso"]))
        real = real.dropna()  # 2026T1 sin renta en la fuente: la línea une 2025T4 con 2026T2
        x_real = [q.to_timestamp() for q in real.index]
        ax.plot(x_real, a_nivel(variable, real), color="#222", lw=1.6, label="Real")
        ax.plot([pd.Period(q, "Q").to_timestamp() for q in prev.index], a_nivel(variable, prev),
                color="#c0392b", lw=1.6, ls="--", label="Previsto sin ley (modelo congelado en 2023T4)")
        ax.axvline(pd.Period("2023Q4", "Q").end_time, color="#888", lw=0.8)
        if ola:
            ax.axvspan(TRANSICION[ola].start_time, pd.Timestamp("2026-06-30"), color="#f3d9d6", alpha=0.5, lw=0)
        ax.set_title({1: "Ola 1 (desde mar-2024)", 2: "Ola 2 (desde oct-2024)", 0: "Control (sin ley)"}[ola],
                     loc="left", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8)
    axes[0].set_ylabel(M.VARIABLES[variable] + (" (€/mes)" if variable == "log_renta" else " (media por municipio)"),
                       fontsize=9)
    axes[0].legend(frameon=False, fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG / nombre_fichero, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------------------------- Main
def pct(x):
    return float(np.expm1(x) * 100)


def robustez_muestra(elegido: dict) -> dict:
    """Repite la estimación con la muestra alternativa de la Entrega 02 (municipios con renta en >= 90 %
    de los trimestres de 2019T1–2023T4, sin mirar después de la ley). Mismo modelo y mismo procedimiento."""
    original = M.MUESTRA
    M.MUESTRA = "muestra_pre_tratamiento"
    try:
        info, series, trimestres = M.cargar()
        out = {"municipios_por_grupo": info["grupo"].value_counts().to_dict()}
        for variable in M.VARIABLES:
            Modelo = nombre_a_clase(elegido[variable])
            p = prever(info, series, trimestres, variable, Modelo)
            ef, ic = efectos(agregar(p)), bootstrap(p)
            pl = placebos(info, series, trimestres, variable, Modelo)
            did = did_clasico(variable, "muestra_pre_tratamiento")
            out[variable] = {
                "efectos_pct": {k: {"estimacion": round(pct(v), 2),
                                    "ic95_bootstrap": [round(pct(ic[k][0]), 2), round(pct(ic[k][1]), 2)],
                                    "placebos_pct": [round(pct(x), 2) for x in pl[k]]} for k, v in ef.items()},
                "did_clasico_pct": {"estimacion": round(pct(did["efecto_log"]), 2),
                                    "ic95": [round(pct(did["ic95"][0]), 2), round(pct(did["ic95"][1]), 2)]},
            }
        return out
    finally:
        M.MUESTRA = original


def main():
    info, series, trimestres = M.cargar()
    elegido = json.load(open(OUT / "03_resultados.json"))["modelo_elegido"]
    resumen, por_municipio = {}, []

    for variable, etiqueta in M.VARIABLES.items():
        Modelo = nombre_a_clase(elegido[variable])
        print(f"\n=== {etiqueta} · modelo {Modelo.nombre} congelado en {CORTE} ===")
        p = prever(info, series, trimestres, variable, Modelo)
        agr = agregar(p)
        agr.columns = [GRUPOS[c] for c in agr.columns]
        tabla_q = agr.apply(np.expm1) * 100
        tabla_q.round(2).to_csv(OUT / f"04_brecha_por_trimestre_{variable}.csv")
        print("Real frente a previsto, por grupo y trimestre (%):")
        print(tabla_q.round(1).to_string())

        ef = efectos(agregar(p))
        ic = bootstrap(p)
        pl = placebos(info, series, trimestres, variable, Modelo)
        pl.round(4).to_csv(OUT / f"04_placebos_{variable}.csv", index=False)
        did = did_clasico(variable)

        # Robustez: el mismo efecto con los otros modelos
        robustez = {}
        for Otro in M.MODELOS:
            robustez[Otro.nombre] = {k: round(pct(v), 2) for k, v in efectos(agregar(
                prever(info, series, trimestres, variable, Otro))).items()}

        resumen[variable] = {
            "modelo": Modelo.nombre,
            "efectos_pct": {k: {"estimacion": round(pct(v), 2), "ic95_bootstrap": [round(pct(ic[k][0]), 2), round(pct(ic[k][1]), 2)],
                                "placebos_pct": [round(pct(x), 2) for x in pl[k]] if k in pl else None}
                            for k, v in ef.items()},
            "did_clasico_pct": {"estimacion": round(pct(did["efecto_log"]), 2),
                                "ic95": [round(pct(did["ic95"][0]), 2), round(pct(did["ic95"][1]), 2)],
                                "p_valor": round(float(did["p_valor"]), 4)},
            "robustez_otros_modelos_pct": robustez,
        }
        print("Efectos (%):")
        print(json.dumps(resumen[variable], ensure_ascii=False, indent=1))
        grafico(variable, series, info, p, f"04_real_vs_previsto_{variable}.png")

        # Por municipio: media de los trimestres tratados
        rq = residuos_municipio(info, series, trimestres, variable, Modelo)
        p = p.join(rq.rename(columns={0.1: "q10", 0.9: "q90"}), on="h")
        ctrl_q = agregar(p)[0]
        p["brecha_ajustada"] = p["brecha"] - p["periodo_objetivo"].map(ctrl_q)
        p["tratado"] = [o > 0 and pd.Period(q, "Q") >= PRIMER_TRATADO[o] for o, q in zip(p["ola"], p["periodo_objetivo"])]
        for cod, d in p.groupby(level=0):
            o = int(d["ola"].iloc[0])
            post = d[d["tratado"] if o else d["periodo_objetivo"].map(lambda q: pd.Period(q, "Q") >= PRIMER_TRATADO[1])]
            post = post.dropna(subset=["real"])
            if not len(post):
                continue
            ult = post.iloc[-1]
            por_municipio.append({
                "codigo_ine": cod, "municipio": info.loc[cod, "municipio"], "provincia": info.loc[cod, "provincia"],
                "grupo": GRUPOS[o], "variable": variable, "trimestres_comparados": len(post),
                "ultimo_trimestre": ult["periodo_objetivo"],
                "real_ultimo": round(float(a_nivel(variable, ult["real"])), 1),
                "previsto_sin_ley_ultimo": round(float(a_nivel(variable, ult["previsto_log"])), 1),
                "rango_previsto_min": round(float(a_nivel(variable, ult["previsto_log"] + ult["q10"])), 1),
                "rango_previsto_max": round(float(a_nivel(variable, ult["previsto_log"] + ult["q90"])), 1),
                "diferencia_media_pct": round(pct(post["brecha"].mean()), 2),
                "diferencia_ajustada_media_pct": round(pct(post["brecha_ajustada"].mean()), 2),
                "fuera_del_rango_ultimo": bool(not (ult["q10"] <= ult["brecha"] <= ult["q90"])),
                "contratos_2023": round(float(info.loc[cod, "peso"]), 1),
            })

    pm = pd.DataFrame(por_municipio)
    pm.to_csv(OUT / "05_efecto_por_municipio.csv", index=False)
    json.dump(resumen, open(OUT / "04_resultados.json", "w"), ensure_ascii=False, indent=2)

    # Robustez: la misma estimación con la muestra elegida solo con datos anteriores a la ley (Entrega 02)
    rob = robustez_muestra(elegido)
    json.dump(rob, open(OUT / "04_robustez_muestra_pre.json", "w"), ensure_ascii=False, indent=2)
    print("\nRobustez con la muestra pre-tratamiento:")
    print(json.dumps(rob, ensure_ascii=False, indent=1))

    # Errores: ¿acierta el modelo donde no hubo ley? ¿qué municipios se salen del rango?
    print("\nControl (sin ley): diferencia media real − previsto por municipio (%):")
    print(pm[pm.grupo == "control"].groupby("variable")["diferencia_media_pct"].describe().round(1).to_string())
    print("\nMunicipios cuyo último dato cae fuera del rango previsto (%), por grupo:")
    print((pm.groupby(["variable", "grupo"])["fuera_del_rango_ultimo"].mean() * 100).round(1).to_string())
    pm["tamano"] = pd.qcut(pm["contratos_2023"], 3, labels=["pequeño", "mediano", "grande"])
    seg = pm[pm.grupo != "control"].groupby(["variable", "grupo", "tamano"], observed=True)["diferencia_ajustada_media_pct"].median()
    seg.round(2).to_csv(OUT / "04_efecto_por_tamano.csv")
    print("\nDiferencia ajustada mediana por tamaño del municipio (%):")
    print(seg.round(1).to_string())
    seg2 = pm[pm.grupo != "control"].groupby(["variable", "provincia"])["diferencia_ajustada_media_pct"].agg(["median", "size"])
    seg2.round(2).to_csv(OUT / "04_efecto_por_provincia.csv")
    print(seg2.round(1).to_string())
    print("\nMayores municipios:")
    print(pm[pm.codigo_ine.isin(pm.nlargest(12, "contratos_2023").codigo_ine)].sort_values(
        ["variable", "contratos_2023"], ascending=[True, False])[[
        "municipio", "grupo", "variable", "real_ultimo", "previsto_sin_ley_ultimo", "rango_previsto_min",
        "rango_previsto_max", "diferencia_media_pct", "diferencia_ajustada_media_pct"]].to_string(index=False))

    # Ejemplo de salida para el producto: Barcelona
    bcn = pm[pm.municipio == "Barcelona"].set_index("variable")
    ejemplo = {
        "municipio": "Barcelona", "codigo_ine": "08019", "grupo": "ola 1 (zona tensionada desde 16/03/2024)",
        "ultimo_trimestre": bcn.loc["log_renta", "ultimo_trimestre"],
        "renta": {
            "real_eur_mes": bcn.loc["log_renta", "real_ultimo"],
            "prevista_sin_ley_eur_mes": bcn.loc["log_renta", "previsto_sin_ley_ultimo"],
            "rango_prevision_eur_mes": [bcn.loc["log_renta", "rango_previsto_min"], bcn.loc["log_renta", "rango_previsto_max"]],
            "diferencia_media_desde_la_ley_pct": bcn.loc["log_renta", "diferencia_media_pct"],
            "diferencia_ajustada_por_control_pct": bcn.loc["log_renta", "diferencia_ajustada_media_pct"],
        },
        "contratos": {
            "real_trimestre": bcn.loc["log_contratos", "real_ultimo"],
            "previstos_sin_ley": bcn.loc["log_contratos", "previsto_sin_ley_ultimo"],
            "rango_prevision": [bcn.loc["log_contratos", "rango_previsto_min"], bcn.loc["log_contratos", "rango_previsto_max"]],
            "diferencia_media_desde_la_ley_pct": bcn.loc["log_contratos", "diferencia_media_pct"],
            "diferencia_ajustada_por_control_pct": bcn.loc["log_contratos", "diferencia_ajustada_media_pct"],
        },
        "efecto_conjunto_ola": {v: resumen[v]["efectos_pct"]["ola1_ajustado_control"] for v in M.VARIABLES},
        "avisos": [
            "La previsión 'sin ley' es una estimación: el rango indica dónde habría caído en 8 de cada 10 casos.",
            "La diferencia frente a lo previsto es una estimación, no una medida directa del efecto de la ley: "
            "si el municipio ya seguía una tendencia distinta antes de 2024, parte de la diferencia puede venir de ahí.",
            "Los municipios tensionados ya subían más que los de control antes de 2024 (ver placebos).",
            "Datos de fianzas del Incasòl: contratos nuevos, no el parque de alquiler completo; sin alquiler de temporada.",
        ],
    }
    json.dump(ejemplo, open(OUT / "05_ejemplo_salida.json", "w"), ensure_ascii=False, indent=2)
    print("\nEjemplo de salida → results/05_ejemplo_salida.json")
    print(json.dumps(ejemplo, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
