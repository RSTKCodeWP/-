"""Tests for the observable replay-dump CLI (Task 1.7)."""

from pathlib import Path

from hades.cli.main import main
from hades.cli.replay_dump import run_replay_dump

FIXTURES = Path(__file__).parent.parent / "fixtures"
CLIP = FIXTURES / "clip_2s.mp4"
SRT = FIXTURES / "clip_2s.srt"


def test_produces_one_image_per_frame(tmp_path):
    n = run_replay_dump(CLIP, SRT, tmp_path)
    images = sorted(tmp_path.glob("*.png"))
    assert n == 20  # fixture has 20 frames
    assert len(images) == 20


def test_images_are_nonempty_and_named_by_seq(tmp_path):
    run_replay_dump(CLIP, SRT, tmp_path)
    images = sorted(tmp_path.glob("*.png"))
    assert images[0].name == "frame_00000.png"
    assert images[-1].name == "frame_00019.png"
    assert all(img.stat().st_size > 0 for img in images)


def test_runs_without_telemetry(tmp_path):
    # Video-only: must still dump frames (telemetry overlay just says "no pose").
    n = run_replay_dump(CLIP, None, tmp_path)
    assert n == 20
    assert len(list(tmp_path.glob("*.png"))) == 20


def test_overlaid_frame_differs_from_raw(tmp_path):
    # The overlay must actually draw onto the frame (not a pass-through copy).
    from PIL import Image

    run_replay_dump(CLIP, SRT, tmp_path)
    import av

    with av.open(str(CLIP)) as c:
        raw = next(c.decode(video=0)).to_ndarray(format="rgb24")
    out = Image.open(tmp_path / "frame_00000.png").convert("RGB")
    import numpy as np

    assert not np.array_equal(np.asarray(out), raw)  # overlay changed pixels


def test_stride_samples_every_nth_frame(tmp_path):
    n = run_replay_dump(CLIP, SRT, tmp_path, stride=5)
    # 20 frames, every 5th -> seq 0,5,10,15 = 4 images.
    assert n == 4
    names = sorted(p.name for p in tmp_path.glob("*.png"))
    assert names == ["frame_00000.png", "frame_00005.png", "frame_00010.png", "frame_00015.png"]


def test_max_frames_caps_output(tmp_path):
    n = run_replay_dump(CLIP, SRT, tmp_path, max_frames=3)
    assert n == 3
    assert len(list(tmp_path.glob("*.png"))) == 3


def test_main_dispatches_replay_dump_subcommand(tmp_path):
    rc = main(["replay-dump", str(CLIP), "--telemetry", str(SRT), "--out", str(tmp_path)])
    assert rc == 0
    assert len(list(tmp_path.glob("*.png"))) == 20


def test_main_unknown_subcommand_errors():
    rc = main(["does-not-exist"])
    assert rc != 0


def test_help_exits_zero():
    # argparse exits SystemExit(0) on --help; that success must not become an error.
    assert main(["--help"]) == 0


def test_subcommand_help_exits_zero():
    assert main(["replay-dump", "--help"]) == 0
