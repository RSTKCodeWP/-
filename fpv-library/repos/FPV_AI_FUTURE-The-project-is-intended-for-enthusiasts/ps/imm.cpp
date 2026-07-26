// imm.cpp -- standalone driver for the IMM filter (core in imm.h).
// Input (argv[1]): a 15-value config line, then one "az el az_rate el_rate ego_quality dt" per frame.
// Output per frame: "az el az_rate el_rate p_cv p_man nis lock_quality nis_true".
// Verified by fpga/ps/test_imm_c.py.

#include <cstdio>
#include "imm.h"

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <seq>\n", argv[0]); return 2; }
    FILE* fp = fopen(argv[1], "r");
    if (!fp) return 1;
    imm::Cfg c;
    if (fscanf(fp, "%lf %lf %lf %lf %lf %lf %lf %lf %lf %d %lf %lf %lf %lf %d",
               &c.sig_az,&c.sig_el,&c.sig_azr,&c.sig_elr,&c.q_cv,&c.q_man,&c.trans_stay,
               &c.ego_gate,&c.ego_damp,&c.n_sustain,&c.init_p_cv,&c.ego_q_infl,&c.nis_chi2,
               &c.nis_gate_chi2,&c.nis_sustain) != 15) { fprintf(stderr,"bad cfg\n"); return 1; }

    imm::State f; imm::reset(f, c);
    double az, el, azr, elr, eq, dt;
    while (fscanf(fp, "%lf %lf %lf %lf %lf %lf", &az,&el,&azr,&elr,&eq,&dt) == 6) {
        imm::V4 z = { az, el, azr, elr };
        double o[9];
        imm::step(f, c, z, eq, dt, o);
        printf("%.15e %.15e %.15e %.15e %.15e %.15e %.15e %.15e %.15e\n",
               o[0],o[1],o[2],o[3],o[4],o[5],o[6],o[7],o[8]);
    }
    fclose(fp);
    return 0;
}
