//! Prints a FrameBlueprint (+ motor count) as one JSON object on stdout, for
//! non-Rust callers (e.g. the desktop app's main process) to shell out to.
//!
//! Two modes:
//!   frame_blueprint <class> <type>        e.g. frame_blueprint octa x   (preset)
//!   frame_blueprint --spec <BuildInput>   a JSON BuildInput describing the
//!                                         real launched frame / vehicle profile
//!
//! Always exits 0 and always prints JSON, even on bad input - callers only
//! need to parse stdout, never branch on exit code or read stderr.

use ardudeck_frame::{build_blueprint, from_build, from_preset, physics_geometry, BuildInput, FrameClass, FrameType};
use serde::Serialize;

#[derive(Serialize)]
struct Output<'a> {
    #[serde(rename = "motorCount")]
    motor_count: usize,
    blueprint: &'a ardudeck_frame::FrameBlueprint,
}

#[derive(Serialize)]
struct ErrorOutput {
    error: String,
}

fn parse_class(s: &str) -> Option<FrameClass> {
    serde_json::from_str(&format!("\"{s}\"")).ok()
}

fn parse_type(s: &str) -> Option<FrameType> {
    serde_json::from_str(&format!("\"{s}\"")).ok()
}

fn print_error(msg: impl Into<String>) {
    println!("{}", serde_json::to_string(&ErrorOutput { error: msg.into() }).unwrap());
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    // --spec <json>: build from the real launched frame / vehicle profile.
    if args.first().map(String::as_str) == Some("--spec") {
        let Some(json) = args.get(1) else {
            print_error("--spec requires a JSON BuildInput argument");
            return;
        };
        let build: BuildInput = match serde_json::from_str(json) {
            Ok(b) => b,
            Err(e) => {
                print_error(format!("invalid BuildInput JSON: {e}"));
                return;
            }
        };
        let spec = from_build(&build);
        emit(&spec);
        return;
    }

    // <class> <type>: preset.
    if args.len() != 2 {
        print_error(format!("expected <class> <type> or --spec <json>, got {} args", args.len()));
        return;
    }
    let (class_s, type_s) = (&args[0], &args[1]);

    let class = match parse_class(class_s) {
        Some(c) => c,
        None => {
            print_error(format!("unknown frame class '{class_s}'"));
            return;
        }
    };
    let ftype = match parse_type(type_s) {
        Some(t) => t,
        None => {
            print_error(format!("unknown frame type '{type_s}'"));
            return;
        }
    };

    let spec = match from_preset(class, ftype) {
        Ok(s) => s,
        Err(e) => {
            print_error(format!("{e:?}"));
            return;
        }
    };
    emit(&spec);
}

fn emit(spec: &ardudeck_frame::FrameGeomSpec) {
    let blueprint = build_blueprint(spec);
    let motor_count = physics_geometry(spec).motors.len();
    let out = Output { motor_count, blueprint: &blueprint };
    println!("{}", serde_json::to_string(&out).unwrap());
}
