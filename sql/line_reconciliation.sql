SELECT
    line_status,
    COUNT(*) AS rows,
    ROUND(SUM(line_value), 2) AS signed_value,
    COUNT(DISTINCT InvoiceNo) AS distinct_invoices
FROM invoice_lines
GROUP BY line_status
ORDER BY line_status;

