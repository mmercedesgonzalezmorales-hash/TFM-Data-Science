# Entrega 02 · Datos y preparación

## 2. Fuentes reales y viabilidad

**Fuente principal: paquete *idealista18*** (Rey-Blanco, Arbués, López y Páez, 2024, *Environment and Planning B*).

- **Qué contiene:** anuncios reales publicados en idealista.com durante 2018. Cada vivienda tiene coordenadas, precio de oferta y unas 40 variables. Los datos vienen cruzados con el Catastro (año de construcción, calidad constructiva, plantas y viviendas del edificio) e incluyen distancias a puntos de interés y los polígonos de los barrios.
- **Volumen (Madrid):** 94.815 anuncios en 135 barrios.
- **Acceso:** ficheros `.rda` del repositorio público `github.com/paezha/idealista18`. Se leen en Python con la librería `rdata`, sin necesidad de instalar R. El script descarga una versión fijada (commit `e9ef806`) y verifica cada fichero con SHA-256, así que cualquiera obtiene exactamente los mismos datos.
- **Cobertura:** municipio de Madrid, los cuatro trimestres de 2018. El paquete incluye también Barcelona y Valencia.
- **Actualización:** ninguna. Es una fotografía cerrada de 2018.
- **Estabilidad:** alta. Es un dataset académico, publicado junto a un artículo revisado por pares y versionado en GitHub.

**Fuentes complementarias previstas** (para enriquecer el dataset en la fase siguiente):

| Fuente | Qué aporta | Acceso |
|---|---|---|
| INE: Atlas de Distribución de Renta de los Hogares | Renta media por sección censal | Descarga abierta |
| INE: cartografía de secciones censales | Geometrías para cruzar coordenadas con renta | Descarga abierta |
| OpenStreetMap | Colegios, parques, comercio cercano | API Overpass (ODbL) |

**Alternativas si la fuente principal no estuviera disponible:**

1. La copia publicada en Kaggle ("Georeferenced Spain Housing").
2. Los datos de Barcelona o Valencia del mismo paquete.
3. Como último recurso, combinar el Catastro (características) con los precios medios por zona del Ministerio de Vivienda y Agenda Urbana. En ese caso el producto pasaría a dar valoraciones por zona, no por vivienda.

**Descartado:** hacer scraping de portales actuales, porque choca con sus condiciones de uso (ver apartado 3).
