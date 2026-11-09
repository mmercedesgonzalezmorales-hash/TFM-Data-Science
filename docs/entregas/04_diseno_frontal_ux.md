# Entrega 4 — Diseño del frontal y experiencia de usuario

## 4. Experiencia de usuario

El principio que guía el diseño es que **el usuario no quiere un modelo, quiere una cifra en la que pueda confiar y saber qué hacer con ella**. Por eso cada decisión busca tres cosas: que la valoración se obtenga en menos de un minuto, que se entienda de dónde sale y que quede claro cuánto fiarse de ella.

### 4.1 Claridad de la información

- **Una cifra protagonista, siempre con su rango.** El resultado muestra en grande el valor estimado y, justo debajo, un rango de precios probable ("entre X € y Y €"). No mostramos nunca un precio sin su rango: una cifra exacta da una falsa sensación de precisión, y el rango es lo que realmente ayuda a fijar un precio de salida o a negociar.
- **Lenguaje llano, sin jerga técnica.** Hablamos de "valor estimado", "rango probable" y "viviendas parecidas", no de "predicción", "intervalo de confianza" o "vecinos más cercanos". Las métricas del modelo (MAE, MAPE) no aparecen en la pantalla principal. Quedan en una sección "Cómo funciona" para quien quiera profundizar.
- **Contexto inmediato.** Junto al precio mostramos el €/m² de la vivienda comparado con la mediana de su barrio ("un 8 % por encima de la mediana de Arganzuela"). Una cifra absoluta dice poco a un particular. Compararla con su zona le dice si su vivienda está cara o barata.
- **Honestidad sobre los datos.** Un aviso fijo y visible indica que las estimaciones se basan en **precios de oferta de 2018** en el municipio de Madrid. No son precios de cierre ni precios actuales. Es la limitación más importante del producto y el usuario debe conocerla antes de tomar cualquier decisión.

### 4.2 Gráficos y controles elegidos

| Elemento | Por qué este y no otro |
|---|---|
| **Formulario corto en una sola pantalla** (ubicación, superficie, habitaciones, baños, planta, ascensor, estado) | Son las variables con más peso en el precio y las que cualquier propietario conoce de memoria. El resto (terraza, trastero, piscina, portero…) va en un bloque plegable "Más detalles" para no alargar el formulario. |
| **Selección de ubicación en mapa o por dirección** | La ubicación es el principal determinante del precio. Señalarla en un mapa es más rápido y menos propenso a errores que pedir barrio, distrito y código postal por separado. |
| **Desplegables y selectores en lugar de texto libre** (estado, planta, sí/no) | Evitan errores de escritura y garantizan que la entrada coincide con las categorías con las que se entrenó el modelo. |
| **Barras horizontales de factores** ("qué sube y qué baja el precio") | Explican la estimación de forma intuitiva: verde a la derecha, lo que suma; rojo a la izquierda, lo que resta. Se entienden sin formación y se apoyan en la explicabilidad del modelo (contribución de cada variable). Se muestran como mucho los 5 factores principales. |
| **Mapa de calor de €/m² por barrio** | Sitúa la vivienda en su contexto y aprovecha el componente geoespacial del proyecto. Es el gráfico más natural para el dato inmobiliario. |
| **Lista de viviendas comparables** (5 anuncios similares de la zona, con precio, m² y distancia) | Es como trabaja un tasador. Ver ejemplos reales parecidos genera más confianza que cualquier métrica y permite al usuario contrastar la cifra con su propio criterio. |

**Lo que hemos descartado a propósito:** cuadros de mando con muchos gráficos, gráficos 3D, tartas y tablas extensas de variables. Añaden complejidad visual sin ayudar a la decisión del usuario.

### 4.3 Facilidad de uso

- **Flujo lineal en dos pasos:** introducir datos → ver resultado. Sin registro ni pantallas intermedias.
- **Valores por defecto sensatos.** Los campos opcionales que el usuario deja vacíos se rellenan con el valor típico de su barrio, y el resultado indica qué datos se han supuesto. Así nadie se queda bloqueado por no saber un dato secundario.
- **Edición sin volver a empezar.** Desde la pantalla de resultado se puede cambiar cualquier dato (por ejemplo, "¿y si estuviera reformado?") y la estimación se recalcula. Esto convierte la herramienta en un simulador útil para decidir si merece la pena reformar antes de vender.
- **Diseño adaptable a móvil**, porque es donde un particular suele consultar estas cosas, por ejemplo durante una visita a un piso.
- **Accesibilidad básica:** buen contraste, tamaños de letra legibles y que el significado nunca dependa solo del color (los factores llevan también signo + / − y texto).

### 4.4 Gestión de errores y resultados inciertos

El modelo se equivoca y no siempre con la misma intensidad. La interfaz debe decirlo en lugar de esconderlo.

- **Indicador de fiabilidad (alta / media / baja).** Acompaña a cada estimación. Se calcula a partir de la amplitud del rango y de cuántas viviendas parecidas había en los datos de esa zona. Con fiabilidad baja, el mensaje recomienda contrastar la cifra con un profesional.
- **Viviendas fuera de lo habitual.** Si la vivienda tiene características poco representadas en los datos de entrenamiento (superficies muy grandes o muy pequeñas, número inusual de habitaciones), el usuario puede seguir adelante. Se le avisa de que la estimación es menos fiable y el rango se muestra más ancho.
- **Ubicación fuera de cobertura.** Si el punto marcado está fuera del municipio de Madrid, no se da ninguna cifra. Se explica que el modelo solo cubre Madrid capital, en lugar de devolver un número sin base.
- **Validación en el propio formulario.** Los datos imposibles o incoherentes (0 m², más baños que habitaciones en un piso pequeño, una planta superior a la del edificio) se señalan junto al campo, con un mensaje que explica cómo corregirlo, antes de enviar.
- **Fallo técnico.** Si el servicio del modelo no responde, se muestra un mensaje claro con opción de reintentar y se conservan los datos introducidos para no tener que escribirlos de nuevo.
