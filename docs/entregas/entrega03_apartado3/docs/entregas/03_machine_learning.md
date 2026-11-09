# Entrega 03 — Machine Learning

## 3. Baseline y selección de modelos

**Punto de partida:** el Gold de la Entrega 02 (`data/gold/viviendas_gold.parquet`, 75.301 viviendas × 43 columnas, generado con `python src/preparacion_datos.py`).
**Código:** `src/modelado.py`, que reproduce todos los números de este apartado con `python src/modelado.py`.
**Resultados:** carpeta `results/` (`03_resumen_cv.csv`, `03_validacion_temporal_T3.csv`, `03_resultados.json`).

El modelo estima el **precio de oferta** de una vivienda a partir de sus características y su ubicación. Se entrena sobre `log_precio`, porque el precio es muy asimétrico (de 28.000 € a 5,5 M€) y los errores relativos importan más que los absolutos. Todas las métricas se dan en euros y en porcentaje, que es lo que entenderá el usuario.

### 3.1 Cómo se comparan

La comparación se hace solo con los anuncios de **T1–T3 de 2018** (44.091 viviendas). El **T4** (31.210) queda apartado y no se usa para elegir nada: es el test del apartado 4.

Hay dos comprobaciones:

1. **Validación cruzada agrupada de 5 folds.** En el Gold, casi 3 de cada 10 anuncios comparten barrio, superficie, habitaciones, baños, planta y antigüedad con otro: es la misma vivienda publicada por otra agencia o en otro trimestre, con distinto identificador. Con un `KFold` normal, una copia caería en entrenamiento y otra en validación, y el modelo "se sabría" la respuesta. Lo comprobamos: el modelo más grande pasaba de un 9,4 % a un 8,2 % de error mediano solo por eso. Por eso se usa `GroupKFold` y todas las copias de una vivienda van al mismo fold.
2. **Comprobación temporal.** Se entrena con T1–T2 y se valida en T3. Imita el uso real: valorar anuncios posteriores a los que vio el modelo.

Dentro de cada fold se calcula todo lo que se aprende de los datos (medianas por barrio, escalado, imputación de nulos, categorías) solo con la parte de entrenamiento.

**Métricas** (detalle en el apartado 4):
- **MdAPE:** error porcentual mediano. Es la métrica principal, la que usan los AVM comerciales.
- **MAE:** error medio en euros.
- **% de viviendas dentro de ±10 % y ±20 %** del precio real: cuántas valoraciones serían "aceptables".

### 3.2 Referencias (baseline)

| | Qué hace | Por qué |
|---|---|---|
| **B0 · Mediana global** | Asigna a todas las viviendas la mediana de precio del entrenamiento (250.000 €). | Suelo mínimo: cualquier modelo tiene que superarlo con mucho. |
| **B1 · €/m² del barrio × m²** | Mediana del €/m² del barrio multiplicada por la superficie. Si el barrio tiene menos de 10 anuncios, usa la del distrito. | Es la regla que aplicaría un tasador o un usuario con el portal abierto (método de comparación). **Es la referencia de verdad:** el ML solo aporta valor si la mejora claramente. |

### 3.3 Alternativas de ML

| | Qué hace | Por qué |
|---|---|---|
| **M1 · Regresión Ridge** | Lineal regularizada sobre `log_precio`, con *one-hot* de barrio, distrito, estado, equipamiento y exterior/interior. | Sencilla e interpretable: cada coeficiente es un % de precio (p. ej. lo que suma tener ascensor). Mide cuánto se gana al pasar de una regla a un modelo con todas las variables. |
| **M2 · LightGBM** | Árboles de *gradient boosting* sobre `log_precio`, con lat/lon y barrio como categoría. | El precio tiene no linealidades e interacciones que un modelo lineal no capta: el ascensor vale más en un 5.º que en un bajo, y la terraza no vale lo mismo en Salamanca que en Villaverde. Es el estándar en datos tabulares y entrena en segundos. |

LightGBM se probó con tres tamaños: pequeño (15 hojas), medio (63) y grande (255). No hubo búsqueda exhaustiva de hiperparámetros, porque no se valora la complejidad por sí misma y la diferencia entre tamaños ya es pequeña.

Las entradas son las 35 variables del Gold que el usuario conoce al pedir la valoración (características, edificio, catastro y ubicación). Se excluyen `precio_m2` (es el objetivo con otra forma), `n_apariciones` (cuántos trimestres estuvo publicado el anuncio; solo se sabe después) y los identificadores. La justificación completa está en el apartado 2.

### 3.4 Resultados

**Validación cruzada agrupada (T1–T3, media de 5 folds)**

| Modelo | MdAPE | MAE | ±10 % | ±20 % |
|---|---:|---:|---:|---:|
| B0 · Mediana global | 50,8 % | 218.081 € | 8,9 % | 18,7 % |
| B1 · €/m² del barrio × m² | 15,6 % | 73.135 € | 33,5 % | 61,2 % |
| M1 · Ridge | 12,2 % | 61.962 € | 42,2 % | 71,8 % |
| M2a · LightGBM pequeño | 10,7 % | 53.706 € | 47,4 % | 76,9 % |
| **M2b · LightGBM medio** | **9,9 %** | **49.560 €** | **50,6 %** | **79,5 %** |
| M2c · LightGBM grande | 9,4 % | 47.878 € | 52,3 % | 80,5 % |

La desviación entre folds es pequeña (MdAPE ±0,06–0,24 puntos), así que el orden entre modelos es estable.

**Comprobación temporal (entrena T1–T2, valida T3)**

| Modelo | MdAPE | MAE | ±10 % | ±20 % |
|---|---:|---:|---:|---:|
| B1 · €/m² del barrio × m² | 15,5 % | 70.105 € | 33,5 % | 62,0 % |
| M1 · Ridge | 12,4 % | 59.897 € | 41,9 % | 72,3 % |
| M2a · LightGBM pequeño | 10,9 % | 52.956 € | 46,6 % | 76,6 % |
| **M2b · LightGBM medio** | **10,1 %** | **49.118 €** | **49,7 %** | **79,0 %** |
| M2c · LightGBM grande | 9,7 % | 47.729 € | 51,1 % | 79,3 % |

Las dos comprobaciones dan el mismo orden y cifras parecidas. Eso indica que la CV agrupada no es optimista.

### 3.5 Qué modelo pasa al apartado 4

- **El ML sí aporta frente a la regla del tasador.** LightGBM medio reduce el error mediano del 15,6 % al 9,9 % (un 37 % menos) y pasa del 33 % al 51 % de viviendas valoradas dentro de ±10 %. En euros, el error medio baja unos 23.600 € por vivienda.
- **Ridge ya mejora bastante a B1** (12,2 %). Es una alternativa razonable si hiciera falta máxima interpretabilidad.
- **Se elige LightGBM medio (M2b) y no el grande.** La regla fijada de antemano es quedarse con la configuración más sencilla que esté a menos de 0,5 puntos de MdAPE de la mejor en las dos comprobaciones. El grande gana 0,5 puntos en CV y 0,3 en la temporal, pero tarda casi 4 veces más en entrenar y tiene 4 veces más hojas por árbol, con más riesgo de memorizar copias de anuncios que el agrupado no detecte.

El modelo elegido se evalúa una sola vez sobre el T4 apartado (apartado 4), junto con B1 como referencia.

### 3.6 Reproducibilidad

```bash
pip install pandas numpy pyarrow rdata shapely scikit-learn lightgbm
python src/preparacion_datos.py   # Entrega 02: genera el Gold
python src/modelado.py            # Entrega 03: este apartado (~4 min)
```

Semilla fija (`42`) y versiones probadas: pandas 3.0.5, scikit-learn 1.9.1 y LightGBM 4.7.0.
