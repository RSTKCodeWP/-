use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::f64::consts::PI;
use crate::math::{Quat, Vec3};
use crate::physics::physics_geometry;
use crate::spec::FrameGeomSpec;
use crate::tables::frame_controls;
use crate::types::EscLayout;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PartKind { Box, Tube, Disc, Blade, Standoff, Vane }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PartRole { Arm, Plate, MotorBell, MotorStator, Prop, Esc, Stack, Servo, Vane, Boom, Battery, Gps, Antenna }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MaterialHint { Carbon, Aluminum, PlasticDark, Metal, PropTranslucent, Pcb, Heatshrink, Heatsink }

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(tag = "shape", rename_all = "snake_case")]
pub enum PartDims {
    Box { l: f64, w: f64, h: f64 },
    Tube { r: f64, h: f64 },
    Disc { r: f64, thick: f64 },
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Spin { pub axis: Vec3, pub dir: f64 }

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Part {
    pub kind: PartKind,
    pub role: PartRole,
    pub dims: PartDims,
    pub position: Vec3,
    pub rotation: Quat,
    pub material_hint: MaterialHint,
    pub spin: Option<Spin>,
    /// Parts that turn as one rotor assembly (a motor's blades + blur disc)
    /// share a `group` id (the motor index). The renderer parents each group
    /// under a single spinning pivot so the blades and disc rotate together.
    /// `None` for static parts.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group: Option<u32>,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Aabb { pub min: Vec3, pub max: Vec3 }

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FrameBlueprint { pub parts: Vec<Part>, pub bounds: Aabb }

pub fn build_blueprint(spec: &FrameGeomSpec) -> FrameBlueprint {
    let g = physics_geometry(spec);
    let mut parts: Vec<Part> = Vec::new();
    // Motor size follows the spec, but is floored to a fraction of arm span so a
    // large frame doesn't wear pinhead motors when the size-class default is
    // small (same span-proportional rule as the arms below). Height is also
    // floored relative to the radius so motors read as chunky cans, not flat
    // pancakes (a real motor is roughly as tall as its radius).
    let stator_r = (spec.motor_stator.dia_mm / 2.0).max(spec.arm_len_mm * 0.05) / 1000.0;
    let stator_h = (spec.motor_stator.height_mm / 1000.0).max(stator_r * 1.15);
    // Cap the DRAWN prop radius so props on adjacent arms don't visibly overlap.
    // Coax motors share an arm (same xy, distance ~0) and are excluded; only
    // distinct arm positions constrain it. Physics is untouched - it reads disc
    // area separately, so this is a purely visual clamp.
    let min_arm_gap = {
        let mut m = f64::MAX;
        for a in 0..g.motors.len() {
            for b in (a + 1)..g.motors.len() {
                let dx = g.motors[a].position.x - g.motors[b].position.x;
                let dy = g.motors[a].position.y - g.motors[b].position.y;
                let d = (dx * dx + dy * dy).sqrt();
                if d > 1e-3 {
                    m = m.min(d);
                }
            }
        }
        m
    };
    let prop_r = {
        let want = spec.prop.radius_mm / 1000.0;
        if min_arm_gap.is_finite() { want.min(min_arm_gap * 0.48) } else { want }
    };
    // Arm cross-section scales with arm span: a longer arm carries a bigger
    // motor and must be structurally thicker, so its width/height track the arm
    // length (~4% wide, ~2.2% thick). The size-class default acts as a floor so
    // small frames don't go below a sensible minimum. This keeps arms visually
    // proportional at every scale instead of rendering wire-thin on large frames.
    let arm_w = (spec.arm_len_mm * 0.04).max(spec.arm_width_mm) / 1000.0;
    let arm_t = (spec.arm_len_mm * 0.022).max(spec.arm_thick_mm) / 1000.0;
    // Round tube radius for the arms (and legs). A round tube reads far heftier
    // than a thin flat box of the same width - the difference between a carbon
    // boom and a toothpick.
    let arm_r = arm_w * 0.6;
    let arm_len_m = spec.arm_len_mm / 1000.0;

    // Central body: a real hull with volume (battery box + electronics stack),
    // sized to the span, not a flat 2 mm plate. Height gives the frame heft so it
    // reads as a body rather than a sheet.
    let body_l = arm_len_m * 0.52;
    let body_w = arm_len_m * 0.46;
    let body_h = (arm_len_m * 0.16).max(spec.plate.thick_mm / 1000.0);
    parts.push(Part {
        kind: PartKind::Box, role: PartRole::Plate,
        dims: PartDims::Box { l: body_l, w: body_w, h: body_h },
        position: Vec3::new(0.0, 0.0, 0.0), rotation: Quat::identity(),
        material_hint: MaterialHint::Carbon, spin: None, group: None,
    });

    // A real motor reads as two stacked cans: a matte stator (the wound base)
    // and a brighter bell (the rotating outer case) on top. Split the configured
    // motor height across the two so overall stack height stays faithful.
    let hs = stator_h * 0.5;
    let hb = stator_h * 0.5;

    let blades = (spec.prop.blades as usize).max(2);
    let blade_len = prop_r * 0.9;
    let chord = (prop_r * 0.11).max(0.008);
    // Blades carry real thickness (scaled to prop size) so they read as props
    // from the side instead of paper-thin plates.
    let blade_thick = (prop_r * 0.02).max(0.003);
    // Blade pitch angle taken at 0.7 R from the prop's geometric pitch. A pitch
    // of 0 (unknown) falls back to a shallow cosmetic tilt so blades never look
    // dead flat.
    let pitch_m = spec.prop.pitch_in * 0.0254;
    let pitch_angle = if pitch_m > 0.0 {
        (pitch_m / (2.0 * PI * 0.7 * prop_r.max(1e-3))).atan()
    } else {
        0.20
    };

    // Group motors by arm angle so coax classes (OctaQuad, Y6, CoaxCopter) render
    // ONE arm carrying stacked top+bottom rotors, instead of overlapping duplicate
    // arms. Non-coax classes have one motor per angle -> one arm each.
    let mut arm_groups: BTreeMap<i64, Vec<usize>> = BTreeMap::new();
    for (i, m) in g.motors.iter().enumerate() {
        let key = (m.position.y.atan2(m.position.x).to_degrees().round() as i64).rem_euclid(360);
        arm_groups.entry(key).or_default().push(i);
    }

    let rotor = RotorDims { stator_r, stator_h, hs, hb, prop_r, blades, blade_len, chord, blade_thick, pitch_angle, arm_r };
    let mut gi: u32 = 0;
    for idxs in arm_groups.values() {
        let m0 = &g.motors[idxs[0]];
        let len = (m0.position.x.powi(2) + m0.position.y.powi(2)).sqrt();
        parts.push(Part {
            kind: PartKind::Tube, role: PartRole::Arm,
            dims: PartDims::Tube { r: arm_r, h: len },
            position: Vec3::new(m0.position.x * 0.5, m0.position.y * 0.5, 0.0),
            rotation: quat_z_to_dir(Vec3::new(m0.position.x, m0.position.y, 0.0)),
            material_hint: MaterialHint::Carbon, spin: None, group: None,
        });

        let is_coax = idxs.len() > 1;
        for &i in idxs {
            let m = &g.motors[i];
            // Coax: the lower (negative-z) motor hangs inverted UNDER the arm,
            // prop below. Everything else mounts on top, prop above.
            let vd = if is_coax && m.position.z < -1e-9 { -1.0 } else { 1.0 };
            push_rotor(&mut parts, gi, m.position.x, m.position.y, vd, m.spin_dir, &rotor);
            gi += 1;
        }
    }

    // ESC(s). Real builds do NOT strap ESCs to the middle of the arms: a small
    // craft carries a 4-in-1 in the body stack; a large craft carries individual
    // finned-alloy ESC bricks mounted in/on the body, clustered around it. Both
    // read from the body, leaving the arms clean carbon tubes.
    match spec.esc_layout {
        EscLayout::Stack4in1 => {
            parts.push(Part {
                kind: PartKind::Box, role: PartRole::Esc,
                dims: PartDims::Box { l: body_l * 0.7, w: body_w * 0.7, h: (arm_r * 0.6).max(0.004) },
                position: Vec3::new(0.0, 0.0, body_h * 0.5 + arm_r * 0.35), rotation: Quat::identity(),
                material_hint: MaterialHint::Heatshrink, spin: None, group: None,
            });
        }
        EscLayout::ArmMounted => {
            // One finned-alloy ESC per motor, in a ring on top of the body.
            let n = spec.motor_count.max(1);
            let ring_r = body_l.min(body_w) * 0.5 * 0.82;
            let esc_l = ring_r * 0.55; // radial
            let esc_w = ring_r * 0.4; // tangential
            let esc_h = (arm_r * 1.6).max(0.005);
            let esc_z = body_h * 0.5 + esc_h * 0.5;
            for k in 0..n {
                let ang = (k as f64) * (2.0 * PI / n as f64) + PI / n as f64;
                parts.push(Part {
                    kind: PartKind::Box, role: PartRole::Esc,
                    dims: PartDims::Box { l: esc_l, w: esc_w, h: esc_h },
                    position: Vec3::new(ring_r * ang.cos(), ring_r * ang.sin(), esc_z),
                    rotation: quat_yaw(ang), material_hint: MaterialHint::Heatsink, spin: None, group: None,
                });
            }
        }
    }

    // Avionics on top of the body: a battery pack, a GPS module on a mast (kept
    // clear of interference), and a couple of antennas. Present on every frame -
    // these are what make it read as a real aircraft instead of a bare airframe.
    let body_top = body_h * 0.5;
    // Battery pack (heatshrink-wrapped) centred on the body top.
    let batt_h = body_h * 0.75;
    parts.push(Part {
        kind: PartKind::Box, role: PartRole::Battery,
        dims: PartDims::Box { l: body_l * 0.6, w: body_w * 0.5, h: batt_h },
        position: Vec3::new(0.0, 0.0, body_top + batt_h * 0.5), rotation: Quat::identity(),
        material_hint: MaterialHint::Heatshrink, spin: None, group: None,
    });
    // GPS mast at the rear of the body, with the puck on top. Sized off the
    // MOTOR (a real GPS puck is roughly motor-sized on a short thin mast), not
    // the body - so it never dwarfs the frame on smaller builds.
    let mast_r = (stator_r * 0.2).max(0.0025);
    let mast_h = (stator_r * 3.0).max(0.05);
    let mast_x = -body_l * 0.3;
    parts.push(Part {
        kind: PartKind::Tube, role: PartRole::Gps,
        dims: PartDims::Tube { r: mast_r, h: mast_h },
        position: Vec3::new(mast_x, 0.0, body_top + mast_h * 0.5), rotation: Quat::identity(),
        material_hint: MaterialHint::PlasticDark, spin: None, group: None,
    });
    let puck_r = (stator_r * 0.8).max(0.012);
    let puck_h = puck_r * 0.35;
    parts.push(Part {
        kind: PartKind::Disc, role: PartRole::Gps,
        dims: PartDims::Disc { r: puck_r, thick: puck_h },
        position: Vec3::new(mast_x, 0.0, body_top + mast_h + puck_h * 0.5), rotation: Quat::identity(),
        material_hint: MaterialHint::Aluminum, spin: None, group: None,
    });
    // Two antennas angling up-and-out from the rear corners (thin rods).
    let ant_r = (stator_r * 0.08).max(0.0015);
    let ant_h = (stator_r * 3.5).max(0.04);
    for side in [-1.0_f64, 1.0] {
        let base = Vec3::new(-body_l * 0.4, side * body_w * 0.4, body_top);
        // Aim the antenna up and outward (in +Z with a lateral lean).
        let dir = Vec3::new(-0.25, side * 0.4, 1.0);
        let n = dir.norm();
        let d = dir.scale(1.0 / n);
        parts.push(Part {
            kind: PartKind::Tube, role: PartRole::Antenna,
            dims: PartDims::Tube { r: ant_r, h: ant_h },
            position: Vec3::new(base.x + d.x * ant_h * 0.5, base.y + d.y * ant_h * 0.5, base.z + d.z * ant_h * 0.5),
            rotation: quat_z_to_dir(dir), material_hint: MaterialHint::PlasticDark, spin: None, group: None,
        });
    }

    // Landing gear: four legs splaying down-and-out from the body, each with a
    // horizontal foot skid. Tall legs are the single strongest "this is a big
    // aircraft" cue - without them any multirotor reads as a toy quad - so gear
    // is added once the frame is larger than a typical mini quad. Legs point in
    // -Z (down); the renderer seats the lowest point (the feet) on the ground.
    if spec.arm_len_mm >= 250.0 {
        let leg_r = arm_r * 0.8;
        let top_r = arm_len_m * 0.16; // radius where the leg meets the body
        let foot_r = arm_len_m * 0.42; // ground contact radius (splayed out)
        let leg_drop = arm_len_m * 0.55; // how far below the body the feet sit
        let foot_len = arm_len_m * 0.22;
        for k in 0..4 {
            let az = PI / 4.0 + k as f64 * (PI / 2.0); // 45/135/225/315 deg
            let (c, s) = (az.cos(), az.sin());
            let top = Vec3::new(top_r * c, top_r * s, -body_h * 0.4);
            let foot = Vec3::new(foot_r * c, foot_r * s, -leg_drop);
            let mid = Vec3::new((top.x + foot.x) * 0.5, (top.y + foot.y) * 0.5, (top.z + foot.z) * 0.5);
            let dir = Vec3::new(foot.x - top.x, foot.y - top.y, foot.z - top.z);
            parts.push(Part {
                kind: PartKind::Tube, role: PartRole::Boom,
                dims: PartDims::Tube { r: leg_r, h: dir.norm() },
                position: mid, rotation: quat_z_to_dir(dir),
                material_hint: MaterialHint::Carbon, spin: None, group: None,
            });
            // Horizontal foot skid, laid tangent to the leg's outward direction.
            parts.push(Part {
                kind: PartKind::Tube, role: PartRole::Boom,
                dims: PartDims::Tube { r: leg_r * 1.1, h: foot_len },
                position: Vec3::new(foot.x, foot.y, foot.z),
                rotation: quat_z_to_dir(Vec3::new(-s, c, 0.0)),
                material_hint: MaterialHint::PlasticDark, spin: None, group: None,
            });
        }
    }

    // Tri/SingleCopter/CoaxCopter/BiCopter carry actuated parts (yaw servo, tilt
    // servos, flap vanes) that motor_factors doesn't model - without this they'd
    // render as bare motors with no visible control surfaces.
    let controls = frame_controls(spec.class);
    for servo in &controls.servos {
        let pos = servo.position.scale(arm_len_m);
        parts.push(Part {
            kind: PartKind::Box, role: PartRole::Servo,
            dims: PartDims::Box { l: 0.02, w: 0.02, h: 0.015 },
            position: pos, rotation: Quat::identity(),
            material_hint: MaterialHint::PlasticDark, spin: None, group: None,
        });
        if spec.class == crate::types::FrameClass::Tri {
            let len = (pos.x.powi(2) + pos.y.powi(2)).sqrt();
            let yaw = pos.y.atan2(pos.x);
            parts.push(Part {
                kind: PartKind::Box, role: PartRole::Boom,
                dims: PartDims::Box { l: len, w: arm_w, h: arm_t },
                position: Vec3::new(pos.x * 0.5, pos.y * 0.5, 0.0),
                rotation: quat_yaw(yaw), material_hint: MaterialHint::PlasticDark, spin: None, group: None,
            });
        }
    }
    // Vanes sit in the prop wash, so they're placed inboard (arm_len/2) and
    // slightly below the plate rather than out at the motor radius.
    let vane_radius_m = arm_len_m / 2.0;
    for vane in &controls.vanes {
        let rad = vane.angle_deg.to_radians();
        parts.push(Part {
            kind: PartKind::Vane, role: PartRole::Vane,
            dims: PartDims::Box { l: 0.03, w: 0.015, h: 0.001 },
            position: Vec3::new(vane_radius_m * rad.cos(), vane_radius_m * rad.sin(), -0.01),
            rotation: quat_yaw(rad), material_hint: MaterialHint::PlasticDark, spin: None, group: None,
        });
    }

    let bounds = compute_bounds(&parts);
    FrameBlueprint { parts, bounds }
}

fn quat_yaw(yaw: f64) -> Quat {
    let h = yaw * 0.5;
    Quat { w: h.cos(), x: 0.0, y: 0.0, z: h.sin() }
}

/// Rotation mapping the +Z axis onto `dir`. The renderer orients every tube
/// along +Z first, so a tube part's `rotation` is exactly this quaternion.
/// `dir` need not be normalized; a zero-length `dir` yields the identity.
fn quat_z_to_dir(dir: Vec3) -> Quat {
    let n = dir.norm();
    if n < 1e-9 {
        return Quat::identity();
    }
    let d = dir.scale(1.0 / n);
    if d.z > 0.999_999 {
        return Quat::identity();
    }
    if d.z < -0.999_999 {
        return Quat::from_axis_angle(Vec3::new(1.0, 0.0, 0.0), PI);
    }
    // Axis = Z x d, angle = acos(Z . d).
    let axis = Vec3::new(-d.y, d.x, 0.0);
    Quat::from_axis_angle(axis, d.z.clamp(-1.0, 1.0).acos())
}

/// Precomputed rotor dimensions shared by every motor on a frame.
struct RotorDims {
    stator_r: f64,
    stator_h: f64,
    hs: f64,
    hb: f64,
    prop_r: f64,
    blades: usize,
    blade_len: f64,
    chord: f64,
    blade_thick: f64,
    pitch_angle: f64,
    arm_r: f64,
}

/// Emit one rotor (stator + bell + hub + blades + blur disc) at `(mx, my)` on an
/// arm. `vd` = +1 mounts it on top of the arm (prop up), -1 hangs it inverted
/// under the arm (prop down) for the lower motor of a coax pair. `gi` is its spin
/// group so the renderer turns the whole rotor as one unit.
fn push_rotor(parts: &mut Vec<Part>, gi: u32, mx: f64, my: f64, vd: f64, spin_dir: f64, r: &RotorDims) {
    let root_z = r.arm_r * vd; // arm surface (top or bottom)
    let stator_z = root_z + vd * r.hs * 0.5;
    let bell_z = root_z + vd * (r.hs + r.hb * 0.5);
    let hub_z = root_z + vd * (r.hs + r.hb + 0.004);

    parts.push(Part {
        kind: PartKind::Tube, role: PartRole::MotorStator,
        dims: PartDims::Tube { r: r.stator_r * 0.92, h: r.hs },
        position: Vec3::new(mx, my, stator_z), rotation: Quat::identity(),
        material_hint: MaterialHint::PlasticDark, spin: None, group: None,
    });
    parts.push(Part {
        kind: PartKind::Tube, role: PartRole::MotorBell,
        dims: PartDims::Tube { r: r.stator_r, h: r.hb },
        position: Vec3::new(mx, my, bell_z), rotation: Quat::identity(),
        material_hint: MaterialHint::Aluminum, spin: None, group: None,
    });
    parts.push(Part {
        kind: PartKind::Tube, role: PartRole::Prop,
        dims: PartDims::Tube { r: r.stator_r * 0.45, h: r.stator_h * 0.5 },
        position: Vec3::new(mx, my, hub_z), rotation: Quat::identity(),
        material_hint: MaterialHint::Aluminum,
        spin: Some(Spin { axis: Vec3::new(0.0, 0.0, 1.0), dir: spin_dir }), group: Some(gi),
    });

    let pitch = r.pitch_angle * if spin_dir >= 0.0 { 1.0 } else { -1.0 } * vd;
    let rr = r.prop_r * 0.5;
    for k in 0..r.blades {
        let az = (k as f64) * (2.0 * PI / r.blades as f64);
        let q_yaw = Quat::from_axis_angle(Vec3::new(0.0, 0.0, 1.0), az);
        let q_pitch = Quat::from_axis_angle(Vec3::new(1.0, 0.0, 0.0), pitch);
        parts.push(Part {
            kind: PartKind::Blade, role: PartRole::Prop,
            dims: PartDims::Box { l: r.blade_len, w: r.chord, h: r.blade_thick },
            position: Vec3::new(mx + rr * az.cos(), my + rr * az.sin(), hub_z),
            rotation: q_yaw.mul(q_pitch), material_hint: MaterialHint::PlasticDark,
            spin: Some(Spin { axis: Vec3::new(0.0, 0.0, 1.0), dir: spin_dir }), group: Some(gi),
        });
    }
    parts.push(Part {
        kind: PartKind::Disc, role: PartRole::Prop,
        dims: PartDims::Disc { r: r.prop_r, thick: 0.0015 },
        position: Vec3::new(mx, my, hub_z + vd * 0.006),
        rotation: Quat::identity(), material_hint: MaterialHint::PropTranslucent,
        spin: Some(Spin { axis: Vec3::new(0.0, 0.0, 1.0), dir: spin_dir }), group: Some(gi),
    });
}

// Half-extent per axis for a part's shape, ignoring rotation. Using the
// axis-aligned half-extent (rather than the rotated one) over-approximates
// the true footprint, which is fine: the goal is an AABB that is guaranteed
// to enclose the part, not a tight fit.
fn half_extent(dims: &PartDims) -> Vec3 {
    match *dims {
        PartDims::Box { l, w, h } => Vec3::new(l / 2.0, w / 2.0, h / 2.0),
        PartDims::Tube { r, h } => Vec3::new(r, r, h / 2.0),
        PartDims::Disc { r, thick } => Vec3::new(r, r, thick / 2.0),
    }
}

fn compute_bounds(parts: &[Part]) -> Aabb {
    let mut min = Vec3::new(f64::MAX, f64::MAX, f64::MAX);
    let mut max = Vec3::new(f64::MIN, f64::MIN, f64::MIN);
    for p in parts {
        let he = half_extent(&p.dims);
        min = Vec3::new(min.x.min(p.position.x - he.x), min.y.min(p.position.y - he.y), min.z.min(p.position.z - he.z));
        max = Vec3::new(max.x.max(p.position.x + he.x), max.y.max(p.position.y + he.y), max.z.max(p.position.z + he.z));
    }
    Aabb { min, max }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adapters::from_preset;
    use crate::physics::physics_geometry;
    use crate::types::{FrameClass, FrameType};

    #[test]
    fn quad_blueprint_has_motor_and_prop_per_arm() {
        let spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        let bp = build_blueprint(&spec);
        let bells = bp.parts.iter().filter(|p| p.role == PartRole::MotorBell).count();
        let stators = bp.parts.iter().filter(|p| p.role == PartRole::MotorStator).count();
        // One blur disc per motor; blades are the other Prop-role parts.
        let discs = bp.parts.iter().filter(|p| p.role == PartRole::Prop && p.kind == PartKind::Disc).count();
        assert_eq!(bells, 4);
        assert_eq!(stators, 4);
        assert_eq!(discs, 4);
    }

    #[test]
    fn each_rotor_has_its_configured_blade_count_grouped() {
        let mut spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        spec.prop.blades = 3;
        let bp = build_blueprint(&spec);
        let blades: Vec<_> = bp.parts.iter().filter(|p| p.kind == PartKind::Blade).collect();
        assert_eq!(blades.len(), 4 * 3);
        // Blades + disc for motor 0 share group 0; every blade carries a group.
        let g0_blades = blades.iter().filter(|p| p.group == Some(0)).count();
        assert_eq!(g0_blades, 3);
        assert!(blades.iter().all(|p| p.group.is_some() && p.spin.is_some()));
        // The blur disc joins its motor's group so it spins with the blades.
        for i in 0..4u32 {
            let disc = bp.parts.iter().find(|p| p.kind == PartKind::Disc && p.group == Some(i));
            assert!(disc.is_some(), "no disc grouped with motor {i}");
        }
    }

    #[test]
    fn stack_build_has_one_central_esc_arm_build_has_one_per_motor() {
        let mut spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        spec.esc_layout = crate::types::EscLayout::Stack4in1;
        let stacked = build_blueprint(&spec);
        assert_eq!(stacked.parts.iter().filter(|p| p.role == PartRole::Esc).count(), 1);

        spec.esc_layout = crate::types::EscLayout::ArmMounted;
        let armed = build_blueprint(&spec);
        assert_eq!(armed.parts.iter().filter(|p| p.role == PartRole::Esc).count(), 4);
    }

    #[test]
    fn every_prop_part_carries_spin() {
        let spec = from_preset(FrameClass::Hexa, FrameType::X).unwrap();
        let bp = build_blueprint(&spec);
        for p in bp.parts.iter().filter(|p| p.role == PartRole::Prop) {
            assert!(p.spin.is_some());
        }
    }

    #[test]
    fn blueprint_motor_positions_equal_physics_mounts() {
        // The invariant: mesh and physics agree on where each motor sits in the
        // rotor plane (XY). The bell is intentionally stacked above the mount in
        // Z (stator below it), so only the radial position must match.
        let spec = from_preset(FrameClass::Octa, FrameType::X).unwrap();
        let bp = build_blueprint(&spec);
        let g = physics_geometry(&spec);
        let mut bells: Vec<_> = bp.parts.iter().filter(|p| p.role == PartRole::MotorBell).map(|p| p.position).collect();
        for mount in &g.motors {
            let hit = bells.iter().position(|b| (b.x - mount.position.x).abs() < 1e-9 && (b.y - mount.position.y).abs() < 1e-9);
            assert!(hit.is_some(), "no bell at mount {:?}", mount.position);
            bells.remove(hit.unwrap());
        }
        assert!(bells.is_empty());
    }

    #[test]
    fn bounds_enclose_prop_tips() {
        // compute_bounds must expand past part centers by each part's
        // half-extent, or the AABB clips prop discs at the outer edge of the
        // frame - this proves it for the farthest-out prop.
        let spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        let bp = build_blueprint(&spec);
        let g = physics_geometry(&spec);
        let prop_radius_m = spec.prop.radius_mm / 1000.0;
        let epsilon = 1e-9;

        let max_x = g.motors.iter().map(|m| m.position.x).fold(f64::MIN, f64::max);
        let min_x = g.motors.iter().map(|m| m.position.x).fold(f64::MAX, f64::min);
        let max_y = g.motors.iter().map(|m| m.position.y).fold(f64::MIN, f64::max);
        let min_y = g.motors.iter().map(|m| m.position.y).fold(f64::MAX, f64::min);

        assert!(bp.bounds.max.x >= max_x + prop_radius_m - epsilon);
        assert!(bp.bounds.min.x <= min_x - prop_radius_m + epsilon);
        assert!(bp.bounds.max.y >= max_y + prop_radius_m - epsilon);
        assert!(bp.bounds.min.y <= min_y - prop_radius_m + epsilon);
    }

    #[test]
    fn single_copter_blueprint_has_four_vanes() {
        let spec = from_preset(FrameClass::SingleCopter, FrameType::Plus).unwrap();
        let bp = build_blueprint(&spec);
        let vanes = bp.parts.iter().filter(|p| p.role == PartRole::Vane).count();
        assert_eq!(vanes, 4);
    }

    #[test]
    fn tri_blueprint_has_a_servo_and_boom() {
        let spec = from_preset(FrameClass::Tri, FrameType::X).unwrap();
        let bp = build_blueprint(&spec);
        let servos = bp.parts.iter().filter(|p| p.role == PartRole::Servo).count();
        let booms = bp.parts.iter().filter(|p| p.role == PartRole::Boom).count();
        assert_eq!(servos, 1);
        assert_eq!(booms, 1);
    }

    #[test]
    fn bicopter_blueprint_has_two_servos() {
        let spec = from_preset(FrameClass::BiCopter, FrameType::X).unwrap();
        let bp = build_blueprint(&spec);
        let servos = bp.parts.iter().filter(|p| p.role == PartRole::Servo).count();
        assert_eq!(servos, 2);
    }

    #[test]
    fn blueprint_json_round_trips() {
        let spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        let bp = build_blueprint(&spec);
        let json = serde_json::to_string(&bp).unwrap();
        let back: FrameBlueprint = serde_json::from_str(&json).unwrap();
        assert_eq!(bp, back);
    }
}
