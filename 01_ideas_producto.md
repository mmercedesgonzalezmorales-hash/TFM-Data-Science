# Entrega 1 — Propuesta inicial de ideas de producto

Este documento recoge tres ideas iniciales de proyecto de Data Science e IA. Cada una se describe con foco en el problema real que resuelve y en el valor que aportaría, sin entrar todavía en arquitectura, modelos ni fuentes concretas de datos.




---

## Idea 1 — Optimización del mix de inversión publicitaria (Marketing Mix Modeling)

### Problema que resuelve

- **Qué ocurre actualmente.** Las empresas que invierten en publicidad reparten su presupuesto entre varios canales (buscadores, redes sociales, televisión, exterior, email…) apoyándose en la inercia del año anterior, en lo que cada plataforma reporta de sí misma o en la atribución al último clic. Es decir, deciden con información sesgada o incompleta. Se toman decisiones en función de la intuición del equipo y no con un criterio de datos. 
- **Por qué supone un problema.** Cada plataforma tiene incentivo a atribuirse el mérito de las ventas, y la atribución basada en seguimiento a nivel de usuario se ha degradado mucho por las restricciones de privacidad y la desaparición de las cookies. El resultado es presupuesto mal repartido: se sigue invirtiendo en canales saturados mientras se infrafinancian otros que sí generan ventas.
- **Qué decisión, proceso o situación podría mejorar con datos.** El proyecto estima la contribución incremental real de cada canal a las ventas y, a partir de ahí, recomienda cómo redistribuir el presupuesto para maximizar el retorno. La decisión que mejora es concreta y muy cara: cuánto invertir en cada canal.
- **Por qué no es simplemente un ejercicio técnico.** El modelo no se limita a predecir ventas: tiene que capturar dos fenómenos  —el *adstock* (el efecto de la publicidad se arrastra en el tiempo, no se agota el día del impacto) y la *saturación* (cada euro adicional rinde menos)— y terminar en una optimización con restricciones que reparte un presupuesto dado entre canales. 

### Motivación para realizar el proyecto

- **Relevancia.** Económica y empresarial, y además muy actual: la pérdida de precisión de la atribución tradicional ha provocado un fuerte resurgimiento del Marketing Mix Modeling, hasta el punto de que las grandes plataformas han publicado sus propias herramientas de código abierto en los últimos años.
- **Interés técnico.** Combina econometría bayesiana, modelado de adstock y curvas de saturación, y optimización con restricciones; un abanico técnico rico y diferenciado del clasificador de manual.
- **Aplicación de contenidos del máster.** Series temporales, regresión bayesiana, ingeniería de características y optimización.
- **Viabilidad de datos.** Las principales librerías de código abierto (por ejemplo PyMC-Marketing en Python, o el enfoque de Meridian) incluyen datasets de demostración, existen datos públicos de inversión publicitaria agregada, y en esta disciplina es metodológicamente aceptado trabajar con datos semi-sintéticos: se genera un conjunto con contribuciones y adstock conocidos y se demuestra que el modelo los recupera, lo que además aporta una verdad-terreno contra la que validar.

### A quién impacta

- Directores de marketing, que deben justificar y repartir el presupuesto de medios.
- Agencias de medios y consultoras de marketing, que asesoran a clientes sobre dónde invertir.
- Pymes que gastan en publicidad digital sin recursos para modelos propietarios y necesitan saber qué canales funcionan de verdad.

### Por qué tiene valor

- **Mejor toma de decisiones:** reparto de presupuesto basado en la contribución incremental real de cada canal, no en lo que cada plataforma dice de sí misma.
- **Ahorro y aumento de ingresos:** se recorta gasto en canales saturados y se refuerzan los rentables, mejorando el retorno de la inversión publicitaria (ROAS).
- **Apoyo a una decisión de negocio:** el modelo se conecta directamente a un KPI en euros (ventas incrementales), cerrando el círculo de la predicción a la decisión.
- **Robustez ante la privacidad:** al trabajar con datos agregados, no depende del seguimiento individual del usuario, cada vez más limitado.

---

## Idea 2 — Valoración automática de vivienda (AVM)

### Problema que resuelve

- **Qué ocurre actualmente.** La valoración de un inmueble —para fijar el precio de venta, tasar de cara a una hipoteca o decidir una compra— se hace de forma mayoritariamente manual: un tasador o agente compara la vivienda con otras similares mediante su criterio y su experiencia, y los particulares fijan precio "a ojo" o por lo que piden en el edificio de al lado.
- **Por qué supone un problema.** Es un proceso lento, costoso, subjetivo y poco consistente entre profesionales. Un precio mal fijado tiene consecuencias directas: si es demasiado alto, la vivienda se queda meses sin venderse; si es demasiado bajo, el vendedor pierde dinero. Para las entidades financieras, una tasación errónea es directamente riesgo en la concesión de la hipoteca. Y el mercado es notoriamente opaco para el comprador medio.
- **Qué decisión, proceso o situación podría mejorar con datos.** Un modelo que estime el valor de mercado de una vivienda a partir de sus características y su ubicación permite fijar el precio de salida con criterio, apoyar la tasación hipotecaria y detectar oportunidades (inmuebles infravalorados) para inversión.
- **Por qué no es simplemente un ejercicio técnico.** No es "predecir un precio" en abstracto: es una decisión de compraventa o tasación con mucho dinero en juego y muy tangible, en la que el modelo sustituye o apoya un juicio experto caro y lento por una estimación instantánea, consistente y explicable.

### Motivación para realizar el proyecto

- **Relevancia.** Económica y social: la vivienda es la mayor decisión de compra en la vida de la mayoría de las personas, y el sector inmobiliario tiene un peso enorme en la economía.
- **Interés técnico.** Regresión con muchas variables, y sobre todo un fuerte componente **geoespacial**: la ubicación es el principal determinante del precio, lo que abre trabajo interesante de ingeniería de características de localización (cercanía a servicios, transporte, equipamientos) e interpretabilidad del modelo.
- **Componente visual.** Da mucho juego en visualización: mapas de calor de precio por zona, comparativas por barrio, mapas de idoneidad. Esto refuerza la parte de comunicación del proyecto.
- **Aplicación de contenidos del máster.** Regresión, modelos de machine learning.
- **Viabilidad de datos.** Los datos son abundantes y abiertos en España: catastro, renta por sección censal del INE, portales inmobiliarios (con extracción responsable), datos abiertos municipales y fuentes tipo OpenStreetMap para equipamientos y servicios cercanos. Es perfectamente abordable construir un dataset de trabajo.

### A quién impacta

- Particulares que compran o venden vivienda, que necesitan fijar o contrastar un precio sin depender solo de la intuición.
- Agencias inmobiliarias, que ganan una valoración rápida y consistente para asesorar a sus clientes.
- Entidades financieras y sociedades de tasación, como apoyo a la tasación hipotecaria y al control de riesgo.
- Inversores inmobiliarios, que pueden detectar inmuebles infravalorados con potencial.

### Por qué tiene valor

- **Mejor toma de decisiones:** un precio fijado con criterio y respaldado por datos, no por corazonada.
- **Ahorro de tiempo:** valoración instantánea frente a una tasación manual lenta y cara.
- **Detección de riesgos y oportunidades:** identificación de inmuebles sobrevalorados o infravalorados.
- **Mayor transparencia:** aporta luz a un mercado tradicionalmente opaco para el comprador medio.
- **Generación de conocimiento:** los mapas y análisis por zona comunican de forma clara cómo se forma el precio en cada área.

---



### Problema que resuelve

- **Qué ocurre actualmente.** Los hospitales dimensionan camas de planta, camas de UCI y personal apoyándose sobre todo en históricos simples y en la experiencia del equipo de gestión. La planificación es en gran medida reactiva: se ajustan recursos cuando la presión asistencial ya está subiendo.
- **Por qué supone un problema.** Los picos previsibles (gripe estacional, olas de calor, brotes respiratorios) llegan sin margen de anticipación suficiente. Esto se traduce en saturación de urgencias, cancelación de cirugía programada, sobrecarga de personal y activación tardía de planes de contingencia. En el otro extremo, sobredimensionar recursos "por si acaso" tiene un coste elevado en camas y personal infrautilizados.
- **Qué decisión, proceso o situación podría mejorar con datos.** Un modelo de previsión de ocupación a 7–14 días permitiría anticipar el dimensionamiento de camas y UCI, planificar turnos, gestionar la agenda de cirugía electiva y decidir con antelación la activación de planes de contingencia o derivación.
- **Por qué no es simplemente un ejercicio técnico.** No es "predecir una serie temporal" por deporte: es planificación sanitaria con impacto directo en la seguridad del paciente, en las listas de espera y en el gasto público. La predicción alimenta una decisión operativa concreta y recurrente.

### Motivación para realizar el proyecto

- **Relevancia.** Social y económica: afecta a la calidad asistencial y al coste del sistema sanitario público.
- **Interés técnico.** Es un problema de forecasting de series temporales con variables exógenas interesantes (vigilancia epidemiológica, calendario, meteorología), lo que da mucho recorrido metodológico.
- **Aplicación de contenidos del máster.** Series temporales, modelos de machine learning, validación temporal, tratamiento de estacionalidad y eventos.
- **Viabilidad de datos.** Existen datos abiertos utilizables: series históricas de vigilancia respiratoria (p. ej. sistemas de vigilancia del ISCIII), datos abiertos de salud de CCAA y ministerio, datos históricos de la etapa COVID y catálogos de datos.gob.es. Es razonable pensar que se puede construir un dataset de trabajo.

### A quién impacta

- Dirección médica y de enfermería, y servicios de admisión y planificación hospitalaria, que son quienes toman las decisiones de dimensionamiento.
- Gerencia del hospital y servicios de salud autonómicos, por el impacto en coste y en cumplimiento de objetivos asistenciales.
- Indirectamente, los pacientes, que se benefician de menos cancelaciones y menor saturación.

### Por qué tiene valor

- **Mejor planificación** de camas, UCI y turnos con antelación real.
- **Reducción de costes** por menos recursos ociosos y menos horas extra de urgencia.
- **Detección temprana de riesgo** de saturación asistencial.
- **Mejor experiencia** para el paciente al reducir cancelaciones de cirugía programada.
