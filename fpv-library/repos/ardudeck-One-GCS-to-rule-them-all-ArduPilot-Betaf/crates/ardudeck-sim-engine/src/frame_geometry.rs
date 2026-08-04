use crate::math::Vec3;
use ardudeck_frame::{motor_factors, FrameClass, FrameType};

#[derive(Debug, Clone, Copy)]
pub struct MotorMount {
    pub position: Vec3,
    pub yaw_factor: f64,
}

fn spec_to_mount(angle_deg: f64, yaw_factor: f64, radius: f64) -> MotorMount {
    let rad = angle_deg.to_radians();
    MotorMount {
        position: Vec3::new(radius * rad.cos(), radius * rad.sin(), 0.0),
        yaw_factor,
    }
}

/// Place the simulated motors for a frame.
///
/// `layout` is the flight controller's OWN mixer configuration (its FRAME_CLASS /
/// FRAME_TYPE). It must be supplied whenever it is known, because the mixer and the
/// simulated airframe are independent: ArduPilot computes per-motor commands from
/// FRAME_CLASS/FRAME_TYPE, and if we place the motors anywhere else the controller
/// is driving motors that are not where it believes they are. The result is
/// roll/pitch cross-coupling and a rotating limit cycle that looks exactly like bad
/// PID tuning but cannot be tuned out. An Octa mixed as X against a Plus airframe is
/// a 22.5 degree offset on all eight motors and is not flyable.
///
/// `None` falls back to guessing from the motor count, which exists only for frame
/// files written before the layout was recorded. The guess picks the PLUS layout for
/// 4/6/8 to match the frame names the desktop app launches SITL with
/// (`quad`/`hexa`/`octa` are all Plus tables in SIM_Frame.cpp) and the FRAME_TYPE 0
/// it writes alongside them. See apps/desktop/src/shared/sitl-frame-geometry.ts.
pub fn frame_geometry(
    num_motors: u32,
    diagonal_size: f64,
    layout: Option<(FrameClass, FrameType)>,
) -> Vec<MotorMount> {
    // ArduPilot SIM_Motor::setup_params (lines 208-210) places each motor at
    // position = (cos(angle), sin(angle)) * diagonal_size (the FULL value, not
    // half). Our previous diagonal_size/2 halved every moment arm, so roll/pitch
    // authority was 2x too low versus stock SITL. Use the full diagonal_size.
    let radius = diagonal_size;
    // Prefer the mixer's real class/type. The motor-count fallback maps 4/6/8 to
    // PLUS, matching the `quad`/`hexa`/`octa` frame tables in SIM_Frame.cpp (all
    // three are Plus) and the FRAME_TYPE 0 the app writes for them. The previous
    // 4 => X guess disagreed with that pairing and gave quads a 45 degree offset.
    // Counts outside 4/6/8 keep the generic ring fallback.
    let combo = layout.or(match num_motors {
        4 => Some((FrameClass::Quad, FrameType::Plus)),
        6 => Some((FrameClass::Hexa, FrameType::Plus)),
        8 => Some((FrameClass::Octa, FrameType::Plus)),
        _ => None,
    });
    let specs: Vec<(f64, f64)> = match combo.and_then(|(c, t)| motor_factors(c, t).ok()) {
        Some(factors) => factors.iter().map(|f| (f.angle_deg, f.yaw_factor)).collect(),
        None => (0..num_motors)
            .map(|i| {
                let angle_deg = (360.0 / num_motors as f64) * i as f64 + 360.0 / (2.0 * num_motors as f64);
                let yaw_factor = if i % 2 == 0 { 1.0 } else { -1.0 };
                (angle_deg, yaw_factor)
            })
            .collect(),
    };
    specs
        .into_iter()
        .map(|(a, y)| spec_to_mount(a, y, radius))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn motors_on_arm_radius_circle() {
        for (n, diag) in [(4u32, 0.4f64), (6, 0.65), (8, 1.325)] {
            let m = frame_geometry(n, diag, None);
            assert_eq!(m.len() as u32, n);
            for mount in &m {
                let r = (mount.position.x.powi(2) + mount.position.y.powi(2)).sqrt();
                // Motor arm radius equals the full diagonal_size (ArduPilot).
                assert!((r - diag).abs() < 1e-6);
                assert_eq!(mount.position.z, 0.0);
            }
        }
    }
    #[test]
    fn balanced_yaw_factors() {
        for n in [4u32, 6, 8] {
            let sum: f64 = frame_geometry(n, 1.0, None).iter().map(|m| m.yaw_factor).sum();
            assert_eq!(sum, 0.0);
        }
    }
    #[test]
    fn geometrically_centered() {
        for n in [4u32, 6, 8] {
            let m = frame_geometry(n, 1.0, None);
            let sx: f64 = m.iter().map(|x| x.position.x).sum();
            let sy: f64 = m.iter().map(|x| x.position.y).sum();
            assert!(sx.abs() < 1e-9 && sy.abs() < 1e-9);
        }
    }

    /// An explicit mixer layout must win over the motor-count guess. Without this
    /// the engine placed motors where it assumed rather than where the flight
    /// controller's mixer expects, which is unflyable (an Octa X mixer against a
    /// Plus airframe is a 22.5 deg offset on all eight motors).
    #[test]
    fn explicit_layout_overrides_motor_count_guess() {
        let plus = frame_geometry(8, 1.0, Some((FrameClass::Octa, FrameType::Plus)));
        let x = frame_geometry(8, 1.0, Some((FrameClass::Octa, FrameType::X)));
        assert_eq!(plus.len(), 8);
        assert_eq!(x.len(), 8);
        // Octa Plus motor 1 sits at 0 deg, Octa X motor 1 at 22.5 deg.
        assert!((plus[0].position.y).abs() < 1e-9, "octa plus MOT_1 on the nose axis");
        let x_angle = x[0].position.y.atan2(x[0].position.x).to_degrees();
        assert!((x_angle - 22.5).abs() < 1e-6, "octa X MOT_1 at 22.5 deg, got {x_angle}");
        // The two layouts must actually differ, or the override does nothing.
        assert!(plus.iter().zip(&x).any(|(a, b)| (a.position.x - b.position.x).abs() > 1e-6));
    }

    /// The motor-count fallback must agree with the frame names the desktop app
    /// launches SITL with (`quad`/`hexa`/`octa`, all PLUS tables) and the
    /// FRAME_TYPE 0 it writes alongside them.
    #[test]
    fn motor_count_fallback_is_plus() {
        for (n, class) in [(4u32, FrameClass::Quad), (6, FrameClass::Hexa), (8, FrameClass::Octa)] {
            let guessed = frame_geometry(n, 1.0, None);
            let plus = frame_geometry(n, 1.0, Some((class, FrameType::Plus)));
            for (g, p) in guessed.iter().zip(&plus) {
                assert!((g.position.x - p.position.x).abs() < 1e-9);
                assert!((g.position.y - p.position.y).abs() < 1e-9);
                assert_eq!(g.yaw_factor, p.yaw_factor);
            }
        }
    }
}
