import os
import requests
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)

LLM_BRIDGE_URL = os.getenv("LLM_BRIDGE_URL", "http://localhost:8000")
HARDWARE_SERVICE_URL = os.getenv("HARDWARE_SERVICE_URL", "http://localhost:8001")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/llm/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_llm(path):
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
            timeout=15.0
        )
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route("/api/hw/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_hw(path):
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
                timeout=5.0
            )
            
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
