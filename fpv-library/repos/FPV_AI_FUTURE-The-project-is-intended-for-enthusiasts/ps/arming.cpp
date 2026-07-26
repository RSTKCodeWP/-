// arming.cpp -- PS-side arming / throttle-authority FSM (Block-3 safety core, M0 safety shell).
//
// Direct port of fpv.fpv_ai.betaflight_link.arming.ArmingStateMachine.  Sequence
// SAFE -> PREARM -> ARMED_IDLE -> STABILIZE -> THROTTLE_RAMP -> AI_ACTIVE, arming ONLY on a
// COMMITTED authorization (verifier + keypress-in-window + unexpired + non-synthetic-for-live);
// kill is dominant and sticky; throttle idles until the smooth ramp; a non-finite clock fails safe.
// Verified vs the Python FSM by fpga/ps/test_armkill_c.py.
//
// Input (argv[1]):
//   cfg(9): idle neutral hover arm_aux disarm_aux armed_idle_dwell stabilize_dwell ramp allow_synth
//   auth(6): verifier keypress_recorded keypress_ts issued expires synthetic
//   then per frame: now has_cmd roll pitch yaw throttle event  (event 0 none/1 kill/2 reset/3 reauthorize)
// Output per frame: "state armed roll pitch yaw throttle aux1 aux2 aux3 aux4"  (state 0..6).

#include <cstdio>
#include <cmath>

enum { SAFE=0, PREARM=1, ARMED_IDLE=2, STABILIZE=3, THROTTLE_RAMP=4, AI_ACTIVE=5, KILLED=6 };
static int armed_state(int s) { return s==ARMED_IDLE||s==STABILIZE||s==THROTTLE_RAMP||s==AI_ACTIVE; }

static double py_round(double x){ double r=floor(x),d=x-r; if(d>0.5)r+=1; else if(d==0.5){ if(fmod(r,2.0)!=0.0)r+=1;} return r; }
static int clamp_us(int v){ return v<1000?1000:(v>2000?2000:v); }
static int sym_us(double v){ if(!isfinite(v))v=0; return clamp_us((int)py_round(1500.0+v*500.0)); }
static int thr_us(double v){ if(!isfinite(v))v=0; return clamp_us((int)py_round(1000.0+v*1000.0)); }

struct Cfg { double idle,neutral,hover,arm_aux,disarm_aux,ai_dwell,stab_dwell,ramp; int allow_synth; };
struct Auth { int verifier,keypress; double keypress_ts,issued,expires; int synthetic; int valid; };

static int auth_authorized(const Auth& a, double now, int allow_synth){
    if(!isfinite(now) || !isfinite(a.expires)) return 0;
    if(!a.verifier) return 0;
    if(now >= a.expires) return 0;
    if(a.synthetic && !allow_synth) return 0;
    return 1;
}
static int auth_committed(const Auth& a, double now, int allow_synth){
    if(!auth_authorized(a,now,allow_synth)) return 0;
    if(!a.keypress) return 0;
    if(!(isfinite(a.issued) && isfinite(a.keypress_ts))) return 0;
    if(!(a.issued <= a.keypress_ts && a.keypress_ts <= a.expires)) return 0;
    return 1;
}

struct Fsm { int state; Auth auth; int killed; double t_enter; };

static void emit(const Cfg& c, int state, int armed, int roll,int pitch,int yaw,int thr){
    printf("%d %d %d %d %d %d %d %d %d %d\n", state, armed, roll,pitch,yaw,thr,
           (int)(armed?c.arm_aux:c.disarm_aux), 1000,1000,1000);
}
static void disarmed(const Cfg& c,int st){ emit(c,st,0,(int)c.neutral,(int)c.neutral,(int)c.neutral,(int)c.idle); }
static void armed_neutral(const Cfg& c,int st,int thr){ emit(c,st,1,(int)c.neutral,(int)c.neutral,(int)c.neutral,thr); }

int main(int argc, char** argv){
    if(argc<2){ fprintf(stderr,"usage: %s <seq>\n",argv[0]); return 2; }
    FILE* fp=fopen(argv[1],"r"); if(!fp) return 1;
    Cfg c;
    if(fscanf(fp,"%lf %lf %lf %lf %lf %lf %lf %lf %d",&c.idle,&c.neutral,&c.hover,&c.arm_aux,&c.disarm_aux,&c.ai_dwell,&c.stab_dwell,&c.ramp,&c.allow_synth)!=9){fprintf(stderr,"bad cfg\n");return 1;}
    Auth a0;
    if(fscanf(fp,"%d %d %lf %lf %lf %d",&a0.verifier,&a0.keypress,&a0.keypress_ts,&a0.issued,&a0.expires,&a0.synthetic)!=6){fprintf(stderr,"bad auth\n");return 1;}
    a0.valid=1;

    Fsm f; f.state=SAFE; f.auth=a0; f.auth.valid=1; f.killed=0; f.t_enter=0.0;   // authorize() at start

    double now,roll,pitch,yaw,thr; int has_cmd,event;
    while(fscanf(fp,"%lf %d %lf %lf %lf %lf %d",&now,&has_cmd,&roll,&pitch,&yaw,&thr,&event)==7){
        // external events
        if(event==1){ f.killed=1; }                                   // kill
        else if(event==2){ f.killed=0; f.auth.valid=0; f.state=SAFE; f.t_enter=0.0; }  // reset
        else if(event==3){ if(!f.killed){ f.auth=a0; f.auth.valid=1; } }               // reauthorize

        int authd = f.auth.valid && auth_authorized(f.auth, now, c.allow_synth);
        int commd = f.auth.valid && auth_committed(f.auth, now, c.allow_synth);

        // (0) non-finite clock -> sticky KILLED
        if(!isfinite(now)){ f.killed=1; f.state=KILLED; disarmed(c,KILLED); continue; }
        // (1) kill dominates
        if(f.killed){ if(f.state!=KILLED){f.state=KILLED; f.t_enter=now;} disarmed(c,KILLED); continue; }
        // (2) armed + not authorized -> abort
        if(armed_state(f.state) && !authd){ f.killed=1; f.state=KILLED; f.t_enter=now; disarmed(c,KILLED); continue; }

        if(f.state==SAFE){
            if(authd){ f.state=PREARM; f.t_enter=now; disarmed(c,PREARM); } else disarmed(c,SAFE);
        } else if(f.state==PREARM){
            if(!authd){ f.state=SAFE; f.t_enter=now; disarmed(c,SAFE); }
            else if(commd){ f.state=ARMED_IDLE; f.t_enter=now; armed_neutral(c,ARMED_IDLE,(int)c.idle); }
            else disarmed(c,PREARM);
        } else if(f.state==ARMED_IDLE){
            if((now-f.t_enter)>=c.ai_dwell){ f.state=STABILIZE; f.t_enter=now; armed_neutral(c,STABILIZE,(int)c.idle); }
            else armed_neutral(c,ARMED_IDLE,(int)c.idle);
        } else if(f.state==STABILIZE){
            if((now-f.t_enter)>=c.stab_dwell){ f.state=THROTTLE_RAMP; f.t_enter=now; armed_neutral(c,THROTTLE_RAMP,(int)c.idle); }
            else armed_neutral(c,STABILIZE,(int)c.idle);
        } else if(f.state==THROTTLE_RAMP){
            double el=now-f.t_enter; if(el<0)el=0; double frac=el/c.ramp; if(frac>1)frac=1;
            int t=(int)py_round(c.idle+frac*(c.hover-c.idle));
            if(frac>=1.0){ f.state=AI_ACTIVE; f.t_enter=now; armed_neutral(c,AI_ACTIVE,(int)c.hover); }
            else armed_neutral(c,THROTTLE_RAMP,t);
        } else if(f.state==AI_ACTIVE){
            if(!has_cmd) armed_neutral(c,AI_ACTIVE,(int)c.hover);
            else emit(c,AI_ACTIVE,1, sym_us(roll),sym_us(pitch),sym_us(yaw),thr_us(thr));
        } else disarmed(c,f.state);
    }
    fclose(fp);
    return 0;
}
