El 97 % de los clientes de Olist compra una sola vez.

Es lo primero que encontré al analizar 96.203 pedidos reales de este marketplace brasileño, en un proyecto personal con su conjunto de datos público. La pregunta de partida era sencilla: por qué no vuelven los clientes y qué se podría hacer.

Lo que más me llamó la atención:

→ La entrega decide la valoración. Un pedido a tiempo recibe 1 o 2 estrellas el 9 % de las veces. Con más de una semana de retraso, el 78 %.

→ Aun así, dos de cada tres malas notas son de pedidos que llegaron en plazo. Los pedidos servidos por varios vendedores tienen un 47 % de mala nota y casi nunca se retrasan.

→ El 18 % de los clientes genera el 49 % de los ingresos, y la mayor parte lleva más de seis meses sin comprar.

Lo que aprendí por el camino vale más que el resultado. Comparar las mismas cifras en SQL, pandas y Power BI me hizo encontrar un error: una medida DAX contaba los pedidos sin valorar como malas notas, porque un valor en blanco se evalúa como cero. Y el modelo predictivo, que daba un AUC de 0,75, bajó a 0,70 al evaluarlo con los meses siguientes en lugar de con una muestra aleatoria. Esa segunda cifra es la que cuenta.

El proyecto recorre el ciclo completo: SQL, limpieza y análisis en Python, segmentación RFM y K-means, modelo de clasificación, cuadro de mando en Power BI e informe ejecutivo.

Código, cuadro de mando e informe: [enlace al repositorio]

#AnálisisDeDatos #PowerBI #Python #SQL
