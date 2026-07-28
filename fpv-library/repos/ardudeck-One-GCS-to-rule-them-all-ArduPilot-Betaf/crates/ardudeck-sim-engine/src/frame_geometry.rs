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

pub fn frame_geometry(num_motors: u32, diagonal_size: f64) -> Vec<MotorMount> {
    // ArduPilot SIM_Motor::setup_params (lines 208-210) places each motor at
    // position = (cos(angle), sin(angle)) * diagonal_size (the FULL value, not
    // half). Our previous diagonal_size/2 halved every moment arm, so roll/pitch
    // authority was 2x too low versus stock SITL. Use the full diagonal_size.
    let radius = diagonal_size;
    // The engine's original hardcoded "hexa X"/"octa X" tables were actually
    // ArduPilot's PLUS (default) layouts, not true FRAME_TYPE_X - map 6/8 to
    // Plus here so the delegated table reproduces the same angles byte-for-byte.
    // Quad genuinely used X. Counts outside 4/6/8 keep the generic ring fallback.
    let combo = match num_motors {
        4 => Some((FrameClass::Quad, FrameType::X)),
        6 => Some((FrameClass::Hexa, FrameType::Plus)),
        8 => Some((FrameClass::Octa, FrameType::Plus)),
        _ => None,
    };
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
            let m = frame_geometry(n, diag);
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
            let sum: f64 = frame_geometry(n, 1.0).iter().map(|m| m.yaw_factor).sum();
            assert_eq!(sum, 0.0);
        }
    }
    #[test]
    fn geometrically_centered() {
        for n in [4u32, 6, 8] {
            let m = frame_geometry(n, 1.0);
            let sx: f64 = m.iter().map(|x| x.position.x).sum();
            let sy: f64 = m.iter().map(|x| x.position.y).sum();
            assert!(sx.abs() < 1e-9 && sy.abs() < 1e-9);
        }
    }
}
