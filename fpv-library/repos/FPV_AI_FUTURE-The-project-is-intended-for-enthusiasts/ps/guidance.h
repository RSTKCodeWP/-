// guidance.h -- PS bearing-rate guidance core (namespaced, inline for multi-TU inclusion).
// Algorithm identical to fpv.guidance.bearing_rate.BearingRateGuidance.compute(); driver in guidance.cpp.
#pragma once
#include <cmath>

namespace guid {

struct Cfg {
    double N, Vc_sched, theta_max, abort_g_margin, cross_thr;
    int    vc_scaled;
    double tau_pursuit, tau_full_brn, pursuit_gain, man_prob_thr, max_a_cmd;
    int    acquire_ticks;
    double acquire_min_frac;
    int    warmup;
};

struct State { long tick; };

struct Out {                 // one guidance tick
    int    abort;            // 1 -> ROE abort (a_cmd suppressed)
    int    geom;             // 0 HEAD_ON, 1 QUARTERING, 2 HIGH_CROSSING
    int    envelope_ok;
    double a_az, a_el, req_g, ach_g, blend, n_eff;
};

inline void reset(State& s) { s.tick = 0; }
inline double a_max_mps2(const Cfg& c) { return 9.81 * tan(c.theta_max); }
inline double eff_cross_thr(const Cfg& c, double Vc) {
    return c.vc_scaled ? a_max_mps2(c) / (c.N * (Vc > 0.1 ? Vc : 0.1)) : c.cross_thr;
}
inline double blend_weight(double tc, double lo, double hi) {
    if (tc <= lo) return 0.0; if (tc >= hi) return 1.0; return (tc - lo) / (hi - lo);
}

inline Out step(State& st, const Cfg& c, double az, double el, double azr, double elr,
                double mode_man, int mdet, double tauc, int csign, double vco) {
    (void)mode_man; (void)mdet;                       // APN gated to 0 (range unobservable)
    st.tick += 1;
    Out o = {0, 0, 0, 0, 0, 0, 0, 0, 0};
    double gain = 1.0;
    if (c.acquire_ticks > 0 && st.tick <= c.acquire_ticks)
        gain = c.acquire_min_frac + (1.0 - c.acquire_min_frac) * ((double)st.tick / c.acquire_ticks);

    double Vc = (vco >= 0.0) ? vco : c.Vc_sched; if (Vc < 0.1) Vc = 0.1;
    double am = a_max_mps2(c), ag = tan(c.theta_max);
    o.ach_g = ag;

    if (!(isfinite(azr) && isfinite(elr))) { o.abort = 1; o.geom = 2; o.req_g = INFINITY; return o; }

    double mag = sqrt(azr*azr + elr*elr);
    double thr = eff_cross_thr(c, Vc);
    int high_rate = mag > thr, not_closing = (!(tauc >= 0.3)) || (csign <= 0), past_warmup = st.tick >= c.warmup;
    o.geom = (high_rate && not_closing && past_warmup) ? 2 : (high_rate ? 1 : 0);

    if (o.geom == 2) { o.abort = 1; o.req_g = mag * Vc * c.N / 9.81; return o; }

    double blend = blend_weight(tauc, c.tau_pursuit, c.tau_full_brn);
    double pgain = c.pursuit_gain > 0.0 ? c.pursuit_gain : Vc;
    double total_az = (1.0 - blend) * (pgain * az) + blend * (c.N * gain * Vc * azr);
    double total_el = (1.0 - blend) * (pgain * el) + blend * (c.N * gain * Vc * elr);
    double a_total = sqrt(total_az*total_az + total_el*total_el);
    o.req_g = a_total / 9.81;                          // reported on an envelope abort too
    o.envelope_ok = a_total <= am * c.abort_g_margin;
    if (!o.envelope_ok) { o.abort = 1; return o; }     // blend/n_eff/a_cmd stay 0 on abort (as Python)

    double maxc = c.max_a_cmd > 0.0 ? c.max_a_cmd : am;
    if (total_az > maxc) total_az = maxc; else if (total_az < -maxc) total_az = -maxc;
    if (total_el > maxc) total_el = maxc; else if (total_el < -maxc) total_el = -maxc;
    o.a_az = total_az; o.a_el = total_el;
    o.blend = blend;
    o.n_eff = blend * c.N * gain + (1.0 - blend) * 1.0;
    return o;
}

}  // namespace guid
