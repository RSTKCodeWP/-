//! Manual test runnable: build any frame preset and dump its physics + blueprint.
//! Usage: cargo run --example dump_frame -- <class> <type>
//! e.g.:  cargo run --example dump_frame -- octa x

use ardudeck_frame::{build_blueprint, from_preset, physics_geometry, FrameClass, FrameType};

const CLASSES: &[FrameClass] = &[
    FrameClass::Quad,
    FrameClass::Hexa,
    FrameClass::Octa,
    FrameClass::OctaQuad,
    FrameClass::Y6,
    FrameClass::Tri,
    FrameClass::Deca,
    FrameClass::DodecaHexa,
    FrameClass::SingleCopter,
    FrameClass::CoaxCopter,
    FrameClass::BiCopter,
];

const TYPES: &[FrameType] = &[
    FrameType::Plus,
    FrameType::X,
    FrameType::V,
    FrameType::H,
    FrameType::Deadcat,
    FrameType::BetaFlightX,
    FrameType::DjiX,
    FrameType::ClockwiseX,
    FrameType::Y6B,
    FrameType::Y6F,
];

// Reflect the enums' own serde rename rather than hand-typing snake_case, so
// this list can't drift from what parse_class/parse_type actually accept.
fn variant_name<T: serde::Serialize>(v: &T) -> String {
    serde_json::to_string(v).unwrap().trim_matches('"').to_string()
}

fn usage() {
    let classes: Vec<String> = CLASSES.iter().map(variant_name).collect();
    let types: Vec<String> = TYPES.iter().map(variant_name).collect();
    eprintln!("usage: dump_frame <class> <type>");
    eprintln!("  classes: {}", classes.join(", "));
    eprintln!("  types:   {}", types.join(", "));
}

fn parse_class(s: &str) -> Option<FrameClass> {
    serde_json::from_str(&format!("\"{s}\"")).ok()
}

fn parse_type(s: &str) -> Option<FrameType> {
    serde_json::from_str(&format!("\"{s}\"")).ok()
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 2 {
        eprintln!("error: expected exactly 2 arguments (class, type), got {}", args.len());
        usage();
        std::process::exit(1);
    }
    let (class_s, type_s) = (&args[0], &args[1]);

    let class = match parse_class(class_s) {
        Some(c) => c,
        None => {
            eprintln!("error: unknown frame class '{class_s}'");
            usage();
            std::process::exit(1);
        }
    };
    let ftype = match parse_type(type_s) {
        Some(t) => t,
        None => {
            eprintln!("error: unknown frame type '{type_s}'");
            usage();
            std::process::exit(1);
        }
    };

    let spec = match from_preset(class, ftype) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("error: {e:?}");
            usage();
            std::process::exit(1);
        }
    };

    let g = physics_geometry(&spec);
    let bp = build_blueprint(&spec);

    println!("motor_count: {}", g.motors.len());
    println!("com: [{:.6}, {:.6}, {:.6}]", g.com.x, g.com.y, g.com.z);
    println!(
        "inertia_diag: [{:.6}, {:.6}, {:.6}]",
        g.inertia.0[0][0], g.inertia.0[1][1], g.inertia.0[2][2]
    );
    println!("{}", serde_json::to_string_pretty(&bp).unwrap());
}
