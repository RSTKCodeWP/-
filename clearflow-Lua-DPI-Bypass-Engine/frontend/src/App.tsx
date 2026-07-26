import { useState, useEffect, useRef } from 'react';
import { 
  ToggleEngine, GetStatus, GetLogs, GetEngines, GetProfiles, 
  CheckAutostart, ToggleAutostart, LoadConfig, SaveConfig, AutoScan 
} from "../wailsjs/go/main/App";
import { EventsOn } from "../wailsjs/runtime";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Shield, ShieldCheck, Zap, Terminal as TerminalIcon, 
  RefreshCcw, Power, ChevronDown, Monitor, Info, AlertTriangle
} from "lucide-react";
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function App() {
  const [active, setActive] = useState(false);
  const [status, setStatus] = useState("Stopped");
  const [logs, setLogs] = useState<string[]>([]);
  const [engines, setEngines] = useState<string[]>([]);
  const [selectedEngine, setSelectedEngine] = useState("");
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [autostart, setAutostart] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    GetStatus().then(setStatus);
    CheckAutostart().then(setAutostart);

    Promise.all([GetEngines(), LoadConfig()]).then(([eList, config]) => {
      setEngines(eList);
      if (eList.length > 0) {
        const engineToSet = config.engineName && eList.includes(config.engineName) ? config.engineName : eList[0];
        setSelectedEngine(engineToSet);
        
        GetProfiles(engineToSet).then(pList => {
          setProfiles(pList);
          if (pList.length > 0) {
            const profileToSet = config.profileName && pList.includes(config.profileName) ? config.profileName : pList[0];
            setSelectedProfile(profileToSet);
          }
        });
      }
    });

    const interval = setInterval(() => {
      if (!isScanning) GetLogs().then(setLogs);
    }, 1500);

    EventsOn("status_changed", (s: string) => {
      setStatus(s);
      setActive(s === "Running");
    });
    
    EventsOn("scan_log", (msg: string) => {
      setLogs(prev => [msg, ...prev].slice(0, 100));
    });

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [logs]);

  const handleEngineChange = async (newEngine: string) => {
    setSelectedEngine(newEngine);
    const pList = await GetProfiles(newEngine);
    setProfiles(pList);
    if (pList.length > 0) {
      setSelectedProfile(pList[0]);
      SaveConfig(newEngine, pList[0]);
    }
  };

  const handleProfileChange = (newProfile: string) => {
    setSelectedProfile(newProfile);
    SaveConfig(selectedEngine, newProfile);
  };

  const handleToggle = async () => {
    if (isScanning) return;
    const newState = !active;
    setActive(newState);
    await ToggleEngine(newState, selectedEngine, selectedProfile);
    GetStatus().then(setStatus);
  };

  const handleAutoScan = async () => {
    if (active) {
      await ToggleEngine(false, selectedEngine, selectedProfile);
      setActive(false);
    }
    setIsScanning(true);
    setShowLogs(true);
    setLogs(["[SYSTEM] Initiating full bypass scan..."]);
    
    const result = await AutoScan();
    setIsScanning(false);
    
    if (result.success) {
      setSelectedEngine(result.engineName);
      const pList = await GetProfiles(result.engineName);
      setProfiles(pList);
      setSelectedProfile(result.profileName);
      setActive(true);
      setStatus("Running");
    } else {
      setLogs(prev => ["ERR: Scan failed. No working combination detected.", ...prev]);
    }
  };

  return (
    <div className="relative min-h-screen flex flex-col bg-grid select-none overflow-hidden">
      
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse-glow" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-pulse-glow" style={{animationDelay: '1.5s'}} />
      </div>

      <header className="flex items-center justify-between px-8 py-6 border-b border-white/10 glass-morphism z-20 relative">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-br from-blue-600/30 to-purple-600/30 rounded-xl border border-blue-500/40 shadow-lg shadow-blue-500/20">
            <Shield className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-blue-400 uppercase italic">Unbound</h1>
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none">Ultimate DPI Bypass</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className={cn(
            "flex items-center gap-2.5 px-4 py-2 rounded-full border transition-all duration-500 glass-morphism",
            active ? "border-emerald-500/50 text-emerald-400 shadow-emerald-500/20 shadow-lg" : "border-white/10 text-slate-500"
          )}>
            <div className={cn("w-2 h-2 rounded-full", active ? "bg-emerald-400 animate-pulse shadow-lg shadow-emerald-400/50" : "bg-slate-600")} />
            <span className="text-[11px] font-black uppercase tracking-widest">{status}</span>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-8 z-10 relative">
        
        <div className="relative flex flex-col items-center mb-12">
          <motion.div 
            animate={{ 
              scale: active ? [1, 1.08, 1] : 1,
              opacity: active ? [0.4, 0.7, 0.4] : 0.15
            }}
            transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
            className={cn(
              "absolute -inset-20 rounded-full blur-3xl transition-colors duration-1000",
              active ? "bg-gradient-to-r from-emerald-500 via-teal-500 to-emerald-500" : "bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500"
            )}
          />
          
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleToggle}
            disabled={isScanning}
            className={cn(
              "relative w-64 h-64 rounded-full flex flex-col items-center justify-center border-[10px] transition-all duration-700 outline-none glass-morphism-strong",
              active 
                ? "bg-gradient-to-br from-emerald-500/90 to-teal-500/90 border-emerald-400/60 shadow-[0_0_80px_rgba(52,211,153,0.4)] glow-shadow-emerald" 
                : "bg-gradient-to-br from-slate-900/80 to-slate-800/80 border-slate-700/50 hover:border-slate-600/60 shadow-2xl",
              isScanning && "opacity-50 cursor-not-allowed"
            )}
          >
            <Power className={cn("w-20 h-20 mb-3 transition-all duration-500", active ? "text-white drop-shadow-lg" : "text-slate-600")} />
            <span className={cn("text-sm font-black tracking-[0.3em] uppercase", active ? "text-white drop-shadow-md" : "text-slate-500")}>
              {active ? "Connected" : isScanning ? "Scanning" : "Disconnected"}
            </span>
          </motion.button>

          <div className="absolute -bottom-10 text-center w-full">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              {active ? `Active: ${selectedEngine} • ${selectedProfile}` : isScanning ? "Testing configurations..." : "Ready for deployment"}
            </p>
          </div>
        </div>

        <div className="w-full max-w-md grid grid-cols-2 gap-4 mb-8">
          <button 
            onClick={handleAutoScan}
            disabled={isScanning}
            className="flex items-center justify-center gap-2.5 glass-morphism hover:glass-morphism-strong border border-white/10 hover:border-blue-500/30 rounded-2xl py-4 transition-all group disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 via-blue-500/10 to-blue-500/0 shimmer opacity-0 group-hover:opacity-100 transition-opacity" />
            <RefreshCcw className={cn("w-5 h-5 text-blue-400 relative z-10", isScanning && "animate-spin")} />
            <span className="text-xs font-black text-white uppercase tracking-tighter relative z-10">Auto-Detect</span>
          </button>
          
          <div 
            className="flex items-center justify-between glass-morphism hover:glass-morphism-strong border border-white/10 hover:border-purple-500/30 rounded-2xl px-5 py-4 cursor-pointer transition-all group relative overflow-hidden" 
            onClick={() => ToggleAutostart(!autostart).then(() => setAutostart(!autostart))}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500/0 via-purple-500/10 to-purple-500/0 shimmer opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex flex-col relative z-10">
              <span className="text-xs font-black text-white uppercase tracking-tighter leading-none mb-1">Persistent</span>
              <span className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">Start on Boot</span>
            </div>
            <div className={cn("w-10 h-5 rounded-full transition-all relative", autostart ? "bg-gradient-to-r from-blue-500 to-purple-500" : "bg-slate-800")}>
              <motion.div 
                animate={{ x: autostart ? 20 : 2 }}
                className="absolute top-1 w-3 h-3 rounded-full bg-white shadow-lg"
              />
            </div>
          </div>
        </div>

        <div className="w-full max-w-md glass-morphism-strong border border-white/10 rounded-3xl p-6 backdrop-blur-xl shadow-2xl">
          <div className="space-y-6">
            
            <div className="space-y-2">
              <div className="flex items-center gap-2 ml-1">
                <Zap className="w-4 h-4 text-blue-400" />
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest">Core Engine</label>
              </div>
              <div className="relative">
                <select 
                  value={selectedEngine}
                  onChange={(e) => handleEngineChange(e.target.value)}
                  disabled={active || isScanning}
                  className="w-full bg-slate-900/80 border border-white/10 hover:border-blue-500/30 focus:border-blue-500/50 text-white text-sm rounded-xl px-4 py-3.5 appearance-none outline-none transition-all disabled:opacity-50 font-bold glass-morphism"
                >
                  {engines.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 ml-1">
                <Monitor className="w-4 h-4 text-emerald-400" />
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest">Strategy Profile</label>
              </div>
              <div className="relative">
                <select 
                  value={selectedProfile}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  disabled={active || isScanning}
                  className="w-full bg-slate-900/80 border border-white/10 hover:border-emerald-500/30 focus:border-emerald-500/50 text-emerald-400 text-sm rounded-xl px-4 py-3.5 appearance-none outline-none transition-all disabled:opacity-50 font-bold glass-morphism"
                >
                  {profiles.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
              </div>
            </div>

          </div>
        </div>

        <button 
          onClick={() => setShowLogs(!showLogs)}
          className="mt-10 mb-5 text-[11px] font-black text-slate-600 hover:text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2 transition-all outline-none group"
        >
          <TerminalIcon className="w-4 h-4 group-hover:text-blue-400 transition-colors" />
          {showLogs ? "Hide Diagnostics" : "View Diagnostics"}
        </button>

        <AnimatePresence>
          {showLogs && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 180, opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="w-full max-w-md glass-morphism border border-white/5 rounded-2xl overflow-hidden flex flex-col mb-8 shadow-2xl"
            >
              <div ref={scrollRef} className="flex-1 p-5 overflow-y-auto font-mono text-[10px] console-scrollbar space-y-1.5 flex flex-col-reverse">
                {logs.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-slate-700 italic text-xs">No diagnostic stream available...</div>
                ) : (
                  logs.map((log, i) => {
                    const isError = log.toLowerCase().includes("err") || log.toLowerCase().includes("fail");
                    const isSystem = log.toLowerCase().includes("[system]") || log.toLowerCase().includes("found") || log.toLowerCase().includes("optimal");
                    const isSuccess = log.toLowerCase().includes("active") || log.toLowerCase().includes("success");
                    return (
                      <div key={i} className="flex gap-3 leading-relaxed group">
                        <span className="text-slate-700 shrink-0 select-none opacity-50 text-[9px]">[{new Date().toLocaleTimeString([], {hour12:false})}]</span>
                        <span className={cn(
                          "break-all",
                          isError ? "text-red-400 font-bold" : 
                          isSuccess ? "text-emerald-400 font-bold" :
                          isSystem ? "text-blue-400 font-bold" : 
                          "text-slate-500 group-hover:text-slate-300"
                        )}>
                          {log}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </main>

      <footer className="px-8 py-4 glass-morphism border-t border-white/10 flex justify-between items-center z-20 relative">
        <div className="flex items-center gap-4 text-[10px] font-bold text-slate-600 uppercase tracking-widest">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-blue-500/70" />
            <span>Encrypted Node</span>
          </div>
          <div className="flex items-center gap-2">
            <Info className="w-3.5 h-3.5 text-purple-500/70" />
            <span>v2.4.0-Ultimate</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500/60" />
          <span className="text-[9px] font-black text-slate-700 uppercase tracking-widest">Authorized Use Only</span>
        </div>
      </footer>

    </div>
  );
}

export default App;
