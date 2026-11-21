# Entrega 02 · Cómo reproducirla

```bash
pip install pandas pyarrow matplotlib            # dependencias
python src/preparacion_datos.py                  # descarga el CSV del Incasòl y genera Silver y Gold
# o, con el CSV ya en data/raw/incasol_fianzas_municipi.csv:
python src/preparacion_datos.py --offline
```

Documento de la entrega: `docs/entregas/02_datos_y_preparacion.md`
Notebook explicativo (ejecutado): `notebooks/02_preparacion_datos.ipynb`

## Qué se sube al repositorio y qué no

| Ruta | ¿Al repo? | Contenido |
|---|---|---|
| `src/preparacion_datos.py` | Sí | Pipeline Bronze → Silver → Gold |
| `notebooks/02_preparacion_datos.ipynb` | Sí | Recorrido paso a paso con comprobaciones |
| `data/referencia/municipios_tensionados.csv` | Sí | 271 municipios tensionados (BOE), con ola y fecha de efectos |
| `data/sample/` | Sí | Muestras pequeñas de Bronze y Gold |
| `data/raw/`, `data/silver/`, `data/gold/` | No (`.gitignore`) | Se regeneran con el script |

## Fuentes

- Incasòl, *Preu mitjà del lloguer d'habitatges per municipi* — Departament de Territori, Habitatge i Transició Ecològica, Generalitat de Catalunya. Portal de datos abiertos, dataset `qww9-bvhh`.
- BOE-A-2024-5214 (15/03/2024) y BOE-A-2024-20576 (09/10/2024): relación de zonas de mercado residencial tensionado.
