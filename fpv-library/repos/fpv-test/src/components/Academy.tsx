/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { 
  BookOpen, 
  Sliders, 
  HelpCircle, 
  Zap, 
  RotateCw, 
  Wrench, 
  Volume2, 
  Tv, 
  ShieldAlert, 
  CheckCircle2, 
  Award, 
  Play, 
  Pause, 
  Compass, 
  Info, 
  Lightbulb, 
  Thermometer, 
  TrendingUp, 
  AlertTriangle,
  Flame,
  Battery,
  Trophy,
  Newspaper,
  Gamepad
} from "lucide-react";
import { playSwitchClick, playBeep } from "../utils/audio";

// Define Types for Academy Section
type AcademyTab = "academy_az" | "races" | "news" | "gear" | "updates" | "simulators" | "pid" | "maneuvers" | "betaflight";

export default function Academy() {
  const [activeTab, setActiveTab] = useState<AcademyTab>("academy_az");

  // State for PID Tuner
  const [pVal, setPVal] = useState<number>(50);
  const [iVal, setIVal] = useState<number>(45);
  const [dVal, setDVal] = useState<number>(35);
  const [pidStateText, setPidStateText] = useState<string>("Hovering stable.");
  const [droneRotation, setDroneRotation] = useState<number>(0);
  const [droneYOffset, setDroneYOffset] = useState<number>(0);
  const [isDisturbed, setIsDisturbed] = useState<boolean>(false);
  const [isOverheating, setIsOverheating] = useState<boolean>(false);
  const [isOscillating, setIsOscillating] = useState<boolean>(false);
  const [isDrifting, setIsDrifting] = useState<boolean>(false);

  // Flight Maneuvers state
  const [selectedManeuver, setSelectedManeuver] = useState<string>("split-s");
  const [isManeuverPlaying, setIsManeuverPlaying] = useState<boolean>(true);
  const [maneuverProgress, setManeuverProgress] = useState<number>(0); // 0 to 100

  // Betaflight interactive OSD simulated tab
  const [bfActiveTab, setBfActiveTab] = useState<"receiver" | "modes" | "rates">("receiver");
  const [aux1Armed, setAux1Armed] = useState<boolean>(false);
  const [rxProvider, setRxProvider] = useState<string>("CRSF"); // CRSF, SBUS, GHST
  const [superRate, setSuperRate] = useState<number>(0.75);
  const [rcRate, setRcRate] = useState<number>(1.00);
  const [rcExpo, setRcExpo] = useState<number>(0.20);

  // FAQ Expanded list
  const [faqExpanded, setFaqExpanded] = useState<Record<string, boolean>>({
    capacitor: true,
    elrs: false,
    voltage_drop: false,
    prop_wash: false,
  });

  const toggleFaq = (key: string) => {
    playSwitchClick();
    setFaqExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // Run Real-time Physics Simulation for the PID Tuner
  useEffect(() => {
    // Determine drone state based on P, I, D sliders
    // Perfect: P=40..60, I=40..60, D=30..45
    let text = "Hovering perfectly on axis.";
    let oscillate = false;
    let heating = false;
    let drifting = false;

    if (pVal > 75) {
      text = "RAPID EXTREME P-TERM OSCILLING! Propellers vibrating, high-frequency motor strain.";
      oscillate = true;
    } else if (pVal < 25) {
      text = "SLUGGISH ROLL RESPONSE. Sloppy recovery under wind gusts. Increase P-gain.";
      drifting = true;
    } else if (iVal < 20) {
      text = "YAW / PITCH AXIS DRIFT. Failing to hold stick angles during crosswinds. Increase I-gain.";
      drifting = true;
    } else if (dVal > 60) {
      text = "D-TERM HEAT WARNING! Motor winding dissipation threshold exceeded. High danger of smoking stator.";
      heating = true;
    } else if (dVal < 15) {
      text = "PROP WASH OSCILLATIONS! Violent shakes detected when descending into raw motor turbulence.";
      oscillate = true;
    } else if (pVal >= 40 && pVal <= 65 && iVal >= 35 && iVal <= 60 && dVal >= 25 && dVal <= 45) {
      text = "PID GAINS HEALTHY. Razor sharp lock-in on all rotational rate coordinate axes.";
    } else {
      text = "Stable flight profile, but minor micro-bounces detected during hard 180 snap turns.";
    }

    setPidStateText(text);
    setIsOscillating(oscillate);
    setIsOverheating(heating);
    setIsDrifting(drifting);
  }, [pVal, iVal, dVal]);

  // Handle visual PID disturbance trigger (wind force)
  const triggerDisturbance = () => {
    playBeep(2100, 0.08);
    setIsDisturbed(true);
    setDroneRotation(25);
    setDroneYOffset(-15);
    setTimeout(() => {
      setIsDisturbed(false);
    }, 120);
  };

  // Keep restoring drone angle with simulated physics loops
  useEffect(() => {
    const interval = setInterval(() => {
      if (isDisturbed) return;

      // Restoring force depends on PID
      let pStrength = pVal / 50; 
      let dStrength = dVal / 35;
      
      // Calculate rotation update
      setDroneRotation(prev => {
        if (Math.abs(prev) < 0.2) return 0;
        
        let target = 0;
        // Sluggish or oscillating restoration
        if (isOscillating) {
          // Keep vibrating
          return (Math.sin(Date.now() / 40) * (pVal - 60) * 0.4);
        }

        let direction = prev > 0 ? -1 : 1;
        let speed = (Math.abs(prev) * 0.15 * pStrength) / (dStrength > 0 ? dStrength : 0.4);
        
        if (isDrifting) {
          // Slow recovery plus random float drift
          return prev + (direction * 0.4) + (Math.sin(Date.now() / 250) * 0.5);
        }

        return prev + (direction * speed);
      });

      // Restoring Y offset (altitude hover)
      setDroneYOffset(prev => {
        if (Math.abs(prev) < 0.2) return 0;
        let direction = prev > 0 ? -1 : 1;
        let restoreSpeed = 0.8 * (pVal / 50);
        return prev + (direction * restoreSpeed);
      });

    }, 30);

    return () => clearInterval(interval);
  }, [isDisturbed, pVal, iVal, dVal, isOscillating, isDrifting]);


  // Flight Maneuvers animation index generator loop
  useEffect(() => {
    if (!isManeuverPlaying) return;
    const interval = setInterval(() => {
      setManeuverProgress(prev => {
        if (prev >= 100) return 0;
        return prev + 1;
      });
    }, 60);
    return () => clearInterval(interval);
  }, [isManeuverPlaying, selectedManeuver]);


  // Helper definitions for FPV Tricks
  const MANEUVERS = [
    {
      id: "split-s",
      name: "Split-S (Yorun Dönüşü)",
      difficulty: "BEGINNER",
      desc: "An elegant, fast descent and direction reversal. Climb, execute a 180-degree half-roll to invert the quad, and pull back hard on pitch to carve a half-loop downwards.",
      steps: [
        "1. Fly straight forward with moderate cruising speed.",
        "2. Roll the stick 180 degrees left/right until the camera is fully inverted.",
        "3. Drop throttle to zero immediately to prevent nose dive speed buildup.",
        "4. Pull pitch backwards (down) hard to complete a half loop downwards.",
        "5. Re-apply throttle smoothly to exit in the opposite direction."
      ],
      sticks: (progress: number) => {
        // Mode 2 Left stick (Throttle, Yaw), Right Stick (Pitch, Roll)
        let throttleVal = 45; // default scale 0-100
        let yawVal = 0; // scale -100 to 100
        let pitchVal = 0; // scale -100 to 100
        let rollVal = 0; // scale -100 to 100
        let pathX = 0;
        let pathY = 0;
        let rot = 0;

        if (progress < 25) {
          // Cruising
          throttleVal = 50; pitchVal = 5; rollVal = 0;
          pathX = progress * 1.5 - 75;
          pathY = -40;
          rot = 0;
        } else if (progress >= 25 && progress < 45) {
          // 180 Roll and throttle cut
          let rollRatio = (progress - 25) / 20;
          rollVal = 85; throttleVal = 10; pitchVal = 0;
          pathX = progress * 1.5 - 75;
          pathY = -40;
          rot = rollRatio * 180;
        } else if (progress >= 45 && progress < 80) {
          // Pulling pitch back into half loop
          let pitchRatio = (progress - 45) / 35;
          throttleVal = 15;
          pitchVal = -80; // pull back
          rot = 180;
          
          // Trigonometric loop down curve
          let angle = pitchRatio * Math.PI;
          pathX = (45 * 1.5 - 75) + Math.sin(angle) * 35;
          pathY = -40 + (1 - Math.cos(angle)) * 35;
          rot = 180 + pitchRatio * 180;
        } else {
          // Re-apply power and straighten
          throttleVal = 60; pitchVal = 10; rollVal = 0;
          pathX = (45 * 1.5 - 75) - (progress - 80) * 1.8;
          pathY = 30;
          rot = 360;
        }

        return { throttle: throttleVal, yaw: yawVal, pitch: pitchVal, roll: rollVal, posX: pathX, posY: pathY, rot };
      }
    },
    {
      id: "powerloop",
      name: "Power Loop (Çember Uçuşu)",
      difficulty: "INTERMEDIATE",
      desc: "A vertical circular trajectory over an object (tree, bridge, gate). Speed up, pull pitch up, boost throttle for gravity-defying climbing momentum, look backward at your target, drop throttle over the top, and glide tail-first.",
      steps: [
        "1. Approach the target structure with high level speed.",
        "2. Pitch backward aggressively to enter vertical climb.",
        "3. Punch throttle (85%+) to maintain altitude during circular climb.",
        "4. At vertical apex (look up), cut throttle completely to fall.",
        "5. Guide the descent loop and smoothly recover with elevator/throttle."
      ],
      sticks: (progress: number) => {
        let throttleVal = 40; let yawVal = 0; let pitchVal = 0; let rollVal = 0;
        let pathX = 0; let pathY = 0; let rot = 0;

        let angle = (progress / 100) * Math.PI * 2;
        rot = (progress / 100) * 360;

        if (progress < 20) {
          throttleVal = 70; pitchVal = 60;  // Entrance speed + pitch up
        } else if (progress >= 20 && progress < 50) {
          throttleVal = 90; pitchVal = 75;  // Punch loop climb
        } else if (progress >= 50 && progress < 75) {
          throttleVal = 10; pitchVal = 80;  // Cut throttle over apex
        } else {
          throttleVal = 60; pitchVal = 40;  // Pull out of dive
        }

        // Circular dynamic coordinate path
        pathX = Math.sin(angle) * 45;
        pathY = -Math.cos(angle) * 45;

        return { throttle: throttleVal, yaw: yawVal, pitch: pitchVal, roll: rollVal, posX: pathX, posY: pathY, rot };
      }
    },
    {
      id: "acro-roll",
      name: "360 Roll (Takla Atma)",
      difficulty: "BEGINNER",
      desc: "The absolute basic acrobatic maneuver. A clean, rapid 360-degree rotation along the longitudinal roll axis. Practice doing it high in the air to establish muscle reflex before low canopy flips.",
      steps: [
        "1. Gain clean forward velocity and pitch slightly upward (10 deg).",
        "2. Snap the roll stick completely to the left/right extreme edge.",
        "3. Release the stick to central deadband immediately at 340 degrees.",
        "4. Keep throttle steady or slightly dip to prevent altitude drop."
      ],
      sticks: (progress: number) => {
        let throttleVal = progress < 20 ? 50 : progress < 80 ? 30 : 50;
        let yawVal = 0;
        let pitchVal = 0;
        let rollVal = (progress >= 20 && progress < 80) ? 95 : 0; // high roll speed
        let rot = progress < 20 ? 0 : progress < 80 ? (progress - 20) * 6 : 360;
        
        // Simple linear flight path with twist rotation
        let pathX = progress * 1.8 - 90;
        let pathY = -20;

        return { throttle: throttleVal, yaw: yawVal, pitch: pitchVal, roll: rollVal, posX: pathX, posY: pathY, rot };
      }
    },
    {
      id: "matty-flip",
      name: "Matty Flip (Geriye Ters Takla)",
      difficulty: "EXPERT",
      desc: "An incredible freestyle trick where the drone flies backwards over an obstacle while remaining inverted, facing in a constant tracking angle. Requires precise coordination between backward pitch and progressive reverse thrust.",
      steps: [
        "1. Fly forward towards and over a specific target obstacle.",
        "2. Pitch forward briefly, then snap backward to roll into inversion.",
        "3. Invert completely but keep pitching backward while looking down.",
        "4. Punch reverse-aimed throttle to pull the quad back *behind* and under the obstacle.",
        "5. Pull back to level and cruise under the target."
      ],
      sticks: (progress: number) => {
        let throttleVal = 35; let yawVal = 0; let pitchVal = 0; let rollVal = 0;
        let pathX = 0; let pathY = 0; let rot = 0;

        if (progress < 25) {
          throttleVal = 70; pitchVal = 30;
          pathX = progress * 1.2 - 60;
          pathY = -40;
          rot = (progress / 25) * 45;
        } else if (progress >= 25 && progress < 65) {
          // The reverse drag
          let ratio = (progress - 25) / 40;
          throttleVal = 85; 
          pitchVal = -90; // pull pitch back
          rot = 45 + ratio * 180;
          
          pathX = (25 * 1.2 - 60) - ratio * 40;
          pathY = -40 - Math.sin(ratio * Math.PI) * 15;
        } else {
          throttleVal = 50; pitchVal = 40;
          pathX = -30 - (progress - 65) * 1.3;
          pathY = -40;
          rot = 225 - (progress - 65) * 1.2;
        }

        return { throttle: throttleVal, yaw: yawVal, pitch: pitchVal, roll: rollVal, posX: pathX, posY: pathY, rot };
      }
    }
  ];

  const currentManeuverData = MANEUVERS.find(m => m.id === selectedManeuver) || MANEUVERS[0];
  const { throttle: activeT, yaw: activeY, pitch: activeP, roll: activeR, posX: droneX, posY: droneY, rot: droneRot } = currentManeuverData.sticks(maneuverProgress);

  // Dynamic Betaflight slider calculations
  const calculateRatesMaxDegSec = () => {
    // Rates formula equivalent: deg_sec = rc_rate * 200 / (1 - super_rate)
    const degSec = (rcRate * 200) / (1.001 - superRate) * (1 + rcExpo * 0.5);
    return Math.round(degSec);
  };

  const bfTones = () => {
    playBeep(2100, 0.05);
    setTimeout(() => playBeep(2400, 0.05), 60);
    setTimeout(() => playBeep(2800, 0.05), 120);
  };

  return (
    <div id="academy-view-root" className="w-full flex-1 overflow-y-auto px-4 md:px-8 py-6 select-text text-left max-h-[calc(100vh-140px)]">
      
      {/* Academy Branding Header Hero */}
      <div className="max-w-7xl mx-auto w-full mb-8 relative">
        <div className="absolute top-0 right-0 bg-orange-600/10 border border-orange-500/20 text-orange-500 px-3 py-1 text-[10px] font-mono rounded-full font-bold uppercase tracking-wider flex items-center gap-1.5 animate-pulse">
          <Award size={13} />
          PILOT KNOWLEDGE BASE ESTABLISHED
        </div>
        <h2 className="text-3xl md:text-4xl text-zinc-100 font-extrabold tracking-tighter uppercase italic flex items-center gap-3">
          <BookOpen className="text-orange-600" size={36} />
          ONLINE ACADEMY
        </h2>
        <p className="text-zinc-500 text-xs md:text-sm mt-1.5 font-sans max-w-2xl leading-relaxed">
          The ultimate interactive reference database for FPV drone flight mechanics, custom board soldering benchmarks, Betaflight calibration loops, and expert acro maneuver guidelines.
        </p>

        {/* Master Selector Tabs */}
        <div className="flex flex-wrap gap-2 mt-6 border-b border-zinc-900 pb-3 select-none">
          {(["academy_az", "races", "news", "gear", "updates", "simulators", "pid", "maneuvers", "betaflight"] as AcademyTab[]).map((tab) => {
            const labelMap: Record<AcademyTab, string> = {
              academy_az: "🎓 A'DAN Z'YE FPV AKADEMİ",
              races: "🏆 DÜNYA YARIŞLARI",
              news: "📰 FPV HABERLERİ",
              gear: "⚡ YENİ ÇIKAN MODELLER",
              updates: "⚙️ YAZILIM GÜNCELLEMELERİ",
              simulators: "🎮 UÇUŞ SİMÜLATÖRLERİ",
              pid: "🛠️ PID TUNER LAB",
              maneuvers: "✈️ AKROBATİK SÜRÜŞ LAB",
              betaflight: "💻 BETAFLIGHT SEKMESİ"
            };
            const active = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => {
                  playSwitchClick();
                  setActiveTab(tab);
                }}
                className={`py-2 px-3.5 rounded-xl font-mono text-[9px] sm:text-[11px] font-black tracking-wider transition-all cursor-pointer ${
                  active 
                    ? "bg-orange-600 text-white shadow-[0_4px_16px_rgba(234,88,12,0.3)]"
                    : "bg-[#0b0c0f] border border-zinc-900 text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {labelMap[tab]}
              </button>
            );
          })}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="max-w-7xl mx-auto w-full"
        >
          {/* TAB 1: A'DAN Z'YE FPV AKADEMİ & KILAVUZ & SSS */}
          {activeTab === "academy_az" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left">
              
              {/* Sol Sütun: A'dan Z'ye Eğitim Adımları */}
              <div className="lg:col-span-8 space-y-6">
                
                {/* Giriş Paneli */}
                <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 md:p-8 font-sans relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-orange-600/5 to-transparent pointer-events-none" />
                  
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-orange-600/10 border border-orange-500/20 flex items-center justify-center text-orange-500">
                      <BookOpen size={20} />
                    </div>
                    <div>
                      <span className="text-[10px] font-mono font-bold text-orange-500 uppercase tracking-widest block">ADIM ADIM REHBER</span>
                      <h3 className="text-xl font-bold text-zinc-100 font-sans tracking-tight">SIFIRDAN UZMANLIĞA FPV PİLOTLUĞU</h3>
                    </div>
                  </div>

                  <p className="text-zinc-400 text-xs mb-6 leading-relaxed">
                    FPV (First Person View) drone dünyasına hoş geldiniz! Bu kılavuz, hiçbir bilginiz olmadığını varsayarak sizi adım adım uçuş teorisinden, donanım montajına ve gelişmiş akrobasi pilotluğuna götürmek için uzman bilgi mimarları tarafından tasarlanmıştır.
                  </p>

                  <div className="space-y-4">
                    
                    {/* Adım 1 */}
                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 flex gap-4">
                      <span className="text-xl font-black font-mono text-orange-500 shrink-0">01</span>
                      <div>
                        <strong className="text-zinc-200 text-xs block mb-1">Simülatör Eğitimi ve Kas Hafızası</strong>
                        <p className="text-zinc-400 text-[11px] leading-relaxed">
                          İlk drone satın alımından önce mutlaka bir radyo kumanda (Transmitter) edinmeli ve bilgisayarda asgari 20-30 saat simülatör uçuşu yapmalısınız. Acro modunda quadcopter kendi kendini düzeltmez; sürekli düzeltme vermeyi kas hafızasına kazımak kırım maliyetinizi sıfıra indirir.
                        </p>
                      </div>
                    </div>

                    {/* Adım 2 */}
                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 flex gap-4">
                      <span className="text-xl font-black font-mono text-orange-500 shrink-0">02</span>
                      <div>
                        <strong className="text-zinc-200 text-xs block mb-1">Doğru Ekipman ve Frekans Seçimi</strong>
                        <p className="text-zinc-400 text-[11px] leading-relaxed">
                          Kumanda RF bağlantısında modern ve açık kaynaklı **ExpressLRS (ELRS)** 2.4GHz protokolü rakipsizdir. Görüntü aktarımında ise bütçenize göre karlı, sıfır gecikmeli **Analog** (5.8GHz) veya kristal netliğinde 1080p **Dijital HD** (DJI O3 / Walksnail) sistemlerinden birini seçmelisiniz.
                        </p>
                      </div>
                    </div>

                    {/* Adım 3 */}
                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 flex gap-4">
                      <span className="text-xl font-black font-mono text-orange-500 shrink-0">03</span>
                      <div>
                        <strong className="text-zinc-200 text-xs block mb-1">Donanım Anatomisi ve Bileşenler</strong>
                        <p className="text-zinc-400 text-[11px] leading-relaxed">
                          Gövde (Frame), Fırçasız Motorlar, Pervaneler, ESC (Elektronik Hız Kontrolcü), FC (Uçuş Kontrol Kartı), Alıcı (RX), Video Verici (VTX) ve Kamera. FC, jiroskoptan aldığı saniyede binlerce veriyi işleyerek ESC&apos;ye gönderir; ESC ise motorların devrini anlık ayarlar.
                        </p>
                      </div>
                    </div>

                    {/* Adım 4 */}
                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 flex gap-4">
                      <span className="text-xl font-black font-mono text-orange-500 shrink-0">04</span>
                      <div>
                        <strong className="text-zinc-200 text-xs block mb-1">Profesyonel Lehimleme Kuralları</strong>
                        <p className="text-zinc-400 text-[11px] leading-relaxed">
                          Pil voltaj girişi gibi yüksek akım taşıyan yollarda mutlaka **12 AWG veya 14 AWG** kalınlığında kablolar kullanılmalıdır. Rosin-Flux (lehim pastası) kullanımı opsiyonel değil, zorunludur. Bakır padlerin mainboard karttan kalkmaması için lehim havyası pad üzerinde 3-4 saniyeden uzun tutulmamalıdır (ideal sıcaklık: 350°C - 380°C).
                        </p>
                      </div>
                    </div>

                  </div>
                </div>

                {/* SSS / BİLGİ BANKASI SEKMESİ */}
                <div className="bg-[#0b0c0f]/95 rounded-2xl border border-zinc-900 p-6 md:p-8 relative">
                  <h3 className="text-xs text-orange-500 font-mono font-bold uppercase tracking-widest border-b border-zinc-900 pb-3 mb-6 flex justify-between items-center">
                    <span>FPV PILOT KNOWLEDGE BASE // SORU-CEVAP BİLGİ BANKASI</span>
                    <HelpCircle size={15} className="text-zinc-500" />
                  </h3>

                  <div className="space-y-4">
                    
                    {/* Item 1 */}
                    <div className="border border-zinc-900 rounded-xl overflow-hidden bg-zinc-950/30">
                      <button
                        type="button"
                        onClick={() => toggleFaq("capacitor")}
                        className="w-full text-left p-4 hover:bg-zinc-900/10 font-bold text-xs sm:text-sm text-zinc-200 flex justify-between items-center cursor-pointer font-sans"
                      >
                        <span>Neden pil girişine kondansatör (capacitor) lehimlemek zorundayız?</span>
                        <span className="text-orange-500 text-[10px] font-mono font-black shrink-0 ml-3">{faqExpanded["capacitor"] ? "KAPAT ▲" : "GÖSTER ▼"}</span>
                      </button>
                      <AnimatePresence>
                        {faqExpanded["capacitor"] && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="p-4 border-t border-zinc-900/60 text-xs text-zinc-400 font-normal leading-relaxed space-y-3 pl-6 bg-zinc-950/70">
                              <p>
                                FPV quadlarda yüksek performanslı her dönüş ve motor frenleme (Dshot active braking) sırasında pilden motora giden voltajda devasa dalgalanmalar (voltage spikes) meydana gelir. Bu dalgalanmalar normal şartlarda 25V seviyesindeki bir sistemde anlık 40V limitlerini aşabilir.
                              </p>
                              <p>
                                Doğrudan ESC XT60 padlerine lehimlenen **Low ESR 35V 470uF veya 1000uF kondansatör**, bu voltaj tepe dalgalarını bir sünger gibi emer. Böylelikle:
                              </p>
                              <ul className="list-disc leading-loose pl-5 text-zinc-450 space-y-1">
                                <li>Kamera ve video verici (VTX) hattındaki parazit dalgalanmaları (karlı ekran görüntüleme) önlenir.</li>
                                <li>Uçuş kontrol kartının hassas jiroskop ve barometre çipleri gürültüden arındırılır.</li>
                                <li>Ani voltaj sıçramalarında ESC mosfetlerinin yanması engellenir.</li>
                              </ul>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* Item 2 */}
                    <div className="border border-zinc-900 rounded-xl overflow-hidden bg-zinc-950/30">
                      <button
                        type="button"
                        onClick={() => toggleFaq("elrs")}
                        className="w-full text-left p-4 hover:bg-zinc-900/10 font-bold text-xs sm:text-sm text-zinc-200 flex justify-between items-center cursor-pointer font-sans"
                      >
                        <span>FrSky, TBS Crossfire ve ExpressLRS (ELRS) arasındaki fark nedir?</span>
                        <span className="text-orange-500 text-[10px] font-mono font-black shrink-0 ml-3">{faqExpanded["elrs"] ? "KAPAT ▲" : "GÖSTER ▼"}</span>
                      </button>
                      <AnimatePresence>
                        {faqExpanded["elrs"] && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="p-4 border-t border-zinc-900/60 text-xs text-zinc-400 font-normal leading-relaxed pl-6 bg-zinc-950/70 space-y-2">
                              <p>
                                **ExpressLRS (ELRS)**, açık kaynaklı geliştirilen, ultra düşük gecikmeli (low-latency) ve uzun menzilli (long-range) çalışan modern kablosuz kontrol sistemidir. LoRa modülasyon teknolojisi ile donatılmıştır ve saniyede 1000Hz yenileme hızına (packet rate) kadar ulaşabilir. Bu, RC kumandanızdaki hareketlerin gecikmesizce motora iletilmesi anlamına gelir.
                              </p>
                              <p>
                                **TBS Crossfire**, 915MHz frekansında çalışan oldukça güvenilir, tescilli ve eski endüstri standardı bir sistemdir. Gürültülü alanlarda ve penetrasyon (binaların arkası) gerektiren yerlerde son derece kararlıdır.
                              </p>
                              <p>
                                **FrSky (D8/D16 / ACCST)**, eski analog günlerden kalma 2.4GHz haberleşmesidir. Menzil ve parazit direnci düşüktür; günümüz performans quadlarında kesinlikle ELRS temsil edilmeli, eski analog protokollerden kaçınılmalıdır.
                              </p>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* Item 3 */}
                    <div className="border border-zinc-900 rounded-xl overflow-hidden bg-zinc-950/30">
                      <button
                        type="button"
                        onClick={() => toggleFaq("voltage_drop")}
                        className="w-full text-left p-4 hover:bg-zinc-900/10 font-bold text-xs sm:text-sm text-zinc-200 flex justify-between items-center cursor-pointer font-sans"
                      >
                        <span>Voltaj Çökmesi (&apos;Battery Sag&apos;) nedir ve uçuşu nasıl etkiler?</span>
                        <span className="text-orange-500 text-[10px] font-mono font-black shrink-0 ml-3">{faqExpanded["voltage_drop"] ? "KAPAT ▲" : "GÖSTER ▼"}</span>
                      </button>
                      <AnimatePresence>
                        {faqExpanded["voltage_drop"] && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="p-4 border-t border-zinc-900/60 text-xs text-zinc-400 font-normal leading-relaxed pl-6 bg-zinc-950/70 space-y-2">
                              <p>
                                Tam gaz (Full-Throttle) verdiğinizde, motorlar aniden çok yüksek akım (Amp) çekmeye başlar. Bu devasa güç ihtiyacı, bataryanın iç direnci (internal resistance) sebebiyle voltajın anlık olarak çökmesine yol açar. Örneğin durağan halde hücre başına 3.8V olan pil, tam gaz verince 3.4V seviyelerine gerileyebilir. Buna **Battery Sag** denir.
                              </p>
                              <p>
                                Yüksek C dereceli piller (High C-rating, örneğin 120C veya 150C), iç dirençleri daha düşük olduğundan voltaj çökmesine çok daha dirençlidir. Sag düzeyi pili zorlamayı bırakınca geri düzelir, ancak bu limitlerin çok zorlanması hücrelerin kimyasına kalıcı hasar verebilir.
                              </p>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* Item 4 */}
                    <div className="border border-zinc-900 rounded-xl overflow-hidden bg-zinc-950/30">
                      <button
                        type="button"
                        onClick={() => toggleFaq("prop_wash")}
                        className="w-full text-left p-4 hover:bg-zinc-900/10 font-bold text-xs sm:text-sm text-zinc-200 flex justify-between items-center cursor-pointer font-sans"
                      >
                        <span>Pervane Türbülansı (&apos;Prop Wash&apos;) neden olur ve nasıl önlenir?</span>
                        <span className="text-orange-500 text-[10px] font-mono font-black shrink-0 ml-3">{faqExpanded["prop_wash"] ? "KAPAT ▲" : "GÖSTER ▼"}</span>
                      </button>
                      <AnimatePresence>
                        {faqExpanded["prop_wash"] && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="p-4 border-t border-zinc-900/60 text-xs text-zinc-400 font-normal leading-relaxed pl-6 bg-zinc-950/70 space-y-2">
                              <p>
                                Kendi ürettiğiniz türbülanslı havanın içerisine dik olarak alçaldığınızda quadın kontrolsüz hızlı sarsıntılar yaşaması hadisesine **Prop Wash** denir. Quad havayı aşağıya doğru iter; siz o havanın üzerine doğrudan düştüğünüzde pervaneler temiz hava yerine girdaplı haitayı yakalar.
                              </p>
                              <p>
                                Azaltmak için:
                              </p>
                              <ul className="list-disc leading-loose pl-5 text-zinc-450 space-y-1">
                                <li>Düşerken doğrudan aşağı inmek yerine hafifçe ileri/geri hareket koordinatları tayin edin (böylece temiz havaya girersiniz).</li>
                                <li>D-Gain limitlerini artırın (Derivative terimi bu sarsıntı ivmesini öngörerek karşı yük komutlandırır).</li>
                                <li>Betaflight filtre sekmesinden gyro kesim filtrelerini ve RPM filtrelemeyi optimize edin.</li>
                              </ul>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                  </div>
                </div>

              </div>

              {/* Sağ Sütun: Güvenlik, RF Tablosu, Batarya Bilgisi */}
              <div className="lg:col-span-4 space-y-6">
                
                {/* Güvenlik Protokolü */}
                <div className="bg-[#120808]/40 border border-red-950 rounded-2xl p-6 font-sans relative">
                  <div className="absolute top-4 right-4 text-red-650">
                    <ShieldAlert size={24} />
                  </div>
                  <h4 className="text-red-500 font-mono font-bold text-xs uppercase tracking-widest mb-4 flex items-center gap-1.5">
                    <span>GÜVENLİK PROTOKOLLERİ // AIR PROTOCOL</span>
                  </h4>
                  <ul className="space-y-3.5 text-xs text-zinc-400 tracking-wide font-normal">
                    <li className="flex items-start gap-2">
                      <span className="text-red-500 mt-0.5 select-none shrink-0">•</span>
                      <span><strong>PERVANELERİ SÖKÜN:</strong> Ev içerisinde Betaflight&apos;a bağlandığınızda veya pil takıp test yaparken pervaneleri asla takılı bırakmayın. Beklenmedik bir sinyal tetiklenmesinde motorlar tam devir dönüp derin kesiklere neden olabilir.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-red-500 mt-0.5 select-none shrink-0">•</span>
                      <span><strong>SMOKE STOPPER:</strong> Yeni bitirdiğiniz bir buildi pile ilk kez bağlarken, şasi üzerinde bir kısa devre olup olmadığını hızlıca keserek kartları kurtaran Smokestopper (Akım sınırlayıcı) kullanın.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-red-500 mt-0.5 select-none shrink-0">•</span>
                      <span><strong>KALABALIKTAN UZAK:</strong> İnsanların, kalabalık yolların, yerleşim yerlerinin veya yüksek gerilim hatlarının üzerinde asla uçuş yapmayın. Güvenli pilot her zaman sorumluluk sahibidir.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-red-500 mt-0.5 select-none shrink-0">•</span>
                      <span><strong>GÜVENLİ ŞARJ:</strong> LiPo pilleri asla başıboş şarj etmeyin. Mutlaka yanmaz lehim torbaları (LiPo şarj torbası) veya metal korunaklı kutularda şarj edin.</span>
                    </li>
                  </ul>
                </div>

                {/* Batarya Voltaj Bilgi Kartı */}
                <div className="bg-[#0b0c0e]/95 border border-zinc-900 rounded-2xl p-6 font-mono">
                  <div className="flex items-center gap-2 mb-4 text-zinc-100 uppercase text-[11px] font-bold">
                    <Battery className="text-orange-500" size={16} />
                    <span>LİPO HÜCRE SEVİYELERİ</span>
                  </div>
                  <div className="divide-y divide-zinc-900 text-xs text-zinc-400 font-sans space-y-3 pt-1">
                    <div className="flex justify-between pb-3">
                      <span>Tam Şarj (Full Limit):</span>
                      <span className="font-mono text-cyan-400 font-bold">4.20V / Hücre</span>
                    </div>
                    <div className="flex justify-between py-3">
                      <span>Nominal Voltaj:</span>
                      <span className="font-mono text-zinc-300">3.70V / Hücre</span>
                    </div>
                    <div className="flex justify-between py-3">
                      <span>Saklama (Storage Limit):</span>
                      <span className="font-mono text-emerald-400 font-bold">3.80V–3.85V / Hücre</span>
                    </div>
                    <div className="flex justify-between pt-3">
                      <span className="text-red-500 font-bold">Kritik Boş Limit:</span>
                      <span className="font-mono text-red-500 font-black">Under 3.30V / Hücre</span>
                    </div>
                  </div>
                </div>

                {/* RF Sinyal Bilgileri */}
                <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 font-sans">
                  <h4 className="text-[11px] font-mono text-zinc-100 font-bold uppercase block tracking-widest mb-3.5 border-b border-zinc-900 pb-2">
                    FREKANS & RF BİLGİ KARTLARI
                  </h4>
                  <div className="space-y-3 text-xs text-zinc-400">
                    <div>
                      <strong className="text-zinc-300 font-mono block text-[10px] uppercase mb-0.5">KONTROL FREKANSI (ELRS):</strong>
                      <span>2.4GHz bandında LoRa modülasyonu ile saniyede 1000Hz yenileme hızı. Yüksek penetrasyon sunar.</span>
                    </div>
                    <div>
                      <strong className="text-zinc-300 font-mono block text-[10px] uppercase mb-0.5">VİDEO FREKANSI (VTX):</strong>
                      <span>Görüntü aktarımı tamamen 5.8GHz spektrumunda gerçekleşir. Raceband 1 (R1) 5658MHz, R8 ise 5917MHz&apos;dir.</span>
                    </div>
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* TAB 2: PID DYNAMIC PLAYGROUND LAB */}
          {activeTab === "pid" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              
              {/* Physics simulator graphic panel */}
              <div className="lg:col-span-2 flex flex-col items-center bg-[#07090b]/80 border-2 border-zinc-900 rounded-2xl p-6 relative">
                <div className="text-left w-full mb-4 pb-2 border-b border-zinc-900 flex justify-between items-center font-mono text-[10px]">
                  <span className="font-black text-cyan-400">[ ACADEMY GYRO SENSOR FLIGHT LAB ]</span>
                  <span className="text-zinc-500 uppercase">Interactive Physics Engine</span>
                </div>

                {/* Drone Visual Workspace Layout */}
                <div className="w-full h-80 relative bg-zinc-950 border border-zinc-900 rounded-xl flex items-center justify-center p-4 overflow-hidden">
                  
                  {/* Scope target crosshair */}
                  <div className="absolute inset-12 border border-zinc-900/40 rounded-full border-dashed pointer-events-none" />
                  <div className="absolute h-full w-px bg-zinc-900/40" />
                  <div className="absolute w-full h-px bg-zinc-900/40" />

                  {/* Visual alert layers for physics states */}
                  <AnimatePresence>
                    {isOscillating && (
                      <motion.div 
                        initial={{ opacity: 0 }} 
                        animate={{ opacity: 0.08 }} 
                        exit={{ opacity: 0 }} 
                        className="absolute inset-0 bg-red-600 pointer-events-none"
                      />
                    )}
                  </AnimatePresence>

                  {/* Interactive floating Drone Vector */}
                  <div 
                    className="flex flex-col items-center cursor-pointer select-none transition-transform duration-100 relative"
                    style={{
                      transform: `translate(0px, ${droneYOffset}px) rotate(${droneRotation}deg)`,
                    }}
                    onClick={triggerDisturbance}
                  >
                    {/* Rotor exhaust thrust lights animation based on state speed */}
                    <div className="flex justify-between w-64 absolute -top-10 px-10 pointer-events-none select-none">
                      <div className={`w-3 h-12 bg-linear-to-b from-cyan-400 to-transparent rounded-full opacity-60 ${isOscillating ? "animate-bounce" : "animate-pulse"}`} />
                      <div className={`w-3 h-12 bg-linear-to-b from-cyan-400 to-transparent rounded-full opacity-60 ${isOscillating ? "animate-bounce" : "animate-pulse"}`} />
                    </div>

                    {/* FPV drone frame body front wire representation */}
                    <div className="relative flex items-center justify-center">
                      {/* Left Arm and Motor */}
                      <div className="w-24 h-4 bg-zinc-700 rounded-full -rotate-12 transform origin-right -mr-2" />
                      <div className="w-6 h-10 bg-zinc-800 border border-zinc-600 rounded-lg -mt-3 relative">
                        <div className="w-12 h-1.5 bg-zinc-400 rounded-full absolute -top-1 -left-3 animate-spin" />
                      </div>

                      {/* Center FC Chassis Core Stack */}
                      <div className="w-16 h-12 bg-orange-600 border-2 border-orange-500 rounded-xl flex flex-col items-center justify-center z-10 shadow-lg relative">
                        {/* GoPro Payload visual representation */}
                        <div className="absolute -top-7 w-10 h-7 bg-zinc-900 border border-zinc-700 rounded-sm flex items-center justify-center">
                          <div className="w-2.5 h-2.5 bg-black rounded-full border border-cyan-400" />
                        </div>
                        <span className="text-[7px] font-mono text-white font-black">APEX-FC</span>
                        <div className="w-2 h-2 bg-emerald-400 rounded-full mt-1 animate-ping absolute" />
                        <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1 absolute" />
                      </div>

                      {/* Right Arm and Motor */}
                      <div className="w-6 h-10 bg-zinc-800 border border-zinc-600 rounded-lg -mt-3 relative">
                        <div className="w-12 h-1.5 bg-zinc-400 rounded-full absolute -top-1 -left-3 animate-spin" style={{ animationDuration: "0.2s" }} />
                      </div>
                      <div className="w-24 h-4 bg-zinc-700 rounded-full rotate-12 transform origin-left -ml-2" />
                    </div>

                    {/* Shadow representation on hover ground */}
                    <div 
                      className="w-48 h-2 bg-black/60 rounded-full mt-24 filter blur-xs pointer-events-none transition-all duration-150"
                      style={{
                        transform: `scale(${1 - droneYOffset / 120})`,
                        opacity: 100 / (100 + Math.abs(droneYOffset))
                      }}
                    />
                  </div>

                  {/* Disturbed wind graphic card */}
                  {isDisturbed && (
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 bg-cyan-600 text-white px-2.5 py-1 text-[8px] tracking-widest uppercase font-mono rounded font-bold animate-ping">
                      💨 Gust Impact
                    </div>
                  )}

                  {/* Center calibration dot */}
                  <div className="absolute bottom-4 right-4 bg-zinc-950/80 px-3 py-1.5 border border-zinc-900 rounded font-mono text-[8px] text-zinc-500 text-right leading-none space-y-1">
                    <div>ROLL ERR: {(droneRotation).toFixed(1)}°</div>
                    <div>TILT VAL: {(droneYOffset).toFixed(1)}mm</div>
                  </div>
                </div>

                {/* Wind Gust disturbance trigger button */}
                <div className="w-full mt-4 flex items-center gap-3">
                  <button 
                    type="button"
                    onClick={triggerDisturbance}
                    className="bg-cyan-500 hover:bg-cyan-600 text-zinc-950 font-mono font-black py-2.5 px-5 text-xs rounded-xl transition-all cursor-pointer uppercase flex items-center gap-2"
                  >
                    <span>💨 WIND GUST FORCE (RÜZGAR ETKİSİ)</span>
                  </button>

                  <div className="flex-1 bg-zinc-950/60 p-3 border border-zinc-900 rounded-xl leading-snug">
                    <span className="text-[10px] uppercase font-mono text-zinc-500 font-bold block mb-0.5">Gyro Dynamics Reading:</span>
                    <span className={`text-[11px] font-bold block ${
                      isOscillating ? "text-red-500 animate-pulse" : isDrifting ? "text-amber-500" : isOverheating ? "text-orange-500" : "text-emerald-400"
                    }`}>
                      {pidStateText}
                    </span>
                  </div>
                </div>

              </div>

              {/* PID Sliders and Theoretical Lessons bar */}
              <div className="flex flex-col gap-6 font-mono">
                
                {/* Sliders Workspace */}
                <div className="bg-[#0b0c0f]/95 rounded-2xl border border-zinc-900 p-6 text-left">
                  <h4 className="text-zinc-100 font-black uppercase text-xs mb-5 flex items-center gap-2 tracking-wider">
                    <Sliders className="text-orange-500" size={16} />
                    TUNING SLIDERS
                  </h4>

                  <div className="space-y-5">
                    
                    {/* P Slider */}
                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between text-[10px] leading-none">
                        <span className="font-extrabold text-orange-500">P (PROPORTIONAL - HIZ)</span>
                        <span className="font-bold text-zinc-100">{pVal}</span>
                      </div>
                      <input 
                        type="range"
                        min="10"
                        max="100"
                        value={pVal}
                        onChange={(e) => {
                          playSwitchClick();
                          setPVal(parseInt(e.target.value));
                        }}
                        className="w-full accent-orange-500 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                      />
                      <span className="text-[8px] text-zinc-500 font-sans leading-relaxed">
                        Sets responsiveness. If P-gain is too slow, the craft drifts. If too high, it oscillates intensely.
                      </span>
                    </div>

                    {/* I Slider */}
                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between text-[10px] leading-none">
                        <span className="font-extrabold text-cyan-400">I (INTEGRAL - DURUŞ TUTUŞUN)</span>
                        <span className="font-bold text-zinc-100">{iVal}</span>
                      </div>
                      <input 
                        type="range"
                        min="10"
                        max="100"
                        value={iVal}
                        onChange={(e) => {
                          playSwitchClick();
                          setIVal(parseInt(e.target.value));
                        }}
                        className="w-full accent-cyan-400 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                      />
                      <span className="text-[8px] text-zinc-500 font-sans leading-relaxed">
                        Corrects cumulative errors (wind drifts). Holds the drone&apos;s physical angle steady during long arcs.
                      </span>
                    </div>

                    {/* D Slider */}
                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between text-[10px] leading-none">
                        <span className="font-extrabold text-amber-500">D (DERIVATIVE - DAMPERLEME)</span>
                        <span className="font-bold text-zinc-100">{dVal}</span>
                      </div>
                      <input 
                        type="range"
                        min="5"
                        max="80"
                        value={dVal}
                        onChange={(e) => {
                          playSwitchClick();
                          setDVal(parseInt(e.target.value));
                        }}
                        className="w-full accent-amber-500 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                      />
                      <span className="text-[8px] text-zinc-500 font-sans leading-relaxed">
                        Dampens momentum swings. Prevents bounce-back overshoots. High D-gain leads to hot ESC windings.
                      </span>
                    </div>

                  </div>
                </div>

                {/* Educational Summary Card */}
                <div className="bg-[#0b0c0f]/95 rounded-2xl border border-zinc-900 p-5 text-[10px] text-zinc-500 font-sans leading-relaxed">
                  <div className="flex items-center gap-1.5 font-bold font-mono text-zinc-300 uppercase mb-2">
                    <Info size={13} className="text-cyan-400" />
                    THE QUICK PID FORMULA
                  </div>
                  <span>
                    Your flight controller monitors error 1000 times a second. Proportional reacts now, Integral corrects the past, and Derivative safely predicts the future. Align these parameters inside 40-55 limits for optimal balance.
                  </span>
                </div>

              </div>
            </div>
          )}

          {/* TAB 3: FLIGHT MANEUVERS ACRO CLINIC */}
          {activeTab === "maneuvers" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 text-left">
              
              {/* Maneuvers Navigation Card List */}
              <div className="lg:col-span-1 space-y-3.5">
                <span className="text-[9px] font-mono font-bold text-zinc-500 block uppercase tracking-widest px-1">SELECT MANEUVER TASK // DERS SEÇİMİ</span>
                <div className="space-y-2">
                  {MANEUVERS.map((man) => {
                    const active = selectedManeuver === man.id;
                    return (
                      <button
                        key={man.id}
                        type="button"
                        onClick={() => {
                          playSwitchClick();
                          setSelectedManeuver(man.id);
                          setManeuverProgress(0);
                        }}
                        className={`w-full text-left p-4 rounded-xl border transition-all flex justify-between items-center cursor-pointer ${
                          active 
                            ? "bg-orange-950/20 border-orange-500 text-orange-400" 
                            : "bg-[#0b0c0f] border-zinc-900 text-zinc-400 hover:border-zinc-800"
                        }`}
                      >
                        <div className="font-sans">
                          <span className="text-[10px] font-mono block text-zinc-500 font-bold tracking-widest mb-1">
                            {man.difficulty} LEVEL
                          </span>
                          <span className="text-sm font-bold block select-none">
                            {man.name}
                          </span>
                        </div>
                        <Play size={14} className={active ? "text-orange-500" : "text-zinc-650"} />
                      </button>
                    );
                  })}
                </div>

                <div className="bg-zinc-950/40 p-4 rounded-xl border border-zinc-900/60 mt-4 leading-relaxed font-sans text-xs text-zinc-500">
                  <div className="flex items-center gap-2 font-mono text-[10px] font-black text-zinc-300 uppercase mb-1.5">
                    <Lightbulb size={13} className="text-yellow-500" />
                    <span>TRAINER TIP</span>
                  </div>
                  Acro mode has absolute self-leveling completely disabled. The drone permanently holds whatever tilt position you set on the stick until coordinate recovery inputs are received. Perfecting muscle memory is mandatory.
                </div>
              </div>

              {/* Central Plot display of maneuvers + live stick diagnostics */}
              <div className="lg:col-span-2 flex flex-col gap-6">
                
                {/* Graphic trace canvas simulating flight path */}
                <div className="bg-[#0b0c0f]/95 border border-zinc-900 rounded-2xl p-6 flex flex-col items-center">
                  <div className="w-full flex items-center justify-between border-b border-zinc-900 pb-3 mb-5 font-mono">
                    <div>
                      <span className="text-xs text-zinc-100 font-black uppercase tracking-tight italic">
                        {currentManeuverData.name}
                      </span>
                      <p className="text-[9px] text-zinc-500 uppercase mt-0.5 tracking-wider">ANIMATED FLIGHT PATH TRAJECTORY</p>
                    </div>

                    {/* Animation parameters controls */}
                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => {
                          playSwitchClick();
                          setIsManeuverPlaying(!isManeuverPlaying);
                        }}
                        className="p-1.5 bg-zinc-900 hover:bg-zinc-850 rounded border border-zinc-800 text-zinc-400 cursor-pointer"
                        title="Pause / Resume"
                      >
                        {isManeuverPlaying ? <Pause size={12} /> : <Play size={12} />}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          playBeep(1900, 0.04);
                          setManeuverProgress(0);
                        }}
                        className="text-[9px] font-black uppercase font-mono bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-zinc-400 px-2 py-1 cursor-pointer"
                      >
                        Restart
                      </button>
                    </div>
                  </div>

                  {/* Flight path simulation box */}
                  <div className="w-full h-56 bg-zinc-950 border border-zinc-900 rounded-xl relative overflow-hidden flex items-center justify-center">
                    
                    {/* Horizon guidelines lines */}
                    <div className="absolute w-full h-px bg-zinc-900/30 border-dashed" />
                    <div className="absolute bottom-6 left-0 right-0 h-0.5 bg-emerald-950/20" /> {/* ground representation */}

                    {/* The dynamic flight trace line representing trail */}
                    <svg className="absolute inset-0 w-full h-full opacity-35" pointerEvents="none">
                      {selectedManeuver === "split-s" && (
                        <path d="M 120 70 L 260 70 C 310 70, 310 140, 230 145 L 80 145" fill="none" stroke="#ea580c" strokeWidth="2.5" strokeDasharray="3 3" />
                      )}
                      {selectedManeuver === "acro-roll" && (
                        <path d="M 60 100 L 400 100" fill="none" stroke="#ea580c" strokeWidth="2.5" strokeDasharray="3 3" />
                      )}
                      {selectedManeuver === "powerloop" && (
                        <circle cx="230" cy="100" r="45" fill="none" stroke="#ea580c" strokeWidth="2.5" strokeDasharray="3 3" />
                      )}
                      {selectedManeuver === "matty-flip" && (
                        <path d="M 120 140 L 260 140 C 270 120, 270 60, 200 60 L 100 80" fill="none" stroke="#ea580c" strokeWidth="2.5" strokeDasharray="3 3" />
                      )}
                    </svg>

                    {/* Animated visual Drone dot */}
                    <div 
                      className="absolute w-12 h-6 border-2 border-orange-500 rounded bg-[#0b0c0f] flex items-center justify-center font-mono opacity-90 shadow-[0_0_12px_rgba(234,88,12,0.4)] transition-all duration-75"
                      style={{
                        transform: `translate(${droneX}px, ${droneY}px) rotate(${droneRot}deg)`
                      }}
                    >
                      <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full mb-0.5 mr-0.5" />
                      <span className="text-[6px] text-zinc-400 font-extrabold scale-75 uppercase">QUAD</span>
                    </div>

                    <div className="absolute right-3.5 top-3.5 bg-zinc-900/90 py-1.5 px-2.5 border border-zinc-800 rounded text-[9px] font-mono text-zinc-400 flex items-center gap-1.5 leading-none shadow">
                      <div className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-ping" />
                      <span>STEP CHRONO: {maneuverProgress}%</span>
                    </div>
                  </div>

                  {/* Dynamic Stick visualization under the path */}
                  <div className="grid grid-cols-2 gap-8 w-full mt-6 bg-zinc-950 p-4 border border-zinc-900 rounded-xl font-mono text-[9px] text-zinc-500 text-center select-none">
                    
                    {/* Left Stick (Throttle / Yaw) */}
                    <div className="flex flex-col items-center">
                      <span className="font-bold uppercase tracking-wider mb-2.5 text-zinc-400">STICK L - THROTTLE & YAW</span>
                      <div className="w-24 h-24 rounded-full bg-[#050608] border-2 border-zinc-800 relative flex items-center justify-center">
                        <div className="absolute h-full w-px bg-zinc-900 pointer-events-none" />
                        <div className="absolute w-full h-px bg-zinc-900 pointer-events-none" />
                        
                        {/* Interactive Gimbal Stick Node */}
                        <div 
                          className="w-4.5 h-4.5 rounded-full bg-orange-600 border border-orange-500 absolute shadow-md transition-all duration-75"
                          style={{
                            left: `calc(50% + ${(activeY / 100) * 32}px - 9px)`,
                            top: `calc(50% - ${((activeT / 50) - 1) * 32}px - 9.5px)`
                          }}
                        />
                      </div>
                      <div className="mt-2.5 flex justify-between w-24 text-[8px] leading-none">
                        <span>YAW: {activeY}</span>
                        <span>THR: {activeT}%</span>
                      </div>
                    </div>

                    {/* Right Stick (Pitch / Roll) */}
                    <div className="flex flex-col items-center">
                      <span className="font-bold uppercase tracking-wider mb-2.5 text-zinc-400">STICK R - PITCH & ROLL</span>
                      <div className="w-24 h-24 rounded-full bg-[#050608] border-2 border-zinc-800 relative flex items-center justify-center">
                        <div className="absolute h-full w-px bg-zinc-900 pointer-events-none" />
                        <div className="absolute w-full h-px bg-zinc-900 pointer-events-none" />
                        
                        <div 
                          className="w-4.5 h-4.5 rounded-full bg-cyan-400 border border-cyan-300 absolute shadow-md transition-all duration-75"
                          style={{
                            left: `calc(50% + ${(activeR / 100) * 32}px - 9px)`,
                            top: `calc(50% - ${(activeP / 100) * 32}px - 9.5px)`
                          }}
                        />
                      </div>
                      <div className="mt-2.5 flex justify-between w-24 text-[8px] leading-none">
                        <span>ROL: {activeR}</span>
                        <span>PIT: {activeP}</span>
                      </div>
                    </div>

                  </div>

                </div>

                {/* Maneuver Description info box */}
                <div className="bg-[#0b0c0f]/95 rounded-2xl border border-zinc-900 p-6 md:p-7 leading-relaxed font-sans text-xs">
                  <h4 className="text-sm font-bold text-zinc-100 flex items-center gap-1.5 mb-2.5">
                    <Compass className="text-orange-500" size={17} />
                    <span>TRAINING PROTOCOL: {currentManeuverData.name}</span>
                  </h4>
                  <p className="text-zinc-400 pb-4 border-b border-zinc-900 mb-4">{currentManeuverData.desc}</p>
                  
                  <span className="text-[10px] font-mono uppercase font-black tracking-widest text-zinc-500 block mb-3">
                    STEP BY STEP GUIDELINE // REHBER ADIMLARI
                  </span>
                  <div className="space-y-2 mt-1 font-mono text-[10px] text-zinc-400 leading-normal">
                    {currentManeuverData.steps.map((str, i) => (
                      <div key={i} className="flex gap-2.5 items-start">
                        <span className="text-orange-500 shrink-0 select-none">&gt;</span>
                        <span>{str}</span>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            </div>
          )}

          {/* TAB 4: SIMULATED BETAFLIGHT CONFIGURATION CORES */}
          {activeTab === "betaflight" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 text-left">
              
              {/* OSD Mock Configuration Workspace */}
              <div className="lg:col-span-2 bg-[#08080a] border-2 border-zinc-900 rounded-2xl font-mono text-zinc-400 p-6">
                
                {/* Header resembling Betaflight UI */}
                <div className="w-full flex items-center justify-between border-b border-zinc-900 pb-3 mb-5 text-[10px]">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 bg-yellow-400 rounded-full animate-ping" />
                    <span className="text-yellow-400 font-extrabold uppercase">BETAFLIGHT CONFIGURATOR 10.9</span>
                  </div>
                  <div className="bg-zinc-900/80 px-3 py-1 border border-zinc-800 rounded">
                    FC PORT: <span className="text-emerald-400 font-bold">COM3 (USB-VCP)</span>
                  </div>
                </div>

                {/* Left tab selector in BF inside */}
                <div className="flex gap-1 bg-zinc-950 p-1 border border-zinc-900 rounded-lg mb-6 max-w-sm">
                  <button
                    onClick={() => { playSwitchClick(); setBfActiveTab("receiver"); }}
                    className={`flex-1 py-1.5 px-2.5 rounded text-[9px] uppercase font-black text-center transition-all cursor-pointer ${
                      bfActiveTab === "receiver" ? "bg-zinc-900 text-yellow-500 border-l-2 border-yellow-500" : "text-zinc-500 hover:text-white"
                    }`}
                  >
                    Alıcı (Receiver)
                  </button>
                  <button
                    onClick={() => { playSwitchClick(); setBfActiveTab("modes"); }}
                    className={`flex-1 py-1.5 px-2.5 rounded text-[9px] uppercase font-black text-center transition-all cursor-pointer ${
                      bfActiveTab === "modes" ? "bg-zinc-900 text-yellow-500 border-l-2 border-yellow-500" : "text-zinc-500 hover:text-white"
                    }`}
                  >
                    Modlar (Modes)
                  </button>
                  <button
                    onClick={() => { playSwitchClick(); setBfActiveTab("rates"); }}
                    className={`flex-1 py-1.5 px-2.5 rounded text-[9px] uppercase font-black text-center transition-all cursor-pointer ${
                      bfActiveTab === "rates" ? "bg-zinc-900 text-yellow-500 border-l-2 border-yellow-500" : "text-zinc-500 hover:text-white"
                    }`}
                  >
                    Oranlar (Rates)
                  </button>
                </div>

                {/* Sub Tab: RECEIVER (ALICI) */}
                {bfActiveTab === "receiver" && (
                  <div className="space-y-4">
                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 leading-relaxed text-xs">
                      <span className="text-[10px] text-zinc-100 font-black tracking-widest block uppercase mb-2">RECEIVER CHANNEL PROTOCOLS</span>
                      <p className="text-zinc-400">
                        Modern ELRS operates exclusively via **Serial-based receiver** protocol mapping using the **CRSF (Crossfire)** protocol. Set telemetry to ON to enable voltage values readings directly on your transmitter screen.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      
                      {/* Mapping Setup box */}
                      <div className="p-4 bg-zinc-950/80 border border-zinc-900 rounded-xl space-y-3">
                        <span className="text-[9px] text-zinc-500 font-black uppercase tracking-wider block">CHANNEL LAYOUT</span>
                        <div className="space-y-2 text-[10px]">
                          <div className="flex justify-between border-b border-zinc-900/60 pb-1">
                            <span>ROLL:</span>
                            <span className="text-yellow-500">CH 1</span>
                          </div>
                          <div className="flex justify-between border-b border-zinc-900/60 pb-1">
                            <span>PITCH:</span>
                            <span className="text-yellow-500">CH 2</span>
                          </div>
                          <div className="flex justify-between border-b border-zinc-900/60 pb-1">
                            <span>THROTTLE:</span>
                            <span className="text-yellow-500">CH 3</span>
                          </div>
                          <div className="flex justify-between border-b border-zinc-900/60 pb-1">
                            <span>YAW:</span>
                            <span className="text-yellow-500">CH 4</span>
                          </div>
                          <div className="flex justify-between pt-1">
                            <span>AUX 1 (ARMING):</span>
                            <span className="text-emerald-400">CH 5</span>
                          </div>
                        </div>
                      </div>

                      {/* Provider toggle interactive */}
                      <div className="p-4 bg-zinc-950/80 border border-zinc-900 rounded-xl flex flex-col justify-between">
                        <div>
                          <span className="text-[9px] text-zinc-500 font-black uppercase tracking-wider block mb-2">ALICI PORT PROTOKOLÜ (SERIAL PROVIDER)</span>
                          <p className="text-[10px] text-zinc-400 leading-normal">
                            Choose the underlying telemetry data layer matching your receiver wiring layout.
                          </p>
                        </div>
                        <div className="flex gap-2 mt-4">
                          {["CRSF", "SBUS", "FPORT"].map((prov) => (
                            <button
                              key={prov}
                              onClick={() => { playSwitchClick(); setRxProvider(prov); }}
                              className={`flex-1 py-1 text-[9px] rounded font-bold transition-all cursor-pointer ${
                                rxProvider === prov ? "bg-yellow-500 text-black font-black" : "bg-zinc-900 hover:text-white"
                              }`}
                            >
                              {prov}
                            </button>
                          ))}
                        </div>
                      </div>

                    </div>
                  </div>
                )}

                {/* Sub Tab: MODES (MODLAR) */}
                {bfActiveTab === "modes" && (
                  <div className="space-y-4">
                    <div className="p-4.5 bg-zinc-950/80 border border-zinc-900 rounded-xl text-xs space-y-4">
                      
                      {/* ARM slider box */}
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900 pb-4">
                        <div className="text-left font-sans">
                          <span className="text-[11px] font-mono font-bold text-zinc-100 uppercase dark:text-zinc-100 tracking-wide block">ARMING MODE (AUX 1 RANGE)</span>
                          <p className="text-zinc-500 text-[10px] leading-relaxed mt-0.5">Maps the absolute state slider values required to spin the motors.</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => { playSwitchClick(); setAux1Armed(!aux1Armed); }}
                            className={`px-3 py-1.5 rounded text-[9px] font-black uppercase transition-all whitespace-nowrap cursor-pointer ${
                              aux1Armed 
                                ? "bg-emerald-950 border border-emerald-900 text-emerald-400" 
                                : "bg-zinc-900 text-zinc-500 hover:text-zinc-400"
                            }`}
                          >
                            Aux1 Signal: {aux1Armed ? "1800 (HIGH)" : "1000 (LOW)"}
                          </button>
                          <span className={`text-[10px] font-bold ${aux1Armed ? "text-emerald-400 animate-pulse" : "text-zinc-650"}`}>
                            {aux1Armed ? "● STATE ACTIVE" : "○ STATE INACTIVE"}
                          </span>
                        </div>
                      </div>

                      {/* Flight mode options list */}
                      <div className="space-y-2.5">
                        <div className="flex justify-between items-center text-[10px] bg-zinc-950 p-2.5 rounded border border-zinc-900">
                          <span className="text-zinc-200">ANGLE MODE - AUTOLEVEL STABILIZED</span>
                          <span className="text-cyan-400 font-bold">&gt; Map to AUX 2 (1300 - 1700 range)</span>
                        </div>
                        <div className="flex justify-between items-center text-[10px] bg-zinc-950 p-2.5 rounded border border-zinc-900">
                          <span className="text-zinc-200">ACRO MODE - FULL GYRO MANUAL</span>
                          <span className="text-zinc-600 font-bold">Standard default mode (No assignments)</span>
                        </div>
                        <div className="flex justify-between items-center text-[10px] bg-zinc-950 p-2.5 rounded border border-zinc-900">
                          <span className="text-zinc-200">BEEPER ACTIVE SWITCH</span>
                          <span className="text-yellow-500 font-bold">&gt; Map to AUX 3 (1700 - 2100 range)</span>
                        </div>
                      </div>

                    </div>
                  </div>
                )}

                {/* Sub Tab: RATES (ORANLAR) */}
                {bfActiveTab === "rates" && (
                  <div className="space-y-4">
                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 leading-relaxed text-xs">
                      <span className="text-[10px] text-zinc-100 font-black tracking-widest block uppercase mb-1">ROTATIONAL ACCELERATION VALUES // ORAN AYARLARI</span>
                      <p className="text-zinc-400">
                        Adjust super rate (acceleration multiplier) and RC rate (center responsiveness sensitivity) to change how fast your quad spins during full stick expansions.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      
                      {/* RC Rate */}
                      <div className="p-4 bg-zinc-950/80 border border-zinc-900 rounded-xl flex flex-col justify-between">
                        <div>
                          <span className="text-[10px] text-zinc-100 font-bold uppercase block mb-1">RC Rate</span>
                          <span className="text-[8px] text-zinc-500 font-sans block leading-normal mb-3">Controls center stick sensitivity. Higher values feels sharp.</span>
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <input 
                            type="range"
                            min="0.5"
                            max="2.0"
                            step="0.05"
                            value={rcRate}
                            onChange={(e) => { playSwitchClick(); setRcRate(parseFloat(e.target.value)); }}
                            className="w-full accent-yellow-500 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                          />
                          <span className="text-yellow-500 font-bold text-xs">{rcRate.toFixed(2)}</span>
                        </div>
                      </div>

                      {/* Super Rate */}
                      <div className="p-4 bg-zinc-950/80 border border-zinc-900 rounded-xl flex flex-col justify-between">
                        <div>
                          <span className="text-[10px] text-zinc-100 font-bold uppercase block mb-1">Super Rate</span>
                          <span className="text-[8px] text-zinc-500 font-sans block leading-normal mb-3">Increases rotational acceleration at full stick extensions.</span>
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <input 
                            type="range"
                            min="0.2"
                            max="0.9"
                            step="0.05"
                            value={superRate}
                            onChange={(e) => { playSwitchClick(); setSuperRate(parseFloat(e.target.value)); }}
                            className="w-full accent-yellow-500 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                          />
                          <span className="text-yellow-500 font-bold text-xs">{superRate.toFixed(2)}</span>
                        </div>
                      </div>

                      {/* RC Expo */}
                      <div className="p-4 bg-zinc-950/80 border border-zinc-900 rounded-xl flex flex-col justify-between">
                        <div>
                          <span className="text-[10px] text-zinc-100 font-bold uppercase block mb-1">RC Expo (Yumuşama)</span>
                          <span className="text-[8px] text-zinc-500 font-sans block leading-normal mb-3">Softens the center stick responses. Protects micro inputs.</span>
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <input 
                            type="range"
                            min="0.0"
                            max="0.5"
                            step="0.05"
                            value={rcExpo}
                            onChange={(e) => { playSwitchClick(); setRcExpo(parseFloat(e.target.value)); }}
                            className="w-full accent-yellow-500 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                          />
                          <span className="text-yellow-500 font-bold text-xs">{rcExpo.toFixed(2)}</span>
                        </div>
                      </div>

                    </div>

                    {/* Peak calculation deg/sec */}
                    <div className="p-4 bg-[#0a0f0d]/60 border border-emerald-950 rounded-xl flex items-center justify-between text-xs">
                      <div>
                        <span className="font-sans block text-zinc-400">Maximum rotational speed calculated at stick limits:</span>
                        <span className="text-[10px] font-mono tracking-wide text-zinc-500">Fast enough to complete vertical loop cycles seamlessly.</span>
                      </div>
                      <div className="text-right">
                        <span className="text-lg md:text-xl font-bold font-mono text-emerald-400">{calculateRatesMaxDegSec()}°</span>
                        <span className="text-[8px] block text-zinc-500 font-mono tracking-wider">DEG/SEC</span>
                      </div>
                    </div>

                  </div>
                )}

                {/* Simulated action buttons */}
                <div className="w-full mt-6 pt-5 border-t border-zinc-900 flex justify-end gap-3 font-mono">
                  <button
                    onClick={bfTones}
                    className="py-2 px-5 bg-yellow-500 hover:bg-yellow-650 text-black font-extrabold text-xs rounded-xl cursor-pointer transition-all flex items-center gap-1.5"
                  >
                    <span>💾 SAVE & REBOOT BOARDS (KAYDET)</span>
                  </button>
                </div>

              </div>

              {/* Sidebar: Help documentation card layout */}
              <div className="space-y-6">
                <div className="bg-[#0b0c0f]/95 border border-zinc-900 rounded-2xl p-6 font-sans text-xs flex flex-col justify-between">
                  <div className="space-y-4">
                    <span className="text-[10px] font-mono font-bold text-orange-500 block uppercase tracking-widest border-b border-zinc-900 pb-2.5 mb-2">
                      GLOSSARY // BETAFLIGHT TERİMLERİ
                    </span>
                    <div className="space-y-3 font-normal text-zinc-405 leading-relaxed">
                      <div>
                        <strong className="text-zinc-100 font-mono block mb-0.5">VCP (Virtual COM Port):</strong>
                        <span>The virtual serial interface connecting physical microcontrollers directly to software terminals on standard PCs via USB.</span>
                      </div>
                      <div>
                        <strong className="text-zinc-100 font-mono block mb-0.5">AUX Channel mapping:</strong>
                        <span>Auxiliary radio channels mapped beyond original layout sticks (Roll, Pitch, Yaw, Throttle) linked directly to physical switches.</span>
                      </div>
                      <div>
                        <strong className="text-zinc-100 font-mono block mb-0.5">RC EXPO curve:</strong>
                        <span>Exponential smoothing parameter that reduces mid-stick resolution mapping while keeping full peak rotational acceleration on extreme stick deflections.</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-yellow-950/15 border border-yellow-900/40 rounded-2xl p-5 text-xs font-sans text-yellow-500/90 leading-relaxed">
                  <strong>IMPORTANT ADVISORY:</strong> Remember to always complete physical calibration checks before applying settings. Ensure matching sensor alignment boards inside your frame layout.
                </div>
              </div>

            </div>
          )}

          {/* TAB: DÜNYA ÇAPINDAKİ FPV YARIŞLARI */}
          {activeTab === "races" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 text-left font-sans">
              
              {/* Sol ve Orta Panel: Ligler ve Kurallar */}
              <div className="lg:col-span-2 space-y-6">
                
                {/* Küresel FPV Ligleri */}
                <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 md:p-8 relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-orange-600/5 to-transparent pointer-events-none" />
                  
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-xl bg-orange-600/10 border border-orange-500/20 flex items-center justify-center text-orange-500">
                      <Trophy size={20} />
                    </div>
                    <div>
                      <span className="text-[10px] font-mono font-bold text-orange-500 uppercase tracking-widest block">CHAMPIONSHIPS</span>
                      <h3 className="text-lg font-bold text-zinc-100">KÜRESEL FPV BİRİNCİLİKLERİ VE LİGLER</h3>
                    </div>
                  </div>

                  <div className="space-y-4 text-xs">
                    
                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900">
                      <div className="flex justify-between items-center mb-1.5">
                        <strong className="text-zinc-100 text-sm">MultiGP Drone Racing</strong>
                        <span className="text-emerald-400 font-mono text-[9px] border border-emerald-500/30 bg-emerald-950/20 px-1.5 py-0.5 rounded font-black">EN AKTİF</span>
                      </div>
                      <p className="text-zinc-400 leading-relaxed mb-2">
                        Dünyanın en büyük FPV topluluğu ve yarış ligidir. Yerel kulüpler standart MultiGP kapı ve bayrak setlerini kullanarak küresel sıralama yarışları düzenler. Her yıl düzenlenen MultiGP Championship, en hızlı pilotları bir araya getirerek taçlandırır.
                      </p>
                      <div className="text-[10px] text-zinc-500 font-mono flex gap-4">
                        <span>Format: Hız & Zamana Karşı</span>
                        <span>Sınıf: 5 inç 6S Açık Sınıf</span>
                      </div>
                    </div>

                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900">
                      <div className="flex justify-between items-center mb-1.5">
                        <strong className="text-zinc-100 text-sm">DRL (Drone Racing League)</strong>
                        <span className="text-cyan-400 font-mono text-[9px] border border-cyan-500/30 bg-cyan-950/20 px-1.5 py-0.5 rounded font-black">PROFESYONEL</span>
                      </div>
                      <p className="text-zinc-400 leading-relaxed mb-2">
                        Televizyon kanallarında ve büyük stadyumlarda neon LED ışıklarla kaplı dehlizlerde düzenlenen profesyonel yarış serisidir. Pilotlar ligin kendi tasarımı olan tek tip kurumsal ağır dronları (DRL Racer serisi) kullanarak eşit donanım şartlarında rekabet ederler.
                      </p>
                      <div className="text-[10px] text-zinc-500 font-mono flex gap-4">
                        <span>Format: Puanlı Eleme Turu</span>
                        <span>Sınıf: 7 inç Ağır LED Quad</span>
                      </div>
                    </div>

                    <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900">
                      <div className="flex justify-between items-center mb-1.5">
                        <strong className="text-zinc-100 text-sm">FAI World Drone Racing Championship</strong>
                        <span className="text-violet-400 font-mono text-[9px] border border-violet-500/30 bg-violet-950/20 px-1.5 py-0.5 rounded font-black">RESMİ OLİMPİK</span>
                      </div>
                      <p className="text-zinc-400 leading-relaxed mb-2">
                        Uluslararası Havacılık Federasyonu (FAI) tarafından resmi ülke federasyon takımlarının katılımıyla düzenlenen dünya şampiyonasıdır. Her sene farklı bir ülkede devasa milli sporcu organizasyonu şeklinde yürütülür.
                      </p>
                      <div className="text-[10px] text-zinc-500 font-mono flex gap-4">
                        <span>Format: Ülkeler Arası Turnuva</span>
                        <span>Sınıf: Standart FAI F9U</span>
                      </div>
                    </div>

                  </div>
                </div>

                {/* Yarış Kuralları */}
                <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 md:p-8">
                  <h4 className="text-xs text-orange-500 font-mono font-bold uppercase tracking-widest border-b border-zinc-900 pb-3 mb-4">
                    FPV YARIŞ STANDARTLARI VE KURAL KİTAPÇIĞI
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="p-4 bg-zinc-950/20 border border-zinc-900 rounded-xl">
                      <strong className="text-zinc-200 block mb-1">Frekans Paylaşımı ve VTX Gücü:</strong>
                      <span className="text-zinc-400 leading-relaxed">
                        Yarışlarda parazit gürültüsünü önlemek için VTX (Video Verici) gücü maksimum **25mW** ile sınırlandırılır. Pilotlar Raceband frekans kanal tablosundaki belirli interwallere (örneğin R1, R2, R4, R7) atanırlar. Sistemini açarken diğer pilotları kör etmemek hayati önemdedir.
                      </span>
                    </div>
                    <div className="p-4 bg-zinc-950/20 border border-zinc-900 rounded-xl">
                      <strong className="text-zinc-200 block mb-1">Zamanlama Transponder Sistemleri:</strong>
                      <span className="text-zinc-400 leading-relaxed">
                        Mil saniye hassasiyetinde tur zamanını ölçmek için drone gövdesine kızılötesi (IR) ışın yayınlayan küçük bir transponder çipi monte edilir. Kapı geçişlerinde yerleştirilen sensörler pilotların geçiş anını anında bilgisayara yazar.
                      </span>
                    </div>
                  </div>
                </div>

              </div>

              {/* Sağ Sütun: TEKNOFEST, Türkiye scene ve Ekipman ağırlıkları */}
              <div className="space-y-6 text-xs">
                
                {/* TEKNOFEST Türkiye Şampiyonası */}
                <div className="bg-[#120808]/40 border border-red-950 rounded-2xl p-6 relative">
                  <div className="absolute top-4 right-4 text-red-650">
                    <Award size={20} />
                  </div>
                  <h4 className="text-red-500 font-mono font-bold text-xs uppercase tracking-widest mb-3.5">
                    TÜRKİYE FPV ŞAMPİYONASI (TEKNOFEST)
                  </h4>
                  <p className="text-zinc-400 leading-relaxed mb-4">
                    Türkiye&apos;de FPV sporunun kalbi TEKNOFEST kapsamında düzenlenen Türkiye Drone Şampiyonası etaplarında atar. Sporcular Türkiye Hava Sporları Federasyonu (THSF) lisansıyla katılarak en zorlu parkurlarda milli takıma seçilmek için yarışırlar.
                  </p>
                  <ul className="space-y-2 text-zinc-450 font-mono text-[11px]">
                    <li className="flex gap-2"><span className="text-red-500">&gt;</span> Etaplar: İstanbul, Ankara, İzmir, Gaziantep</li>
                    <li className="flex gap-2"><span className="text-red-500">&gt;</span> Ödül Havuzu: Yüksek bütçeli teknoloji destekleri</li>
                    <li className="flex gap-2"><span className="text-red-500">&gt;</span> Klasman: Genel Klasman ve Gençler Kategorisi</li>
                  </ul>
                </div>

                {/* Yarış Ekipmanı Limitleri */}
                <div className="bg-[#0b0c0e]/95 border border-zinc-900 rounded-2xl p-6 font-mono">
                  <span className="text-[10px] text-zinc-500 font-black block uppercase tracking-wider mb-3">YARIŞ DRONU SINIRLAMALARI</span>
                  <div className="space-y-2.5">
                    <div className="flex justify-between border-b border-zinc-900 pb-1.5">
                      <span>Maksimum Ağırlık:</span>
                      <span className="text-yellow-500 font-bold">800g (Lipo Dahil)</span>
                    </div>
                    <div className="flex justify-between border-b border-zinc-900 pb-1.5">
                      <span>Pervane Çapı:</span>
                      <span className="text-zinc-300">Max 5.1 inç</span>
                    </div>
                    <div className="flex justify-between border-b border-zinc-900 pb-1.5">
                      <span>Hücre Sayısı:</span>
                      <span className="text-cyan-400 font-bold">4S - 6S LiPo</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Kamera Açısı:</span>
                      <span className="text-emerald-400">45° - 60° (Agresif Hız)</span>
                    </div>
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* TAB: FPV HABERLERİ */}
          {activeTab === "news" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left font-sans">
              
              {/* Haber 1 */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 relative flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-center border-b border-zinc-900 pb-3 mb-4">
                    <span className="text-[10px] font-mono text-cyan-400 font-black tracking-widest uppercase">GÜNCEL GELİŞMELER // INDUSTRY</span>
                    <span className="text-[10px] font-mono text-zinc-650">Mayıs 2026</span>
                  </div>
                  <h4 className="text-sm font-bold text-zinc-100 mb-2">DJI Dijital VTX Sistem Halefi O4 Hava Birimi Dedikoduları Sızdırıldı</h4>
                  <p className="text-zinc-400 text-xs leading-relaxed">
                    Sektör kaynaklarından gelen sızıntılara göre, DJI yeni nesil O4 Air Unit üzerinde saha testlerini tamamlamak üzere. 4K/120Fps video kaydının yanı sıra, iletim gücünün 15km ye kadar sıfır piksel kaybı ile 1080p/144hz dijital akış sağlayacağı belirtiliyor. Bu durum analog sistemlerin popülaritesini tamamen bitirebilir.
                  </p>
                </div>
                <div className="mt-5 pt-3 border-t border-zinc-900/60 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Kategori: Donanım Sızıntıları / DJI</span>
                </div>
              </div>

              {/* Haber 2 */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 relative flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-center border-b border-zinc-900 pb-3 mb-4">
                    <span className="text-[10px] font-mono text-orange-500 font-black tracking-widest uppercase">KABLOSUZ KONTROL // PROTOCOLS</span>
                    <span className="text-[10px] font-mono text-zinc-650">Nisan 2026</span>
                  </div>
                  <h4 className="text-sm font-bold text-zinc-100 mb-2">ExpressLRS v3.4 Sürümü 1000Hz Paket Hızıyla Çıktı</h4>
                  <p className="text-zinc-400 text-xs leading-relaxed">
                    Açık kaynak kodlu RC protokolu lideri olan ELRS, beklenen v3.4 ana güncellemesini yayınladı. Güncelleme, özellikle mikro kapalı alan yarışçıları ve akrobasi pilotları için donanımsal gecikmeyi 0.8ms seviyesine indirirken, paket kaybı koruma algoritmalarında devrimsel iyileştirmeler içeriyor.
                  </p>
                </div>
                <div className="mt-5 pt-3 border-t border-zinc-900/60 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                  <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Kategori: Yazılım Sürümleri / ELRS</span>
                </div>
              </div>

              {/* Haber 3 */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 relative flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-center border-b border-zinc-900 pb-3 mb-4">
                    <span className="text-[10px] font-mono text-rose-500 font-black tracking-widest uppercase">YÖNETMELİK HUKUKU // REGULATION</span>
                    <span className="text-[10px] font-mono text-zinc-650">Mart 2026</span>
                  </div>
                  <h4 className="text-sm font-bold text-zinc-100 mb-2">SHGM İHA-1 Kayıt ve Sınav Zorunluluk Sınırları Yeniden Düzenlendi</h4>
                  <p className="text-zinc-450 text-xs leading-relaxed">
                    Sivil Havacılık Genel Müdürlüğü, 500 gram altı hobi amaçlı kullanılan mikrodronlar ve cine-whooplar için tescil zorunluluğunu esneten yeni bülteni onayladı. Ancak 250 gram üzeri dronlar için şehir içi meskun mahal uçuş izni başvurularında artık &quot;Güvenli FPV Sertifikası&quot; aranacağı ilan edildi.
                  </p>
                </div>
                <div className="mt-5 pt-3 border-t border-zinc-900/60 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                  <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Kategori: Yasal Mevzuat / Türkiye</span>
                </div>
              </div>

              {/* Haber 4 */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 relative flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-center border-b border-zinc-900 pb-3 mb-4">
                    <span className="text-[10px] font-mono text-yellow-500 font-black tracking-widest uppercase">PİL DÜNYASI // BATTERY</span>
                    <span className="text-[10px] font-mono text-zinc-650">Şubat 2026</span>
                  </div>
                  <h4 className="text-sm font-bold text-zinc-100 mb-2">Graphene Sürüm Hücrelerde Ağırlık/Güç Oranında %15 Parlak Gelişme</h4>
                  <p className="text-[#9ea4b0] text-xs leading-relaxed">
                    Uluslararası batarya üreticilerinden bir konsorsiyum, lityum polimer hücrelerin iç direncini neredeyse yarıya indirecek yeni tek katman grafen sargı metodunu prototipledi. Bu gelişme, tam gaz verildiğinde meydana gelen can sıkıcı voltaj çöküşünü (Battery Sag) tamamen tarihe gömecek.
                  </p>
                </div>
                <div className="mt-5 pt-3 border-t border-zinc-900/60 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
                  <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Kategori: Kimya Teknolojileri / LiPo</span>
                </div>
              </div>

            </div>
          )}

          {/* TAB: YENİ ÇIKAN MODELLER */}
          {activeTab === "gear" && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 text-left font-sans">
              
              {/* Model 1 */}
              <div className="bg-[#0b0c0f] border border-zinc-900 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
                <div>
                  <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-orange-500/10 to-transparent pointer-events-none" />
                  <span className="text-[9px] font-mono font-black tracking-widest text-orange-500 bg-orange-950/20 border border-orange-900/40 px-2 py-0.5 rounded-xs uppercase">CINEMATIC WHOOP</span>
                  
                  <h4 className="text-md font-bold text-zinc-100 mt-3 mb-1.5">DJI Avata 2</h4>
                  <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                    Yeni başlayanlar ve yedek kameramanlar için biçilmiş kaftan olan hazır set (RTF) sinematik drone. O4 HD Dijital aktarım sistemi ve entegre tescilli çarpışma sensörleri ile ev içi, dar delikler ve hızlı kovalama aksiyonlarında tam koruma sağlar.
                  </p>
                </div>
                <div className="border-t border-zinc-900 pt-3 text-[10px] font-mono text-zinc-500 leading-normal space-y-1">
                  <div>• Kamera: 1/1.3 inç CMOS 4K/60fps HDR</div>
                  <div>• Sinyal: DJI O4 Link (24ms Latency)</div>
                  <div>• Ağırlık: 377 gram (Korumalı Tasarım)</div>
                </div>
              </div>

              {/* Model 2 */}
              <div className="bg-[#0b0c0f] border border-zinc-900 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
                <div>
                  <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-cyan-500/10 to-transparent pointer-events-none" />
                  <span className="text-[9px] font-mono font-black tracking-widest text-cyan-400 bg-cyan-950/20 border border-cyan-900/40 px-2 py-0.5 rounded-xs uppercase">MICRO FLYER</span>
                  
                  <h4 className="text-md font-bold text-zinc-100 mt-3 mb-1.5 font-sans">BetaFPV Air65 / Air75 Brushless</h4>
                  <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                    Ev içerisinde mobilyaların altından süzülmek veya arka bahçede dar manevralar yapmak için tasarlanmış, dünyanın en hafif brushless whoop drone serisidir. Yeni süper ince fırçasız motorları ve F4 1S AIO uçuş kartı ile milimetrik tepki üretir.
                  </p>
                </div>
                <div className="border-t border-zinc-900 pt-3 text-[10px] font-mono text-zinc-500 leading-normal space-y-1">
                  <div>• Motorlar: 0802SE 23000KV Brushless</div>
                  <div>• Batarya: 1S LiHV (Süper hafif BT2.0)</div>
                  <div>• Ağırlık: 17.5 gram (Pilsiz Ağırlık)</div>
                </div>
              </div>

              {/* Model 3 */}
              <div className="bg-[#0b0c0f] border border-zinc-900 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
                <div>
                  <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-purple-500/10 to-transparent pointer-events-none" />
                  <span className="text-[9px] font-mono font-black tracking-widest text-purple-400 bg-purple-950/20 border border-purple-900/40 px-2 py-0.5 rounded-xs uppercase">PRO FREESTYLE</span>
                  
                  <h4 className="text-md font-bold text-zinc-100 mt-3 mb-1.5 font-sans">AxisFlying Manta v2 5&quot;</h4>
                  <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                    Usta freestyle FPV pilotlarının favori yarış/akrobasi gövdesi. Ezilmeye ve kırılmaya dayanıklı kalın karbon fiber kolları, T-Motor F60 Pro motor yuvaları ve O3 Air Unit için özel izole edilmiş alüminyum kamera kafesi ile ekstrem dayanıklılık sunar.
                  </p>
                </div>
                <div className="border-t border-zinc-900 pt-3 text-[10px] font-mono text-zinc-500 leading-normal space-y-1">
                  <div>• Gövde Kolları: 5mm Kalın Japon Karbon</div>
                  <div>• Motor Tipi: 2207.5 Pro Serisi fırçasız</div>
                  <div>• Ağırlık: 380-420 gram (Bataryasız)</div>
                </div>
              </div>

            </div>
          )}

          {/* TAB: YAZILIM GÜNCELLEMELERİ */}
          {activeTab === "updates" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 text-left font-sans text-xs">
              
              {/* Betaflight Firmware */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 space-y-4">
                <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 bg-yellow-500 rounded-full animate-pulse" />
                    <strong className="text-base font-bold text-zinc-100 font-sans">Betaflight v4.5.1</strong>
                  </div>
                  <span className="font-mono text-yellow-500 font-extrabold text-[10px]">LATEST FIRMWARE</span>
                </div>
                <p className="text-zinc-400 leading-relaxed text-xs">
                  Dünyanın en yaygın açık kaynaklı uçuş yazılımı olan Betaflight, v4.5 ana sürümüyle jiroskop parazit gürültülerini filtrelemede devrim yarattı.
                </p>
                <div className="space-y-2 font-mono text-[10px] text-zinc-500 leading-normal pl-4 border-l border-zinc-800">
                  <div>• **RPM Filtreleme 4.0:** Motor gürültüsünü devire göre filtreleyip motor ısınmasını önler.</div>
                  <div>• **GPS Kurtarma 2.0 (RTH):** Sinyal kaybında quadcopter eve dönerken açıyı daha hassas korur.</div>
                  <div>• **Dinamik RTA filtre:** Çizgisel olmayan eksen sapmalarını anında çözer.</div>
                </div>
              </div>

              {/* ExpressLRS Firmware */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 space-y-4">
                <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 bg-cyan-400 rounded-full animate-pulse" />
                    <strong className="text-base font-bold text-zinc-100 font-sans">ExpressLRS v3.3.3</strong>
                  </div>
                  <span className="font-mono text-cyan-400 font-extrabold text-[10px]">RC LINK STACK</span>
                </div>
                <p className="text-zinc-400 leading-relaxed text-xs">
                  Ultra yüksek yenileme hızları sunan radyo protokol yazılımındaki bu kararlı sürüm, telemetri verilerinin aktarım hızını ikiye katladı.
                </p>
                <div className="space-y-2 font-mono text-[10px] text-zinc-500 leading-normal pl-4 border-l border-zinc-800">
                  <div>• **1000Hz Paket Oranı:** Pilot hareketlerini 1 milisaniyenin altında gecikmeyle gönderir.</div>
                  <div>• **FLRC Modülasyon Değişimi:** Mikrosaniyede yüksek paket bütünlüğü sağlar.</div>
                  <div>• **Wifi Güncelleme Arayüzü:** Kumanda ve alıcı doğrudan tarayıcı üzerinden flaşlanabilir.</div>
                </div>
              </div>

              {/* EdgeTX RC Kumanda OS */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 space-y-4">
                <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-pulse" />
                    <strong className="text-base font-bold text-zinc-100 font-sans">EdgeTX v2.10 &quot;Centurion&quot;</strong>
                  </div>
                  <span className="font-mono text-purple-400 font-extrabold text-[10px]">TRANSMITTER OS</span>
                </div>
                <p className="text-zinc-400 leading-relaxed text-xs">
                  Modüler dokunmatik kumanda işletim sistemi EdgeTX, Centurion sürümüyle ses kütüphanelerini ve telemetri ekranını yeniledi.
                </p>
                <div className="space-y-2 font-mono text-[10px] text-zinc-500 leading-normal pl-4 border-l border-zinc-800">
                  <div>• Dokunmatik ekran hassasiyeti ve renk skalası optimizasyonu.</div>
                  <div>• Seslendirme paketleri ve ses sentezleyici motor yenilikleri.</div>
                  <div>• ELRS entegre kumanda LUA betiklerinin arka planda hızlı derlenmesi.</div>
                </div>
              </div>

              {/* ESC AM32 & Bluejay Firmware */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 space-y-4">
                <div className="flex justify-between items-center border-b border-zinc-900 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse" />
                    <strong className="text-base font-bold text-zinc-100 font-sans">Bluejay / AM32 ESC Firmware</strong>
                  </div>
                  <span className="font-mono text-emerald-400 font-extrabold text-[10px]">MOTOR DRIVERS</span>
                </div>
                <p className="text-zinc-400 leading-relaxed text-xs">
                  Motor sürücülerinin (ESC) açık kaynak yazılımları olan Bluejay ve AM32, tescilli BLHeli_32 yazılım kalitesini ücretsiz sunuyor.
                </p>
                <div className="space-y-2 font-mono text-[10px] text-zinc-500 leading-normal pl-4 border-l border-zinc-800">
                  <div>• **Bidirectional DShot:** Motor dönme hızını anlık olarak uçuş kontrolcüsüne geri iletir.</div>
                  <div>• **96kHz PWM Modeli:** Fırçasız motor verimliliğini %10 artırır ve pili korur.</div>
                  <div>• **Melodi Düzenleyici:** Kumandayı açarken ESC&apos;nin ürettiği bekleme sesini özelleştirme.</div>
                </div>
              </div>

            </div>
          )}

          {/* TAB: FPV SİMÜLASYON YAZILIMLARI */}
          {activeTab === "simulators" && (
            <div className="space-y-8 text-left font-sans text-xs">
              
              {/* Giriş */}
              <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 md:p-8 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-orange-600/5 to-transparent pointer-events-none" />
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-orange-600/10 border border-orange-500/20 flex items-center justify-center text-orange-500">
                    <Gamepad size={20} />
                  </div>
                  <div>
                    <span className="text-[10px] font-mono font-bold text-orange-500 uppercase tracking-widest block font-black">FLIGHT SIMULATION</span>
                    <h3 className="text-lg font-bold text-zinc-100">KÜRESEL FPV FLIGHT SIMULATOR YAZILIMLARI</h3>
                  </div>
                </div>
                <p className="text-zinc-400 leading-relaxed text-xs max-w-3xl">
                  Gerçek uçuşlardan önce simülatörde yeterli idman yapmak FPV dünyasının yazılmamış ilk kuralıdır. Aşağıdaki karşılaştırma tablosu ve detaylar, uçuş tarzınıza (Yarışçı veya Freestyle) uygun simülasyon yazılımını belirlemenize yardımcı olacaktır.
                </p>
              </div>

              {/* Simülasyon Yazılımları Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                
                {/* Liftoff */}
                <div className="bg-[#0b0c0f] border border-zinc-900 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
                  <div>
                    <span className="text-[9px] font-mono font-black tracking-widest text-[#ea580c] bg-orange-950/20 border border-orange-900/40 px-2 py-0.5 rounded-xs uppercase">EN POPÜLER</span>
                    <h4 className="text-md font-bold text-zinc-100 mt-3 mb-1.5 font-sans">Liftoff: FPV Drone Racing</h4>
                    <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                      Sektörün en popüler simülatörüdür. Geniş uçuş atölyesi (workshop) sayesinde yüzlerce yedek parçayı bir araya getirerek kendi dronunuzu oluşturabilirsiniz. Topluluk tarafından yapılan harita sayısı sınırsızdır.
                    </p>
                  </div>
                  <div className="border-t border-zinc-900 pt-3 text-[10px] font-mono text-zinc-500 leading-normal space-y-1">
                    <div>• Fizik Kalitesi: Dengeli (Tavsiye Edilen)</div>
                    <div>• Grafik Kalitesi: Çok İyi (Unity Motoru)</div>
                    <div>• Platform: PC / Mac / Playstation</div>
                  </div>
                </div>

                {/* Velocidrone */}
                <div className="bg-[#0b0c0f] border border-zinc-900 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
                  <div>
                    <span className="text-[9px] font-mono font-black tracking-widest text-emerald-400 bg-emerald-950/20 border border-emerald-900/40 px-2 py-0.5 rounded-xs uppercase">YARIŞÇININ SEÇİMİ</span>
                    <h4 className="text-md font-bold text-zinc-100 mt-3 mb-1.5 font-sans">Velocidrone FPV</h4>
                    <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                      Profesyonel yarış pilotlarının tartışılamaz bir numaralı tercihidir. Fizik motoru, gerçek havacılık dinamiklerine inanılmaz derecede yakındır ve pil voltajı düşüşünü dahi gerçekçi şekilde simüle eder.
                    </p>
                  </div>
                  <div className="border-t border-zinc-900 pt-3 text-[10px] font-mono text-zinc-500 leading-normal space-y-1">
                    <div>• Fizik Kalitesi: Kusursuz (En Gerçekçi)</div>
                    <div>• Grafik Kalitesi: Orta Seviye</div>
                    <div>• Platform: PC / Mac / Linux</div>
                  </div>
                </div>

                {/* Uncrashed */}
                <div className="bg-[#0b0c0f] border border-zinc-900 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
                  <div>
                    <span className="text-[9px] font-mono font-black tracking-widest text-cyan-400 bg-cyan-950/20 border border-cyan-900/40 px-2 py-0.5 rounded-xs uppercase">MODERN AKSİYON</span>
                    <h4 className="text-md font-bold text-zinc-100 mt-3 mb-1.5 font-sans">Uncrashed FPV</h4>
                    <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                      Üstün grafik kalitesi ve harika serbest stil (freestyle) uçuş fizikleri sunar. Dağ zirvelerinden süzülürken veya hareketli trenleri kovalarken inanılmaz sinematik doyum sağlar.
                    </p>
                  </div>
                  <div className="border-t border-zinc-900 pt-3 text-[10px] font-mono text-zinc-500 leading-normal space-y-1">
                    <div>• Fizik Kalitesi: Çok İyi (Freestyle)</div>
                    <div>• Grafik Kalitesi: Kristal Netlikte (Unreal Engine)</div>
                    <div>• Platform: PC / Mac</div>
                  </div>
                </div>

                {/* TRYP FPV */}
                <div className="bg-[#0b0c0f] border border-zinc-900 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
                  <div>
                    <span className="text-[9px] font-mono font-black tracking-widest text-purple-400 bg-purple-950/20 border border-purple-900/40 px-2 py-0.5 rounded-xs uppercase">SİNEMATİK DEV HARİTA</span>
                    <h4 className="text-md font-bold text-zinc-100 mt-3 mb-1.5 font-sans">TRYP FPV Cinematic</h4>
                    <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                      Devasa büyüklükte (kilometre karelerce) fotorealistik doğal haritalara sahip simülatör. Uzak mesafe (long range) sinematik dağ süzülüşleri, kayakçı takipleri ve rüzgar direnci testleri için mükemmeldir.
                    </p>
                  </div>
                  <div className="border-t border-zinc-900 pt-3 text-[10px] font-mono text-zinc-500 leading-normal space-y-1">
                    <div>• Fizik Kalitesi: İyi Seviye</div>
                    <div>• Grafik Kalitesi: Üst Seviye (Next-Gen Unreal)</div>
                    <div>• Platform: PC / Mac / Linux</div>
                  </div>
                </div>

              </div>

              {/* Bilgi Kutusu */}
              <div className="p-4 bg-zinc-950 rounded-xl border border-zinc-900 text-xs text-zinc-400 leading-relaxed">
                <strong>💡 Altın Değerinde Tavsiye:</strong> Hangi simülatörü seçerseniz seçin, bilgisayarınızın klavyesi veya oyun kolu (Playstation/Xbox Controller) ile uçuş yapmaya çalışmayın. Gerçek radyo kumandanızı USB üzerinden bilgisayara seri port ile bağlayarak kumanda üzerindeki gerçek stick hassasiyet ayar değerleriyle idman yapmalısınız.
              </div>

            </div>
          )}

        </motion.div>
      </AnimatePresence>

    </div>
  );
}
