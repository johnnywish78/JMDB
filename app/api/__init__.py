"""JMDB local HTTP/WebSocket API (FastAPI).

The API is a transport layer over the existing Container/Services — it owns
no business logic. It binds to 127.0.0.1 only and requires a per-launch
bearer token (or same-origin session cookie) for every endpoint except
/api/health.
"""
