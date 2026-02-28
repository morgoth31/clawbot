"""
Flask application for the Clawbot Monitoring Frontend.

This module provides a web interface to view and control the FastAPI backend
of the `ros2_llm_bridge` and a hardware service. It serves a main HTML page
and proxies API requests to the respective backend services.
"""

import os
import requests
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__, static_folder="static", static_url_path="/")

LLM_BRIDGE_URL = os.getenv("LLM_BRIDGE_URL", "http://localhost:8000")
HARDWARE_SERVICE_URL = os.getenv("HARDWARE_SERVICE_URL", "http://localhost:8001")

@app.route("/")
def index():
    """
    Renders the main monitoring interface.

    Returns:
        Response: The generated index.html file from the Vite build.
    """
    return app.send_static_file("index.html")

@app.route("/api/llm/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_llm(path):
    """
    Proxies requests to the LLM bridge FastAPI backend.

    This route forwards HTTP requests to the LLM bridge service, allowing the
    frontend to view and control the robot's capabilities (e.g., retrieving
    available tools or executing commands).

    Args:
        path (str): The remaining URL path to be appended to the LLM bridge URL.

    Returns:
        Response: A Flask Response object containing the bridged service's
            reply, or a JSON error message with HTTP status 503 if the proxying
            fails.
    """
    url = f"{LLM_BRIDGE_URL}/{path}"
    headers = {key: value for (key, value) in request.headers if key != 'Host'}
    
    try:
        resp = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True,
            timeout=15.0
        )
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        return Response(resp.iter_content(chunk_size=8192), resp.status_code, headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route("/api/hw/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_hw(path):
    """
    Proxies requests to the hardware service.

    This route forwards HTTP requests to the hardware backend service.
    Specifically, it handles custom timeout logic depending on the endpoint path
    (e.g., the 'capture' endpoint).

    Args:
        path (str): The remaining URL path to be appended to the hardware
            service URL.

    Returns:
        Response: A Flask Response object containing the hardware service's
            reply, or a JSON error message with HTTP status 503 if the proxying
            fails.
    """
    url = f"{HARDWARE_SERVICE_URL}/{path}"
    headers = {key: value for (key, value) in request.headers if key != 'Host'}
    
    try:
        if path == "capture":
             resp = requests.request(
                method=request.method,
                url=url,
                headers=headers,
                data=request.get_data(),
                params=request.args,
                stream=True,
                timeout=5.0
             )
        else:
            resp = requests.request(
                method=request.method,
                url=url,
                headers=headers,
                data=request.get_data(),
                params=request.args,
                allow_redirects=False,
                stream=True,
                timeout=5.0
            )
            
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        return Response(resp.iter_content(chunk_size=8192), resp.status_code, headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route("/health")
def health():
    """
    Checks the health status of the monitoring frontend.

    Returns:
        Response: A JSON response indicating the status is "healthy".
    """
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
