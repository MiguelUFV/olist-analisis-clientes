# SPEC — Olist: análisis de cartera de clientes

## Escenario
Analista junior en Olist (marketplace brasileño). Pregunta de dirección:
**"Casi ningún cliente repite compra. ¿Quiénes son nuestros clientes valiosos, por qué se van y qué hacemos?"**

## Datos
- Fuente: dataset público de Olist (repositorio oficial `olist/work-at-olist-data`, el mismo que está en Kaggle).
- 9 CSV en `data/raw/`, ~100k pedidos entre 2016 y 2018.
- Se cargan sin modificar en `data/olist.db` (SQLite).

## Modo de trabajo
Claude hace cada fase paso a paso y abre los archivos en VS Code. Miguel revisa código, CSV y SQL, y pregunta lo que no entienda antes de pasar a la siguiente fase.

## Fases (CRISP-DM)

| # | Fase | Herramienta | Entregable | Estado |
|---|---|---|---|---|
| 0 | Entorno y obtención de datos | SQLite, Python | `scripts/00_cargar_datos.py`, `data/olist.db` | Hecho |
| 1 | Exploración con SQL | SQL | `sql/01_exploracion.sql` | Hecho |
| 2 | Limpieza | pandas | `notebooks/02_limpieza.ipynb`, `data/clean/` | Hecho |
| 3 | EDA y KPIs | pandas, matplotlib | `notebooks/03_eda_kpis.ipynb` | Hecho |
| 4 | Segmentación (RFM, cohortes, K-means) | pandas, sklearn | `notebooks/04_segmentacion.ipynb`, `data/clean/clientes.csv` | Hecho |
| 5 | Predicción de mala valoración (1-2 estrellas) | sklearn | `notebooks/05_modelo.ipynb` | Hecho |
| 6 | Dashboard | Power BI | `scripts/06_generar_powerbi.py`, `powerbi/olist.pbip`, `dashboard_olist.pbix` | Hecho |
| 7 | Informe ejecutivo, README y post | Word, GitHub | `informe/informe_ejecutivo_olist.docx`, `README.md`, `informe/post_linkedin.md`, `scripts/07_figuras_portfolio.py`, `informe/figuras/` | Hecho |

## Decisiones
- **SQLite** y no PostgreSQL: sin servidor que instalar; el SQL que se usa es el mismo.
- **Se predice mala valoración, no churn**: ~97% de los clientes compra una sola vez, así que un modelo de churn no sería defendible.
- Fuera de alcance: series temporales, deep learning.

## Criterios de éxito
- Miguel explica cada query y cada celda sin ayuda.
- Los KPIs cuadran entre SQL, pandas y Power BI.
- El informe da 3-5 recomendaciones con cifra detrás.
