// hwkill.cpp -- independent hardware motor-power kill (Block-3 safety shell, M0): the spec the
// separate watchdog-MCU firmware implements.  Direct port of
// fpv.fpv_ai.betaflight_link.HardwareKill + effective_motor_power.
//
// DEFAULT-DENY: power is CUT unless a permit beacon is actively received within beacon_timeout_s;
// an operator kill latches CUT until reset; a non-finite clock cuts.  effective = FC-commands AND
// hw-kill-permits (a dominant AND-gate).  Verified vs Python by fpga/ps/test_armkill_c.py.
//
// Input (argv[1]): cfg(1) beacon_timeout ; then per frame "now event fc_commands"
//   (event 0 none / 1 permit_beacon / 2 operator_kill / 3 reset).
// Output per frame: "power effective".

#include <cstdio>
#include <cmath>

int main(int argc, char** argv){
    if(argc<2){ fprintf(stderr,"usage: %s <seq>\n",argv[0]); return 2; }
    FILE* fp=fopen(argv[1],"r"); if(!fp) return 1;
    double timeout;
    if(fscanf(fp,"%lf",&timeout)!=1){ fprintf(stderr,"bad cfg\n"); return 1; }

    double last=0.0; int has_last=0, latched=0;
    double now; int event, fc;
    while(fscanf(fp,"%lf %d %d",&now,&event,&fc)==3){
        if(event==1){ if(isfinite(now)){ last=now; has_last=1; } }   // permit_beacon
        else if(event==2){ latched=1; }                             // operator_kill (latched)
        else if(event==3){ latched=0; }                             // reset

        int power;
        if(latched) power=0;
        else power = (has_last && isfinite(now) && (now-last)>=0.0 && (now-last)<=timeout) ? 1 : 0;
        int effective = (fc && power) ? 1 : 0;
        printf("%d %d\n", power, effective);
    }
    fclose(fp);
    return 0;
}
