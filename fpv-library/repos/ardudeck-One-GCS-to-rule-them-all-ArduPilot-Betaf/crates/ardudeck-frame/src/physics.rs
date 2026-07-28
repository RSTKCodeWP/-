use serde::{Deserialize, Serialize};
use crate::math::{Mat3, Vec3};
use crate::spec::FrameGeomSpec;
use crate::tables::motor_factors;
use crate::types::{EscLayout, UpDown};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct MotorMount {
    pub position: Vec3,
    pub thrust_axis: Vec3,
    pub spin_dir: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PhysicsGeometry {
    pub motors: Vec<MotorMount>,
    pub com: Vec3,
    pub inertia: Mat3,
}

struct PointMass {
    pos: Vec3,
    mass: f64,
}

fn add_point_inertia(inertia: &mut Mat3, p: &PointMass, com: Vec3) {
    // Parallel-axis point-mass inertia about the CoM.
    let r = Vec3::new(p.pos.x - com.x, p.pos.y - com.y, p.pos.z - com.z);
    let m = p.mass;
    inertia.0[0][0] += m * (r.y * r.y + r.z * r.z);
    inertia.0[1][1] += m * (r.x * r.x + r.z * r.z);
    inertia.0[2][2] += m * (r.x * r.x + r.y * r.y);
    inertia.0[0][1] -= m * r.x * r.y;
    inertia.0[1][0] -= m * r.x * r.y;
    inertia.0[0][2] -= m * r.x * r.z;
    inertia.0[2][0] -= m * r.x * r.z;
    inertia.0[1][2] -= m * r.y * r.z;
    inertia.0[2][1] -= m * r.y * r.z;
}

pub fn physics_geometry(spec: &FrameGeomSpec) -> PhysicsGeometry {
    let arm = spec.arm_len_mm / 1000.0;
    let factors = motor_factors(spec.class, spec.frame_type).unwrap_or_default();
    let stack_z = spec.plate.stack_height_mm / 1000.0;
    let coax_gap = 0.02; // metres between stacked coax layers

    let mut mounts = Vec::new();
    let mut points: Vec<PointMass> = Vec::new();

    for f in &factors {
        let rad = f.angle_deg.to_radians();
        let z = match f.updown {
            UpDown::Up => coax_gap * 0.5,
            UpDown::Down => -coax_gap * 0.5,
            UpDown::Flat => 0.0,
        };
        let pos = Vec3::new(arm * rad.cos(), arm * rad.sin(), z);
        mounts.push(MotorMount { position: pos, thrust_axis: Vec3::new(0.0, 0.0, 1.0), spin_dir: f.yaw_factor });
        points.push(PointMass { pos, mass: (spec.masses.per_motor_g + spec.masses.per_prop_g) / 1000.0 });
        let esc_pos = match spec.esc_layout {
            EscLayout::Stack4in1 => Vec3::new(0.0, 0.0, stack_z * 0.5),
            EscLayout::ArmMounted => Vec3::new(pos.x * 0.5, pos.y * 0.5, 0.0),
        };
        points.push(PointMass { pos: esc_pos, mass: spec.masses.per_esc_g / 1000.0 });
    }
    // Frame plate point-mass sits at the origin; the battery is offset to its
    // configured CoG so shifting battery placement actually moves the CoM.
    points.push(PointMass { pos: Vec3::new(0.0, 0.0, 0.0), mass: spec.masses.frame_g / 1000.0 });
    points.push(PointMass { pos: Vec3::new(spec.cog_offset_mm.x / 1000.0, spec.cog_offset_mm.y / 1000.0, spec.cog_offset_mm.z / 1000.0), mass: spec.masses.battery_g / 1000.0 });

    let total: f64 = points.iter().map(|p| p.mass).sum();
    let com = if total > 0.0 {
        let mut c = Vec3::new(0.0, 0.0, 0.0);
        for p in &points {
            c = c.add(p.pos.scale(p.mass));
        }
        c.scale(1.0 / total)
    } else {
        Vec3::new(0.0, 0.0, 0.0)
    };

    let mut inertia = Mat3::zero();
    for p in &points {
        add_point_inertia(&mut inertia, p, com);
    }

    PhysicsGeometry { motors: mounts, com, inertia }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adapters::from_preset;
    use crate::types::{FrameClass, FrameType};

    #[test]
    fn quad_x_mounts_are_centered_and_on_radius() {
        let spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        let g = physics_geometry(&spec);
        assert_eq!(g.motors.len(), 4);
        let arm_m = spec.arm_len_mm / 1000.0;
        for m in &g.motors {
            let r = (m.position.x.powi(2) + m.position.y.powi(2)).sqrt();
            assert!((r - arm_m).abs() < 1e-9);
            assert_eq!(m.thrust_axis, Vec3::new(0.0, 0.0, 1.0));
        }
        let sx: f64 = g.motors.iter().map(|m| m.position.x).sum();
        let sy: f64 = g.motors.iter().map(|m| m.position.y).sum();
        assert!(sx.abs() < 1e-9 && sy.abs() < 1e-9);
    }

    #[test]
    fn symmetric_frame_has_symmetric_diagonal_inertia() {
        let spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        let g = physics_geometry(&spec);
        // Off-diagonal terms ~0 for a symmetric X; Ixx ~ Iyy.
        assert!(g.inertia.0[0][1].abs() < 1e-6);
        assert!((g.inertia.0[0][0] - g.inertia.0[1][1]).abs() < 1e-6);
        assert!(g.inertia.0[2][2] > 0.0);
    }

    #[test]
    fn arm_mounted_esc_shifts_inertia_vs_stack() {
        let mut spec = from_preset(FrameClass::Quad, FrameType::X).unwrap();
        spec.esc_layout = crate::types::EscLayout::Stack4in1;
        let stack = physics_geometry(&spec).inertia.0[2][2];
        spec.esc_layout = crate::types::EscLayout::ArmMounted;
        let arm = physics_geometry(&spec).inertia.0[2][2];
        assert!(arm > stack); // mass moved outward raises yaw inertia
    }
}
