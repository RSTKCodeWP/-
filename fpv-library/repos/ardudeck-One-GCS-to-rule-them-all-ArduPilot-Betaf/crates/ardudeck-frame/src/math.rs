use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Vec3 {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Vec3 {
    pub fn new(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }
    pub fn add(self, o: Vec3) -> Vec3 {
        Vec3::new(self.x + o.x, self.y + o.y, self.z + o.z)
    }
    pub fn scale(self, s: f64) -> Vec3 {
        Vec3::new(self.x * s, self.y * s, self.z * s)
    }
    pub fn dot(self, o: Vec3) -> f64 {
        self.x * o.x + self.y * o.y + self.z * o.z
    }
    pub fn norm(self) -> f64 {
        self.dot(self).sqrt()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Quat {
    pub w: f64,
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Quat {
    pub fn identity() -> Self {
        Self { w: 1.0, x: 0.0, y: 0.0, z: 0.0 }
    }

    /// Unit quaternion for a rotation of `angle` radians about `axis`. `axis`
    /// need not be normalized; a zero-length axis yields the identity.
    pub fn from_axis_angle(axis: Vec3, angle: f64) -> Self {
        let n = axis.norm();
        if n < 1e-12 {
            return Self::identity();
        }
        let h = angle * 0.5;
        let s = h.sin() / n;
        Self { w: h.cos(), x: axis.x * s, y: axis.y * s, z: axis.z * s }
    }

    /// Hamilton product `self * o`. When rotating a vector, `(a * b)` applies
    /// `b` first, then `a` (v' = a b v b* a*).
    pub fn mul(self, o: Quat) -> Quat {
        Quat {
            w: self.w * o.w - self.x * o.x - self.y * o.y - self.z * o.z,
            x: self.w * o.x + self.x * o.w + self.y * o.z - self.z * o.y,
            y: self.w * o.y - self.x * o.z + self.y * o.w + self.z * o.x,
            z: self.w * o.z + self.x * o.y - self.y * o.x + self.z * o.w,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Mat3(pub [[f64; 3]; 3]);

impl Mat3 {
    pub fn zero() -> Self {
        Mat3([[0.0; 3]; 3])
    }
    pub fn add(self, o: Mat3) -> Mat3 {
        let mut r = Mat3::zero();
        for i in 0..3 {
            for j in 0..3 {
                r.0[i][j] = self.0[i][j] + o.0[i][j];
            }
        }
        r
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vec3_ops() {
        let a = Vec3::new(1.0, 2.0, 2.0);
        assert_eq!(a.norm(), 3.0);
        assert_eq!(a.scale(2.0), Vec3::new(2.0, 4.0, 4.0));
        assert_eq!(a.add(Vec3::new(1.0, 0.0, 0.0)), Vec3::new(2.0, 2.0, 2.0));
        assert_eq!(a.dot(Vec3::new(1.0, 0.0, 0.0)), 1.0);
    }

    #[test]
    fn mat3_add() {
        let z = Mat3::zero();
        let m = Mat3([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]);
        assert_eq!(z.add(m), m);
    }

    #[test]
    fn axis_angle_is_unit_and_composes() {
        let q = Quat::from_axis_angle(Vec3::new(0.0, 0.0, 2.0), std::f64::consts::FRAC_PI_2);
        let mag = (q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z).sqrt();
        assert!((mag - 1.0).abs() < 1e-12);
        // Half of pi/2 -> component sin(pi/4) on the (normalized) z axis.
        assert!((q.z - std::f64::consts::FRAC_1_SQRT_2).abs() < 1e-12);
        assert!(q.x.abs() < 1e-12 && q.y.abs() < 1e-12);

        // Identity is the multiplicative unit.
        let id = Quat::identity();
        assert_eq!(q.mul(id), q);
        assert_eq!(id.mul(q), q);
    }

    #[test]
    fn zero_axis_is_identity() {
        assert_eq!(Quat::from_axis_angle(Vec3::new(0.0, 0.0, 0.0), 1.0), Quat::identity());
    }
}
