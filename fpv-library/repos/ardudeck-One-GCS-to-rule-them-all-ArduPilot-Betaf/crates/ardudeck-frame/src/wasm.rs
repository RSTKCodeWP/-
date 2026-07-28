#![cfg(feature = "wasm")]

use wasm_bindgen::prelude::*;
use crate::adapters::{from_preset, from_vehicle_profile, VehicleProfileInput};
use crate::blueprint::build_blueprint;
use crate::physics::physics_geometry;
use crate::types::{FrameClass, FrameType};

fn parse2(class_json: &str, type_json: &str) -> Result<(FrameClass, FrameType), String> {
    let c: FrameClass = serde_json::from_str(class_json).map_err(|e| e.to_string())?;
    let t: FrameType = serde_json::from_str(type_json).map_err(|e| e.to_string())?;
    Ok((c, t))
}

fn err_json(msg: String) -> String {
    format!("{{\"error\":{}}}", serde_json::to_string(&msg).unwrap_or_else(|_| "\"error\"".into()))
}

#[wasm_bindgen]
pub fn blueprint_from_preset(class_json: &str, type_json: &str) -> String {
    match parse2(class_json, type_json).and_then(|(c, t)| from_preset(c, t).map_err(|e| format!("{:?}", e))) {
        Ok(spec) => serde_json::to_string(&build_blueprint(&spec)).unwrap_or_else(|e| err_json(e.to_string())),
        Err(e) => err_json(e),
    }
}

#[wasm_bindgen]
pub fn blueprint_from_vehicle_profile(profile_json: &str, class_json: &str, type_json: &str) -> String {
    let parsed = (|| {
        let profile: VehicleProfileInput = serde_json::from_str(profile_json).map_err(|e| e.to_string())?;
        let (c, t) = parse2(class_json, type_json)?;
        Ok::<_, String>((profile, c, t))
    })();
    match parsed {
        Ok((p, c, t)) => serde_json::to_string(&build_blueprint(&from_vehicle_profile(&p, c, t))).unwrap_or_else(|e| err_json(e.to_string())),
        Err(e) => err_json(e),
    }
}

#[wasm_bindgen]
pub fn physics_from_preset(class_json: &str, type_json: &str) -> String {
    match parse2(class_json, type_json).and_then(|(c, t)| from_preset(c, t).map_err(|e| format!("{:?}", e))) {
        Ok(spec) => serde_json::to_string(&physics_geometry(&spec)).unwrap_or_else(|e| err_json(e.to_string())),
        Err(e) => err_json(e),
    }
}
