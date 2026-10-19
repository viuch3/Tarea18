"""Pipeline ETL - SuperMart Colombia (EAN TechRetail Solutions)."""
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")


def extraer_csv(nombre_archivo: str) -> pd.DataFrame:
    """Carga un CSV con manejo de errores y muestra cuántos registros trae."""
    ruta = DATA_DIR / nombre_archivo
    try:
        df = pd.read_csv(ruta, encoding="utf-8")
    except FileNotFoundError:
        print(f"ERROR: no se encontró el archivo {ruta}")
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print(f"ERROR: el archivo {ruta} está vacío")
        sys.exit(1)
    except pd.errors.ParserError as e:
        print(f"ERROR: formato incorrecto en {ruta}: {e}")
        sys.exit(1)

    print(f"  {nombre_archivo}: {len(df)} registros, {df.shape[1]} columnas")
    return df


def extraer() -> tuple:
    """FASE 1: extrae las tres fuentes."""
    print("=== FASE 1: EXTRACCIÓN ===")
    ventas = extraer_csv("ventas_crudas.csv")
    productos = extraer_csv("productos.csv")
    tiendas = extraer_csv("tiendas.csv")
    return ventas, productos, tiendas


def limpiar_ventas(ventas: pd.DataFrame) -> pd.DataFrame:
    """Corrige fechas, maneja nulos y valida IDs duplicados."""
    print("\n=== FASE 2: TRANSFORMACIÓN ===")
    df = ventas.copy()

    # Fechas: unificar separadores (2024/03/16 -> 2024-03-16) y convertir
    df["fecha"] = df["fecha"].astype(str).str.replace("/", "-", regex=False)
    df["fecha"] = pd.to_datetime(df["fecha"], format="%Y-%m-%d", errors="coerce")
    invalidas = df["fecha"].isna().sum()
    print(f"  Fechas inválidas detectadas: {invalidas}")
    df = df.dropna(subset=["fecha"])

    # Nulos en cliente_id
    nulos = df["cliente_id"].isna().sum()
    df["cliente_id"] = df["cliente_id"].fillna("CLIENTE_DESCONOCIDO")
    print(f"  cliente_id nulos reemplazados: {nulos}")

    # IDs duplicados
    duplicados = df["order_id"].duplicated().sum()
    if duplicados > 0:
        print(f"  AVISO: {duplicados} order_id duplicados eliminados")
        df = df.drop_duplicates(subset="order_id", keep="first")
    else:
        print("  Sin order_id duplicados")

    return df

def calcular_metricas(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula venta_total y la categoría de venta."""
    df = df.copy()
    df["venta_total"] = df["cantidad"] * df["precio_unitario"]

    # Baja: < 20 | Media: 20 a 50 | Alta: >= 50
    df["categoria_venta"] = pd.cut(
        df["venta_total"],
        bins=[-np.inf, 20, 50, np.inf],
        labels=["Baja", "Media", "Alta"],
        right=False,
    )
    return df

def enriquecer(df: pd.DataFrame, productos: pd.DataFrame,
               tiendas: pd.DataFrame) -> pd.DataFrame:
    """Une productos y tiendas, y crea dimensiones temporales."""
    df = df.merge(productos, on="producto_id", how="left")
    df = df.merge(tiendas, on="tienda_id", how="left")

    dias = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
            4: "Viernes", 5: "Sábado", 6: "Domingo"}
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month
    df["dia_semana"] = df["fecha"].dt.dayofweek.map(dias)
    return df

def control_calidad(df: pd.DataFrame, productos: pd.DataFrame,
                    tiendas: pd.DataFrame) -> dict:
    """Verifica integridad referencial y rangos. Devuelve indicadores."""
    indicadores = {}

    # Integridad referencial
    prod_huerfanos = (~df["producto_id"].isin(productos["producto_id"])).sum()
    tienda_huerfanas = (~df["tienda_id"].isin(tiendas["tienda_id"])).sum()
    indicadores["productos_sin_match"] = int(prod_huerfanos)
    indicadores["tiendas_sin_match"] = int(tienda_huerfanas)

    # Rangos
    indicadores["cantidades_no_positivas"] = int((df["cantidad"] <= 0).sum())
    indicadores["precios_no_positivos"] = int((df["precio_unitario"] <= 0).sum())
    hoy = pd.Timestamp(datetime.now())
    indicadores["fechas_futuras"] = int((df["fecha"] > hoy).sum())

    indicadores["total_registros"] = len(df)
    indicadores["clientes_desconocidos"] = int(
        (df["cliente_id"] == "CLIENTE_DESCONOCIDO").sum()
    )

    print("  Control de calidad:")
    for k, v in indicadores.items():
        print(f"    {k}: {v}")
    return indicadores

def transformar(ventas, productos, tiendas):
    """FASE 2: ejecuta toda la transformación."""
    df = limpiar_ventas(ventas)
    df = calcular_metricas(df)
    df = enriquecer(df, productos, tiendas)
    indicadores = control_calidad(df, productos, tiendas)
    return df, indicadores

def guardar_dataset_completo(df: pd.DataFrame) -> pd.DataFrame:
    """Guarda todas las columnas del dataset transformado."""
    ruta = OUTPUT_DIR / "dataset_transformado.csv"
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"  Dataset completo: {ruta} ({len(df)} filas, {df.shape[1]} columnas)")
    return df

def crear_data_mart(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla agregada por ciudad, categoría y mes, lista para analizar."""
    mart = (
        df.groupby(["anio", "mes", "ciudad", "region", "categoria"],
                   observed=True)
        .agg(
            ventas_totales=("venta_total", "sum"),
            transacciones=("order_id", "count"),
            unidades_vendidas=("cantidad", "sum"),
            ticket_promedio=("venta_total", "mean"),
        )
        .round(2)
        .reset_index()
    )
    ruta = OUTPUT_DIR / "data_mart_ventas.csv"
    mart.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"  Data Mart: {ruta} ({len(mart)} filas)")
    return mart

def crear_resumen_ejecutivo(df: pd.DataFrame) -> pd.DataFrame:
    """Métricas clave del negocio en formato métrica/valor."""
    por_ciudad = df.groupby("ciudad")["venta_total"].sum()
    por_categoria = df.groupby("categoria")["venta_total"].sum()

    resumen = pd.DataFrame({
        "metrica": [
            "ventas_totales",
            "total_transacciones",
            "ticket_promedio",
            "unidades_vendidas",
            "clientes_unicos",
            "ciudad_lider",
            "ventas_ciudad_lider",
            "categoria_lider",
            "ventas_categoria_lider",
        ],
        "valor": [
            round(df["venta_total"].sum(), 2),
            len(df),
            round(df["venta_total"].mean(), 2),
            int(df["cantidad"].sum()),
            df.loc[df["cliente_id"] != "CLIENTE_DESCONOCIDO",
                   "cliente_id"].nunique(),
            por_ciudad.idxmax(),
            round(por_ciudad.max(), 2),
            por_categoria.idxmax(),
            round(por_categoria.max(), 2),
        ],
    })
    ruta = OUTPUT_DIR / "resumen_ejecutivo.csv"
    resumen.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"  Resumen ejecutivo: {ruta}")
    return resumen

def cargar(df: pd.DataFrame) -> tuple:
    """FASE 3: genera los tres archivos de salida."""
    print("\n=== FASE 3: CARGA ===")
    OUTPUT_DIR.mkdir(exist_ok=True)
    guardar_dataset_completo(df)
    mart = crear_data_mart(df)
    resumen = crear_resumen_ejecutivo(df)
    return mart, resumen

def generar_graficos(df: pd.DataFrame) -> None:
    """Genera y guarda las 4 visualizaciones pedidas."""
    sns.set_theme(style="whitegrid")

    # 1. Barras: ventas totales por ciudad
    por_ciudad = df.groupby("ciudad")["venta_total"].sum().sort_values(ascending=False)
    plt.figure(figsize=(8, 5))
    ax = sns.barplot(x=por_ciudad.index, y=por_ciudad.values, hue=por_ciudad.index,
                     palette="viridis", legend=False)
    for c in ax.containers:
        ax.bar_label(c, fmt="$%.1f")
    plt.title("Ventas totales por ciudad")
    plt.xlabel("Ciudad")
    plt.ylabel("Ventas ($)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "ventas_por_ciudad.png", dpi=150)
    plt.close()

    # 2. Pie: distribución de ventas por categoría
    por_cat = df.groupby("categoria")["venta_total"].sum()
    plt.figure(figsize=(7, 7))
    plt.pie(por_cat.values, labels=por_cat.index, autopct="%1.1f%%",
            startangle=90, colors=sns.color_palette("pastel"))
    plt.title("Distribución de ventas por categoría")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "ventas_por_categoria.png", dpi=150)
    plt.close()

    # 3. Barras: transacciones por día de la semana
    orden = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    por_dia = df["dia_semana"].value_counts().reindex(orden, fill_value=0)
    plt.figure(figsize=(9, 5))
    ax = sns.barplot(x=por_dia.index, y=por_dia.values, hue=por_dia.index,
                     palette="mako", legend=False)
    for c in ax.containers:
        ax.bar_label(c, fmt="%d")
    plt.title("Transacciones por día de la semana")
    plt.xlabel("Día")
    plt.ylabel("Número de transacciones")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "transacciones_por_dia.png", dpi=150)
    plt.close()

    # 4. Histograma: distribución de montos de venta
    plt.figure(figsize=(8, 5))
    sns.histplot(df["venta_total"], bins=8, kde=False, color="steelblue")
    plt.title("Distribución de montos de venta")
    plt.xlabel("Monto de la venta ($)")
    plt.ylabel("Frecuencia")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "histograma_montos.png", dpi=150)
    plt.close()

    print("  Gráficos guardados en output/ (4 archivos .png)")

def generar_reporte(df: pd.DataFrame, indicadores: dict) -> None:
    """Escribe el reporte ejecutivo en un archivo de texto."""
    total = df["venta_total"].sum()
    por_ciudad = df.groupby("ciudad")["venta_total"].sum().sort_values(ascending=False)
    por_cat = df.groupby("categoria")["venta_total"].sum().sort_values(ascending=False)
    por_dia = df["dia_semana"].value_counts()
    dist_cat_venta = df["categoria_venta"].value_counts()

    ciudad_lider, cat_lider = por_ciudad.index[0], por_cat.index[0]
    pct_ciudad = por_ciudad.iloc[0] / total * 100
    pct_cat = por_cat.iloc[0] / total * 100
    pct_desconocidos = indicadores["clientes_desconocidos"] / indicadores["total_registros"] * 100

    lineas = [
        "=" * 60,
        "REPORTE EJECUTIVO - SUPERMART COLOMBIA",
        "Elaborado por: EAN TechRetail Solutions",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M}",
        f"Periodo analizado: {df['fecha'].min():%Y-%m-%d} a {df['fecha'].max():%Y-%m-%d}",
        "=" * 60,
        "",
        "1. METRICAS PRINCIPALES",
        f"  Ventas totales:       ${total:,.2f}",
        f"  Transacciones:        {len(df)}",
        f"  Ticket promedio:      ${df['venta_total'].mean():,.2f}",
        f"  Unidades vendidas:    {int(df['cantidad'].sum())}",
        f"  Clientes identificados: "
        f"{df.loc[df['cliente_id'] != 'CLIENTE_DESCONOCIDO', 'cliente_id'].nunique()}",
        "",
        "2. TOP PERFORMERS",
        f"  Ciudad lider:    {ciudad_lider} (${por_ciudad.iloc[0]:,.2f}, {pct_ciudad:.1f}% del total)",
        f"  Categoria lider: {cat_lider} (${por_cat.iloc[0]:,.2f}, {pct_cat:.1f}% del total)",
        f"  Dia con mas transacciones: {por_dia.idxmax()} ({por_dia.max()})",
        "",
        "  Ventas por ciudad:",
        *[f"    - {c}: ${v:,.2f}" for c, v in por_ciudad.items()],
        "",
        "  Ventas por categoria:",
        *[f"    - {c}: ${v:,.2f}" for c, v in por_cat.items()],
        "",
        "  Segmentacion por monto de venta:",
        *[f"    - {c}: {n} transacciones" for c, n in dist_cat_venta.items()],
        "",
        "3. INDICADORES DE CALIDAD DE DATOS",
        *[f"  {k}: {v}" for k, v in indicadores.items()],
        f"  % de ventas sin cliente identificado: {pct_desconocidos:.1f}%",
        "",
        "4. INSIGHTS ACCIONABLES",
        f"  - {ciudad_lider} concentra {pct_ciudad:.1f}% de las ventas: reforzar inventario "
        f"all\u00ed y replicar sus practicas en las ciudades de menor desempe\u00f1o "
        f"({por_ciudad.index[-1]} es la mas baja).",
        f"  - {cat_lider} aporta {pct_cat:.1f}% de los ingresos: priorizar promociones "
        f"y disponibilidad de esta categoria.",
        f"  - {pct_desconocidos:.1f}% de las ventas no tiene cliente asociado: implementar "
        f"captura obligatoria del ID (programa de fidelizacion) para poder analizar recompra.",
        f"  - El dia {por_dia.idxmax()} es el de mayor trafico: concentrar personal "
        f"y campa\u00f1as ese dia.",
        "",
        "Nota: el analisis se basa en una muestra pequeña de datos; conviene validar "
        "las conclusiones con un volumen mayor.",
    ]

    ruta = OUTPUT_DIR / "reporte_ejecutivo.txt"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"  Reporte ejecutivo: {ruta}")


def analizar(df: pd.DataFrame, indicadores: dict) -> None:
    """FASE 4: gráficos y reporte."""
    print("\n=== FASE 4: ANALISIS Y REPORTES ===")
    generar_graficos(df)
    generar_reporte(df, indicadores)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    ventas, productos, tiendas = extraer()
    df, indicadores = transformar(ventas, productos, tiendas)
    cargar(df)
    analizar(df, indicadores)
    print("\nPipeline completado sin errores.")

if __name__ == "__main__":
    main()
