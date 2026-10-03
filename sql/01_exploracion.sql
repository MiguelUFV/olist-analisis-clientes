-- Fase 1 - Exploración con SQL
-- Objetivo: entender qué hay en los datos y detectar problemas ANTES de limpiar.
-- De menos a más: SELECT -> GROUP BY -> JOIN -> CTE -> funciones ventana.
-- Cada consulta se ejecuta por separado.

-- ============================================================
-- BLOQUE A. Calidad de los datos
-- ============================================================

-- Q1. ¿Cuántos nulos hay en las fechas de los pedidos?
-- COUNT(*) cuenta filas. COUNT(columna) cuenta solo las que NO son nulas.
SELECT COUNT(*)                                        AS pedidos,
       COUNT(*) - COUNT(order_approved_at)             AS sin_fecha_aprobacion,
       COUNT(*) - COUNT(order_delivered_carrier_date)  AS sin_fecha_transportista,
       COUNT(*) - COUNT(order_delivered_customer_date) AS sin_fecha_entrega
FROM orders;

-- Q2. ¿Hay pedidos marcados como entregados que no tienen fecha de entrega?
SELECT COUNT(*) AS entregados_sin_fecha
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NULL;

-- Q3. ¿Cuántos clientes hay de verdad?
-- DISTINCT elimina repetidos antes de contar.
SELECT COUNT(*)                           AS filas,
       COUNT(DISTINCT customer_id)        AS customer_id_distintos,
       COUNT(DISTINCT customer_unique_id) AS personas_distintas
FROM customers;

-- Q4. ¿Hay pedidos sin productos? (LEFT JOIN + IS NULL = "los que no tienen pareja")
SELECT o.order_status, COUNT(*) AS pedidos_sin_productos
FROM orders o
LEFT JOIN order_items i ON i.order_id = o.order_id
WHERE i.order_id IS NULL
GROUP BY o.order_status
ORDER BY pedidos_sin_productos DESC;

-- Q5. ¿Las valoraciones son únicas?
SELECT COUNT(*)                  AS filas,
       COUNT(DISTINCT review_id) AS review_id_distintos,
       COUNT(DISTINCT order_id)  AS pedidos_con_valoracion
FROM order_reviews;

-- Q6. ¿Hay productos sin categoría?
SELECT COUNT(*) AS productos_sin_categoria
FROM products
WHERE product_category_name IS NULL;

-- ============================================================
-- BLOQUE B. Volumen e ingresos
-- ============================================================

-- Q7. Pedidos por mes
-- strftime('%Y-%m', fecha) se queda con el año y el mes: '2017-10-02 10:56:33' -> '2017-10'
SELECT strftime('%Y-%m', order_purchase_timestamp) AS mes,
       COUNT(*)                                    AS pedidos
FROM orders
GROUP BY mes
ORDER BY mes;

-- Q8. Ingresos y ticket medio (solo pedidos entregados)
-- JOIN une cada producto vendido con su pedido para poder filtrar por estado.
SELECT COUNT(DISTINCT o.order_id)                                         AS pedidos,
       ROUND(SUM(i.price), 2)                                             AS ingresos_producto,
       ROUND(SUM(i.freight_value), 2)                                     AS ingresos_envio,
       ROUND(SUM(i.price + i.freight_value) / COUNT(DISTINCT o.order_id), 2) AS ticket_medio
FROM orders o
JOIN order_items i ON i.order_id = o.order_id
WHERE o.order_status = 'delivered';

-- Q9. Métodos de pago
-- La subconsulta entre paréntesis calcula el total para sacar el porcentaje.
SELECT payment_type,
       COUNT(*)                                                          AS pagos,
       ROUND(SUM(payment_value), 2)                                      AS importe,
       ROUND(100.0 * SUM(payment_value) / (SELECT SUM(payment_value) FROM order_payments), 1) AS pct_importe,
       ROUND(AVG(payment_installments), 1)                               AS cuotas_medias
FROM order_payments
GROUP BY payment_type
ORDER BY importe DESC;

-- Q10. Top 10 categorías por ingresos (JOIN de 4 tablas)
-- COALESCE devuelve el primer valor que no sea nulo.
SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'sin_categoria') AS categoria,
       COUNT(*)               AS unidades,
       ROUND(SUM(i.price), 0) AS ingresos
FROM order_items i
JOIN orders o        ON o.order_id = i.order_id
JOIN products p      ON p.product_id = i.product_id
LEFT JOIN product_category_name_translation t
                     ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
GROUP BY categoria
ORDER BY ingresos DESC
LIMIT 10;

-- ============================================================
-- BLOQUE C. Clientes (la pregunta de dirección)
-- ============================================================

-- Q11. ¿Cuántos clientes repiten compra?
-- CTE (WITH): una consulta con nombre que se usa después como si fuera una tabla.
WITH pedidos_por_cliente AS (
    SELECT c.customer_unique_id,
           COUNT(*) AS pedidos
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT COUNT(*)                                                    AS clientes,
       SUM(CASE WHEN pedidos >= 2 THEN 1 ELSE 0 END)               AS clientes_que_repiten,
       ROUND(100.0 * SUM(CASE WHEN pedidos >= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_repiten,
       MAX(pedidos)                                                AS max_pedidos_un_cliente
FROM pedidos_por_cliente;

-- Q12. ¿El retraso en la entrega afecta a la valoración?
-- julianday() convierte una fecha en número de días, así se pueden restar.
WITH entregas AS (
    SELECT o.order_id,
           julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS dias_vs_estimado
    FROM orders o
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
),
-- Un pedido puede tener varias valoraciones (ver Q5): ROW_NUMBER() las numera
-- de más reciente a más antigua y nos quedamos con la primera.
ultima_valoracion AS (
    SELECT order_id, review_score
    FROM (SELECT order_id, review_score,
                 ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) AS n
          FROM order_reviews)
    WHERE n = 1
)
SELECT CASE WHEN e.dias_vs_estimado <= 0 THEN '1. A tiempo'
            WHEN e.dias_vs_estimado <= 7 THEN '2. Retraso hasta 7 dias'
            ELSE '3. Retraso de mas de 7 dias' END AS entrega,
       COUNT(*)                                    AS valoraciones,
       ROUND(AVG(r.review_score), 2)               AS nota_media,
       ROUND(100.0 * SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mala_nota
FROM entregas e
JOIN ultima_valoracion r ON r.order_id = e.order_id
GROUP BY entrega
ORDER BY entrega;

-- ============================================================
-- BLOQUE D. Funciones ventana
-- ============================================================

-- Q13. Ingresos mensuales, crecimiento respecto al mes anterior y acumulado
-- LAG() trae el valor de la fila anterior. SUM() OVER acumula sin agrupar filas.
WITH mensual AS (
    SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS mes,
           SUM(i.price + i.freight_value)                AS ingresos
    FROM orders o
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY mes
)
SELECT mes,
       ROUND(ingresos, 0)                                                    AS ingresos,
       ROUND(100.0 * (ingresos - LAG(ingresos) OVER (ORDER BY mes))
                   / LAG(ingresos) OVER (ORDER BY mes), 1)                   AS pct_vs_mes_anterior,
       ROUND(SUM(ingresos) OVER (ORDER BY mes), 0)                           AS ingresos_acumulados
FROM mensual
ORDER BY mes;

-- Q14. Concentración de ventas por estado (Pareto)
-- RANK() numera de mayor a menor. el SUM() OVER acumula el porcentaje.
WITH por_estado AS (
    SELECT c.customer_state               AS estado,
           SUM(i.price + i.freight_value) AS ingresos
    FROM orders o
    JOIN customers c   ON c.customer_id = o.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_state
)
SELECT RANK() OVER (ORDER BY ingresos DESC)                                    AS puesto,
       estado,
       ROUND(ingresos, 0)                                                      AS ingresos,
       ROUND(100.0 * ingresos / SUM(ingresos) OVER (), 1)                      AS pct,
       ROUND(100.0 * SUM(ingresos) OVER (ORDER BY ingresos DESC) / SUM(ingresos) OVER (), 1) AS pct_acumulado
FROM por_estado
ORDER BY puesto
LIMIT 8;
