import React, { useState, useEffect, useCallback } from 'react';
import { Bot, Camera, Terminal, Navigation, Cpu, Activity, VideoOff, Loader, Send, ArrowUp, ArrowLeft, ArrowRight, ArrowDown, Octagon, RotateCcw, RotateCw, Scissors, Lock, Volume2 } from 'lucide-react';

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

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
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
          <Card title="Chassis & Arm" icon={<Navigation />}>
            <div className="grid grid-cols-3 gap-2 max-w-[240px] mx-auto mb-6">
              <div />
              <Button variant="secondary" onClick={() => moveRobot(0.1, 0, 0)} className="h-16"><ArrowUp className="w-6 h-6" /></Button>
              <div />
              <Button variant="secondary" onClick={() => moveRobot(0, 0.1, 0)} className="h-16"><ArrowLeft className="w-6 h-6" /></Button>
              <Button variant="danger" onClick={stopRobot} className="h-16 flex-col gap-0 text-xs shadow-rose-900/50 shadow-[inset_0px_2px_4px_rgba(255,255,255,0.2)]">
                <Octagon className="w-6 h-6 mb-1" />
                STOP
              </Button>
              <Button variant="secondary" onClick={() => moveRobot(0, -0.1, 0)} className="h-16"><ArrowRight className="w-6 h-6" /></Button>
              <div />
              <Button variant="secondary" onClick={() => moveRobot(-0.1, 0, 0)} className="h-16"><ArrowDown className="w-6 h-6" /></Button>
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
