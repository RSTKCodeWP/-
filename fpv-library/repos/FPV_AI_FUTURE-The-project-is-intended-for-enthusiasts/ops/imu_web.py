"""Web IMU/gimbal calibration console — runs ON THE PI, open it in a browser on the same LAN.

  http://<pi-ip>:8091/

You can: move the 2 gimbal servos, watch the LIVE gyro/accel orientation change, see which RAW axis
responds, assign the IMU axes (which raw axis is body X/Y/Z and its sign) for gyro and accel, set the
servo ZERO, and SAVE — everything is written to gimbal_calib_fixed.json.

Run:  cd ~/03-fpv && PYTHONPATH=.:fpv python3 ops/imu_web.py
"""
from __future__ import annotations

import json
import math
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import sys
sys.path[:0] = ["/home/admin/03-fpv", ".", "fpv"]
from seeker_core.pi5_io import load_calibration, make_pca9685_servo_writer, make_i2c_imu_reader, Pi5Config

CALIB = "gimbal_calib_fixed.json"
PORT = 8091
_lock = threading.Lock()

_raw = make_i2c_imu_reader()
_write = make_pca9685_servo_writer()
_cfg = load_calibration(CALIB) if os.path.exists(CALIB) else Pi5Config()
_st = {"pan_us": 1500.0, "tilt_us": 1305.0}


def _json_calib():
    return json.load(open(CALIB)) if os.path.exists(CALIB) else {}


def _us_limits():
    d = _json_calib()
    return (tuple(d.get("pan_us_limit", (1392.0, 1560.0))), tuple(d.get("tilt_us_limit", (1050.0, 1560.0))))


def _clamp(v, lim):
    lo, hi = min(lim), max(lim)
    return lo if v < lo else hi if v > hi else v


def read_state():
    global _cfg
    with _lock:
        r = _raw()
    gL = [float(x) for x in r[0:3]]
    aL = [float(x) for x in r[3:6]]
    gs = math.degrees(_cfg.gyro_scale_rps)
    asc = _cfg.accel_scale_mps2
    gmap, gsign = list(_cfg.gyro_axis_map), list(_cfg.gyro_sign)
    amap, asign = list(_cfg.accel_axis_map), list(_cfg.accel_sign)
    gyro = [round(gsign[i] * gL[gmap[i]] * gs, 1) for i in range(3)]
    accel = [round(asign[i] * aL[amap[i]] * asc, 2) for i in range(3)]
    return dict(rawg=[round(x) for x in gL], rawa=[round(x) for x in aL],
                gyro=gyro, accel=accel, gmap=gmap, gsign=gsign, amap=amap, asign=asign,
                pan_us=round(_st["pan_us"]), tilt_us=round(_st["tilt_us"]))


def set_servo(pan_us=None, tilt_us=None):
    plim, tlim = _us_limits()
    if pan_us is not None:
        _st["pan_us"] = _clamp(float(pan_us), plim)
    if tilt_us is not None:
        _st["tilt_us"] = _clamp(float(tilt_us), tlim)
    with _lock:
        _write(_cfg.pan_channel, _st["pan_us"])
        _write(_cfg.tilt_channel, _st["tilt_us"])


def save_calib(body):
    global _cfg
    d = _json_calib()
    for k in ("gmap", "gsign", "amap", "asign"):
        if k in body:
            d[{"gmap": "gyro_axis_map", "gsign": "gyro_sign",
               "amap": "accel_axis_map", "asign": "accel_sign"}[k]] = body[k]
    if body.get("savezero"):
        d["pan_us_zero"] = _st["pan_us"]
        d["tilt_us_zero"] = _st["tilt_us"]
    d["gyro_scale_rps"] = math.radians(1.0) / 16.4
    d["accel_scale_mps2"] = 9.80665 / 2048.0
    json.dump(d, open(CALIB, "w"), indent=2)
    _cfg = load_calibration(CALIB)
    return d


PAGE = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Сокол · IMU / гимбал калибровка</title><style>
*{box-sizing:border-box} body{font-family:system-ui,Arial;margin:0;background:#0f1115;color:#e6e6e6}
h1{font-size:18px;margin:0 0 4px} h2{font-size:14px;color:#8fd;margin:18px 0 8px;font-weight:600}
.wrap{max-width:900px;margin:0 auto;padding:16px}
.row{display:flex;gap:16px;flex-wrap:wrap} .card{background:#171a21;border:1px solid #2a2f3a;border-radius:10px;padding:14px;flex:1;min-width:260px}
.bar{height:16px;background:#222833;border-radius:4px;position:relative;overflow:hidden;margin:3px 0}
.bar>i{position:absolute;top:0;bottom:0;left:50%;background:#3a8ee6;width:0}
.bar.hot>i{background:#39ff88} .lab{display:flex;justify-content:space-between;font-size:12px;color:#9aa}
select,button,input{background:#222833;color:#e6e6e6;border:1px solid #38414f;border-radius:6px;padding:5px 8px;font-size:13px}
button{cursor:pointer} button.pri{background:#1d5fa5;border-color:#2a78d6}
table{width:100%;border-collapse:collapse;font-size:13px} td{padding:3px 6px;border-bottom:1px solid #232833}
.mono{font-variant-numeric:tabular-nums;font-family:ui-monospace,monospace}
.mrow{display:grid;grid-template-columns:70px 1fr 60px;gap:8px;align-items:center;margin:6px 0}
.scene{perspective:520px;height:150px;display:flex;align-items:center;justify-content:center}
.cube{width:78px;height:78px;position:relative;transform-style:preserve-3d;transition:transform .06s linear}
.face{position:absolute;width:78px;height:78px;border:1px solid #4a7;display:flex;align-items:center;justify-content:center;font-size:13px;color:#cfe;background:rgba(40,90,70,.35)}
.fx{transform:rotateY(90deg) translateZ(39px)} .fxm{transform:rotateY(-90deg) translateZ(39px)}
.fy{transform:rotateX(90deg) translateZ(39px)} .fym{transform:rotateX(-90deg) translateZ(39px)}
.fz{transform:translateZ(39px)} .fzm{transform:rotateY(180deg) translateZ(39px)}
small{color:#889}
</style></head><body><div class=wrap>
<h1>Сокол · калибровка IMU + управление гимбалом</h1>
<small>двигай гимбал → смотри, какая ось гироскопа/акселерометра меняется → назначь оси → сохрани</small>

<div class=row>
 <div class=card>
  <h2>как стоит гироскоп (ориентация)</h2>
  <div class=scene><div class=cube id=cube>
   <div class="face fx">X+</div><div class="face fxm">X−</div>
   <div class="face fy">Y+</div><div class="face fym">Y−</div>
   <div class="face fz">Z+ (вверх/камера)</div><div class="face fzm">Z−</div>
  </div></div>
  <small id=grav>гравитация: …</small>
 </div>
 <div class=card>
  <h2>живые данные IMU</h2>
  <table><tr><td></td><td>сырое (LSB)</td><td>калибр.</td></tr>
   <tr><td>ось 0</td><td class=mono id=r0>–</td><td class=mono id=c0>–</td></tr>
   <tr><td>ось 1</td><td class=mono id=r1>–</td><td class=mono id=c1>–</td></tr>
   <tr><td>ось 2</td><td class=mono id=r2>–</td><td class=mono id=c2>–</td></tr></table>
  <small>сырой гироскоп (dps) — подсвечивается активная ось при вращении:</small>
  <div class=bar id=b0><i></i></div><div class=bar id=b1><i></i></div><div class=bar id=b2><i></i></div>
 </div>
</div>

<div class=card>
 <h2>управление гимбалом</h2>
 <div class=lab><span>пан (ch<span id=pch></span>) <span class=mono id=pv></span> µs</span></div>
 <input type=range id=pan style="width:100%">
 <div class=lab><span>тилт (ch<span id=tch></span>) <span class=mono id=tv></span> µs</span></div>
 <input type=range id=tilt style="width:100%">
 <div style="margin-top:8px"><button onclick=savezero()>зафиксировать текущее как НОЛЬ</button></div>
</div>

<div class=row>
 <div class=card>
  <h2>назначить оси ГИРОСКОПА</h2>
  <small>покрути гимбал вокруг оси → смотри какая сырая подсветилась → выбери её</small>
  <div id=gmaprows></div>
 </div>
 <div class=card>
  <h2>назначить оси АКСЕЛЕРОМЕТРА</h2>
  <small>наклони гимбал → гравитация должна лечь на Z+ (вверх)</small>
  <div id=amaprows></div>
 </div>
</div>
<div style="margin:14px 0 40px"><button class=pri onclick=save()>СОХРАНИТЬ калибровку</button> <span id=msg></span></div>

<script>
const $=id=>document.getElementById(id);
let cur=null;
function mrow(kind,axis,map,sign){
 return `<div class=mrow><b>${axis}</b>
  <select id=${kind}m${axis}><option value=0>сырая ось 0</option><option value=1>сырая ось 1</option><option value=2>сырая ось 2</option></select>
  <select id=${kind}s${axis}><option value=1>+</option><option value=-1>−</option></select></div>`;}
$('gmaprows').innerHTML=['X','Y','Z'].map(a=>mrow('g',a)).join('');
$('amaprows').innerHTML=['X','Y','Z'].map(a=>mrow('a',a)).join('');
function fillsel(kind,map,sign){['X','Y','Z'].forEach((a,i)=>{$(kind+'m'+a).value=map[i];$(kind+'s'+a).value=sign[i];});}
async function poll(){
 try{const d=await (await fetch('/imu')).json();cur=d;
  for(let i=0;i<3;i++){$('r'+i).textContent=d.rawg[i]+' / '+d.rawa[i];$('c'+i).textContent=d.gyro[i]+'° '+d.accel[i];}
  const mx=Math.max(...d.rawg.map(Math.abs),1);
  for(let i=0;i<3;i++){const w=Math.min(50,Math.abs(d.rawg[i])/mx*50);const el=$('b'+i);const bar=el.querySelector('i');
   bar.style.width=w+'%';bar.style.left=d.rawg[i]<0?(50-w)+'%':'50%';el.className='bar'+(Math.abs(d.rawg[i])==mx&&mx>400?' hot':'');}
  // cube tilt from calibrated accel (gravity)
  const ax=d.accel[0],ay=d.accel[1],az=d.accel[2];
  const roll=Math.atan2(ay,az)*57.3, pitch=Math.atan2(-ax,Math.hypot(ay,az))*57.3;
  $('cube').style.transform=`rotateX(${(-pitch).toFixed(1)}deg) rotateY(${(roll).toFixed(1)}deg)`;
  $('grav').textContent=`гравитация: X${ax} Y${ay} Z${az} м/с² (должна лечь на Z+ ≈ +9.8)`;
  if(!$('pan').dataset.init){$('pan').dataset.init=1;
   $('pan').min=1392;$('pan').max=1560;$('pan').value=d.pan_us;$('tilt').min=1050;$('tilt').max=1560;$('tilt').value=d.tilt_us;
   $('pch').textContent=d.gmap?'15':'15';$('tch').textContent='14';fillsel('g',d.gmap,d.gsign);fillsel('a',d.amap,d.asign);}
  $('pv').textContent=d.pan_us;$('tv').textContent=d.tilt_us;
 }catch(e){}
}
setInterval(poll,120);poll();
async function sendServo(){await fetch('/servo?pan='+$('pan').value+'&tilt='+$('tilt').value,{method:'POST'});$('pv').textContent=$('pan').value;$('tv').textContent=$('tilt').value;}
$('pan').addEventListener('input',sendServo);$('tilt').addEventListener('input',sendServo);
function collect(){const g=a=>[+$('gmX').value,+$('gmY').value,+$('gmZ').value],s=a=>[+$('gsX').value,+$('gsY').value,+$('gsZ').value];
 return {gmap:['X','Y','Z'].map(a=>+$('gm'+a).value),gsign:['X','Y','Z'].map(a=>+$('gs'+a).value),
         amap:['X','Y','Z'].map(a=>+$('am'+a).value),asign:['X','Y','Z'].map(a=>+$('as'+a).value)};}
async function save(){const b=collect();const r=await fetch('/calib',{method:'POST',body:JSON.stringify(b)});const d=await r.json();$('msg').textContent='сохранено ✓';setTimeout(()=>$('msg').textContent='',2500);}
async function savezero(){await fetch('/calib',{method:'POST',body:JSON.stringify({savezero:true})});$('msg').textContent='ноль зафиксирован ✓';setTimeout(()=>$('msg').textContent='',2500);}
</script></div></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif p.path == "/imu":
            self._send(200, json.dumps(read_state()).encode())
        else:
            self._send(404, b"{}")

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/servo":
            q = parse_qs(p.query)
            set_servo(q.get("pan", [None])[0], q.get("tilt", [None])[0])
            self._send(200, b'{"ok":true}')
        elif p.path == "/calib":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            save_calib(body)
            self._send(200, json.dumps(read_state()).encode())
        else:
            self._send(404, b"{}")


if __name__ == "__main__":
    import socket
    ip = socket.gethostbyname(socket.gethostname())
    set_servo(_st["pan_us"], _st["tilt_us"])
    print("IMU/gimbal web console:  http://%s:%d/   (Ctrl-C to stop)" % (ip, PORT))
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
