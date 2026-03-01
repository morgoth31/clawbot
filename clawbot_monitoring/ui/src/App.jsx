import React, { useState, useEffect, useCallback } from 'react';
import { Bot, Camera, Terminal, Navigation, Cpu, Activity, VideoOff, Loader, Send, ArrowUp, ArrowLeft, ArrowRight, ArrowDown, Octagon, RotateCcw, RotateCw, Scissors, Lock, Volume2, Server, Radio, Gauge, Waves, Map, Eye, EyeOff } from 'lucide-react';

const Button = ({ children, onClick, active, variant = 'primary', className = '', disabled = false, type = "button" }) => {
  const baseStyle = "relative overflow-hidden flex items-center justify-center gap-2 px-4 py-2 font-medium transition-all duration-300 rounded-lg active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-500/20",
    secondary: "bg-dark-panel hover:bg-[#2a3a52] text-gray-200 border border-dark-border",
    danger: "bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-500/20",
  };
  const activeStyle = active ? "ring-2 ring-brand-400 ring-offset-2 ring-offset-dark-bg" : "";
  return (
    <button type={type} onClick={onClick} className={`${baseStyle} ${variants[variant]} ${activeStyle} ${className}`} disabled={disabled}>
      {children}
    </button>
  );
};

const Card = ({ title, children, icon, className = '', action }) => (
  <div className={`glass-panel rounded-2xl overflow-hidden flex flex-col ${className}`}>
    <div className="px-5 py-4 border-b border-dark-border/50 flex items-center justify-between bg-white/5">
      <div className="flex items-center gap-3">
        {icon && <div className="text-brand-400">{icon}</div>}
        <h2 className="text-lg font-semibold tracking-wide text-gray-100">{title}</h2>
      </div>
      {action && <div>{action}</div>}
    </div>
    <div className="p-5 flex-grow">
      {children}
    </div>
  </div>
);

const App = () => {
  const [battery, setBattery] = useState({ voltage: 0, percentage: 0 });
  const [cameraFrame, setCameraFrame] = useState(null);
  const [llmCommand, setLlmCommand] = useState("");
  const [llmResponse, setLlmResponse] = useState(null);
  const [loadingCmd, setLoadingCmd] = useState(false);
  const [hwStatus, setHwStatus] = useState("unknown");
  const [logs, setLogs] = useState([]);
  const [sysStatus, setSysStatus] = useState(null);
  const [telemetry, setTelemetry] = useState(null);

  // YOLO detection feed
  const [yoloStatus, setYoloStatus] = useState(null);
  const [yoloFrame, setYoloFrame] = useState(null);
  const [yoloDetections, setYoloDetections] = useState([]);
  const [yoloPolling, setYoloPolling] = useState(false);

  // SLAM map
  const [slamLive, setSlamLive] = useState(false);
  const [slamFrame, setSlamFrame] = useState(null);
  const [slamMeta, setSlamMeta] = useState(null);
  const [savedMaps, setSavedMaps] = useState([]);
  const [selectedMap, setSelectedMap] = useState('');
  const [mapNameInput, setMapNameInput] = useState('');
  const [savingMap, setSavingMap] = useState(false);

  const addLog = (msg, type = "info") => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg, type }].slice(-50));
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/hw/health');
      setHwStatus(res.ok ? "online" : "error");
    } catch (e) { setHwStatus("offline"); }

    try {
      const res = await fetch('/api/hw/battery');
      if (res.ok) setBattery(await res.json());
    } catch (e) { }
  };

  const fetchSysStatus = async () => {
    try {
      const res = await fetch('/api/hw/system/status');
      if (res.ok) setSysStatus(await res.json());
    } catch (e) { }
  };

  const fetchTelemetry = async () => {
    try {
      const res = await fetch('/api/hw/telemetry');
      if (res.ok) setTelemetry(await res.json());
    } catch (e) { }
  };

  useEffect(() => {
    fetchStatus();
    fetchSysStatus();
    fetchTelemetry();
    fetchSavedMaps();
    const i1 = setInterval(fetchStatus, 5000);
    const i2 = setInterval(fetchSysStatus, 5000);
    const i3 = setInterval(fetchTelemetry, 500); // 2Hz — IMU moves fast
    return () => { clearInterval(i1); clearInterval(i2); clearInterval(i3); };
  }, []);

  const fetchCamera = useCallback(async () => {
    try {
      const res = await fetch('/api/hw/capture?camera=front&save=false');
      if (res.ok) {
        const data = await res.json();
        setCameraFrame(`data:image/jpeg;base64,${data.image_base64}`);
      }
    } catch (e) { console.error("Camera fail:", e); }
  }, []);

  useEffect(() => {
    fetchCamera();
  }, [fetchCamera]);

  const moveRobot = async (x, y, z) => {
    addLog(`Move: x=${x} y=${y} z=${z}`);
    try {
      await fetch('/api/hw/motion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ linear_x: x, linear_y: y, angular_z: z })
      });
    } catch (e) { addLog(`Move error: ${e.message}`, "error"); }
  };

  const stopRobot = async () => {
    addLog("STOP");
    try { await fetch('/api/hw/motion/stop', { method: 'POST' }); } catch (e) { }
  };

  const beep = async () => {
    try { await fetch('/api/hw/beep?delay_ms=300', { method: 'POST' }); addLog("Beeped"); } catch (e) { }
  };

  const setLamps = async (r, g, b) => {
    try {
      await fetch('/api/hw/lamps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ r, g, b })
      });
      addLog(`Lamps R:${r} G:${g} B:${b}`);
    } catch (e) { }
  };

  const controlClaw = async (state) => {
    try {
      await fetch('/api/hw/claw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state })
      });
      addLog(`Claw: ${state}`);
    } catch (e) { }
  };

  // ── YOLO Detection Feed ───────────────────────────────────────────────────
  const fetchYoloStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/hw/yolo/status');
      if (res.ok) setYoloStatus(await res.json());
    } catch (e) {}
  }, []);

  const fetchYoloFrame = useCallback(async () => {
    try {
      const res = await fetch('/api/hw/yolo/frame');
      if (res.ok) {
        const data = await res.json();
        setYoloFrame(`data:image/jpeg;base64,${data.image_base64}`);
        setYoloDetections(data.detections || []);
      }
    } catch (e) {}
  }, []);

  useEffect(() => {
    fetchYoloStatus();
    const interval = setInterval(fetchYoloStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchYoloStatus]);

  useEffect(() => {
    if (!yoloPolling) return;
    fetchYoloFrame();
    const interval = setInterval(fetchYoloFrame, 500);
    return () => clearInterval(interval);
  }, [yoloPolling, fetchYoloFrame]);

  // ── SLAM Map ──────────────────────────────────────────────────────────────
  const fetchSavedMaps = async () => {
    try {
      const res = await fetch('/api/hw/maps');
      if (res.ok) {
        const data = await res.json();
        setSavedMaps(data.maps || []);
        if (data.maps.length > 0)
          setSelectedMap(prev => prev || data.maps[data.maps.length - 1].name);
      }
    } catch (e) {}
  };

  const fetchLiveMap = useCallback(async () => {
    try {
      const res = await fetch('/api/hw/map/live');
      if (res.ok) {
        const data = await res.json();
        setSlamFrame(`data:image/png;base64,${data.image_base64}`);
        setSlamMeta({ width: data.width, height: data.height, resolution: data.resolution });
      }
    } catch (e) {}
  }, []);

  const loadSavedMap = async () => {
    if (!selectedMap) return;
    try {
      const res = await fetch(`/api/hw/maps/${selectedMap}/image`);
      if (res.ok) {
        const data = await res.json();
        setSlamFrame(`data:image/png;base64,${data.image_base64}`);
        setSlamMeta({ width: data.width, height: data.height, resolution: data.resolution });
        addLog(`Map loaded: ${selectedMap}`, 'success');
      }
    } catch (e) { addLog(`Load map error: ${e.message}`, 'error'); }
  };

  const saveCurrentMap = async () => {
    if (!mapNameInput.trim()) return;
    setSavingMap(true);
    try {
      const res = await fetch('/api/hw/maps/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: mapNameInput.trim() })
      });
      if (res.ok) {
        addLog(`Map saved: ${mapNameInput}`, 'success');
        setMapNameInput('');
        await fetchSavedMaps();
      } else {
        const err = await res.json();
        addLog(`Save failed: ${err.detail}`, 'error');
      }
    } catch (e) { addLog(`Save error: ${e.message}`, 'error'); }
    setSavingMap(false);
  };

  const deleteMap = async (name) => {
    try {
      const res = await fetch(`/api/hw/maps/${name}`, { method: 'DELETE' });
      if (res.ok) {
        addLog(`Map deleted: ${name}`, 'info');
        setSlamFrame(null); setSlamMeta(null); setSelectedMap('');
        await fetchSavedMaps();
      }
    } catch (e) { addLog(`Delete error: ${e.message}`, 'error'); }
  };

  useEffect(() => {
    if (!slamLive) return;
    fetchLiveMap();
    const interval = setInterval(fetchLiveMap, 2000);
    return () => clearInterval(interval);
  }, [slamLive, fetchLiveMap]);

  const sendLLMCommand = async (e) => {
    e.preventDefault();
    if (!llmCommand.trim()) return;
    setLoadingCmd(true);
    addLog(`LLM Command: ${llmCommand}`, "info");
    try {
      const params = { function: "reason_and_execute", arguments: { "prompt": llmCommand } };
      const res = await fetch('/api/llm/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      if (res.ok) {
        const data = await res.json();
        setLlmResponse(data.result);
        addLog(`Response: ${data.result}`, "success");
      } else {
        const err = await res.text();
        setLlmResponse("Error: " + err);
        addLog(`Error: ${err}`, "error");
      }
    } catch (e) {
      setLlmResponse("Error connecting to LLM Bridge.");
      addLog(`Bridge error: ${e.message}`, "error");
    }
    setLoadingCmd(false);
  };

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6 text-slate-100">
      <header className="flex flex-col sm:flex-row items-center justify-between gap-4 glass-panel p-4 rounded-2xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/30">
            <Bot className="text-white w-7 h-7" />
          </div>
          <div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
              Clawbot Center
            </h1>
            <p className="text-brand-400 text-sm font-medium flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${hwStatus === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}></span>
              {hwStatus === 'online' ? 'Online & Linked' : 'Offline'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="text-xs text-gray-400 uppercase tracking-wide font-semibold mb-1">Battery</div>
            <div className="flex items-center gap-2">
              <div className="w-32 h-2.5 bg-dark-bg rounded-full overflow-hidden border border-dark-border">
                <div className={`h-full transition-all duration-1000 ${battery.percentage > 20 ? 'bg-gradient-to-r from-emerald-500 to-green-400' : 'bg-rose-500'}`} style={{ width: `${battery.percentage}%` }}></div>
              </div>
              <span className="font-mono text-sm font-medium w-10">{battery.percentage}%</span>
            </div>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card title="Vision Feed" icon={<Camera />} action={<Button variant="secondary" onClick={fetchCamera} className="text-xs py-1 px-3">Refresh</Button>} className="h-[460px]">
            <div className="w-full h-full rounded-xl overflow-hidden bg-black/60 border border-dark-border/50 relative flex items-center justify-center">
              {cameraFrame ? (
                <img src={cameraFrame} alt="Feed" className="object-contain w-full h-full opacity-90 hover:opacity-100 transition-opacity" />
              ) : (
                <div className="flex flex-col items-center text-gray-500 gap-2">
                  <VideoOff className="w-10 h-10 opacity-50" />
                  <p className="text-sm">Initializing Video Stream...</p>
                </div>
              )}
              <div className="absolute top-4 left-4 flex gap-2">
                <span className="bg-black/50 backdrop-blur-md px-2 py-1 rounded text-xs font-mono border border-white/10 text-emerald-400">REC 🔴</span>
                <span className="bg-black/50 backdrop-blur-md px-2 py-1 rounded text-xs font-mono border border-white/10">{battery.voltage.toFixed(1)}V</span>
              </div>
            </div>
          </Card>

          <Card
            title="SLAM Map"
            icon={<Map className="w-5 h-5" />}
            action={
              <div className="flex gap-2">
                <Button
                  variant={slamLive ? 'primary' : 'secondary'}
                  onClick={() => setSlamLive(v => !v)}
                  className="text-xs py-1 px-3"
                >
                  {slamLive ? '⏹ Live' : '▶ Live'}
                </Button>
                <Button variant="secondary" onClick={fetchLiveMap} className="text-xs py-1 px-3">Refresh</Button>
              </div>
            }
          >
            <div className="flex flex-col gap-4">
              {/* Map display */}
              <div className="w-full h-64 rounded-xl overflow-hidden bg-black/60 border border-dark-border/50 relative flex items-center justify-center">
                {slamFrame ? (
                  <img src={slamFrame} alt="SLAM Map" className="object-contain w-full h-full" />
                ) : (
                  <div className="flex flex-col items-center text-gray-500 gap-2">
                    <Map className="w-10 h-10 opacity-30" />
                    <p className="text-sm">No map — start SLAM or load a saved map</p>
                  </div>
                )}
                {slamLive && (
                  <span className="absolute top-2 left-2 bg-black/50 backdrop-blur-md px-2 py-1 rounded text-xs font-mono border border-white/10 text-brand-400">
                    LIVE 🗺
                  </span>
                )}
              </div>
              {slamMeta && (
                <p className="text-xs font-mono text-gray-400 text-center">
                  {slamMeta.width}×{slamMeta.height}px
                  {slamMeta.resolution ? ` · ${slamMeta.resolution}m/px` : ''}
                </p>
              )}

              {/* Saved maps */}
              <div className="border-t border-dark-border/40 pt-3 space-y-3">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold">Saved Maps</p>
                <div className="flex gap-2">
                  <select
                    value={selectedMap}
                    onChange={e => setSelectedMap(e.target.value)}
                    className="flex-1 bg-dark-bg/80 border border-dark-border rounded-lg px-3 py-2 text-white text-sm font-mono outline-none focus:ring-2 focus:ring-brand-500/50"
                  >
                    <option value="">— select a map —</option>
                    {savedMaps.map(m => (
                      <option key={m.name} value={m.name}>{m.name}</option>
                    ))}
                  </select>
                  <Button variant="secondary" onClick={loadSavedMap} disabled={!selectedMap} className="text-sm">Load</Button>
                  <Button variant="danger" onClick={() => selectedMap && deleteMap(selectedMap)} disabled={!selectedMap} className="text-sm">Del</Button>
                </div>

                {/* Save current */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={mapNameInput}
                    onChange={e => setMapNameInput(e.target.value.replace(/[^a-zA-Z0-9_-]/g, ''))}
                    placeholder="map-name (a-z, 0-9, _, -)"
                    className="flex-1 bg-dark-bg/80 border border-dark-border rounded-lg px-3 py-2 text-white text-sm font-mono outline-none focus:ring-2 focus:ring-brand-500/50 placeholder:text-gray-500"
                  />
                  <Button onClick={saveCurrentMap} disabled={!mapNameInput.trim() || savingMap} className="text-sm">
                    {savingMap ? <Loader className="animate-spin w-4 h-4" /> : null}
                    Save
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <Card
            title="YOLO Detection Feed"
            icon={<Eye className="w-5 h-5" />}
            action={
              <div className="flex items-center gap-2">
                {yoloStatus && (
                  <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${yoloStatus.active ? 'bg-emerald-900/40 border-emerald-700 text-emerald-300' : 'bg-gray-900/40 border-gray-700 text-gray-400'}`}>
                    {yoloStatus.active ? '● active' : '○ inactive'}
                  </span>
                )}
                <Button
                  variant={yoloPolling ? 'primary' : 'secondary'}
                  onClick={() => setYoloPolling(v => !v)}
                  className="text-xs py-1 px-3"
                  disabled={yoloStatus && !yoloStatus.active && !yoloStatus.has_frame}
                >
                  {yoloPolling ? <><EyeOff className="w-3 h-3" /> Stop</> : <><Eye className="w-3 h-3" /> Watch</>}
                </Button>
              </div>
            }
          >
            <div className="flex flex-col gap-3">
              <div className="w-full h-56 rounded-xl overflow-hidden bg-black/60 border border-dark-border/50 relative flex items-center justify-center">
                {yoloFrame ? (
                  <img src={yoloFrame} alt="YOLO Detection" className="object-contain w-full h-full" />
                ) : (
                  <div className="flex flex-col items-center text-gray-500 gap-2">
                    <Eye className="w-10 h-10 opacity-30" />
                    <p className="text-sm text-center px-4">
                      {yoloStatus && !yoloStatus.active
                        ? 'yolo-detector service not running'
                        : yoloPolling ? 'Waiting for frame…' : 'Click Watch to start'}
                    </p>
                  </div>
                )}
                {yoloPolling && yoloFrame && (
                  <span className="absolute top-2 left-2 bg-black/50 backdrop-blur-md px-2 py-1 rounded text-xs font-mono border border-white/10 text-emerald-400">
                    YOLO 🔍
                  </span>
                )}
              </div>
              {/* Detections list */}
              {yoloDetections.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {yoloDetections.map((d, i) => (
                    <span key={i} className="bg-emerald-900/30 border border-emerald-700/50 text-emerald-300 px-2 py-0.5 rounded-full text-xs font-mono">
                      {d.label} {Math.round(d.confidence * 100)}%
                    </span>
                  ))}
                </div>
              )}
              {yoloDetections.length === 0 && yoloFrame && (
                <p className="text-xs text-gray-500 text-center font-mono">No objects detected</p>
              )}
            </div>
          </Card>

          <Card title="LLM Command Bridge" icon={<Terminal />}>
            <form onSubmit={sendLLMCommand} className="flex gap-3 mb-4">
              <input type="text" value={llmCommand} onChange={e => setLlmCommand(e.target.value)} placeholder="Ex: Turn around and look for a red object..." className="flex-grow bg-dark-bg/80 border border-dark-border rounded-lg px-4 py-2 text-white outline-none focus:ring-2 focus:ring-brand-500/50 transition-all font-mono text-sm placeholder:text-gray-500" />
              <Button type="submit" disabled={loadingCmd}>
                {loadingCmd ? <Loader className="animate-spin w-5 h-5" /> : <Send className="w-5 h-5" />}
                <span>Send</span>
              </Button>
            </form>
            {llmResponse && (
              <div className="bg-dark-bg/50 border border-dark-border/50 rounded-lg p-4 font-mono text-sm text-emerald-300">
                <span className="text-gray-500 mr-2">Bridge &gt;</span>
                {llmResponse}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="System Status" icon={<Server className="w-5 h-5" />}>
            {sysStatus ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-widest mb-2 font-semibold">Services</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(sysStatus.services).map(([name, state]) => {
                      const ok = state === 'active' || state === 'running';
                      const short = name.replace('ros2-', '').replace('clawbot-', '').replace('-1', '').replace('_bridge', '-bridge');
                      return (
                        <span key={name} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-semibold border ${ok ? 'bg-emerald-900/40 border-emerald-700 text-emerald-300' : 'bg-rose-900/40 border-rose-700 text-rose-300'}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`}></span>
                          {short}
                        </span>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-widest mb-2 font-semibold flex items-center gap-1"><Radio className="w-3 h-3" /> ROS2 Nodes</p>
                  <div className="flex flex-wrap gap-1">
                    {sysStatus.ros2_nodes.filter((v, i, a) => a.indexOf(v) === i).map(node => (
                      <span key={node} className="bg-brand-900/40 border border-brand-700/50 text-brand-300 px-2 py-0.5 rounded text-xs font-mono">{node}</span>
                    ))}
                    {sysStatus.ros2_nodes.length === 0 && <span className="text-gray-600 text-xs">No nodes</span>}
                  </div>
                </div>
                <div className="pt-2 border-t border-dark-border/40 flex items-center justify-between">
                  <span className="text-xs text-gray-400 uppercase tracking-widest font-semibold">LiDAR Safety</span>
                  <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${sysStatus.lidar.enabled ? 'bg-emerald-900/40 border-emerald-700 text-emerald-300' : 'bg-yellow-900/40 border-yellow-700 text-yellow-300'}`}>
                    {sysStatus.lidar.enabled ? (sysStatus.lidar.age_s !== null ? `active · ${sysStatus.lidar.age_s}s` : 'waiting…') : 'DISABLED'}
                  </span>
                </div>
                {sysStatus.lidar.enabled && sysStatus.lidar.safe_to_move && (
                  <div className="grid grid-cols-4 gap-1 text-center text-xs font-mono">
                    {Object.entries(sysStatus.lidar.safe_to_move).map(([dir, safe]) => (
                      <div key={dir} className={`rounded py-1 ${safe ? 'bg-emerald-900/30 text-emerald-400' : 'bg-rose-900/30 text-rose-400'}`}>
                        {dir.slice(0, 3).toUpperCase()}<br />
                        <span className="text-[10px]">{sysStatus.lidar.distances?.[dir === 'forward' ? 'front' : dir === 'backward' ? 'back' : dir]?.toFixed(2)}m</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-gray-500 text-sm"><Loader className="animate-spin w-4 h-4" /> Loading…</div>
            )}
          </Card>

          <Card title="Telemetry" icon={<Gauge className="w-5 h-5" />}>
            {telemetry ? (() => {
              const fmt = (v, d=3) => v === undefined ? '—' : v.toFixed(d);
              const bar = (v, min, max, warn) => {
                const pct = Math.min(100, Math.max(0, ((v - min) / (max - min)) * 100));
                const color = Math.abs(v) > warn ? 'bg-rose-400' : 'bg-brand-400';
                return (
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-dark-bg rounded-full overflow-hidden">
                      <div className={`h-full transition-all duration-200 ${color}`} style={{width:`${pct}%`}}/>
                    </div>
                  </div>
                );
              };
              const servoEntries = Object.entries(telemetry.servos);
              const SERVO_LABELS = {1:'J1',2:'J2',3:'J3',4:'J4',5:'J5',6:'🦾'};
              return (
                <div className="space-y-4 text-xs font-mono">
                  {/* IMU */}
                  <div>
                    <p className="text-gray-400 uppercase tracking-widest mb-2 flex items-center gap-1">
                      <Waves className="w-3 h-3"/> IMU
                      {telemetry.imu.stale && <span className="text-rose-400 ml-1">STALE</span>}
                    </p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                      {['x','y','z'].map(ax => (
                        <React.Fragment key={ax}>
                          <div className="flex justify-between text-gray-300">
                            <span className="text-gray-500">Accel {ax.toUpperCase()}</span>
                            <span className={Math.abs(telemetry.imu.accel[ax]) > 2 && ax !== 'z' ? 'text-yellow-400' : ''}>
                              {fmt(telemetry.imu.accel[ax],2)} m/s²
                            </span>
                          </div>
                          <div>{bar(telemetry.imu.accel[ax], -12, 12, 2)}</div>
                        </React.Fragment>
                      ))}
                      {['x','y','z'].map(ax => (
                        <React.Fragment key={'g'+ax}>
                          <div className="flex justify-between text-gray-300">
                            <span className="text-gray-500">Gyro {ax.toUpperCase()}</span>
                            <span className={Math.abs(telemetry.imu.gyro[ax]) > 0.5 ? 'text-yellow-400' : ''}>
                              {fmt(telemetry.imu.gyro[ax],3)} r/s
                            </span>
                          </div>
                          <div>{bar(telemetry.imu.gyro[ax], -3, 3, 0.5)}</div>
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                  {/* Velocity */}
                  <div className="border-t border-dark-border/40 pt-3">
                    <p className="text-gray-400 uppercase tracking-widest mb-2">Wheels (vel_raw)</p>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      {[['Vx', telemetry.velocity.vx,'m/s'], ['Vy', telemetry.velocity.vy,'m/s'], ['ω', telemetry.velocity.angular,'r/s']].map(([l,v,u]) => (
                        <div key={l} className="bg-dark-bg/50 rounded-lg py-2 px-1">
                          <div className="text-gray-500 text-[10px]">{l}</div>
                          <div className={`text-sm font-bold ${Math.abs(v) > 0.01 ? 'text-brand-300' : 'text-gray-500'}`}>
                            {fmt(v,3)}
                          </div>
                          <div className="text-[10px] text-gray-600">{u}</div>
                        </div>
                      ))}
                    </div>
                    {telemetry.velocity.stale && <p className="text-gray-600 text-center mt-1">vel_raw stale — odom issue</p>}
                  </div>
                  {/* Servo angles */}
                  <div className="border-t border-dark-border/40 pt-3">
                    <p className="text-gray-400 uppercase tracking-widest mb-2">Arm Servos (last cmd)</p>
                    <div className="grid grid-cols-3 gap-1.5">
                      {servoEntries.map(([id, angle]) => (
                        <div key={id} className="bg-dark-bg/50 rounded-lg py-1.5 px-2 text-center">
                          <div className="text-gray-500 text-[10px]">{SERVO_LABELS[id]}</div>
                          <div className={`font-bold ${angle < 0 ? 'text-gray-600' : 'text-brand-300'}`}>
                            {angle < 0 ? '—' : `${angle}°`}
                          </div>
                          {angle >= 0 && (
                            <div className="mt-1 h-1 bg-dark-bg rounded-full overflow-hidden">
                              <div className="h-full bg-brand-500 transition-all duration-300" style={{width:`${(angle/180)*100}%`}}/>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })() : <div className="flex items-center gap-2 text-gray-500 text-sm"><Loader className="animate-spin w-4 h-4"/>Loading…</div>}
          </Card>

          <Card title="Chassis & Arm" icon={<Navigation />}>
            <div className="grid grid-cols-3 gap-2 max-w-[240px] mx-auto mb-6">
              <div />
              <Button variant="secondary" onClick={() => moveRobot(0.06, 0, 0)} className="h-16"><ArrowUp className="w-6 h-6" /></Button>
              <div />
              <Button variant="secondary" onClick={() => moveRobot(0, 0.06, 0)} className="h-16"><ArrowLeft className="w-6 h-6" /></Button>
              <Button variant="danger" onClick={stopRobot} className="h-16 flex-col gap-0 text-xs shadow-rose-900/50 shadow-[inset_0px_2px_4px_rgba(255,255,255,0.2)]">
                <Octagon className="w-6 h-6 mb-1" />
                STOP
              </Button>
              <Button variant="secondary" onClick={() => moveRobot(0, -0.06, 0)} className="h-16"><ArrowRight className="w-6 h-6" /></Button>
              <div />
              <Button variant="secondary" onClick={() => moveRobot(-0.06, 0, 0)} className="h-16"><ArrowDown className="w-6 h-6" /></Button>
              <div />
            </div>
            <div className="flex gap-2 justify-center mt-4 pt-4 border-t border-dark-border/50">
              <Button variant="secondary" onClick={() => moveRobot(0, 0, 0.2)} className="flex-1"><RotateCcw className="w-5 h-5" /> Left Spin</Button>
              <Button variant="secondary" onClick={() => moveRobot(0, 0, -0.2)} className="flex-1">Right Spin <RotateCw className="w-5 h-5" /></Button>
            </div>
            <div className="flex gap-2 justify-center mt-4 pt-4 border-t border-dark-border/50">
              <Button variant="secondary" onClick={() => controlClaw("open")} className="flex-1 text-sm"><Scissors className="w-4 h-4" /> Open Claw</Button>
              <Button variant="secondary" onClick={() => controlClaw("close")} className="flex-1 text-sm"><Lock className="w-4 h-4" /> Close Claw</Button>
            </div>
          </Card>

          <Card title="Peripherals" icon={<Cpu />}>
            <div className="space-y-4">
              <Button variant="secondary" onClick={beep} className="w-full justify-start">
                <Volume2 className="w-5 h-5 text-yellow-400" />
                <span>Sound Buzzer</span>
              </Button>
              <div className="grid grid-cols-3 gap-2">
                <Button onClick={() => setLamps(255, 0, 0)} className="bg-rose-950/50 hover:bg-rose-900/80 border border-rose-800 text-rose-300">Red</Button>
                <Button onClick={() => setLamps(0, 255, 0)} className="bg-emerald-950/50 hover:bg-emerald-900/80 border border-emerald-800 text-emerald-300">Green</Button>
                <Button onClick={() => setLamps(0, 0, 255)} className="bg-blue-950/50 hover:bg-blue-900/80 border border-blue-800 text-blue-300">Blue</Button>
              </div>
              <Button variant="secondary" onClick={() => setLamps(0, 0, 0)} className="w-full text-gray-400">Lights Off</Button>
            </div>
          </Card>

          <Card title="Activity Log" icon={<Activity />} className="h-56">
            <div className="font-mono text-xs flex flex-col-reverse gap-2 h-full overflow-y-auto custom-scrollbar pr-2">
              {logs.map((log, i) => (
                <div key={i} className={`flex gap-3 border-b border-dark-border/30 pb-1 ${log.type === 'error' ? 'text-red-400' : log.type === 'success' ? 'text-emerald-400' : 'text-gray-400'}`}>
                  <span className="opacity-50 flex-shrink-0">{log.time}</span>
                  <span className="break-all">{log.msg}</span>
                </div>
              ))}
              {logs.length === 0 && <div className="text-gray-600 text-center mt-4">No recent activity</div>}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default App;
