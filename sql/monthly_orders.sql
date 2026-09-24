SELECT
    DATE_TRUNC('month', invoice_date) AS order_month,
    COUNT(DISTINCT InvoiceNo) AS purchase_invoices,
    COUNT(DISTINCT CustomerID) AS active_customers,
    ROUND(SUM(order_value), 2) AS gross_purchase_value
FROM purchase_invoices
GROUP BY order_month
ORDER BY order_month;

