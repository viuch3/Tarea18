# Pipeline ETL - Análisis de Ventas Retail (SuperMart Colombia)

Proyecto de EAN TechRetail Solutions. Pipeline ETL en Python que extrae datos
de ventas desde CSV, los limpia y transforma, genera archivos optimizados para
análisis, visualizaciones y un reporte ejecutivo.

**Integrantes:** Juan Felipe Viuche, Jorge Piñeros, Juan Avila, Diego Bustos

## Requisitos
- Python 3.8 o superior
- Librerías: pandas, numpy, matplotlib, seaborn

## Instalación
```bash
python3 -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución
```bash
python3 crear_datos.py     # genera los 3 CSV de entrada en data/
python3 etl_pipeline.py    # ejecuta el pipeline completo
```

## Estructura
```
Tarea18/
├── data/                  # CSV de entrada (ventas_crudas, productos, tiendas)
├── output/                # Archivos generados por el pipeline
├── crear_datos.py         # Genera los datos de entrada
├── etl_pipeline.py        # Pipeline ETL (extraer, transformar, cargar, analizar)
├── requirements.txt
└── README.md
```

## Fases del pipeline
1. **Extracción:** lee los 3 CSV con pandas, maneja errores (archivo no
   encontrado, vacío o con formato incorrecto) y muestra registros por archivo.
2. **Transformación:** unifica formatos de fecha, reemplaza `cliente_id` nulos por
   `CLIENTE_DESCONOCIDO`, valida IDs duplicados, calcula `venta_total` y
   `categoria_venta` (Baja < $20, Media $20-$50, Alta ≥ $50), une productos y
   tiendas, crea año, mes y día de la semana, y valida integridad referencial y rangos.
3. **Carga:** genera el dataset completo, el Data Mart y el resumen ejecutivo (CSV).
4. **Análisis:** 4 gráficos (.png) y reporte ejecutivo (.txt).

## Archivos generados en `output/`
| Archivo | Descripción |
|---|---|
| dataset_transformado.csv | Dataset completo y enriquecido |
| data_mart_ventas.csv | Agregado por año, mes, ciudad, región y categoría |
| resumen_ejecutivo.csv | Métricas clave y líderes |
| ventas_por_ciudad.png | Barras: ventas totales por ciudad |
| ventas_por_categoria.png | Pie: distribución por categoría |
| transacciones_por_dia.png | Barras: transacciones por día de la semana |
| histograma_montos.png | Histograma de montos de venta |
| reporte_ejecutivo.txt | Reporte con métricas, top performers, calidad e insights |
