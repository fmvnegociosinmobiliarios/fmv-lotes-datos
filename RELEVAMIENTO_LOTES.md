# Relevamiento mensual de a estrenar y lotes (paso 6 del relevamiento automático del Tasador M2)

Se corre el día 1 de cada mes, después del relevamiento del tasador, en el Chrome de Fernando (Claude en Chrome). Objetivo: regenerar `mercado.json` de este repositorio con datos del mes. Si el relevamiento del tasador no pasó los controles ese mes, este paso NO se corre.

## 1. Clonar este repo

`add_repo fmvnegociosinmobiliarios/fmv-lotes-datos` con acceso push, clonar, y tener a mano `data/mercado.json` del repo `fmv-web` (salida del tasador del mismo día).

## 2. Relevar en Zonaprop, barrio por barrio (48 barrios), con pausas de 4,5 s entre páginas (Cloudflare corta a las ~12 páginas seguidas)

**Método probado el 04/10/2026 (tarda ~60 min para los 48 barrios):** abrir una pestaña de Zonaprop en el Chrome de Fernando y, con la herramienta de JavaScript de Claude en Chrome, correr un bucle dentro de la página que hace `fetch()` de cada listado (misma sesión, sin navegar) y lo parsea con `DOMParser`: cards `div[data-qa="posting PROPERTY"]`, precio `[data-qa="POSTING_CARD_PRICE"]`, m² en `[data-qa="POSTING_CARD_FEATURES"] span` ("840 m² tot."), dirección `[class*="ddress"]`, ubicación `[data-qa="POSTING_CARD_LOCATION"]`, descripción `[data-qa="POSTING_CARD_DESCRIPTION"]` (de ahí salen los m² vendibles y la altura declarada), link `a[href*="/propiedades/"]` sin query string. Guardar todo en `window.__fmv` y, al final, bajarlo como JSON con un `<a download>` (Chrome permite UNA descarga automática por sitio: si hace falta una segunda, pedirle a Fernando que la acepte en el ícono de la barra de direcciones). Después `python3 procesar_relevamiento.py volcado.json relevamientos/AAAA-MM/` genera `relevamiento_lotes.json` y `lotes_avisos.csv` (filtra por ubicación = barrio, deduplica por url, descarta m² < 80 o > 2.000 y USD/m² fuera de 150–15.000).

URLs: terrenos `/terrenos-venta-<slug>.html` y páginas `-pagina-N.html` (cortar cuando una página trae menos de 30 cards o al llegar a 10; más allá del total real Zonaprop repite avisos y rellena con barrios vecinos, por eso el filtro por ubicación). Unidades nuevas: NO usar `-a-estrenar` (devuelve emprendimientos con precio "desde"); usar `/departamentos-venta-<slug>-hasta-5-anos.html`, 3 páginas. Slugs distintos del nombre: La Boca = `la-boca`, Nueva Pompeya = `pompeya`, Paternal = `la-paternal`, Núñez = `nunez`, Villa Gral. Mitre = `villa-general-mitre`; el resto es el nombre en minúsculas con guiones y sin tildes.


`procesar_relevamiento.py` arma `relevamiento_lotes.json` con esta forma (si se releva de otra manera, respetarla):

```json
{"fecha": "2026-11-01",
 "barrios": {
   "Belgrano": {"estrenar": {"n": 38, "p25": 3100, "p50": 3400, "p75": 3900},
                "lotes":    {"n": 6, "lote_m2": [2200, 3100, 4800], "inc_vendible": [480, 590, 760]}}}}
```

**A estrenar** (`estrenar`): URL `https://www.zonaprop.com.ar/departamentos-venta-<barrio>-a-estrenar.html` (si no existe el filtro en la URL, usar el filtro "A estrenar" de la página). Tomar precio en USD y m² totales de cada card `div[data-qa="posting PROPERTY"]`, deduplicar por id de aviso, descartar avisos sin m² o con USD/m² fuera de 800–12.000, y calcular p25 / p50 / p75 de USD/m². `n` = avisos válidos. Tope 60 avisos por barrio (2-3 páginas).

**Lotes** (`lotes`): URL `https://www.zonaprop.com.ar/terrenos-venta-<barrio>.html`. Tomar precio, m² del lote y, si la ficha o el título lo dicen, los m² vendibles/construibles ("1.800 m² vendibles", "FOT", "PB+7"). `lote_m2` = [p25, p50, p75] de USD/m² de lote; `inc_vendible` = [p25, p50, p75] de precio / m² vendibles sólo con los avisos que lo publican (si son menos de 3, omitir la clave). `n` = avisos válidos de lote. Descartar cocheras, "fracciones" fuera de CABA y lotes de más de 2.000 m².

Si Zonaprop bloquea, completar con MercadoLibre (`https://inmuebles.mercadolibre.com.ar/terrenos/venta/capital-federal/<barrio>/`, paginado `_Desde_N_NoIndex_True`); MercadoLibre publica m² cubiertos: en a estrenar restar nada (son unidades nuevas) pero marcarlo en `fuente`.

Nombres de barrio: los mismos que las claves de `mercado.json` ("Belgrano", "Nuñez", "Villa Del Parque", "San Cristobal"…).

## 3. Costo de obra

Buscar en la web el último valor del índice MESH de costo directo de construcción (USD/m², obra terminada calidad estándar-alta, publicación mensual). Pasarlo como `--mesh`. Si no se consigue, omitir el parámetro: se mantiene el anterior.

## 4. Correr y controlar

```bash
python3 actualizar_mercado.py --tasador ../fmv-web/data/mercado.json --lotes relevamiento_lotes.json --mesh 1650
```

El script baja UVA y dólar MEP solo, escribe `mercado.json` y `actualizacion_resumen.md`. Controles antes de publicar:
- `mercado.json` tiene que seguir siendo JSON válido con los 48 barrios y las mismas claves.
- Si hay más de 10 barrios en "Alertas" (saltos > 25 %) respecto del mes anterior, NO publicar (la primera corrida real fue la de octubre 2026: sus 19 alertas fueron contra valores estimados a mano, no contra un relevamiento): avisar a Fernando con el resumen y dejar el relevamiento en `relevamientos/AAAA-MM/`.
- Prueba funcional: `python3 motor_fmv.py "Cuba 2494" --out /tmp/m.json` tiene que correr sin error y dar un residual positivo para Belgrano.

## 5. Publicar

Commit en `main` de `mercado.json`, `actualizacion_resumen.md` y `relevamientos/AAAA-MM/relevamiento_lotes.json`. Mensaje: "Mercado AAAA-MM". Nada más se toca. En el mensaje final a Fernando agregar dos líneas: variación de los a estrenar y de los lotes en Belgrano, Núñez, Villa Urquiza, Colegiales y Caballito, y cuántos barrios quedaron pendientes por muestra chica.

## 6. Catálogo de lotes y ranking de oportunidades (se hace en la misma pasada)

Además de las medianas, guardar TODOS los avisos de terrenos relevados en `relevamientos/AAAA-MM/lotes_avisos.csv` con columnas: `barrio, direccion, sup_m2, precio_usd, usd_m2_lote, vendibles_m2, usd_m2_vendible, altura_declarada, portal, url, fecha`. Deduplicar por url. Después correr:

```bash
python3 ranking_lotes.py relevamientos/AAAA-MM/lotes_avisos.csv
```

Genera `relevamientos/AAAA-MM/ranking_lotes.md` con los 25 lotes cuyo USD/m² de lote pedido queda más abajo del valor de referencia del barrio (`lote_m2[1]` de `mercado.json`), con la diferencia en %, y una lista aparte de los que publican m² vendibles con incidencia por debajo de `inc_vendible[0]`. Se commitea junto con lo demás y en el mensaje final a Fernando se agregan las 5 primeras oportunidades (barrio, dirección, superficie, precio pedido, % bajo referencia) con su link. Son candidatos para pedir "informe de lote de <dirección>", no una recomendación de compra.

## 7. Si se sube por la web de GitHub (sin git)

El formulario de subida no crea carpetas: en ese caso los archivos del mes van en la raíz con el prefijo `rel_AAAA-MM_` (`rel_2026-10_relevamiento_lotes.json`, `rel_2026-10_lotes_avisos.csv`, `rel_2026-10_ranking_lotes.md`). La tarea automática, que usa git, los deja en `relevamientos/AAAA-MM/`.
