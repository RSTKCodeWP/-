use serde::{Deserialize, Serialize};
use std::f64::consts::PI;
use crate::math::Vec3;
use crate::spec::{defaults_for, size_class_from_diagonal_mm, FrameGeomSpec, Masses, MotorStator, PlateSpec, PropSpec};
use crate::tables::{motor_factors, FrameError};
use crate::types::{FrameClass, FrameType};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct SitlCustomFrameInput {
    pub mass: f64,
    pub diagonal_size: f64,
    pub disc_area: f64,
    pub num_motors: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct VehicleProfileInput {
    pub weight_g: f64,
    pub frame_size_mm: Option<f64>,
    pub motor_count: Option<u32>,
    pub motor_kv: Option<f64>,
    pub prop_diameter_mm: Option<f64>,
    pub esc_rating_a: Option<f64>,
    pub battery_cells: u32,
    pub cog_offset_mm: Option<Vec3>,
}

fn build_spec(
    class: FrameClass,
    ftype: FrameType,
    motor_count: u32,
    diagonal_mm: f64,
    prop_radius_mm: f64,
    total_mass_g: f64,
    cog: Vec3,
) -> FrameGeomSpec {
    let size = size_class_from_diagonal_mm(diagonal_mm);
    let d = defaults_for(size);
    // Split total mass into lumped components by rough fraction. These fractions
    // only set the inertia distribution; total mass is preserved.
    let n = motor_count.max(1) as f64;
    let per_motor = total_mass_g * 0.12 / n;
    let per_prop = total_mass_g * 0.02 / n;
    let per_esc = total_mass_g * 0.06 / n;
    let battery = total_mass_g * 0.35;
    let frame = total_mass_g - per_motor * n - per_prop * n - per_esc * n - battery;
    FrameGeomSpec {
        class,
        frame_type: ftype,
        motor_count,
        arm_len_mm: diagonal_mm / 2.0,
        arm_width_mm: d.arm_width_mm,
        arm_thick_mm: d.arm_thick_mm,
        plate: PlateSpec { len_mm: diagonal_mm * 0.4, width_mm: diagonal_mm * 0.3, thick_mm: 2.0, stack_height_mm: d.stack_height_mm },
        motor_stator: MotorStator { dia_mm: d.stator_dia_mm, height_mm: d.stator_height_mm },
        prop: PropSpec { radius_mm: prop_radius_mm, pitch_in: 0.0, blades: 3 },
        esc_layout: d.esc_layout,
        masses: Masses { frame_g: frame, per_motor_g: per_motor, per_prop_g: per_prop, per_esc_g: per_esc, battery_g: battery },
        cog_offset_mm: cog,
    }
}

pub fn from_sitl_custom_frame(i: &SitlCustomFrameInput) -> FrameGeomSpec {
    let n = i.num_motors.max(1);
    let prop_r_m = (i.disc_area / (n as f64 * PI)).sqrt();
    let class = class_for_motor_count(n);
    build_spec(class, FrameType::X, n, i.diagonal_size * 1000.0, prop_r_m * 1000.0, i.mass * 1000.0, Vec3::new(0.0, 0.0, 0.0))
}

pub fn from_vehicle_profile(i: &VehicleProfileInput, class: FrameClass, ftype: FrameType) -> FrameGeomSpec {
    let motors = motor_factors(class, ftype).map(|m| m.len() as u32).unwrap_or(4);
    let diagonal = i.frame_size_mm.unwrap_or(220.0);
    let prop_r = i.prop_diameter_mm.map(|d| d / 2.0).unwrap_or(diagonal * 0.29);
    let cog = i.cog_offset_mm.unwrap_or(Vec3::new(0.0, 0.0, 0.0));
    build_spec(class, ftype, motors, diagonal, prop_r, i.weight_g, cog)
}

/// A build described by whatever real sources are available: the launched SITL
/// custom frame and/or the user's selected vehicle profile, plus an optional
/// explicit class/type. `from_build` merges them into one spec so the rendered
/// airframe reflects the actual build, not a hardcoded preset.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, Default)]
pub struct BuildInput {
    #[serde(default)]
    pub sitl: Option<SitlCustomFrameInput>,
    #[serde(default)]
    pub profile: Option<VehicleProfileInput>,
    #[serde(default)]
    pub class: Option<FrameClass>,
    #[serde(default)]
    pub frame_type: Option<FrameType>,
}

/// A sensible reference diagonal (motor-to-motor, mm) per frame class, used when
/// nothing else supplies a size. Bigger classes default bigger, so an OctaQuad
/// selected with no custom frame doesn't inherit a 5-inch quad's dimensions.
fn class_default_diagonal_mm(class: FrameClass) -> f64 {
    use FrameClass::*;
    match class {
        Quad => 250.0,
        Y6 => 450.0,
        Tri => 400.0,
        Hexa => 550.0,
        OctaQuad => 650.0,
        Octa => 750.0,
        Deca => 900.0,
        DodecaHexa => 950.0,
        SingleCopter | CoaxCopter | BiCopter => 380.0,
    }
}

pub fn from_build(b: &BuildInput) -> FrameGeomSpec {
    // The SELECTED frame class (from the SITL frame dropdown) is authoritative
    // for the layout + motor count. The launched SITL custom frame is
    // authoritative for physical size/mass/disc-area. The vehicle profile is a
    // separate record that applies ONLY when it is for this same frame (matching
    // motor count) - a mismatched profile (e.g. a 5-inch quad while an OctaQuad
    // is launched) is ignored so it can't shrink an unrelated frame. Absent all
    // of those, a per-class default keeps the frame sensibly proportioned.
    let ftype = b.frame_type.unwrap_or(FrameType::X);
    let count_hint = b
        .sitl
        .map(|s| s.num_motors)
        .filter(|&n| n > 0)
        .or_else(|| b.profile.and_then(|p| p.motor_count).filter(|&n| n > 0))
        .unwrap_or(4);
    let class = b.class.unwrap_or_else(|| class_for_motor_count(count_hint));
    // Motor count comes from the class's own table (the selected frame's true
    // count), not the possibly-mismatched profile.
    let motor_count = motor_factors(class, ftype).map(|m| m.len() as u32).unwrap_or(count_hint);

    // Profile applies only if it is for this frame (same motor count, or count
    // unspecified). Otherwise drop it entirely for sizing.
    let profile = b.profile.filter(|p| p.motor_count.map_or(true, |mc| mc == motor_count));

    let diagonal_mm = b
        .sitl
        .map(|s| s.diagonal_size * 1000.0)
        .filter(|&d| d > 0.0)
        .or_else(|| profile.and_then(|p| p.frame_size_mm).filter(|&d| d > 0.0))
        .unwrap_or_else(|| class_default_diagonal_mm(class));

    let mass_g = b
        .sitl
        .map(|s| s.mass * 1000.0)
        .filter(|&m| m > 0.0)
        .or_else(|| profile.map(|p| p.weight_g).filter(|&m| m > 0.0))
        // Rough default so inertia isn't degenerate; mass is cosmetic to the
        // engine (it reads total mass separately from the SITL frame).
        .unwrap_or(diagonal_mm * 2.0);

    // Prop radius: SITL disc area (authoritative) -> matching profile prop
    // diameter -> a fraction of the diagonal.
    let sitl_prop_mm = b.sitl.and_then(|s| {
        if s.disc_area > 0.0 {
            Some((s.disc_area / (s.num_motors.max(1) as f64 * PI)).sqrt() * 1000.0)
        } else {
            None
        }
    });
    let prop_radius_mm = sitl_prop_mm
        .or_else(|| profile.and_then(|p| p.prop_diameter_mm).map(|d| d / 2.0).filter(|&r| r > 0.0))
        .unwrap_or(diagonal_mm * 0.29);

    let cog = b.profile.and_then(|p| p.cog_offset_mm).unwrap_or(Vec3::new(0.0, 0.0, 0.0));
    build_spec(class, ftype, motor_count, diagonal_mm, prop_radius_mm, mass_g, cog)
}

pub fn from_preset(class: FrameClass, ftype: FrameType) -> Result<FrameGeomSpec, FrameError> {
    let motors = motor_factors(class, ftype)?.len() as u32;
    // Preset diagonal by class default; a 5-inch quad-class reference.
    let diagonal = 220.0;
    Ok(build_spec(class, ftype, motors, diagonal, 63.5, 650.0, Vec3::new(0.0, 0.0, 0.0)))
}

fn class_for_motor_count(n: u32) -> FrameClass {
    match n {
        6 => FrameClass::Hexa,
        8 => FrameClass::Octa,
        10 => FrameClass::Deca,
        12 => FrameClass::DodecaHexa,
        _ => FrameClass::Quad,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{FrameClass, FrameType, EscLayout};

    #[test]
    fn sitl_frame_derives_prop_radius_from_disc_area() {
        // disc_area total = num_motors * pi * r^2 -> r = sqrt(area/(n*pi))
        let i = SitlCustomFrameInput { mass: 1.5, diagonal_size: 0.4, disc_area: 0.05, num_motors: 4 };
        let s = from_sitl_custom_frame(&i);
        let expected_r_m = (0.05f64 / (4.0 * std::f64::consts::PI)).sqrt();
        assert!((s.prop.radius_mm - expected_r_m * 1000.0).abs() < 1e-6);
        assert_eq!(s.motor_count, 4);
        assert_eq!(s.arm_len_mm, 200.0); // diagonal 0.4 m / 2 -> 200 mm
    }

    #[test]
    fn vehicle_profile_is_faithful_when_rich() {
        let i = VehicleProfileInput {
            weight_g: 650.0, frame_size_mm: Some(220.0), motor_count: Some(4),
            motor_kv: Some(2400.0), prop_diameter_mm: Some(127.0), esc_rating_a: Some(45.0),
            battery_cells: 6, cog_offset_mm: None,
        };
        let s = from_vehicle_profile(&i, FrameClass::Quad, FrameType::BetaFlightX);
        assert_eq!(s.motor_count, 4);
        assert_eq!(s.arm_len_mm, 110.0);
        assert!((s.prop.radius_mm - 63.5).abs() < 1e-6);
        assert_eq!(s.esc_layout, EscLayout::Stack4in1); // 220mm -> Seven class default
    }

    #[test]
    fn preset_rejects_unsupported_combo() {
        assert!(from_preset(FrameClass::Quad, FrameType::Y6B).is_err());
    }

    #[test]
    fn build_prefers_sitl_frame_then_profile() {
        // SITL frame is authoritative for mass, motor count and (via disc area)
        // prop size; profile diagonal fills in when the frame has none in mm.
        let sitl = SitlCustomFrameInput { mass: 2.0, diagonal_size: 0.5, disc_area: 0.2, num_motors: 6 };
        let b = BuildInput { sitl: Some(sitl), profile: None, class: None, frame_type: None };
        let s = from_build(&b);
        assert_eq!(s.motor_count, 6);
        assert_eq!(s.class, FrameClass::Hexa); // derived from 6 motors
        assert_eq!(s.arm_len_mm, 250.0); // diagonal 0.5 m / 2
        let total = s.masses.frame_g + s.masses.per_motor_g * 6.0 + s.masses.per_prop_g * 6.0 + s.masses.per_esc_g * 6.0 + s.masses.battery_g;
        assert!((total - 2000.0).abs() < 1e-6); // 2 kg preserved
        let expected_r = (0.2f64 / (6.0 * std::f64::consts::PI)).sqrt() * 1000.0;
        assert!((s.prop.radius_mm - expected_r).abs() < 1e-6); // from disc area
    }

    #[test]
    fn build_takes_only_cog_and_type_from_profile_when_sitl_present() {
        let sitl = SitlCustomFrameInput { mass: 1.5, diagonal_size: 0.22, disc_area: 0.05, num_motors: 4 };
        let profile = VehicleProfileInput {
            weight_g: 700.0, frame_size_mm: None, motor_count: Some(4), motor_kv: None,
            prop_diameter_mm: Some(127.0), esc_rating_a: None, battery_cells: 6,
            cog_offset_mm: Some(Vec3::new(0.0, 0.0, 5.0)),
        };
        let b = BuildInput { sitl: Some(sitl), profile: Some(profile), class: None, frame_type: Some(FrameType::BetaFlightX) };
        let s = from_build(&b);
        // With a SITL frame present, disc area (not the profile prop diameter)
        // sets prop size, so it scales WITH the frame.
        let expected_r = (0.05f64 / (4.0 * std::f64::consts::PI)).sqrt() * 1000.0;
        assert!((s.prop.radius_mm - expected_r).abs() < 1e-6);
        assert_eq!(s.frame_type, FrameType::BetaFlightX);
        assert_eq!(s.cog_offset_mm.z, 5.0); // cog still comes from the profile
    }

    #[test]
    fn profile_frame_size_never_shrinks_a_launched_sitl_frame() {
        // Regression: a heavy octa (1.6 m) launched while the active profile is a
        // default 5-inch quad (127 mm) must render at 1.6 m, not 127 mm - else
        // the frame is tiny under giant disc-area props.
        let sitl = SitlCustomFrameInput { mass: 60.0, diagonal_size: 1.6, disc_area: 2.5, num_motors: 8 };
        let profile = VehicleProfileInput {
            weight_g: 600.0, frame_size_mm: Some(127.0), motor_count: Some(4), motor_kv: Some(2400.0),
            prop_diameter_mm: Some(127.0), esc_rating_a: Some(45.0), battery_cells: 4, cog_offset_mm: None,
        };
        let s = from_build(&BuildInput { sitl: Some(sitl), profile: Some(profile), class: None, frame_type: None });
        assert_eq!(s.arm_len_mm, 800.0); // 1.6 m sitl diagonal / 2, NOT 127/2
        assert_eq!(s.motor_count, 8);
        assert_eq!(s.class, FrameClass::Octa);
        let prop_r = (2.5f64 / (8.0 * std::f64::consts::PI)).sqrt() * 1000.0;
        assert!((s.prop.radius_mm - prop_r).abs() < 1e-6); // from disc area, ~315 mm
        // Prop radius must stay well under the arm length (not a giant prop on a tiny frame).
        assert!(s.prop.radius_mm < s.arm_len_mm);
    }

    #[test]
    fn build_uses_profile_fully_when_no_sitl_frame() {
        // No launched custom frame -> the profile drives everything.
        let profile = VehicleProfileInput {
            weight_g: 700.0, frame_size_mm: Some(180.0), motor_count: Some(6), motor_kv: None,
            prop_diameter_mm: Some(139.7), esc_rating_a: None, battery_cells: 6, cog_offset_mm: None,
        };
        let s = from_build(&BuildInput { sitl: None, profile: Some(profile), class: None, frame_type: None });
        assert_eq!(s.arm_len_mm, 90.0); // 180 / 2
        assert_eq!(s.motor_count, 6);
        assert!((s.prop.radius_mm - 69.85).abs() < 1e-6); // 139.7 / 2
    }

    #[test]
    fn build_falls_back_to_class_default_when_empty() {
        let s = from_build(&BuildInput::default());
        assert_eq!(s.motor_count, 4);
        assert_eq!(s.class, FrameClass::Quad);
        assert_eq!(s.arm_len_mm, 125.0); // 250 mm quad class default / 2
    }

    #[test]
    fn selected_class_wins_and_mismatched_profile_is_ignored() {
        // User picks OctaQuad in the frame dropdown but has a default 5-inch quad
        // profile active and no custom JSON: the frame must be a proper OctaQuad
        // at its class-default size, NOT a tiny 127 mm quad-sized frame.
        let profile = VehicleProfileInput {
            weight_g: 600.0, frame_size_mm: Some(127.0), motor_count: Some(4), motor_kv: None,
            prop_diameter_mm: Some(127.0), esc_rating_a: None, battery_cells: 4, cog_offset_mm: None,
        };
        let b = BuildInput { sitl: None, profile: Some(profile), class: Some(FrameClass::OctaQuad), frame_type: Some(FrameType::X) };
        let s = from_build(&b);
        assert_eq!(s.class, FrameClass::OctaQuad);
        assert_eq!(s.motor_count, 8); // from the OctaQuad table, not the profile's 4
        assert_eq!(s.arm_len_mm, 325.0); // 650 mm OctaQuad default / 2, not 127/2
        assert!(s.prop.radius_mm > 100.0); // proportional to the frame, not a 5-inch prop
    }

    #[test]
    fn build_input_round_trips_partial_json() {
        // The desktop main process sends only the fields it has; the rest must
        // deserialize as None, not fail.
        let json = r#"{"sitl":{"mass":1.5,"diagonal_size":0.22,"disc_area":0.05,"num_motors":4},"class":"quad","frame_type":"x"}"#;
        let b: BuildInput = serde_json::from_str(json).unwrap();
        assert!(b.profile.is_none());
        assert_eq!(b.class, Some(FrameClass::Quad));
        let s = from_build(&b);
        assert_eq!(s.motor_count, 4);
    }
}
