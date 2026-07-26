"""Tracking: persistent IDs over the stateless detector (DESIGN.md §1, Task 3.x).

`ByteTracker` (Task 3.1) is a from-scratch numpy ByteTrack — two-stage association,
constant-velocity Kalman, lost-buffer with no ID resurrection. `GMC` (Task 3.2) is the
image ego-motion estimator that warps track predictions before association so a moving
camera does not break IoU matching. Both are torch-free by design.
"""
