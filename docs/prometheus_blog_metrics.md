# Prometheus variables: Atacama main (BLOG) server

These metrics are exported by the shared `/metrics` endpoint when `BLUEPRINT_SET=BLOG`, and they cover host health, process health, HTTP behavior, auth activity, and blog content inventory. This list is intended for monitoring configuration and includes only Atacama-defined metric names (Prometheus client default runtime metrics like `process_*` and `python_*` are available separately).

- `atacama_cpu_usage_percent`
- `atacama_memory_usage_percent`
- `atacama_memory_used_bytes`
- `atacama_memory_total_bytes`
- `atacama_disk_usage_percent`
- `atacama_disk_used_bytes`
- `atacama_disk_total_bytes`
- `atacama_network_bytes_sent_total`
- `atacama_network_bytes_recv_total`
- `atacama_process_cpu_percent`
- `atacama_process_memory_bytes`
- `atacama_process_threads`
- `atacama_process_open_fds`
- `atacama_uptime_seconds`
- `atacama_content_count{content_type="emails|articles|widgets|quotes"}`
- `atacama_database_connected`
- `atacama_http_requests_total{method,endpoint,status}`
- `atacama_http_request_duration_seconds{method,endpoint}`
- `atacama_http_errors_total{status_class="4xx|5xx"}`
- `atacama_auth_logins_total{provider,status}`
- `atacama_auth_logouts_total`
- `atacama_db_session_duration_seconds`
- `atacama_db_query_errors_total`
