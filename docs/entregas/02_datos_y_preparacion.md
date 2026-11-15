# Entrega 02 · Datos y preparación

## 0. Reorientación del proyecto respecto a la Entrega 01

En la Entrega 01 se propuso un modelo de valoración automática de viviendas (AVM) para el mercado inmobiliario de Madrid. Al analizar las fuentes disponibles en esta fase, comprobamos que el único conjunto de datos abierto con información a nivel de vivienda individual (*idealista18*) corresponde a 2018. Por ello no recoge la fuerte subida de precios registrada entre 2022 y 2025, y un modelo entrenado con él valoraría las viviendas a precios desfasados. Además, una exploración preliminar indicó que las características de los barrios en 2018 no permitían anticipar qué zonas se revalorizarían más, lo que apunta a que los factores relevantes son posteriores.

Ante esto, mantenemos el sector y el objetivo de aportar valor al análisis del mercado de la vivienda, pero reorientamos la pregunta de *cuánto vale una vivienda* a *qué explica la evolución de los precios*. En concreto, aprovechamos un experimento natural: la declaración de zonas de mercado residencial tensionado en Cataluña en 2024 (Ley 12/2023, por el derecho a la vivienda), que limitó las rentas del alquiler en unos municipios y no en otros, ni en la Comunidad de Madrid. Esto permite comparar zonas reguladas y no reguladas con métodos de inferencia causal (diferencias en diferencias), usando datos administrativos reales, abiertos y actualizados, como el registro de fianzas del Incasòl. Así se combina el enfoque predictivo de la propuesta inicial con un análisis explicativo de mayor interés práctico y social.

**Pregunta del proyecto:** ¿qué efecto tuvo la declaración de zonas tensionadas sobre el **precio** y la **oferta** del alquiler en Cataluña? Como contraste complementario, ¿cómo evolucionó el alquiler en Madrid, donde no se aplicó?

## 1. Qué datos necesita el producto

**Unidad de observación:** un municipio catalán en un trimestre (por ejemplo, *Girona, 2024T3*).

**Imprescindibles:**

- **Renta media de los contratos nuevos** (€/mes). Es la variable de precio.
- **Número de contratos nuevos.** Es el indicador de oferta: si la regulación retira pisos del mercado, debería caer.
- **Si el municipio está declarado tensionado y desde cuándo.** Es la variable de tratamiento.

**Deseables:**

- Población y renta de los hogares por municipio, para controlar diferencias de tamaño y nivel económico.
- Oferta de alquiler de temporada y de pisos turísticos, por el posible desvío de viviendas hacia esos usos.
- Para la comparativa con Madrid: precio de oferta del alquiler por distrito en Madrid y en Barcelona, de una misma fuente.

**Granularidad e histórico:** datos trimestrales y varios años antes y después de 2024. El modelo de diferencias en diferencias necesita un periodo previo largo para comprobar que los grupos evolucionaban igual antes de la norma. Con este dataset tenemos 5 años antes (2019–2023) y 2 después (2024–2026T2).

## 2. Fuentes reales y viabilidad

**Fuente principal: registro de fianzas de alquiler del Incasòl** ("Preu mitjà del lloguer d'habitatges per municipi", Generalitat de Catalunya).

- **Qué contiene:** todos los contratos de alquiler cuya fianza se deposita en el Incasòl, que es obligatorio. Por eso es prácticamente censal. Para cada municipio y periodo da el número de contratos nuevos y su renta media mensual.
- **Acceso:** descarga directa en CSV desde el portal de datos abiertos de la Generalitat (`analisi.transparenciacatalunya.cat`, dataset `qww9-bvhh`). El script descarga el fichero completo y registra su huella SHA-256.
- **Volumen:** 47.541 filas, unos 4,3 MB, 942 municipios.
- **Cobertura:** de 2007 a 2026T2. Hasta 2018 los datos son anuales; desde 2019, trimestrales.
- **Actualización:** trimestral. La instantánea usada en esta entrega se descargó el 15/11/2026.
- **Estabilidad:** alta. Es una estadística oficial que se publica desde hace más de 15 años.

**Fuente de tratamiento: relación oficial de municipios tensionados (BOE).**

- **Ola 1:** 140 municipios, con efectos desde el **16/03/2024** (BOE-A-2024-5214; Resolución TER/800/2024).
- **Ola 2:** 131 municipios, con efectos desde el **10/10/2024** (BOE-A-2024-20576; Resolución TER/2408/2024).
- **Lista:** transcrita a `data/referencia/municipios_tensionados.csv` y cruzada por nombre con los códigos INE del Incasòl. Cruzan los 271 municipios.

**Fuente complementaria (fase siguiente), para la comparativa Madrid–Barcelona:** informes públicos de precio del alquiler por distrito de idealista (sala de prensa). Son mensuales, desde 2018, y se publican para las dos ciudades. Son precios de oferta, no de contratos firmados, así que esta parte se planteará como contraste descriptivo y no como estimación causal.

**Alternativas si una fuente clave no estuviera disponible:**

- **Para Cataluña:** el índice SERPAVI del Ministerio de Vivienda, basado en el IRPF. Cubre todos los municipios, pero es anual y llega con dos años de retraso.
- **Para Madrid:** el mismo SERPAVI, o los informes de alquiler de otros portales (Fotocasa).
- **Descartado:** hacer scraping de portales, porque choca con sus condiciones de uso.

## 3. Uso, privacidad y datos personales

**Licencia.** El Incasòl publica estos datos en el portal de datos abiertos de la Generalitat, que permite reutilizarlos libremente citando la fuente: *Departament de Territori, Habitatge i Transició Ecològica – Incasòl*. Citamos la fuente aquí, en el código y en el README. Las resoluciones del BOE son textos oficiales y pueden reproducirse libremente.

**Datos personales:** ninguno. El dataset solo contiene agregados por municipio y periodo. El propio Incasòl suprime la renta media cuando un municipio tiene muy pocos contratos y publica solo un tramo de precio, para que no se pueda identificar ningún contrato. No necesitamos ni pedimos datos a nivel de contrato.

**Minimización:** solo guardamos las variables que usa el análisis. En el repositorio se suben únicamente una muestra pequeña y la lista de municipios tensionados. El CSV completo se descarga con el script.

## 4. Del dato bruto al dato utilizable

El flujo completo está en `src/preparacion_datos.py` (`python src/preparacion_datos.py`) y se explica paso a paso en `notebooks/02_preparacion_datos.ipynb`.

```
Incasòl (CSV, 47.541 filas) ──► Bronze ──► Silver ──► Gold: panel municipio × trimestre (28.260 filas)
BOE (271 municipios) ──────────────────────┘ (tratamiento)
```

| Capa | Qué se hace | Resultado |
|---|---|---|
| **Bronze** | Se descarga el CSV completo y se guarda **sin tocar**. Se registran la URL, la fecha y el hash SHA-256 en `bronze_metadata.json`. | `data/raw/incasol_fianzas_municipi.csv` |
| **Silver** | Se convierten los números en formato español (`30.789` → 30789; `1.134,61` → 1134,61). Se rellena el código INE a 5 dígitos. Se separan los datos anuales (2007+) de los trimestrales (2019+) y se descartan los periodos acumulados (`gener-juny`, `gener-setembre`: 11.920 filas que se pueden reconstruir con los trimestres). Se marca la renta suprimida (20.947 filas, el 44 %). Se unifica el nombre de los 10 municipios que cambian de nombre. Se comprueban duplicados y valores imposibles (no hay ninguno). | `data/silver/fianzas_trimestral.parquet`, `fianzas_anual.parquet` |
| **Tratamiento** | Se cruza la lista del BOE con los códigos del Incasòl, normalizando los nombres (`la Bisbal d'Empordà` ↔ `Bisbal d'Empordà, la`). Si algún municipio no cruza, el script se detiene. | 271 municipios: 140 de la ola 1 y 131 de la ola 2 |
| **Gold** | Panel equilibrado de 942 municipios × 30 trimestres (2019T1–2026T2). Lleva las variables de resultado, el tratamiento, las marcas de calidad y la muestra principal. | `data/gold/panel_municipio_trimestre.parquet` + `informe_calidad.json` |

**Comprobaciones de calidad:**

- **Coherencia:** la suma de los cuatro trimestres coincide con el dato anual en el **99,97 %** de los 3.521 municipio-año comparados.
- **Anomalía de la fuente:** en **2026T1** falta la renta en casi todos los municipios, aunque está en los trimestres de antes y de después. Ese trimestre se marca (`trimestre_anomalo_fuente`) y se excluye.
- **Muestra principal:** muchos municipios pequeños tienen la renta suprimida casi siempre. La muestra principal incluye los municipios con renta en al menos el 90 % de los trimestres: **250 municipios** (134 de la ola 1, 87 de la ola 2 y 29 de control), que suman el **95,6 %** de los contratos.

**Qué significa cada fila del Gold:** un municipio en un trimestre. Columnas principales:

| Columna | Uso |
|---|---|
| `renta_media`, `log_renta` | Variable de resultado: precio |
| `contratos`, `log_contratos` | Variable de resultado: oferta |
| `ola`, `grupo`, `fecha_efectos` | Grupo de tratamiento (0 control, 1 marzo 2024, 2 octubre 2024) |
| `post`, `trimestres_desde_tratamiento` | Variables para el modelo de diferencias en diferencias y el estudio de eventos |
| `trimestre_transicion` | Trimestre de entrada en vigor, tratado solo en parte |
| `periodo_ley_catalana_2020` | Control del tope autonómico anterior (2020T4–2022T1) |
| `muestra_principal`, `cobertura_renta`, `fila_en_fuente`, `renta_disponible`, `trimestre_anomalo_fuente` | Calidad y filtrado |

El diccionario completo está al final del notebook.

**Para qué se usará:** en la fase siguiente, para estimar el efecto de la declaración sobre la renta y los contratos. Usaremos diferencias en diferencias con efectos fijos de municipio y trimestre, y un estudio de eventos para comprobar que las tendencias de antes de 2024 eran paralelas. Como hay dos olas, el estimador tendrá en cuenta la entrada escalonada en el tratamiento. En una primera mirada descriptiva, la renta media de los tres grupos evoluciona de forma muy parecida hasta 2024 y se separa después; la fase siguiente dirá si esa diferencia se sostiene estadísticamente.

## 5. Riesgos y limitaciones

- **Falta** el alquiler de temporada y turístico, que no pasa por el Incasòl: una caída de contratos podría ser desvío y no pérdida de oferta.
- **Sesgo:** el grupo de control es pequeño (29 municipios) y más pequeño que los tratados; lo reforzamos con la ola 2 como control "aún no tratado". El tope catalán de 2020–2022 se controla aparte.
- **Madrid** solo tiene precios de oferta, así que su comparación será descriptiva.
- **Si el Incasòl dejara de publicar:** la instantánea queda guardada con su hash y el índice SERPAVI sirve de alternativa anual.
