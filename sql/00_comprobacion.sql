-- Fase 0 - Comprobar que la carga ha ido bien
-- Cada consulta se ejecuta por separado.

-- 1. ¿Qué tablas hay en la base de datos?
SELECT name
FROM sqlite_master
WHERE type = 'table'
ORDER BY name;

-- 2. Primeras filas de la tabla principal
SELECT *
FROM orders
LIMIT 5;

-- 3. ¿Cuántos pedidos hay y entre qué fechas?
SELECT COUNT(*)                      AS pedidos,
       MIN(order_purchase_timestamp) AS primer_pedido,
       MAX(order_purchase_timestamp) AS ultimo_pedido
FROM orders;

-- 4. ¿order_id es único? (debe devolver 0 filas)
SELECT order_id, COUNT(*) AS veces
FROM orders
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 5. Pedidos por estado
SELECT order_status, COUNT(*) AS pedidos
FROM orders
GROUP BY order_status
ORDER BY pedidos DESC;
