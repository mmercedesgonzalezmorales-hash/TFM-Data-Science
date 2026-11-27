# Entrega 02 · Datos y preparación

## 0. Reorientación del proyecto respecto a la Entrega 01

En la Entrega 01 se propuso un modelo de valoración automática de viviendas (AVM) para el mercado inmobiliario de Madrid. Al analizar las fuentes disponibles en esta fase, comprobamos que el único conjunto de datos abierto con información a nivel de vivienda individual (*idealista18*) corresponde a 2018. Por ello no recoge la fuerte subida de precios registrada entre 2022 y 2025, y un modelo entrenado con él valoraría las viviendas a precios desfasados. Además, una exploración preliminar indicó que las características de los barrios en 2018 no permitían anticipar qué zonas se revalorizarían más, lo que apunta a que los factores relevantes son posteriores.

Ante esto, mantenemos el sector y el objetivo de aportar valor al análisis del mercado de la vivienda, pero reorientamos la pregunta de *cuánto vale una vivienda* a *qué explica la evolución de los precios*. En concreto, aprovechamos un experimento natural: la declaración de zonas de mercado residencial tensionado en Cataluña en 2024 (Ley 12/2023, por el derecho a la vivienda), que limitó las rentas del alquiler en unos municipios y no en otros, ni en la Comunidad de Madrid. Esto permite comparar zonas reguladas y no reguladas con métodos de inferencia causal (diferencias en diferencias), usando datos administrativos reales, abiertos y actualizados, como el registro de fianzas del Incasòl. Así se combina el enfoque predictivo de la propuesta inicial con un análisis explicativo de mayor interés práctico y social.

**Pregunta del proyecto:** ¿qué efecto tuvo la declaración de zonas tensionadas sobre la **renta** de los alquileres y el número de **contratos nuevos registrados** en Cataluña? Como contexto, se describirá cómo evolucionó el alquiler en Madrid, donde no se aplicó.

## 1. Qué datos necesita el producto

**Unidad de observación:** un municipio catalán en un trimestre (por ejemplo, *Girona, 2024T3*).

**Imprescindibles:**

- **Renta media de los contratos nuevos** (€/mes). Es la variable de precio.
- **Número de contratos nuevos registrados** (con fianza depositada en el Incasòl). No es una medida directa de la oferta: si baja, todavía no sabemos si se anunciaron menos viviendas, si se alquilaron más despacio o si cambió el tipo de contrato (por ejemplo, hacia alquiler de temporada, que no se registra aquí). Lo tratamos como lo que es: contratos nuevos registrados.
- **Si el municipio está declarado tensionado y desde cuándo.** Es la variable de tratamiento.

**Deseables:**

- Población y renta de los hogares por municipio, para controlar diferencias de tamaño y nivel económico.
- Anuncios de alquiler de temporada y de pisos turísticos, para saber si una caída de contratos registrados es desvío hacia esos usos.
- Para el contexto de Madrid: precio de anuncio del alquiler por distrito en Madrid y en Barcelona, de una misma fuente.

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

**Fuente de contexto (fase siguiente), para Madrid:** informes públicos de precio del alquiler por distrito de idealista (sala de prensa), mensuales desde 2018, para Madrid y Barcelona. Hay que distinguir dos cosas que no son comparables entre sí:

- **Precio de anuncio** (idealista): lo que pide el propietario en el portal. Existe para Madrid y Barcelona.
- **Renta firmada** (Incasòl): lo que se paga en el contrato. Solo existe para Cataluña.

Por eso Madrid no entra en la estimación del efecto: sirve solo como contexto, y se compara siempre anuncio con anuncio (Madrid frente a Barcelona en idealista), nunca con las rentas firmadas del Incasòl.

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
| **Gold** | Panel equilibrado de 942 municipios × 30 trimestres (2019T1–2026T2). Lleva las variables de resultado, el tratamiento, las marcas de calidad y las dos muestras de análisis. | `data/gold/panel_municipio_trimestre.parquet` + `informe_calidad.json` |

**Comprobaciones de calidad:**

- **Coherencia:** la suma de los cuatro trimestres coincide con el dato anual en el **99,97 %** de los 3.521 municipio-año comparados.
- **Anomalía de la fuente:** en **2026T1** falta la renta en casi todos los municipios, aunque está en los trimestres de antes y de después. Ese trimestre se marca (`trimestre_anomalo_fuente`) y se excluye.
- **Rentas que la fuente no publica:** en **10.498 filas** del Gold el Incasòl da el número de contratos pero suprime la renta media por secreto estadístico. Se marcan con `renta_no_publicada`, distinta de `fila_en_fuente = False` (el municipio no aparece ese trimestre). Ninguna se rellena ni se imputa.
- **Trimestres con la medida vigente solo una parte del tiempo:** el trimestre en que entra en vigor cada ola se marca con `trimestre_transicion` (271 filas, una por municipio tratado) y `fraccion_trimestre_vigente` indica qué parte del trimestre estuvo vigente: **17,6 %** en la ola 1 (2024T1, desde el 16 de marzo) y **90,2 %** en la ola 2 (2024T4, desde el 10 de octubre). Esos trimestres no cuentan como tratados (`post`) ni como previos; en el análisis se excluyen.
- **Muestra principal:** muchos municipios pequeños tienen la renta suprimida casi siempre. La muestra principal incluye los municipios con renta en al menos el 90 % de los trimestres: **250 municipios** (134 de la ola 1, 87 de la ola 2 y 29 de control), que suman el **95,6 %** de los contratos.
- **Muestra alternativa, elegida solo con datos anteriores a la medida:** la muestra principal mira todos los trimestres, también los posteriores a 2024, y eso puede cambiar qué municipios quedan dentro. Por ejemplo, si la ley reduce los contratos de un municipio y por eso el Incasòl deja de publicar su renta, ese municipio saldría de la muestra por el propio efecto que queremos medir. Para evitarlo, `muestra_pre_tratamiento` aplica la misma regla (≥ 90 % de trimestres con renta) pero solo con **2019T1–2023T4**. Entran **266 municipios** (135 de la ola 1, 101 de la ola 2 y 30 de control): los 250 de la principal y 16 más (14 de ellos de la ola 2), que tenían la renta publicada antes de la medida y la perdieron después. El análisis se hará con las dos muestras para comprobar que el resultado no depende de esta elección.

**Qué significa cada fila del Gold:** un municipio en un trimestre. Columnas principales:

| Columna | Uso |
|---|---|
| `renta_media`, `log_renta` | Variable de resultado: precio |
| `contratos`, `log_contratos` | Variable de resultado: contratos nuevos registrados |
| `ola`, `grupo`, `fecha_efectos` | Grupo de tratamiento (0 control, 1 marzo 2024, 2 octubre 2024) |
| `post`, `trimestres_desde_tratamiento` | Variables para el modelo de diferencias en diferencias y el estudio de eventos |
| `trimestre_transicion`, `fraccion_trimestre_vigente` | Trimestre de entrada en vigor y qué parte de él estuvo vigente la medida |
| `periodo_ley_catalana_2020` | Control del tope autonómico anterior (2020T4–2022T1) |
| `fila_en_fuente`, `renta_disponible`, `renta_no_publicada`, `trimestre_anomalo_fuente` | Calidad: qué publica la fuente en cada fila |
| `muestra_principal`, `cobertura_renta` | Muestra elegida con todos los trimestres |
| `muestra_pre_tratamiento`, `cobertura_renta_pre` | Muestra alternativa elegida solo con 2019T1–2023T4 |

El diccionario completo está al final del notebook.

**Para qué se usará:** en la fase siguiente, para estimar el efecto de la declaración sobre la renta y los contratos. Usaremos diferencias en diferencias con efectos fijos de municipio y trimestre, y un estudio de eventos para comprobar que las tendencias de antes de 2024 eran paralelas. Como hay dos olas, el estimador tendrá en cuenta la entrada escalonada en el tratamiento. En particular, la ola 2 sirve de comparación para la ola 1 durante los **dos trimestres** en que la ola 1 ya tenía la medida y la ola 2 todavía no (2024T2 y 2024T3; el 2024T4 es de transición).

Una primera mirada descriptiva, antes de cualquier modelo, ya marca la diferencia entre las dos variables:

- **Renta:** los tres grupos evolucionan de forma muy parecida hasta 2024 (entre 2019 y 2023, +14 % a +18 % de media) y se separan después.
- **Contratos nuevos registrados:** ya había diferencias **antes** de la medida. Entre 2021 y 2023 cayeron de media un 16 % en la ola 1 y un 13 % en la ola 2, frente a un 7 % en los municipios de control. Por eso, si después de 2024 los contratos caen más en los municipios tensionados, no se le podrá atribuir a la medida toda esa caída: una parte ya venía de antes. El análisis tendrá que descontar esa tendencia previa y apoyarse en la comparación con la ola 2.

## 5. Riesgos y limitaciones

- **Falta** el alquiler de temporada y turístico, que no pasa por el Incasòl: una caída de contratos nuevos registrados puede ser desvío a otros tipos de contrato y no menos viviendas en alquiler.
- **Sesgo:** el grupo de control es pequeño (29–30 municipios) y más pequeño que los tratados, y en contratos ya evolucionaba distinto antes de la medida. Lo reforzamos con la ola 2 como control "aún no tratado" en 2024T2–2024T3 (solo dos trimestres) y comparamos dos muestras (una elegida solo con datos previos). El tope catalán de 2020–2022 se controla aparte.
- **Madrid** solo tiene precios de anuncio, no rentas firmadas: queda como contexto descriptivo, comparando anuncio con anuncio.
- **Si el Incasòl dejara de publicar:** la instantánea queda guardada con su hash y el índice SERPAVI sirve de alternativa anual.
