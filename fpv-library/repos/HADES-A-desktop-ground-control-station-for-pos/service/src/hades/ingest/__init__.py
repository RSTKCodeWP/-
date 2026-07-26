"""Ingestion: frame and telemetry sources that feed the pipeline.

`FrameSource` yields `Frame(frame, timestamp, seq)`; `TelemetrySource` yields
`Pose` time-synced to frames by `seq` (the frame_id). One interface per source,
swappable impls (synthetic / recorded file / live).
"""
