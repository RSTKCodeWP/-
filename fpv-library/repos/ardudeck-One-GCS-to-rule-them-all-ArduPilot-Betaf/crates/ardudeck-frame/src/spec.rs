use serde::{Deserialize, Serialize};
use crate::math::Vec3;
use crate::types::{EscLayout, FrameClass, FrameType};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SizeClass {
    Whoop,
    Micro,
    Five,
    Seven,
    Ten,
    Heavy,
}

pub fn size_class_from_diagonal_mm(d: f64) -> SizeClass {
    // Diagonal in mm. Thresholds are deliberately coarse; they only pick default
    // component dimensions when the input omits them.
    match d {
        x if x < 90.0 => SizeClass::Whoop,
        x if x < 120.0 => SizeClass::Micro,
        x if x < 160.0 => SizeClass::Five,
        x if x < 230.0 => SizeClass::Seven,
        x if x < 400.0 => SizeClass::Ten,
        _ => SizeClass::Heavy,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct SpecDefaults {
    pub arm_width_mm: f64,
    pub arm_thick_mm: f64,
    pub stator_dia_mm: f64,
    pub stator_height_mm: f64,
    pub stack_height_mm: f64,
    pub esc_layout: EscLayout,
}

pub fn defaults_for(size: SizeClass) -> SpecDefaults {
    use SizeClass::*;
    match size {
        Whoop => SpecDefaults { arm_width_mm: 4.0, arm_thick_mm: 2.0, stator_dia_mm: 8.5, stator_height_mm: 3.0, stack_height_mm: 12.0, esc_layout: EscLayout::Stack4in1 },
        Micro => SpecDefaults { arm_width_mm: 5.0, arm_thick_mm: 3.0, stator_dia_mm: 14.0, stator_height_mm: 5.0, stack_height_mm: 16.0, esc_layout: EscLayout::Stack4in1 },
        Five => SpecDefaults { arm_width_mm: 7.0, arm_thick_mm: 4.0, stator_dia_mm: 23.0, stator_height_mm: 7.0, stack_height_mm: 30.0, esc_layout: EscLayout::Stack4in1 },
        Seven => SpecDefaults { arm_width_mm: 9.0, arm_thick_mm: 5.0, stator_dia_mm: 28.0, stator_height_mm: 7.0, stack_height_mm: 30.0, esc_layout: EscLayout::Stack4in1 },
        Ten => SpecDefaults { arm_width_mm: 12.0, arm_thick_mm: 6.0, stator_dia_mm: 31.0, stator_height_mm: 15.0, stack_height_mm: 30.0, esc_layout: EscLayout::ArmMounted },
        Heavy => SpecDefaults { arm_width_mm: 20.0, arm_thick_mm: 8.0, stator_dia_mm: 40.0, stator_height_mm: 20.0, stack_height_mm: 40.0, esc_layout: EscLayout::ArmMounted },
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MotorStator {
    pub dia_mm: f64,
    pub height_mm: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PropSpec {
    pub radius_mm: f64,
    pub pitch_in: f64,
    pub blades: u8,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PlateSpec {
    pub len_mm: f64,
    pub width_mm: f64,
    pub thick_mm: f64,
    pub stack_height_mm: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Masses {
    pub frame_g: f64,
    pub per_motor_g: f64,
    pub per_prop_g: f64,
    pub per_esc_g: f64,
    pub battery_g: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FrameGeomSpec {
    pub class: FrameClass,
    pub frame_type: FrameType,
    pub motor_count: u32,
    pub arm_len_mm: f64,
    pub arm_width_mm: f64,
    pub arm_thick_mm: f64,
    pub plate: PlateSpec,
    pub motor_stator: MotorStator,
    pub prop: PropSpec,
    pub esc_layout: EscLayout,
    pub masses: Masses,
    pub cog_offset_mm: Vec3,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn size_class_thresholds() {
        assert_eq!(size_class_from_diagonal_mm(65.0), SizeClass::Whoop);
        assert_eq!(size_class_from_diagonal_mm(127.0), SizeClass::Five);
        assert_eq!(size_class_from_diagonal_mm(178.0), SizeClass::Seven);
        assert_eq!(size_class_from_diagonal_mm(600.0), SizeClass::Heavy);
    }

    #[test]
    fn five_inch_defaults_are_reasonable() {
        let d = defaults_for(SizeClass::Five);
        assert!(d.stator_dia_mm >= 22.0 && d.stator_dia_mm <= 24.0); // ~2207
        assert_eq!(d.esc_layout, EscLayout::Stack4in1);
    }
}
