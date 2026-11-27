"""
Entrega 04 — Datos para el mockup del frontal.

Lee las salidas de la Entrega 03 (carpeta results/) y escribe
docs/entregas/mockup/datos_mockup.js, que carga el mockup HTML
(docs/entregas/mockup/04_mockup.html). No recalcula nada: el frontal
solo muestra lo que ya producen src/evaluacion.py y src/modelado.py.

Uso:
    python src/frontal_mockup.py
"""
import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RES = RAIZ / "results"
SALIDA = RAIZ / "docs" / "entregas" / "mockup" / "datos_mockup.js"

# Tendencia previa de los contratos nuevos registrados (cambio medio 2021-2023),
# tal y como la describe la Entrega 02 (apartado 4, "Para qué se usará").
TENDENCIA_PREVIA_CONTRATOS = {"periodo": "2021–2023", "ola 1": -16, "ola 2": -13, "control": -7}


def main():
    pm = pd.read_csv(RES / "05_efecto_por_municipio.csv", dtype={"codigo_ine": str})
    resumen = json.load(open(RES / "04_resultados.json", encoding="utf-8"))
    ejemplo = json.load(open(RES / "05_ejemplo_salida.json", encoding="utf-8"))

    municipios = {}
    for _, f in pm.iterrows():
        m = municipios.setdefault(f.codigo_ine, {
            "nombre": f.municipio, "provincia": f.provincia, "grupo": f.grupo,
            "contratos_2023": round(float(f.contratos_2023), 1),
        })
        clave = "renta" if f.variable == "log_renta" else "contratos"
        m[clave] = {
            "ultimo_trimestre": f.ultimo_trimestre,
            "real": f.real_ultimo, "previsto": f.previsto_sin_ley_ultimo,
            "rango": [f.rango_previsto_min, f.rango_previsto_max],
            "dif_media": f.diferencia_media_pct,
            "dif_ajustada": f.diferencia_ajustada_media_pct,
            "fuera_rango": bool(f.fuera_del_rango_ultimo),
            "trimestres": int(f.trimestres_comparados),
        }

    series = {}
    for var, clave in [("log_renta", "renta"), ("log_contratos", "contratos")]:
        b = pd.read_csv(RES / f"04_brecha_por_trimestre_{var}.csv")
        series[clave] = {
            "periodos": b.periodo_objetivo.tolist(),
            **{g: b[g].tolist() for g in ["ola 1", "ola 2", "control"]},
        }

    # Renta (o contratos) observada frente a la estimada sin ley, por grupo y trimestre, en nivel
    nivel = {}
    for var, clave in [("log_renta", "renta"), ("log_contratos", "contratos")]:
        sg = pd.read_csv(RES / f"04_serie_grupo_{var}.csv")
        nivel[clave] = {"periodos": sorted(sg.periodo.unique().tolist())}
        for g, d in sg.groupby("grupo"):
            d = d.set_index("periodo").reindex(nivel[clave]["periodos"])
            nivel[clave][g] = {"real": [None if pd.isna(v) else v for v in d.real],
                               "previsto": [None if pd.isna(v) else v for v in d.previsto_sin_ley]}

    grupo = {}
    for var, clave in [("log_renta", "renta"), ("log_contratos", "contratos")]:
        e = resumen[var]["efectos_pct"]
        grupo[clave] = {
            ola: {
                "estimacion": e[f"{ola}_ajustado_control"]["estimacion"],
                "ic95": e[f"{ola}_ajustado_control"]["ic95_bootstrap"],
                "placebos": [min(e[f"{ola}_ajustado_control"]["placebos_pct"]),
                             max(e[f"{ola}_ajustado_control"]["placebos_pct"])],
            }
            for ola in ["ola1", "ola2"]
        }
        # Ola 1 frente a ola 2: solo 2024T2-2024T3, cuando la ola 2 aún no tenía la medida
        c = e["ola1_ajustado_ola2"]
        grupo[clave]["ola1_vs_ola2"] = {
            "estimacion": c["estimacion"], "ic95": c["ic95_bootstrap"],
            "placebos": [min(c["placebos_pct"]), max(c["placebos_pct"])],
            "periodos": ["2024Q2", "2024Q3"],
        }

    datos = {
        "municipios": municipios, "series": series, "nivel": nivel, "grupo": grupo,
        "avisos": ejemplo["avisos"],
        "tendencia_previa_contratos": TENDENCIA_PREVIA_CONTRATOS,
        "fuente": "Fianzas del Incasòl · modelo Ridge congelado en 2023T4 (Entrega 03)",
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("window.DATOS = " + json.dumps(datos, ensure_ascii=False) + ";\n",
                      encoding="utf-8")
    print(f"{SALIDA.relative_to(RAIZ)}: {len(municipios)} municipios")


if __name__ == "__main__":
    main()
