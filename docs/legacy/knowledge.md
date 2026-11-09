# Clawbot Knowledge & Troubleshooting

This document serves as a repository for important lessons learned, architectural quirks, and troubleshooting tips for the Clawbot project.

## Frontend Proxying & Streaming (Flask)

**Symptom:** The frontend UI becomes extremely slow, hangs, or eventually becomes completely unresponsive when requesting data from the backend.
**Root Cause:** When the Flask web application in `app.py` proxies requests to the `llm_bridge` and `hardware_service`, using the `requests.request()` method without the `stream=True` flag causes `requests` to attempt to download the entire response body into memory before returning it to the browser. If a streamed request (such as an ongoing MJPEG video feed from a camera) is requested, it tries to buffer an infinite stream. With limited Gunicorn workers configured, the backend quickly becomes totally blocked as workers hang indefinitely.
**Solution:** 
When proxying endpoints that might stream data (like `/capture` or `/video_feed`), the Flask proxy routes must use `stream=True` in the `requests.request()` call and stream the response incrementally using `Response(resp.iter_content(chunk_size=8192), ...)`.

```python
# Example of the correct streaming architecture for Flask proxies:
resp = requests.request(
    method=request.method,
    url=url,
    headers=headers,
    stream=True,  # CRITICAL FOR PREVENTING HANGS
    timeout=5.0
)

return Response(resp.iter_content(chunk_size=8192), resp.status_code, headers)
```

## Service Restart Constraints

When making changes to the `clawbot_monitoring` UI, remember that the proxy code in `app.py` is baked into the Docker container. Changes to `app.py` will require a full rebuild of the `clawbot_monitoring` container:
```bash
docker compose up -d --build clawbot_monitoring
```
If the backend services (`hardware_service` or `llm_bridge`) are hung up on dead connections from a frozen proxy, they may also need to be forcefully restarted.
