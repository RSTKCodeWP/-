"""Phase 1.5 latency spike — CoreML export + ANE benchmark.

This package is a **spike**, not part of the runtime pipeline (DESIGN.md §1). It
exists to bound which detection input resolutions can hold the ≥10fps gate on the
field-laptop floor (MacBook Air M4), so Phase 2.5 can pick the final resolution
against fine-tuned recall. Heavy ML deps (`ultralytics`, `coremltools`) live in the
optional `bench` dependency-group and are imported lazily inside functions, so this
package imports cleanly on a machine that only has the core service deps.
"""
