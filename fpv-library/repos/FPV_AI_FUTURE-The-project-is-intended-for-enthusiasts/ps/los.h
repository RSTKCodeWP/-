// los.h -- PS LOS computer core (namespaced so it composes into the seeker back-end).
// Algorithm identical to fpv.seeker.los.LOSComputer; see los.cpp for the standalone driver.
#pragma once
#include <cmath>

namespace los {

struct State {
    double cum_ego_x, cum_ego_y, cum_roll;
    double prev_wx, prev_wy;
    int    have_prev;
};

inline void reset(State& s) {
    s.cum_ego_x = s.cum_ego_y = s.cum_roll = 0.0;
    s.prev_wx = s.prev_wy = 0.0;
    s.have_prev = 0;
}

// centroid (px,py) + per-frame ego (shift dx/dy, roll increment) -> az/el bearing + LOS rate.
inline void step(State& st, double px, double py, double ego_dx, double ego_dy, double roll_inc,
                 double dt, double f, double cx, double cy,
                 double* az, double* el, double* azr, double* elr) {
    if (dt <= 0.0) dt = 1e-3;
    st.cum_ego_x += ego_dx;
    st.cum_ego_y += ego_dy;
    st.cum_roll  += roll_inc;

    double c = cos(st.cum_roll), s = sin(st.cum_roll);
    double dxt = (px - cx) - st.cum_ego_x;
    double dyt = (py - cy) - st.cum_ego_y;
    double wx = cx + (dxt * c - dyt * s);
    double wy = cy + (dxt * s + dyt * c);

    *az = atan2(wx - cx, f);
    *el = atan2(-(wy - cy), f);
    if (st.have_prev) {
        double vtx = (wx - st.prev_wx) / dt, vty = (wy - st.prev_wy) / dt;
        double dxw = wx - cx, dyw = wy - cy;
        *azr =  vtx * f / (f * f + dxw * dxw);
        *elr = -vty * f / (f * f + dyw * dyw);
    } else { *azr = 0.0; *elr = 0.0; }
    st.prev_wx = wx; st.prev_wy = wy; st.have_prev = 1;
}

}  // namespace los
