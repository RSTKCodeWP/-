//! ArduDeck procedural frame generator: build spec -> render-agnostic blueprint
//! and physics geometry, from one shared motor-factor table.

pub mod adapters;
pub mod blueprint;
pub mod math;
pub mod physics;
pub mod spec;
pub mod tables;
pub mod types;
#[cfg(feature = "wasm")]
pub mod wasm;

pub use adapters::{from_build, from_preset, from_sitl_custom_frame, from_vehicle_profile, BuildInput, SitlCustomFrameInput, VehicleProfileInput};
pub use blueprint::{build_blueprint, Aabb, FrameBlueprint, MaterialHint, Part, PartDims, PartKind, PartRole, Spin};
pub use math::{Mat3, Quat, Vec3};
pub use physics::{physics_geometry, MotorMount, PhysicsGeometry};
pub use spec::{defaults_for, size_class_from_diagonal_mm, FrameGeomSpec, Masses, MotorStator, PlateSpec, PropSpec, SizeClass, SpecDefaults};
pub use tables::{frame_controls, motor_factors, FrameControls, FrameError, ServoMount, VaneMount};
pub use types::{EscLayout, FrameClass, FrameType, MotorFactor, UpDown};
