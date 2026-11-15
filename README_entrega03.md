# Entrega 03 · Cómo reproducirla

```bash
pip install pandas pyarrow numpy scikit-learn lightgbm statsmodels matplotlib
python src/preparacion_datos.py   # Entrega 02: descarga el CSV del Incasòl y genera el Gold
python src/modelado.py            # Apartado 3: backtests y elección del modelo (~10 s)
python src/evaluacion.py          # Apartados 4 y 5: previsión congelada en 2023T4, efectos y salida (~4 min)
```

Documento de la entrega: `docs/entregas/03_machine_learning.md`

## Qué hay en el repositorio

| Ruta | Contenido |
|---|---|
| `src/modelado.py` | Baseline (persistencia, tendencia propia) y modelos de ML (Ridge, LightGBM); backtests sin ver el futuro y elección del modelo |
| `src/evaluacion.py` | Previsión "sin ley" congelada en 2023T4, comparación con 2024–2026, placebos, *bootstrap*, DiD clásico y salida por municipio |
| `results/03_*` | Resultados de los backtests y modelo elegido |
| `results/04_*` | Efectos estimados, placebos, errores por segmento y robustez con la muestra pre-tratamiento (`04_robustez_muestra_pre.json`) |
| `results/05_*` | Salida para el producto (por municipio y ejemplo JSON) |
| `results/figuras/` | Real frente a previsto sin ley, renta y contratos |

Todos los resultados se regeneran con los comandos de arriba (semilla fija 42).
