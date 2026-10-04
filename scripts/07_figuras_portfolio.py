"""
Fase 7 - Figuras para el portfolio (README y LinkedIn).

Ejecutar desde la carpeta del proyecto:
    python scripts/07_figuras_portfolio.py

Genera cuatro imágenes 16:9 en informe/figuras/. Ninguna cifra está escrita a mano:
todas se calculan aquí a partir de la base de datos original (consulta SQL) y de
las tablas limpias de data/clean (cohortes, segmentos y modelo).
"""
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SALIDA = Path("informe/figuras")
AZUL, NARANJA = "#3b6ea5", "#d9822b"
TINTA, GRIS, LINEA, FONDO = "#1F2937", "#6B7280", "#E5E7EB", "#F3F4F6"
PIE = "Olist · análisis de la cartera de clientes · Miguel Martín-Caro"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "text.color": TINTA, "axes.labelcolor": GRIS, "axes.edgecolor": LINEA,
    "xtick.color": GRIS, "ytick.color": GRIS, "xtick.labelsize": 10, "ytick.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": LINEA, "grid.linewidth": 0.8, "savefig.facecolor": "white",
})


def es(numero, decimales=1):
    """Número con coma decimal y punto de millares, como se escribe en español."""
    texto = f"{numero:,.{decimales}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def lienzo(etiqueta, titulo, subtitulo):
    """Figura 16:9 (2560 x 1440 px) con la cabecera y el pie comunes."""
    fig = plt.figure(figsize=(12.8, 7.2), dpi=200)
    fig.text(0.05, 0.925, etiqueta.upper(), color=AZUL, size=11, weight="bold")
    fig.text(0.05, 0.862, titulo, size=24, weight="bold")
    fig.text(0.05, 0.812, subtitulo, color=GRIS, size=12.5)
    fig.text(0.05, 0.04, PIE, color=GRIS, size=9)
    fig.text(0.95, 0.04, "Datos públicos de Olist, 2017-2018", color=GRIS, size=9, ha="right")
    return fig


def guardar(fig, nombre):
    SALIDA.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA / nombre)
    plt.close(fig)
    print("  ", SALIDA / nombre)


def tablero(fig):
    """Ejes invisibles que ocupan toda la figura, en unidades 16 x 9, para colocar tarjetas y texto."""
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")
    return ax


def tarjeta(ax, x, y, ancho, alto, relleno=FONDO, borde="none"):
    ax.add_patch(FancyBboxPatch((x, y), ancho, alto, boxstyle="round,pad=0,rounding_size=0.14",
                                facecolor=relleno, edgecolor=borde, linewidth=0.8))


# ======================================================================================
# 1. Cálculos
# ======================================================================================

def _col(expresion, alias, coma=","):
    """Línea del SELECT con los alias alineados en la misma columna."""
    return f"{expresion:<60} AS {alias}{coma}"


CONSULTA = f"""-- ¿Afecta el retraso en la entrega a la valoración?
WITH entregas AS (
    SELECT order_id,
           julianday(order_delivered_customer_date)
         - julianday(order_estimated_delivery_date) AS dias_vs_estimado
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
),
-- Un pedido puede tener varias valoraciones: se usa la más reciente
ultima_valoracion AS (
    SELECT order_id, review_score
    FROM (SELECT order_id, review_score,
                 ROW_NUMBER() OVER (PARTITION BY order_id
                                    ORDER BY review_answer_timestamp DESC) AS n
          FROM order_reviews)
    WHERE n = 1
)
SELECT CASE WHEN e.dias_vs_estimado <= 0 THEN 'A tiempo'
            WHEN e.dias_vs_estimado <= 7 THEN 'Hasta 7 días tarde'
{_col("            ELSE 'Más de 7 días tarde' END", "entrega")}
{_col("       COUNT(*)", "pedidos")}
{_col("       ROUND(AVG(r.review_score), 2)", "nota_media")}
{_col("       ROUND(100.0 * SUM(r.review_score <= 2) / COUNT(*), 1)", "pct_mala_nota", coma="")}
FROM entregas e
JOIN ultima_valoracion r ON r.order_id = e.order_id
GROUP BY entrega
ORDER BY MIN(e.dias_vs_estimado)"""


def calcular():
    r = {}

    # --- Consulta SQL sobre la base de datos original
    con = sqlite3.connect("data/olist.db")
    r["sql"] = pd.read_sql(CONSULTA, con)
    con.close()

    pedidos = pd.read_csv("data/clean/pedidos.csv",
                          parse_dates=["order_purchase_timestamp", "order_estimated_delivery_date"])
    clientes = pd.read_csv("data/clean/clientes.csv")

    # --- Cifras de la portada
    por_cliente = pedidos.groupby("customer_unique_id")["order_id"].count()
    r["pedidos"] = len(pedidos)
    r["pct_una_compra"] = 100 * (por_cliente == 1).mean()
    valorados = pedidos.dropna(subset=["review_score"])
    mala = valorados["review_score"] <= 2
    r["pct_mala_muy_tarde"] = 100 * mala[valorados["dias_vs_estimado"] > 7].mean()
    r["pct_mala_a_tiempo"] = 100 * mala[valorados["dias_vs_estimado"] <= 0].mean()
    alto_valor = clientes["segmento"].str.startswith("Alto valor")
    r["pct_clientes_alto_valor"] = 100 * alto_valor.mean()
    r["pct_ingresos_alto_valor"] = 100 * clientes.loc[alto_valor, "gasto"].sum() / clientes["gasto"].sum()

    # --- Cohortes de retención (igual que en notebooks/04_segmentacion.ipynb)
    pedidos["mes"] = pedidos["order_purchase_timestamp"].dt.to_period("M")
    pedidos["cohorte"] = pedidos.groupby("customer_unique_id")["mes"].transform("min")
    pedidos["n_mes"] = ((pedidos["mes"].dt.year - pedidos["cohorte"].dt.year) * 12
                        + (pedidos["mes"].dt.month - pedidos["cohorte"].dt.month))
    tabla = pedidos.groupby(["cohorte", "n_mes"])["customer_unique_id"].nunique().unstack()
    r["cohortes_tamano"] = tabla[0]
    r["cohortes"] = (tabla.div(tabla[0], axis=0) * 100).iloc[:, 1:13]

    # --- Modelo (mismas variables, partición y parámetros que notebooks/05_modelo.ipynb)
    datos = valorados.copy()
    datos["mala_nota"] = (datos["review_score"] <= 2).astype(int)
    datos["dias_prometidos"] = (datos["order_estimated_delivery_date"]
                                - datos["order_purchase_timestamp"]).dt.total_seconds() / 86400
    datos["pct_envio"] = datos["valor_envio"] / datos["valor_total"]
    top = datos["categoria_principal"].value_counts().head(15).index
    datos["categoria"] = datos["categoria_principal"].where(datos["categoria_principal"].isin(top), "otras")
    numericas = ["valor_total", "valor_envio", "pct_envio", "n_items", "n_vendedores", "cuotas",
                 "dias_prometidos", "dias_entrega", "dias_vs_estimado"]
    categoricas = ["categoria", "customer_state", "tipo_pago"]
    X = pd.get_dummies(datos[numericas + categoricas], columns=categoricas, dtype=int)
    y = datos["mala_nota"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    logistica = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
    bosque = RandomForestClassifier(n_estimators=300, min_samples_leaf=20, class_weight="balanced",
                                    n_jobs=-1, random_state=42)
    prob_log = logistica.fit(X_train, y_train).predict_proba(X_test)[:, 1]
    prob_rf = bosque.fit(X_train, y_train).predict_proba(X_test)[:, 1]

    r["roc_rf"] = roc_curve(y_test, prob_rf)[:2]
    r["roc_log"] = roc_curve(y_test, prob_log)[:2]
    r["auc_rf"] = roc_auc_score(y_test, prob_rf)
    r["auc_log"] = roc_auc_score(y_test, prob_log)

    # Curva de ganancia: pedidos ordenados de más a menos riesgo
    orden = np.argsort(-prob_rf)
    r["ganancia_x"] = 100 * np.arange(1, len(orden) + 1) / len(orden)
    r["ganancia_y"] = 100 * np.cumsum(y_test.values[orden]) / y_test.sum()
    r["ganancia_10"] = r["ganancia_y"][int(len(orden) * 0.10) - 1]
    r["tasa_base"] = 100 * y_test.mean()
    return r


# ======================================================================================
# 2. Figuras
# ======================================================================================

def figura_resumen(r):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=200)
    ax = tablero(fig)
    ax.text(0.8, 8.2, "PROYECTO DE ANÁLISIS DE DATOS", color=AZUL, size=11, weight="bold")
    ax.text(0.8, 7.5, "Olist: por qué los clientes no repiten compra", size=30, weight="bold")
    ax.text(0.8, 6.95, f"Análisis de principio a fin de {es(r['pedidos'], 0)} pedidos reales de un marketplace brasileño (2017-2018)",
            color=GRIS, size=13.5)

    cifras = [
        (f"{es(r['pct_una_compra'], 0)} %", "de los clientes compra\nuna sola vez"),
        (f"{es(r['pct_mala_muy_tarde'], 0)} %",
         f"de malas notas si el pedido llega\nmás de 7 días tarde\n({es(r['pct_mala_a_tiempo'], 0)} % si llega a tiempo)"),
        (f"{es(r['pct_ingresos_alto_valor'], 0)} %",
         f"de los ingresos procede del\n{es(r['pct_clientes_alto_valor'], 0)} % de los clientes"),
        (f"{es(r['ganancia_10'], 1)} %", "de las malas notas está en el\n10 % de pedidos que el modelo\nmarca como de riesgo"),
    ]
    for i, (valor, texto) in enumerate(cifras):
        x = 0.8 + i * 3.66
        tarjeta(ax, x, 3.95, 3.42, 2.35)
        ax.text(x + 0.3, 5.42, valor, size=40, weight="bold")
        ax.text(x + 0.3, 5.14, texto, size=10.5, color=GRIS, va="top", linespacing=1.35)

    ax.text(0.8, 3.38, "EL PROCESO", color=GRIS, size=10, weight="bold")
    pasos = [
        ("SQL", "9 tablas · JOIN, CTE\ny funciones ventana"),
        ("Limpieza", "nulos, duplicados y\nvalores anómalos"),
        ("EDA y KPIs", "ingresos, recompra,\nentrega y valoración"),
        ("Segmentación", "RFM, cohortes\ny K-means"),
        ("Modelo", f"random forest\nAUC {es(r['auc_rf'], 2)}"),
        ("Power BI", "4 páginas\n21 medidas DAX"),
        ("Informe", "conclusiones y\nrecomendaciones"),
    ]
    for i, (nombre, detalle) in enumerate(pasos):
        x = 0.8 + i * 2.09
        tarjeta(ax, x, 1.4, 1.86, 1.7, relleno="white", borde=LINEA)
        ax.text(x + 0.2, 2.72, str(i + 1), size=10, weight="bold", color=AZUL)
        ax.text(x + 0.2, 2.34, nombre, size=12.5, weight="bold")
        ax.text(x + 0.2, 2.1, detalle, size=9, color=GRIS, va="top", linespacing=1.35)
        if i < len(pasos) - 1:
            ax.text(x + 1.975, 2.25, "›", size=16, color=GRIS, ha="center", va="center")

    ax.plot([0.8, 15.2], [0.98, 0.98], color=LINEA, linewidth=0.8)
    ax.text(0.8, 0.52, "Miguel Martín-Caro  ·  github.com/MiguelUFV/olist-analisis-clientes", size=10, color=GRIS)
    ax.text(15.2, 0.52, "Proyecto personal con datos públicos de Olist", size=10, color=GRIS, ha="right")
    guardar(fig, "1_resumen_proyecto.png")


def figura_sql(r):
    fig = lienzo("SQL", "¿Afecta el retraso en la entrega a la valoración?",
                 "Consulta con dos CTE y la función ventana ROW_NUMBER() sobre la base de datos original (SQLite, 9 tablas)")
    ax = tablero(fig)

    # Tarjeta con la consulta, tal cual se ejecuta
    tarjeta(ax, 0.8, 0.85, 9.0, 6.0, relleno="#F8FAFC", borde=LINEA)
    lineas = CONSULTA.splitlines()
    paso = 5.5 / len(lineas)
    for i, linea in enumerate(lineas):
        ax.text(1.05, 6.55 - i * paso, linea, family="Consolas", size=8.3, va="top",
                color=GRIS if linea.lstrip().startswith("--") else TINTA)

    # Tarjeta con el resultado
    tarjeta(ax, 10.1, 0.85, 5.1, 6.0, relleno="white", borde=LINEA)
    ax.text(10.4, 6.38, "RESULTADO", color=GRIS, size=10, weight="bold")
    ax.text(10.4, 5.98, "% de pedidos con 1 o 2 estrellas", size=11, color=GRIS)
    ancho_max = 3.4
    for i, fila in r["sql"].iterrows():
        y = 5.2 - i * 1.45
        ax.text(10.4, y, fila["entrega"], size=13, weight="bold")
        ax.text(10.4, y - 0.34, f"{es(fila['pedidos'], 0)} pedidos · nota media {es(fila['nota_media'], 2)}",
                size=9.5, color=GRIS)
        ax.add_patch(FancyBboxPatch((10.4, y - 0.86), ancho_max, 0.2, boxstyle="round,pad=0,rounding_size=0.1",
                                    facecolor=FONDO, edgecolor="none"))
        ax.add_patch(FancyBboxPatch((10.4, y - 0.86), ancho_max * fila["pct_mala_nota"] / 100, 0.2,
                                    boxstyle="round,pad=0,rounding_size=0.1", facecolor=NARANJA, edgecolor="none"))
        ax.text(10.4 + ancho_max + 0.2, y - 0.76, f"{es(fila['pct_mala_nota'], 1)} %", size=13, weight="bold", va="center")
    ax.text(10.4, 1.12, "Tablas orders y order_reviews.", size=8.5, color=GRIS)
    guardar(fig, "2_sql_retraso_valoracion.png")


def figura_cohortes(r):
    tabla = r["cohortes"].dropna(how="all")              # la última cohorte aún no tiene meses posteriores
    tamano = r["cohortes_tamano"].loc[tabla.index]
    assert np.nanmax(tabla.values) < 1, "El título dice que no se llega al 1 %: revisar"
    fig = lienzo("Python · análisis de cohortes", "La retención mensual nunca llega al 1 %",
                 "% de los clientes de cada cohorte mensual que repite compra N meses después de su primera compra")
    ax = fig.add_axes([0.17, 0.13, 0.68, 0.62])
    imagen = ax.imshow(tabla.values, cmap="Blues", aspect="auto", vmin=0, vmax=np.nanmax(tabla.values))
    for i in range(tabla.shape[0]):
        for j in range(tabla.shape[1]):
            v = tabla.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, es(v, 1), ha="center", va="center", size=7.5,
                        color="white" if v > 0.6 * np.nanmax(tabla.values) else TINTA)
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    ax.set_yticks(range(tabla.shape[0]),
                  [f"{meses[c.month - 1]} {c.year}  ·  {es(n, 0)} clientes" for c, n in zip(tabla.index, tamano)], size=8.5)
    ax.set_xticks(range(tabla.shape[1]), tabla.columns, size=9)
    ax.set_xlabel("meses desde la primera compra", size=10.5, labelpad=8)
    ax.tick_params(length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)
    barra = fig.colorbar(imagen, cax=fig.add_axes([0.875, 0.13, 0.012, 0.62]))
    barra.outline.set_visible(False)
    barra.ax.tick_params(length=0, labelsize=9)
    barra.set_label("% de la cohorte", size=10)
    barra.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: es(v, 1)))
    guardar(fig, "3_python_cohortes_retencion.png")


def figura_modelo(r):
    fig = lienzo("Python · scikit-learn", "Un modelo para anticipar las malas valoraciones",
                 "Clasificación de pedidos entregados según su riesgo de recibir 1 o 2 estrellas (19.112 pedidos de prueba)")

    # Izquierda: curva ROC
    ax = fig.add_axes([0.07, 0.14, 0.38, 0.56])
    ax.plot(*r["roc_rf"], color=AZUL, linewidth=2, label=f"Random forest · AUC {es(r['auc_rf'], 3)}")
    ax.plot(*r["roc_log"], color=NARANJA, linewidth=2, label=f"Regresión logística · AUC {es(r['auc_log'], 3)}")
    ax.plot([0, 1], [0, 1], color=GRIS, linewidth=1, linestyle=(0, (4, 3)), label="Al azar · AUC 0,5")
    ax.set_xlabel("falsos positivos", size=10.5)
    ax.set_ylabel("malas notas detectadas (recall)", size=10.5)
    ax.set_title("Curva ROC", loc="left", size=13, weight="bold", pad=12)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: es(v, 1)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: es(v, 1)))
    ax.grid(True)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right", fontsize=10)

    # Derecha: curva de ganancia
    ax = fig.add_axes([0.56, 0.14, 0.38, 0.56])
    ax.plot(r["ganancia_x"], r["ganancia_y"], color=AZUL, linewidth=2, label="Pedidos ordenados por el modelo")
    ax.plot([0, 100], [0, 100], color=GRIS, linewidth=1, linestyle=(0, (4, 3)), label="Pedidos elegidos al azar")
    ax.plot([10], [r["ganancia_10"]], marker="o", markersize=9, color=AZUL, markeredgecolor="white", markeredgewidth=2)
    ax.annotate(f"Contactando con el 10 %\nde los pedidos se llega al\n{es(r['ganancia_10'], 1)} % de las malas notas",
                xy=(10, r["ganancia_10"]), xytext=(4, 80), va="center", size=10.5, linespacing=1.35,
                arrowprops={"arrowstyle": "-", "color": GRIS, "linewidth": 0.8})
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 101)
    ax.set_xlabel("% de pedidos contactados, de más a menos riesgo", size=10.5)
    ax.set_ylabel("% de malas notas alcanzadas", size=10.5)
    ax.set_title("Curva de ganancia", loc="left", size=13, weight="bold", pad=12)
    ax.grid(True)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right", fontsize=10)
    guardar(fig, "4_python_modelo_predictivo.png")


if __name__ == "__main__":
    print("Calculando (el modelo tarda alrededor de un minuto)...")
    resultados = calcular()
    print("Figuras:")
    figura_resumen(resultados)
    figura_sql(resultados)
    figura_cohortes(resultados)
    figura_modelo(resultados)
    print(resultados["sql"].to_string(index=False))
    print(f"una compra {resultados['pct_una_compra']:.2f} | muy tarde {resultados['pct_mala_muy_tarde']:.1f} | "
          f"a tiempo {resultados['pct_mala_a_tiempo']:.1f} | alto valor {resultados['pct_clientes_alto_valor']:.1f} -> "
          f"{resultados['pct_ingresos_alto_valor']:.1f} | ganancia 10% {resultados['ganancia_10']:.1f} | "
          f"AUC rf {resultados['auc_rf']:.3f} log {resultados['auc_log']:.3f}")
