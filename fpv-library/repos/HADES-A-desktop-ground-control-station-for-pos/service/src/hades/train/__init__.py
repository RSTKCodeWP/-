"""HADES detection-model fine-tuning (Phase 2.5).

The committed, reproducible *training* code — dataset normalization, the training
config, and the cluster training entry. Trained weights are a versioned artifact, NOT
committed (DESIGN.md §4). Developed + unit-tested locally on the Mac (fast red→green);
the real multi-hour train runs on the NCShare H200 cluster.

Heavy deps (ultralytics, torch) are in the optional `train` dependency-group and are
lazy-imported, so this package imports — and its pure logic unit-tests — on a machine
without the ML stack (mirrors the `bench` group pattern).
"""
