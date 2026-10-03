# fmv-lotes-datos

Datos y herramientas para los **informes de factibilidad y tasación de lotes en CABA** de FMV Soluciones Inmobiliarias (Fernando M. Veiga, CUCICBA 9981).

## Contenido

| Archivo | Qué es |
|---|---|
| `comuna_01.sqlite.gz` … `comuna_15.sqlite.gz` | Base SQLite por comuna, comprimida (1,4–5,6 MB c/u). Tablas: `parcelas` (geometría EPSG:5347 simplificada, partida, barrio), `cu` (Código Urbanístico por parcela, norma 31/12/2024), `rus` (usos del suelo 2022-2024, pisos), `frentes` (calle y numeración), `obras` (DGROC desde 2021), `aph`, `cur3d` (volumetría oficial), `meta`. |
| `indice_calles.csv` | Índice calle → sección → comuna → rango de numeración (para saber qué base abrir). |
| `mercado.json` | Parámetros de mercado por barrio (precios a estrenar por nivel, costo directo, incidencias, usados), UVA, MEP, indirectos, plazos. **Actualizar mensualmente.** |
| `motor_fmv.py` | Motor: dirección → parcela → geometría (frentes, ochava, LFI al 25 % del ancho de manzana, huella, banda del fondo) → normativa → modelo económico en 3 niveles → plusvalía → englobamiento (de a uno y de a pares; recomendado sólo si rinde ≥ 10 % y el residual es positivo) → tasación por uso actual → mapas. |
| `informe_fmv.py` | Plantilla PDF negro y dorado (reportlab). Portada con mapa, KPIs y contacto con QR de WhatsApp; 12 capítulos; contratapa "Próximos pasos". |
| `DejaVuSans*.ttf` | Fuentes (por si el entorno no las tiene). |

Fuente de los datos: datos abiertos del GCBA (data.buenosaires.gob.ar), descargados en jul-2026. Regenerar la base con `build_db.py` + `split_db.py` cuando se actualicen los datasets.

## Uso

```bash
pip install shapely numpy matplotlib reportlab qrcode pillow pyproj
curl -sLO https://raw.githubusercontent.com/fmvnegociosinmobiliarios/fmv-lotes-datos/main/motor_fmv.py   # ídem informe_fmv.py, mercado.json, indice_calles.csv
python3 motor_fmv.py "Cuba 2494" --cfg config.json --out modelo.json     # descarga sola comuna_XX.sqlite.gz
python3 informe_fmv.py modelo.json textos.json Informe.pdf
```

`config.json` (opcional): `{"smp": "025-014-001", "comps": [{"nombre": "...", "sup": 249, "precio": 890000, "vendibles": 1801}], "overrides": {"cub_exist": 300, "huella": 180, "lfi": 24, "pb_comun": 45, "factor_estado": 0.65, "extras": {"retardo_pluvial": 18000}, "mercado": {"precio_venta": [3250, 3550, 3950]}, "normativa": {"n_tipo": 7}}}`

`textos.json` (opcional): `numero`, `titulo`, `fecha_mercado`, `cliente`, `uso_actual_txt`, `resumen`, `entorno`, `veredicto`, `normativa_nota`, `fondo_nota`, `mercado_nota`, `comps_fuente`, `estrategia`, `englobe_nota`, `uso_nota`, `comprador`, `conclusiones` (lista), `recomendacion`, `pasos` (lista de [título, texto]).

## Reglas del informe

- Precios y plazos de aprobación y de obra separados; 3 niveles constructivos (estándar / alto / premium) y sensibilidad precio × costo.
- Englobamiento sólo como argumento si mejora ≥ 10 % los metros vendibles; se excluyen edificios en PH / varios dueños y combinaciones de más de dos linderos.
- Cuando el residual del desarrollador no cubre la mitad del valor de publicación, el informe pasa a modo **tasación por uso actual** (valor de piso).
- Sin honorarios ni la palabra "gratis"/"sin cargo". Firma: Fernando M. Veiga · Corredor Inmobiliario y Martillero Público · CUCICBA 9981.
