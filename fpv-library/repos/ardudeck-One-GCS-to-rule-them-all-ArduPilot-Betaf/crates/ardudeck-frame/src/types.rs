use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FrameClass {
    Quad,
    Hexa,
    Octa,
    OctaQuad,
    Y6,
    Tri,
    Deca,
    DodecaHexa,
    SingleCopter,
    CoaxCopter,
    BiCopter,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FrameType {
    Plus,
    X,
    V,
    H,
    Deadcat,
    BetaFlightX,
    DjiX,
    ClockwiseX,
    Y6B,
    Y6F,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum UpDown {
    Up,
    Down,
    Flat,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EscLayout {
    Stack4in1,
    ArmMounted,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct MotorFactor {
    pub angle_deg: f64,
    pub yaw_factor: f64,
    pub updown: UpDown,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn framet_serde_snake_case() {
        let j = serde_json::to_string(&FrameType::BetaFlightX).unwrap();
        assert_eq!(j, "\"beta_flight_x\"");
        let d: FrameClass = serde_json::from_str("\"octa_quad\"").unwrap();
        assert_eq!(d, FrameClass::OctaQuad);
    }

    #[test]
    fn motor_factor_constructs() {
        let m = MotorFactor { angle_deg: 45.0, yaw_factor: 1.0, updown: UpDown::Flat };
        assert_eq!(m.angle_deg, 45.0);
    }
}
