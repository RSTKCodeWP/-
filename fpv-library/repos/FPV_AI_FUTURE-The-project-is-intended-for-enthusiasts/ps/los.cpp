// los.cpp -- standalone driver for the LOS computer (core in los.h).
// Input (argv[1]): "f_px cx cy" then one "px py ego_dx ego_dy roll_inc dt" per frame.
// Output: "az el az_rate el_rate" per frame.  Verified by fpga/ps/test_los_c.py.

#include <cstdio>
#include "los.h"

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <seq>\n", argv[0]); return 2; }
    FILE* fp = fopen(argv[1], "r");
    if (!fp) { fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }

    double f, cx, cy;
    if (fscanf(fp, "%lf %lf %lf", &f, &cx, &cy) != 3) { fprintf(stderr, "bad header\n"); return 1; }

    los::State st; los::reset(st);
    double px, py, edx, edy, rr, dt;
    while (fscanf(fp, "%lf %lf %lf %lf %lf %lf", &px, &py, &edx, &edy, &rr, &dt) == 6) {
        double az, el, azr, elr;
        los::step(st, px, py, edx, edy, rr, dt, f, cx, cy, &az, &el, &azr, &elr);
        printf("%.15e %.15e %.15e %.15e\n", az, el, azr, elr);
    }
    fclose(fp);
    return 0;
}
