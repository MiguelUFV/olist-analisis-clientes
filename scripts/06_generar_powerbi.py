"""
Fase 6 - Generar el proyecto de Power BI (formato PBIP) como archivos de texto.

Ejecutar desde la carpeta del proyecto:
    python scripts/06_generar_powerbi.py

Un .pbix es un archivo binario que solo Power BI puede escribir. Un proyecto .pbip es lo mismo
guardado como carpetas de texto, y por eso se puede generar con código:

    powerbi/olist.pbip                  -> el archivo que se abre con Power BI Desktop
    powerbi/olist.SemanticModel/        -> modelo de datos en TMDL: tablas, relaciones y medidas DAX
    powerbi/olist.Report/               -> informe en PBIR: un JSON por página y por gráfico

Tras abrirlo hay que pulsar "Actualizar" para que Power BI cargue los CSV de data/clean.
"""
import json
import re
import shutil
import uuid
from pathlib import Path

PROYECTO = Path("powerbi")
MODELO = PROYECTO / "olist.SemanticModel"
INFORME = PROYECTO / "olist.Report"
RUTA_DATOS = str(Path("data/clean").resolve()) + "\\"
TEMA_BASE = PROYECTO / "tema_base_CY24SU10.json"      # tema por defecto de Power BI

ESQUEMAS = "https://developer.microsoft.com/json-schemas/fabric"
AZUL, NARANJA, FONDO, TINTA = "#3b6ea5", "#d9822b", "#F3F4F6", "#1F2937"


def escribir(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(contenido, str):
        contenido = json.dumps(contenido, indent=2, ensure_ascii=False)
    ruta.write_text(contenido, encoding="utf-8")


def guid(nombre):
    """Identificador estable: el mismo nombre da siempre el mismo GUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "olist/" + nombre))


def q(nombre):
    """En TMDL, los nombres con espacios o símbolos van entre comillas simples."""
    return nombre if re.fullmatch(r"[A-Za-z0-9_]+", nombre) else f"'{nombre}'"


# ======================================================================================
# 1. MODELO SEMÁNTICO (TMDL)
# ======================================================================================

# Cada tabla: columnas (nombre, tipo, formato, ordenar_por), consulta M que la carga y medidas DAX
TABLAS = {
    "Pedidos": {
        "columnas": [
            ("order_id", "string", None, None), ("customer_unique_id", "string", None, None),
            ("customer_state", "string", None, None), ("categoria_principal", "string", None, None),
            ("tipo_pago", "string", None, None), ("n_items", "double", None, None),
            ("n_vendedores", "double", None, None), ("valor_productos", "double", None, None),
            ("valor_envio", "double", None, None), ("valor_total", "double", None, None),
            ("review_score", "double", None, None), ("dias_entrega", "double", None, None),
            ("dias_vs_estimado", "double", None, None), ("con_retraso", "boolean", None, None),
            ("fecha_compra", "dateTime", "dd/MM/yyyy", None),
            ("tramo_entrega", "string", None, "tramo_orden"), ("tramo_orden", "int64", None, None),
            ("tipo_pedido", "string", None, None),
        ],
        "m": """let
    Origen = Csv.Document(File.Contents(RutaDatos & "pedidos.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Columnas = Table.SelectColumns(Encabezados, {"order_id", "customer_unique_id", "customer_state", "categoria_principal", "tipo_pago", "order_purchase_timestamp", "n_items", "n_vendedores", "valor_productos", "valor_envio", "valor_total", "review_score", "dias_entrega", "dias_vs_estimado", "con_retraso"}),
    Tipos = Table.TransformColumnTypes(Columnas, {{"order_purchase_timestamp", type datetime}, {"n_items", type number}, {"n_vendedores", type number}, {"valor_productos", type number}, {"valor_envio", type number}, {"valor_total", type number}, {"review_score", type number}, {"dias_entrega", type number}, {"dias_vs_estimado", type number}, {"con_retraso", type logical}}, "en-US"),
    Fecha = Table.AddColumn(Tipos, "fecha_compra", each DateTime.Date([order_purchase_timestamp]), type date),
    Tramo = Table.AddColumn(Fecha, "tramo_entrega", each if [dias_vs_estimado] <= 0 then "A tiempo" else if [dias_vs_estimado] <= 3 then "1-3 días tarde" else if [dias_vs_estimado] <= 7 then "4-7 días tarde" else "Más de 7 días tarde", type text),
    TramoOrden = Table.AddColumn(Tramo, "tramo_orden", each if [dias_vs_estimado] <= 0 then 1 else if [dias_vs_estimado] <= 3 then 2 else if [dias_vs_estimado] <= 7 then 3 else 4, Int64.Type),
    TipoPedido = Table.AddColumn(TramoOrden, "tipo_pedido", each if [n_vendedores] >= 2 then "Varios vendedores" else if [n_items] >= 2 then "Varios productos, 1 vendedor" else "1 producto", type text),
    Final = Table.RemoveColumns(TipoPedido, {"order_purchase_timestamp"})
in
    Final""",
        "medidas": [
            ("Pedidos totales", "COUNTROWS(Pedidos)", "#,0"),
            ("Ingresos", "SUM(Pedidos[valor_total])", "#,0"),
            ("Ticket medio", "DIVIDE([Ingresos], [Pedidos totales])", "#,0.00"),
            ("Clientes únicos", "DISTINCTCOUNT(Pedidos[customer_unique_id])", "#,0"),
            ("% Clientes que repiten",
             "DIVIDE(COUNTROWS(FILTER(VALUES(Pedidos[customer_unique_id]), CALCULATE(COUNTROWS(Pedidos)) >= 2)), [Clientes únicos])",
             "0.0%"),
            ("Nota media", "AVERAGE(Pedidos[review_score])", "0.00"),
            ("% Mala nota",
             # El ">= 1" es necesario: en DAX un valor en blanco cuenta como 0, y 0 <= 2 es verdadero
             "DIVIDE(CALCULATE(COUNTROWS(Pedidos), Pedidos[review_score] >= 1 && Pedidos[review_score] <= 2), CALCULATE(COUNTROWS(Pedidos), NOT ISBLANK(Pedidos[review_score])))",
             "0.0%"),
            ("% Retraso", "DIVIDE(CALCULATE(COUNTROWS(Pedidos), Pedidos[con_retraso] = TRUE()), [Pedidos totales])", "0.0%"),
            ("Días de entrega", "AVERAGE(Pedidos[dias_entrega])", "0.0"),
            # Para rankings: con muy pocos pedidos el porcentaje no es fiable y se deja en blanco
            ("% Mala nota (mín. 100 pedidos)", "IF([Pedidos totales] >= 100, [% Mala nota])", "0.0%"),
            ("Pedidos con mala nota", "CALCULATE(COUNTROWS(Pedidos), Pedidos[review_score] >= 1 && Pedidos[review_score] <= 2)", "#,0"),
        ],
    },
    "Clientes": {
        "columnas": [
            ("customer_unique_id", "string", None, None), ("estado", "string", None, None),
            ("recencia", "double", None, None), ("frecuencia", "double", None, None),
            ("gasto", "double", None, None), ("nota_media", "double", None, None),
            ("segmento", "string", None, None), ("cluster", "string", None, None),
        ],
        "m": """let
    Origen = Csv.Document(File.Contents(RutaDatos & "clientes.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Columnas = Table.SelectColumns(Encabezados, {"customer_unique_id", "estado", "recencia", "frecuencia", "gasto", "nota_media", "segmento", "cluster"}),
    Tipos = Table.TransformColumnTypes(Columnas, {{"recencia", type number}, {"frecuencia", type number}, {"gasto", type number}, {"nota_media", type number}}, "en-US"),
    Final = Table.ReplaceValue(Tipos, "", "Sin valoración", Replacer.ReplaceValue, {"cluster"})
in
    Final""",
        "medidas": [
            ("Nº clientes", "COUNTROWS(Clientes)", "#,0"),
            ("% de clientes", "DIVIDE([Nº clientes], CALCULATE([Nº clientes], ALL(Clientes)))", "0.0%"),
            ("Gasto de clientes", "SUM(Clientes[gasto])", "#,0"),
            ("% de ingresos", "DIVIDE([Gasto de clientes], CALCULATE([Gasto de clientes], ALL(Clientes)))", "0.0%"),
            ("Gasto medio por cliente", "AVERAGE(Clientes[gasto])", "#,0.00"),
            ("Recencia media (días)", "AVERAGE(Clientes[recencia])", "#,0"),
            ("Nota media del cliente", "AVERAGE(Clientes[nota_media])", "0.00"),
        ],
    },
    "Items": {
        "columnas": [
            ("order_id", "string", None, None), ("categoria", "string", None, None),
            ("price", "double", None, None), ("freight_value", "double", None, None),
        ],
        "m": """let
    Origen = Csv.Document(File.Contents(RutaDatos & "items.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Columnas = Table.SelectColumns(Encabezados, {"order_id", "categoria", "price", "freight_value"}),
    Tipos = Table.TransformColumnTypes(Columnas, {{"price", type number}, {"freight_value", type number}}, "en-US")
in
    Tipos""",
        "medidas": [
            ("Ingresos de producto", "SUM(Items[price])", "#,0"),
            ("Unidades vendidas", "COUNTROWS(Items)", "#,0"),
            ("Precio medio", "AVERAGE(Items[price])", "#,0.00"),
        ],
    },
    "Calendario": {
        "columnas": [
            ("Fecha", "dateTime", "dd/MM/yyyy", None), ("Mes", "dateTime", "MMM yyyy", None),
            ("Año", "int64", "0", None),
        ],
        "m": """let
    Fechas = List.Dates(#date(2017, 1, 1), 608, #duration(1, 0, 0, 0)),
    Tabla = Table.FromList(Fechas, Splitter.SplitByNothing(), {"Fecha"}),
    Tipos = Table.TransformColumnTypes(Tabla, {{"Fecha", type date}}),
    Mes = Table.AddColumn(Tipos, "Mes", each Date.StartOfMonth([Fecha]), type date),
    Anio = Table.AddColumn(Mes, "Año", each Date.Year([Fecha]), Int64.Type)
in
    Anio""",
        "medidas": [],
    },
}

# Relaciones: de la tabla de "muchos" a la de "uno"
RELACIONES = [
    ("Pedidos.customer_unique_id", "Clientes.customer_unique_id"),
    ("Pedidos.fecha_compra", "Calendario.Fecha"),
    ("Items.order_id", "Pedidos.order_id"),
]


def tmdl_tabla(nombre, t):
    lineas = [f"table {q(nombre)}", f"\tlineageTag: {guid('tabla/' + nombre)}", ""]
    for medida, dax, formato in t["medidas"]:
        lineas += [f"\tmeasure {q(medida)} = {dax}", f"\t\tformatString: {formato}",
                   f"\t\tlineageTag: {guid('medida/' + medida)}", ""]
    for col, tipo, formato, ordenar_por in t["columnas"]:
        lineas += [f"\tcolumn {q(col)}", f"\t\tdataType: {tipo}"]
        if formato:
            lineas.append(f"\t\tformatString: {formato}")
        if ordenar_por:
            lineas.append(f"\t\tsortByColumn: {q(ordenar_por)}")
        lineas += [f"\t\tlineageTag: {guid(f'columna/{nombre}/{col}')}", "\t\tsummarizeBy: none",
                   f"\t\tsourceColumn: {col}", ""]
    lineas += [f"\tpartition {q(nombre)} = m", "\t\tmode: import", "\t\tsource ="]
    lineas += ["\t\t\t\t" + linea for linea in t["m"].splitlines()]
    lineas += ["", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(lineas)


def generar_modelo():
    d = MODELO / "definition"
    escribir(MODELO / "definition.pbism", {
        "$schema": f"{ESQUEMAS}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}})
    escribir(MODELO / ".platform", plataforma("SemanticModel"))
    escribir(d / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    escribir(d / "model.tmdl", "\n".join([
        "model Model", "\tculture: es-ES", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: es-ES", "\tdataAccessOptions", "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull", "",
        # Sin esto Power BI crea una tabla de fechas oculta por cada columna de fecha
        "annotation __PBI_TimeIntelligenceEnabled = 0", "",
        'annotation PBI_QueryOrder = ["RutaDatos","Pedidos","Clientes","Items","Calendario"]', "",
        *[f"ref table {q(n)}" for n in TABLAS], ""]))
    escribir(d / "expressions.tmdl", "\n".join([
        f'expression RutaDatos = "{RUTA_DATOS}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {guid('expresion/RutaDatos')}", "", "\tannotation PBI_ResultType = Text", ""]))
    escribir(d / "relationships.tmdl", "\n".join(
        f"relationship {guid(origen + destino)}\n\tfromColumn: {origen}\n\ttoColumn: {destino}\n"
        for origen, destino in RELACIONES))
    for nombre, t in TABLAS.items():
        escribir(d / "tables" / f"{nombre}.tmdl", tmdl_tabla(nombre, t))


# ======================================================================================
# 2. INFORME (PBIR)
# ======================================================================================

def lit(valor):
    """Valor literal en el formato de expresiones de Power BI."""
    return {"expr": {"Literal": {"Value": valor}}}


def color(hex_):
    return {"solid": {"color": lit(f"'{hex_}'")}}


def campo(ref):
    """'Tabla.Campo' -> referencia a columna o medida, según lo que sea en el modelo."""
    tabla, nombre = ref.split(".", 1)
    es_medida = any(nombre == m[0] for m in TABLAS[tabla]["medidas"])
    return {"Measure" if es_medida else "Column": {
        "Expression": {"SourceRef": {"Entity": tabla}}, "Property": nombre}}


def proyeccion(ref, activa=False, nombre=None):
    """Campo dentro de un visual. 'nombre' es el texto que verá el usuario en vez del nombre técnico."""
    p = {"field": campo(ref), "queryRef": ref, "nativeQueryRef": nombre or ref.split(".", 1)[1]}
    if nombre:
        p["displayName"] = nombre
    if activa:
        p["active"] = True
    return p


def marco(titulo):
    """Título, fondo blanco y sin borde: el aspecto común de todas las tarjetas y gráficos."""
    return {
        "title": [{"properties": {"show": lit("true"), "text": lit(f"'{titulo}'"),
                                  "fontSize": lit("11D"), "fontColor": color(TINTA)}}],
        "background": [{"properties": {"show": lit("true"), "color": color("#FFFFFF"),
                                       "transparency": lit("0D")}}],
        "border": [{"properties": {"show": lit("false")}}],
    }


def contenedor(nombre, x, y, ancho, alto, visual):
    return {"$schema": f"{ESQUEMAS}/item/report/definition/visualContainer/2.7.0/schema.json",
            "name": nombre, "position": {"x": x, "y": y, "z": 0, "width": ancho, "height": alto, "tabOrder": 0},
            "visual": visual}


def texto(nombre, x, y, ancho, alto, titulo, subtitulo):
    return contenedor(nombre, x, y, ancho, alto, {
        "visualType": "textbox",
        "objects": {"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": titulo, "textStyle": {"fontSize": "18pt", "fontWeight": "bold", "color": TINTA}}]},
            {"textRuns": [{"value": subtitulo, "textStyle": {"fontSize": "9pt", "color": "#6B7280"}}]},
        ]}}]},
        "drillFilterOtherVisuals": True})


def tarjeta(nombre, x, y, ancho, alto, medida):
    return contenedor(nombre, x, y, ancho, alto, {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [proyeccion(medida)]}}},
        "objects": {"labels": [{"properties": {"fontSize": lit("22D"), "color": color(TINTA),
                                               "labelDisplayUnits": lit("1D")}}],  # 1 = cifra completa, sin "mil" ni "mill."
                    "categoryLabels": [{"properties": {"show": lit("true"), "fontSize": lit("10D")}}]},
        "visualContainerObjects": {"background": marco("")["background"], "border": marco("")["border"]},
        "drillFilterOtherVisuals": True})


def grafico(nombre, tipo, x, y, ancho, alto, titulo, categoria, medida, orden="medida",
            tooltips=(), color_serie=AZUL, etiqueta_eje=None):
    """tipo: lineChart, barChart (horizontal) o columnChart (vertical).
    tooltips: medidas extra que aparecen al pasar el ratón por encima.
    color_serie: azul para magnitudes neutras, naranja para indicadores de problema."""
    if orden == "medida":
        sort = {"field": campo(medida), "direction": "Descending"}
    else:
        sort = {"field": campo(categoria), "direction": "Ascending"}
    es_linea = tipo == "lineChart"
    estado = {"Category": {"projections": [proyeccion(categoria, activa=True, nombre=etiqueta_eje)]},
              "Y": {"projections": [proyeccion(medida)]}}
    if tooltips:
        estado["Tooltips"] = {"projections": [proyeccion(t) for t in tooltips]}
    return contenedor(nombre, x, y, ancho, alto, {
        "visualType": tipo,
        "query": {"queryState": estado, "sortDefinition": {"sort": [sort]}},
        "objects": {
            "dataPoint": [{"properties": {"fill": color(color_serie)}}],
            "labels": [{"properties": {"show": lit("false" if es_linea else "true"), "labelPrecision": lit("1L")}}],
            # maxMarginFactor: % del ancho reservado a los nombres del eje, para que no se corten
            "categoryAxis": [{"properties": {"showAxisTitle": lit("false"), "maxMarginFactor": lit("40L")}}],
            "valueAxis": [{"properties": {"showAxisTitle": lit("false")}}],
            "legend": [{"properties": {"show": lit("false")}}],
        },
        "visualContainerObjects": marco(titulo),
        "drillFilterOtherVisuals": True})


def tabla(nombre, x, y, ancho, alto, titulo, campos):
    """campos: lista de 'Tabla.Campo' o de tuplas ('Tabla.Campo', 'Nombre visible')."""
    proyecciones = [proyeccion(c) if isinstance(c, str) else proyeccion(c[0], nombre=c[1]) for c in campos]
    primera_medida = next(c for c in campos if isinstance(c, str))
    return contenedor(nombre, x, y, ancho, alto, {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": proyecciones}},
                  "sortDefinition": {"sort": [{"field": campo(primera_medida), "direction": "Descending"}]}},
        "visualContainerObjects": marco(titulo),
        "drillFilterOtherVisuals": True})


def filtro(nombre, x, columna, titulo, grupo=None):
    """Desplegable de filtro en la franja superior. Los filtros con el mismo 'grupo' se
    sincronizan entre páginas: lo que se elige en una se mantiene en las demás."""
    visual = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [proyeccion(columna, activa=True, nombre=titulo)]}}},
        "objects": {"data": [{"properties": {"mode": lit("'Dropdown'")}}],
                    "header": [{"properties": {"show": lit("false")}}]},
        "visualContainerObjects": marco(titulo),
        "drillFilterOtherVisuals": True}
    if grupo:
        visual["syncGroup"] = {"groupName": grupo, "fieldChanges": True, "filterChanges": True}
    return contenedor(nombre, x, 12, 200, 64, visual)


def fila_tarjetas(prefijo, medidas, y=84, alto=92):
    """Reparte las tarjetas a lo ancho de la página (1280 px, márgenes de 24 y separación de 12)."""
    ancho = (1280 - 48 - 12 * (len(medidas) - 1)) // len(medidas)
    return [tarjeta(f"{prefijo}_kpi{i}", 24 + i * (ancho + 12), y, ancho, alto, m) for i, m in enumerate(medidas)]


AYUDA = "Clic en una barra para filtrar la página. Pasa el ratón para ver el detalle."
X1, X2, X3 = 632, 844, 1056          # posiciones de los tres filtros de la franja superior
MEDIDAS_DETALLE = ["Pedidos.Pedidos totales", "Pedidos.Ingresos", "Pedidos.Ticket medio", "Pedidos.Días de entrega",
                   "Pedidos.% Retraso", "Pedidos.Nota media", "Pedidos.% Mala nota"]

PAGINAS = [
    ("resumen", "Resumen de ventas", [
        texto("res_titulo", 24, 12, 596, 64, "Olist - Resumen de ventas", AYUDA),
        filtro("res_f_anio", X1, "Calendario.Año", "Año", grupo="anio"),
        filtro("res_f_estado", X2, "Pedidos.customer_state", "Estado del cliente", grupo="estado"),
        filtro("res_f_categoria", X3, "Pedidos.categoria_principal", "Categoría", grupo="categoria"),
        *fila_tarjetas("res", ["Pedidos.Ingresos", "Pedidos.Pedidos totales", "Pedidos.Ticket medio",
                               "Pedidos.Clientes únicos", "Pedidos.% Clientes que repiten"]),
        grafico("res_linea", "lineChart", 24, 188, 1232, 254, "Ingresos por mes (reales)",
                "Calendario.Mes", "Pedidos.Ingresos", orden="categoria",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.Ticket medio"]),
        grafico("res_estados", "barChart", 24, 454, 402, 254, "Ingresos por estado del cliente",
                "Pedidos.customer_state", "Pedidos.Ingresos", etiqueta_eje="Estado",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.Ticket medio", "Pedidos.Nota media"]),
        grafico("res_categorias", "barChart", 438, 454, 402, 254, "Ingresos de producto por categoría",
                "Items.categoria", "Items.Ingresos de producto", etiqueta_eje="Categoría",
                tooltips=["Items.Unidades vendidas", "Items.Precio medio"]),
        grafico("res_pago", "barChart", 852, 454, 404, 254, "Ingresos por método de pago",
                "Pedidos.tipo_pago", "Pedidos.Ingresos", etiqueta_eje="Método de pago",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.Ticket medio"]),
    ]),
    ("experiencia", "Experiencia del cliente", [
        texto("exp_titulo", 24, 12, 596, 64, "Olist - Experiencia del cliente",
              "Mala nota = 1 o 2 estrellas. Naranja = indicador de problema. Clic en una barra para filtrar."),
        filtro("exp_f_anio", X1, "Calendario.Año", "Año", grupo="anio"),
        filtro("exp_f_estado", X2, "Pedidos.customer_state", "Estado del cliente", grupo="estado"),
        filtro("exp_f_categoria", X3, "Pedidos.categoria_principal", "Categoría", grupo="categoria"),
        *fila_tarjetas("exp", ["Pedidos.Nota media", "Pedidos.% Mala nota", "Pedidos.% Retraso",
                               "Pedidos.Días de entrega", "Pedidos.Pedidos con mala nota"]),
        grafico("exp_tramo", "columnChart", 24, 188, 610, 254, "% de mala nota según el retraso en la entrega",
                "Pedidos.tramo_entrega", "Pedidos.% Mala nota", orden="categoria", color_serie=NARANJA,
                etiqueta_eje="Entrega",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.Pedidos con mala nota", "Pedidos.Nota media"]),
        grafico("exp_tipo", "columnChart", 646, 188, 610, 254, "% de mala nota según el tipo de pedido",
                "Pedidos.tipo_pedido", "Pedidos.% Mala nota", color_serie=NARANJA, etiqueta_eje="Tipo de pedido",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.Pedidos con mala nota", "Pedidos.% Retraso"]),
        grafico("exp_retraso_mes", "lineChart", 24, 454, 610, 254, "% de pedidos con retraso por mes de compra",
                "Calendario.Mes", "Pedidos.% Retraso", orden="categoria", color_serie=NARANJA,
                tooltips=["Pedidos.Pedidos totales", "Pedidos.Nota media"]),
        grafico("exp_dias_estado", "barChart", 646, 454, 610, 254, "Días de entrega por estado del cliente",
                "Pedidos.customer_state", "Pedidos.Días de entrega", etiqueta_eje="Estado",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.% Retraso", "Pedidos.Nota media"]),
    ]),
    ("clientes", "Segmentación de clientes", [
        texto("cli_titulo", 24, 12, 596, 64, "Olist - Segmentación de clientes",
              "Segmentos por reglas RFM y grupos de K-means. Clic en una barra o fila para filtrar."),
        filtro("cli_f_segmento", X1, "Clientes.segmento", "Segmento RFM"),
        filtro("cli_f_cluster", X2, "Clientes.cluster", "Grupo K-means"),
        filtro("cli_f_estado", X3, "Clientes.estado", "Estado del cliente"),
        *fila_tarjetas("cli", ["Clientes.Nº clientes", "Clientes.Gasto de clientes", "Clientes.Gasto medio por cliente",
                               "Clientes.Recencia media (días)", "Clientes.Nota media del cliente"]),
        grafico("cli_seg_clientes", "barChart", 24, 188, 610, 254, "% de clientes por segmento RFM",
                "Clientes.segmento", "Clientes.% de clientes", etiqueta_eje="Segmento",
                tooltips=["Clientes.Nº clientes", "Clientes.Gasto medio por cliente", "Clientes.Recencia media (días)"]),
        grafico("cli_seg_ingresos", "barChart", 646, 188, 610, 254, "% de ingresos por segmento RFM",
                "Clientes.segmento", "Clientes.% de ingresos", etiqueta_eje="Segmento",
                tooltips=["Clientes.Gasto de clientes", "Clientes.Nº clientes", "Clientes.Gasto medio por cliente"]),
        grafico("cli_grupos", "barChart", 852, 454, 404, 254, "% de ingresos por grupo K-means",
                "Clientes.cluster", "Clientes.% de ingresos", etiqueta_eje="Grupo",
                tooltips=["Clientes.Nº clientes", "Clientes.Nota media del cliente", "Clientes.Gasto medio por cliente"]),
        tabla("cli_clusters", 24, 454, 816, 254, "Grupos de K-means",
              [("Clientes.cluster", "Grupo"), "Clientes.Nº clientes", "Clientes.% de clientes",
               "Clientes.Gasto medio por cliente", "Clientes.Recencia media (días)", "Clientes.Nota media del cliente"]),
    ]),
    ("detalle", "Detalle por estado y categoría", [
        texto("det_titulo", 24, 12, 596, 64, "Olist - Detalle por estado y categoría",
              "Clic en una fila o barra para filtrar el resto. Clic en una cabecera para ordenar."),
        filtro("det_f_anio", X1, "Calendario.Año", "Año", grupo="anio"),
        filtro("det_f_estado", X2, "Pedidos.customer_state", "Estado del cliente", grupo="estado"),
        filtro("det_f_categoria", X3, "Pedidos.categoria_principal", "Categoría", grupo="categoria"),
        tabla("det_estados", 24, 84, 700, 306, "Por estado del cliente",
              [("Pedidos.customer_state", "Estado"), *MEDIDAS_DETALLE]),
        grafico("det_g_estados", "barChart", 736, 84, 520, 306, "% de mala nota por estado (mín. 100 pedidos)",
                "Pedidos.customer_state", "Pedidos.% Mala nota (mín. 100 pedidos)", color_serie=NARANJA, etiqueta_eje="Estado",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.% Retraso", "Pedidos.Días de entrega"]),
        tabla("det_categorias", 24, 402, 900, 306, "Por categoría principal del pedido",
              [("Pedidos.categoria_principal", "Categoría"), *MEDIDAS_DETALLE]),
        grafico("det_g_categorias", "barChart", 936, 402, 320, 306, "% de mala nota por categoría (mín. 100)",
                "Pedidos.categoria_principal", "Pedidos.% Mala nota (mín. 100 pedidos)", color_serie=NARANJA, etiqueta_eje="Categoría",
                tooltips=["Pedidos.Pedidos totales", "Pedidos.% Retraso", "Pedidos.Nota media"]),
    ]),
]


def plataforma(tipo):
    return {"$schema": f"{ESQUEMAS}/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": tipo, "displayName": "olist"},
            "config": {"version": "2.0", "logicalId": guid("plataforma/" + tipo)}}


def generar_informe(tema_base):
    d = INFORME / "definition"
    escribir(INFORME / ".platform", plataforma("Report"))
    escribir(INFORME / "definition.pbir", {
        "$schema": f"{ESQUEMAS}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../olist.SemanticModel"}}})
    escribir(d / "version.json", {
        "$schema": f"{ESQUEMAS}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})

    # Tema: el base de Power BI más uno propio con la paleta del proyecto
    recursos = INFORME / "StaticResources"
    (recursos / "SharedResources" / "BaseThemes").mkdir(parents=True, exist_ok=True)
    shutil.copy(tema_base, recursos / "SharedResources" / "BaseThemes" / "CY24SU10.json")
    escribir(recursos / "RegisteredResources" / "olist_tema.json", {
        "name": "Olist",
        "dataColors": [AZUL, NARANJA, "#5B8C5A", "#8E6BBF", "#C0504D", "#4AA3A2", "#B8860B", "#6B7280"],
        "background": "#FFFFFF", "foreground": TINTA, "tableAccent": AZUL})

    escribir(d / "report.json", {
        "$schema": f"{ESQUEMAS}/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "type": "SharedResources",
                          "reportVersionAtImport": {"visual": "1.8.95", "report": "2.0.95", "page": "1.3.95"}},
            "customTheme": {"name": "olist_tema.json", "type": "RegisteredResources",
                            "reportVersionAtImport": {"visual": "2.1.0", "report": "2.1.0", "page": "2.0.0"}}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "olist_tema.json", "path": "olist_tema.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})

    escribir(d / "pages" / "pages.json", {
        "$schema": f"{ESQUEMAS}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p[0] for p in PAGINAS], "activePageName": PAGINAS[0][0]})

    for nombre, titulo, visuales in PAGINAS:
        escribir(d / "pages" / nombre / "page.json", {
            "$schema": f"{ESQUEMAS}/item/report/definition/page/2.0.0/schema.json",
            "name": nombre, "displayName": titulo, "displayOption": "FitToPage", "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {"color": color(FONDO), "transparency": lit("0D")}}]}})
        for orden, v in enumerate(visuales):
            v["position"]["z"] = v["position"]["tabOrder"] = orden
            escribir(d / "pages" / nombre / "visuals" / v["name"] / "visual.json", v)


if __name__ == "__main__":
    for carpeta in (MODELO, INFORME):
        shutil.rmtree(carpeta, ignore_errors=True)

    generar_modelo()
    generar_informe(TEMA_BASE)
    escribir(PROYECTO / "olist.pbip", {
        "$schema": f"{ESQUEMAS}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": "olist.Report"}}], "settings": {"enableAutoRecovery": True}})

    n_visuales = sum(len(p[2]) for p in PAGINAS)
    n_medidas = sum(len(t["medidas"]) for t in TABLAS.values())
    print(f"Modelo:  {len(TABLAS)} tablas, {len(RELACIONES)} relaciones, {n_medidas} medidas")
    print(f"Informe: {len(PAGINAS)} páginas, {n_visuales} visuales")
    print(f"Datos:   {RUTA_DATOS}")
