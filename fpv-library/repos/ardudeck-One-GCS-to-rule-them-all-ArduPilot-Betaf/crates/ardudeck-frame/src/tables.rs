use crate::math::Vec3;
use crate::types::{FrameClass, FrameType, MotorFactor, UpDown};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameError {
    UnsupportedCombo(FrameClass, FrameType),
}

fn flat(specs: &[(f64, f64)]) -> Vec<MotorFactor> {
    specs
        .iter()
        .map(|&(angle_deg, yaw_factor)| MotorFactor { angle_deg, yaw_factor, updown: UpDown::Flat })
        .collect()
}

fn stacked(specs: &[(f64, f64, UpDown)]) -> Vec<MotorFactor> {
    specs
        .iter()
        .map(|&(angle_deg, yaw_factor, updown)| MotorFactor { angle_deg, yaw_factor, updown })
        .collect()
}

// Porting note: the old crates/ardudeck-sim-engine/src/frame_geometry.rs labeled its
// "hexa X" / "octa X" constants with the angle sets that AP_MotorsMatrix.cpp's
// setup_hexa_matrix / setup_octa_matrix actually assign to MOTOR_FRAME_TYPE_PLUS, not
// MOTOR_FRAME_TYPE_X. FrameType::X here MUST return the real ArduPilot X layout (see
// setup_hexa_matrix@792, setup_octa_matrix@874) and FrameType::Plus the real Plus layout
// (setup_hexa_matrix@779, setup_octa_matrix@858) - do not swap these to make old code
// byte-identical. Task 11 (ardudeck-sim-engine delegation) is responsible for mapping the
// legacy 6/8-motor "X" call sites onto FrameType::Plus so the simulated engine keeps
// producing identical physics; that mapping belongs there, not in this table.
pub fn motor_factors(class: FrameClass, ftype: FrameType) -> Result<Vec<MotorFactor>, FrameError> {
    use FrameClass::*;
    use FrameType::*;
    let flat_specs: Option<&[(f64, f64)]> = match (class, ftype) {
        // AP_MotorsMatrix.cpp setup_quad_matrix, case MOTOR_FRAME_TYPE_X (line 591).
        (Quad, X) => Some(&[(45.0, 1.0), (-135.0, 1.0), (-45.0, -1.0), (135.0, -1.0)]),
        // AP_MotorsMatrix.cpp setup_quad_matrix, case MOTOR_FRAME_TYPE_PLUS (line 580).
        (Quad, Plus) => Some(&[(90.0, 1.0), (-90.0, 1.0), (0.0, -1.0), (180.0, -1.0)]),
        // AP_MotorsMatrix.cpp setup_quad_matrix, case MOTOR_FRAME_TYPE_H (line 688): same
        // angles as X, yaw factors inverted (source comment: "same as X but motors spin in
        // opposite directions").
        (Quad, H) => Some(&[(45.0, -1.0), (-135.0, -1.0), (-45.0, 1.0), (135.0, 1.0)]),
        // AP_MotorsMatrix.cpp setup_quad_matrix, case MOTOR_FRAME_TYPE_V (line 677). Yaw
        // factors are ArduPilot's own thrust-vectoring-derived constants (0.7981), not
        // +-1; they still sum to zero. Do not round these to +-1.
        (Quad, V) => Some(&[(45.0, 0.7981), (-135.0, 1.0), (-45.0, -0.7981), (135.0, -1.0)]),
        // AP_MotorsMatrix.cpp setup_quad_matrix, case MOTOR_FRAME_TYPE_BF_X (line 626).
        (Quad, BetaFlightX) => Some(&[(135.0, -1.0), (45.0, 1.0), (-135.0, 1.0), (-45.0, -1.0)]),

        // AP_MotorsMatrix.cpp setup_hexa_matrix, case MOTOR_FRAME_TYPE_X (line 792).
        (Hexa, X) => Some(&[
            (90.0, -1.0), (-90.0, 1.0), (-30.0, -1.0),
            (150.0, 1.0), (30.0, 1.0), (-150.0, -1.0),
        ]),
        // AP_MotorsMatrix.cpp setup_hexa_matrix, case MOTOR_FRAME_TYPE_PLUS (line 779).
        (Hexa, Plus) => Some(&[
            (0.0, -1.0), (180.0, 1.0), (-120.0, -1.0),
            (60.0, 1.0), (-60.0, 1.0), (120.0, -1.0),
        ]),

        // AP_MotorsMatrix.cpp setup_octa_matrix, case MOTOR_FRAME_TYPE_X (line 874).
        (Octa, X) => Some(&[
            (22.5, -1.0), (-157.5, -1.0), (67.5, 1.0), (157.5, 1.0),
            (-22.5, 1.0), (-112.5, 1.0), (-67.5, -1.0), (112.5, -1.0),
        ]),
        // AP_MotorsMatrix.cpp setup_octa_matrix, case MOTOR_FRAME_TYPE_PLUS (line 858).
        (Octa, Plus) => Some(&[
            (0.0, -1.0), (180.0, -1.0), (45.0, 1.0), (135.0, 1.0),
            (-45.0, 1.0), (-135.0, 1.0), (-90.0, -1.0), (90.0, -1.0),
        ]),

        // AP_MotorsMatrix.cpp setup_deca_matrix, case MOTOR_FRAME_TYPE_X / MOTOR_FRAME_TYPE_CW_X
        // (line 1218; both frame types share this table).
        (Deca, X) => Some(&[
            (18.0, 1.0), (54.0, -1.0), (90.0, 1.0), (126.0, -1.0), (162.0, 1.0),
            (-162.0, -1.0), (-126.0, 1.0), (-90.0, -1.0), (-54.0, 1.0), (-18.0, -1.0),
        ]),

        // SIM_Frame.cpp tri_motors (line 244-248): MOT_1 front-right 60 CCW, MOT_2 front-left
        // -60 CW, MOT_4 rear 180 CCW. The rear motor's yaw comes from the AP_MOTORS_MOT_7
        // tail-tilt servo (frame_controls' Tri ServoMount), not from its own spin direction -
        // cross-checked against AP_MotorsTri.cpp (MOT_1=_thrust_right, MOT_2=_thrust_left,
        // MOT_4=_thrust_rear, lines 105-107), which never differentiates MOT_4's yaw by spin.
        (Tri, X) => Some(&[(60.0, 1.0), (-60.0, -1.0), (180.0, 1.0)]),

        // AP_MotorsSingle.cpp (Copter-4.6.3, lines 97-98): both physical motors (MOT_5, MOT_6)
        // are driven by the same _thrust_out with no yaw-differential term - the real hardware
        // is a co-spinning coaxial pair, but the mixer treats it as a single thrust source with
        // zero motor-yaw authority (all attitude control comes from the 4 vane servos, see
        // frame_controls). Modeled here as one motor entry, angle 0 (on the centerline).
        (SingleCopter, Plus) => Some(&[(0.0, 0.0)]),

        // AP_MotorsTailsitter.cpp (Copter-4.6.3, lines 174-175 for thrust, 213-214 for tilt):
        // _thrust_left/_thrust_right carry only throttle +- roll*0.5, no yaw term; yaw comes
        // entirely from _tilt_left/_tilt_right servo deflection (frame_controls' BiCopter
        // ServoMount). AP_MotorsTailsitter has no MotorFactor-style angle table (it drives
        // SRV_Channel outputs directly), so the 90/-90 angles here are the left/right wingtip
        // positions matching frame_controls' y = +-1 ServoMount placement, not a literal
        // source-file angle constant.
        (BiCopter, X) => Some(&[(90.0, 0.0), (-90.0, 0.0)]),

        _ => None,
    };
    if let Some(specs) = flat_specs {
        return Ok(flat(specs));
    }

    use UpDown::{Down, Up};
    let stacked_specs: Option<&[(f64, f64, UpDown)]> = match (class, ftype) {
        // AP_MotorsMatrix.cpp setup_dodecahexa_matrix, case MOTOR_FRAME_TYPE_X (line 1118).
        // Each pair has an explicit "// ...-top" / "// ...-bottom" source comment; Task 3
        // wrongly flattened this to UpDown::Flat, this corrects it.
        (DodecaHexa, X) => Some(&[
            (30.0, 1.0, Up), (30.0, -1.0, Down),
            (90.0, -1.0, Up), (90.0, 1.0, Down),
            (150.0, 1.0, Up), (150.0, -1.0, Down),
            (-150.0, -1.0, Up), (-150.0, 1.0, Down),
            (-90.0, 1.0, Up), (-90.0, -1.0, Down),
            (-30.0, -1.0, Up), (-30.0, 1.0, Down),
        ]),

        // AP_MotorsMatrix.cpp setup_octaquad_matrix, case MOTOR_FRAME_TYPE_X (line 992).
        // No inline top/bottom comment here (unlike DodecaHexa/Y6B), so Up/Down is inferred
        // from add_motors' loop index i, which add_motors passes as the literal motor_num:
        // the first four array entries become motor_num 0..3 (AP motors 1-4, top) and the
        // last four become motor_num 4..7 (AP motors 5-8, bottom) - ArduPilot's own
        // OctaQuad/X8 convention. Each arm's Up/Down entry is still an exact angle+yaw pair
        // pulled straight from the source array below (unmodified).
        (OctaQuad, X) => Some(&[
            (45.0, 1.0, Up), (-45.0, -1.0, Up), (-135.0, 1.0, Up), (135.0, -1.0, Up),
            (-45.0, 1.0, Down), (45.0, -1.0, Down), (135.0, 1.0, Down), (-135.0, -1.0, Down),
        ]),

        // Angles: SIM_Frame.cpp `y6_motors[]` (line 265-273), the physical arm positions -
        // NOT AP_MotorsMatrix.cpp's MotorDefRaw(roll_fac, pitch_fac), which are mixer
        // authority weights (front pitch_fac 0.5 vs roll_fac 1.0 is a deliberate control
        // over-weighting, not a unit-circle position; atan2 of those is not a geometric
        // angle). Y6 arms are physically at 60/-60/180 degrees.
        // Top/bottom: `y6_motors` MOT_1(60,CCW) pairs with MOT_5(60,CW), MOT_2(-60,CW) with
        // MOT_3(-60,CCW), MOT_4(180,CW) with MOT_6(180,CCW) - matches
        // AP_MotorsMatrix.cpp setup_y6_matrix Y6B (line 1150-1163) comment verbatim: "Y6
        // motor definition with all top motors spinning clockwise, all bottom motors
        // counter clockwise" - CW (yaw -1) = Up, CCW (yaw +1) = Down.
        (Y6, Y6B) => Some(&[
            (60.0, -1.0, Up), (60.0, 1.0, Down),
            (180.0, -1.0, Up), (180.0, 1.0, Down),
            (-60.0, -1.0, Up), (-60.0, 1.0, Down),
        ]),

        // Angles: SIM_Frame.cpp `firefly_motors[]` (line 278-286), same physical arm
        // positions as y6_motors (60/-60/180). No inline top/bottom comment for FireflyY6 in
        // either source file, but `firefly_motors` orders MOT_1/2/3 (all CCW) before
        // MOT_4/5/6 (all CW) - the same first-half/second-half motor-number split used for
        // OctaQuad above - and FireFly Y6 hardware is well known to spin its top/bottom
        // motors opposite to a standard Y6, so CCW (yaw +1) = Up, CW (yaw -1) = Down here.
        (Y6, Y6F) => Some(&[
            (180.0, 1.0, Up), (60.0, 1.0, Up), (-60.0, 1.0, Up),
            (180.0, -1.0, Down), (60.0, -1.0, Down), (-60.0, -1.0, Down),
        ]),

        // AP_MotorsCoax.cpp (Copter-4.6.3, lines 190-191: _thrust_yt_ccw drives MOT_5,
        // _thrust_yt_cw drives MOT_6; lines 94-95 confirm the MOT_5/MOT_6 wiring). Unlike
        // SingleCopter, Coax has two independently-throttled, contra-rotating motors on the
        // same coaxial centerline giving real differential-yaw authority. Up/Down assignment
        // follows source declaration order (MOT_5 first = Up, MOT_6 second = Down), the same
        // first-declared/second-declared convention already used for OctaQuad above - AP's
        // source has no explicit top/bottom comment here.
        (CoaxCopter, Plus) => Some(&[(0.0, 1.0, Up), (0.0, -1.0, Down)]),

        _ => None,
    };
    if let Some(specs) = stacked_specs {
        return Ok(stacked(specs));
    }
    Err(FrameError::UnsupportedCombo(class, ftype))
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct ServoMount {
    /// Where the servo body sits, in the same normalized frame as motors
    /// (multiplied by arm_len downstream). z up-positive.
    pub position: Vec3,
    /// Axis the servo tilts about.
    pub tilt_axis: Vec3,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct VaneMount {
    pub angle_deg: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FrameControls {
    pub servos: Vec<ServoMount>,
    pub vanes: Vec<VaneMount>,
}

// Motors for Tri/Single/Coax/BiCopter come from motor_factors above; this supplies the extra
// actuated parts that don't fit MotorFactor (Tri tail servo, Single/Coax vanes, BiCopter tilt
// servos) - see AP_MotorsTri.cpp AP_MOTORS_CH_TRI_YAW, AP_MotorsSingle.cpp/AP_MotorsCoax.cpp's
// 4 flap servos (MOT_1-4), and AP_MotorsTailsitter.cpp's k_tiltMotorLeft/Right.
pub fn frame_controls(class: FrameClass) -> FrameControls {
    use FrameClass::*;
    match class {
        Tri => FrameControls {
            servos: vec![ServoMount {
                position: Vec3::new(-1.0, 0.0, 0.0),
                tilt_axis: Vec3::new(0.0, 1.0, 0.0),
            }],
            vanes: vec![],
        },
        SingleCopter => FrameControls {
            servos: vec![],
            vanes: (0..4).map(|i| VaneMount { angle_deg: 90.0 * i as f64 }).collect(),
        },
        CoaxCopter => FrameControls {
            servos: vec![],
            vanes: (0..4).map(|i| VaneMount { angle_deg: 90.0 * i as f64 }).collect(),
        },
        BiCopter => FrameControls {
            servos: vec![
                ServoMount { position: Vec3::new(0.0, 1.0, 0.0), tilt_axis: Vec3::new(0.0, 1.0, 0.0) },
                ServoMount { position: Vec3::new(0.0, -1.0, 0.0), tilt_axis: Vec3::new(0.0, 1.0, 0.0) },
            ],
            vanes: vec![],
        },
        _ => FrameControls { servos: vec![], vanes: vec![] },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{FrameClass, FrameType, UpDown};

    fn yaw_sum(v: &[MotorFactor]) -> f64 {
        v.iter().map(|m| m.yaw_factor).sum()
    }

    #[test]
    fn quad_x_matches_stock_sitl() {
        // Verbatim from frame_geometry.rs: MOT_1(45,CCW) 2(-135,CCW) 3(-45,CW) 4(135,CW)
        let m = motor_factors(FrameClass::Quad, FrameType::X).unwrap();
        let expect = [(45.0, 1.0), (-135.0, 1.0), (-45.0, -1.0), (135.0, -1.0)];
        assert_eq!(m.len(), 4);
        for (got, (a, y)) in m.iter().zip(expect) {
            assert_eq!(got.angle_deg, a);
            assert_eq!(got.yaw_factor, y);
            assert_eq!(got.updown, UpDown::Flat);
        }
    }

    #[test]
    fn hexa_x_matches_ardupilot() {
        // AP_MotorsMatrix.cpp setup_hexa_matrix, case MOTOR_FRAME_TYPE_X (line 792).
        let m = motor_factors(FrameClass::Hexa, FrameType::X).unwrap();
        let expect = [
            (90.0, -1.0), (-90.0, 1.0), (-30.0, -1.0),
            (150.0, 1.0), (30.0, 1.0), (-150.0, -1.0),
        ];
        assert_eq!(m.len(), 6);
        for (got, (a, y)) in m.iter().zip(expect) {
            assert_eq!(got.angle_deg, a);
            assert_eq!(got.yaw_factor, y);
        }
    }

    #[test]
    fn hexa_plus_matches_ardupilot() {
        // AP_MotorsMatrix.cpp setup_hexa_matrix, case MOTOR_FRAME_TYPE_PLUS (line 779).
        let m = motor_factors(FrameClass::Hexa, FrameType::Plus).unwrap();
        let expect = [
            (0.0, -1.0), (180.0, 1.0), (-120.0, -1.0),
            (60.0, 1.0), (-60.0, 1.0), (120.0, -1.0),
        ];
        assert_eq!(m.len(), 6);
        for (got, (a, y)) in m.iter().zip(expect) {
            assert_eq!(got.angle_deg, a);
            assert_eq!(got.yaw_factor, y);
        }
    }

    #[test]
    fn octa_x_matches_ardupilot() {
        // AP_MotorsMatrix.cpp setup_octa_matrix, case MOTOR_FRAME_TYPE_X (line 874).
        let m = motor_factors(FrameClass::Octa, FrameType::X).unwrap();
        let expect = [
            (22.5, -1.0), (-157.5, -1.0), (67.5, 1.0), (157.5, 1.0),
            (-22.5, 1.0), (-112.5, 1.0), (-67.5, -1.0), (112.5, -1.0),
        ];
        assert_eq!(m.len(), 8);
        for (got, (a, y)) in m.iter().zip(expect) {
            assert_eq!(got.angle_deg, a);
            assert_eq!(got.yaw_factor, y);
        }
    }

    #[test]
    fn octa_plus_matches_ardupilot() {
        // AP_MotorsMatrix.cpp setup_octa_matrix, case MOTOR_FRAME_TYPE_PLUS (line 858).
        let m = motor_factors(FrameClass::Octa, FrameType::Plus).unwrap();
        let expect = [
            (0.0, -1.0), (180.0, -1.0), (45.0, 1.0), (135.0, 1.0),
            (-45.0, 1.0), (-135.0, 1.0), (-90.0, -1.0), (90.0, -1.0),
        ];
        assert_eq!(m.len(), 8);
        for (got, (a, y)) in m.iter().zip(expect) {
            assert_eq!(got.angle_deg, a);
            assert_eq!(got.yaw_factor, y);
        }
    }

    #[test]
    fn balanced_and_sized_for_standard_classes() {
        // (class, type, motor_count) for every standard-matrix combo ported so far.
        let combos = [
            (FrameClass::Quad, FrameType::X, 4),
            (FrameClass::Quad, FrameType::Plus, 4),
            (FrameClass::Quad, FrameType::H, 4),
            (FrameClass::Quad, FrameType::V, 4),
            (FrameClass::Quad, FrameType::BetaFlightX, 4),
            (FrameClass::Hexa, FrameType::X, 6),
            (FrameClass::Hexa, FrameType::Plus, 6),
            (FrameClass::Octa, FrameType::X, 8),
            (FrameClass::Octa, FrameType::Plus, 8),
            (FrameClass::Deca, FrameType::X, 10),
            (FrameClass::DodecaHexa, FrameType::X, 12),
        ];
        for (c, t, n) in combos {
            let m = motor_factors(c, t).unwrap();
            assert_eq!(m.len(), n, "{:?}/{:?} motor count", c, t);
            assert!(yaw_sum(&m).abs() < 1e-9, "{:?}/{:?} yaw not balanced", c, t);
        }
    }

    #[test]
    fn unsupported_combo_errors() {
        assert!(motor_factors(FrameClass::Quad, FrameType::Y6B).is_err());
    }

    #[test]
    fn octaquad_x_is_four_arms_stacked() {
        let m = motor_factors(FrameClass::OctaQuad, FrameType::X).unwrap();
        assert_eq!(m.len(), 8);
        let ups = m.iter().filter(|x| x.updown == UpDown::Up).count();
        let downs = m.iter().filter(|x| x.updown == UpDown::Down).count();
        assert_eq!((ups, downs), (4, 4));
        // Each arm has an Up+Down sharing the same angle with opposite spin.
        for up in m.iter().filter(|x| x.updown == UpDown::Up) {
            let mate = m.iter().find(|d| d.updown == UpDown::Down && d.angle_deg == up.angle_deg);
            assert!(mate.is_some(), "no coax mate at {}", up.angle_deg);
            assert_eq!(mate.unwrap().yaw_factor, -up.yaw_factor);
        }
        assert!(m.iter().map(|x| x.yaw_factor).sum::<f64>().abs() < 1e-9);
    }

    #[test]
    fn y6b_has_three_arms_six_motors() {
        let m = motor_factors(FrameClass::Y6, FrameType::Y6B).unwrap();
        assert_eq!(m.len(), 6);
        assert_eq!(m.iter().filter(|x| x.updown == UpDown::Up).count(), 3);
        assert_eq!(m.iter().filter(|x| x.updown == UpDown::Down).count(), 3);
        // Physical Y6 arm angle per SIM_Frame.cpp y6_motors (line 265), not the AP_MotorsMatrix
        // mixer's atan2(roll_fac, pitch_fac), which is not a geometric angle.
        assert!(m.iter().any(|x| x.angle_deg == 60.0));
    }

    #[test]
    fn y6f_has_three_arms_six_motors() {
        let m = motor_factors(FrameClass::Y6, FrameType::Y6F).unwrap();
        assert_eq!(m.len(), 6);
        assert_eq!(m.iter().filter(|x| x.updown == UpDown::Up).count(), 3);
        assert_eq!(m.iter().filter(|x| x.updown == UpDown::Down).count(), 3);
        assert!(m.iter().any(|x| x.angle_deg == 60.0));
    }

    #[test]
    fn tri_has_three_motors_and_a_tail_servo() {
        let m = motor_factors(FrameClass::Tri, FrameType::X).unwrap();
        assert_eq!(m.len(), 3);
        let c = frame_controls(FrameClass::Tri);
        assert_eq!(c.servos.len(), 1); // tail yaw servo
        assert!(c.vanes.is_empty());
    }

    #[test]
    fn singlecopter_has_one_motor_and_four_vanes() {
        let m = motor_factors(FrameClass::SingleCopter, FrameType::Plus).unwrap();
        assert_eq!(m.len(), 1);
        let c = frame_controls(FrameClass::SingleCopter);
        assert_eq!(c.vanes.len(), 4);
    }

    #[test]
    fn bicopter_has_two_tilt_servos() {
        let m = motor_factors(FrameClass::BiCopter, FrameType::X).unwrap();
        assert_eq!(m.len(), 2);
        let c = frame_controls(FrameClass::BiCopter);
        assert_eq!(c.servos.len(), 2);
    }

    #[test]
    fn dodecahexa_x_is_six_arms_stacked() {
        // Task 3 wrongly left this Flat; DodecaHexa is coax (setup_dodecahexa_matrix@1118
        // has explicit "// forward-right-top" / "// ...-bottom" comments per motor).
        let m = motor_factors(FrameClass::DodecaHexa, FrameType::X).unwrap();
        assert_eq!(m.len(), 12);
        let ups = m.iter().filter(|x| x.updown == UpDown::Up).count();
        let downs = m.iter().filter(|x| x.updown == UpDown::Down).count();
        assert_eq!((ups, downs), (6, 6));
        for up in m.iter().filter(|x| x.updown == UpDown::Up) {
            let mate = m.iter().find(|d| d.updown == UpDown::Down && d.angle_deg == up.angle_deg);
            assert!(mate.is_some(), "no coax mate at {}", up.angle_deg);
            assert_eq!(mate.unwrap().yaw_factor, -up.yaw_factor);
        }
        assert!(m.iter().map(|x| x.yaw_factor).sum::<f64>().abs() < 1e-9);
    }
}
