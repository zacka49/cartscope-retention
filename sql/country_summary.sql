SELECT
    Country AS country,
    COUNT(DISTINCT InvoiceNo) AS purchase_invoices,
    COUNT(DISTINCT CustomerID) AS identified_customers,
    ROUND(SUM(order_value), 2) AS gross_purchase_value
FROM purchase_invoices
GROUP BY Country
ORDER BY gross_purchase_value DESC;

