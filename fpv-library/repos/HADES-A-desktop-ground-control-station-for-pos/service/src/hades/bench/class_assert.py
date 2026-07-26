"""Export-time guard: the exported model is single-class with `person` at index 0.

`hades.detect.postprocess.decode_yolo` reads the person score at output row
`4 + PERSON_CLASS_INDEX` (= row 4). The fine-tuned model MUST therefore be single-class
with `person` at index 0, or the decode silently reads the wrong score row and the whole
detector goes quietly blind. This is the assertion the postprocess docstring asks for —
run it at export time so a mislabeled/multi-class checkpoint fails loudly here, not in the
field.
"""

from __future__ import annotations


def assert_single_person_class(names: dict[int, str]) -> None:
    """Raise unless `names` is exactly `{0: 'person'}` (case-insensitive on the name).

    `names` is Ultralytics' `model.names` — `{index: class_name}`. We require a single class
    named `person` at index 0 so the `PERSON_CLASS_INDEX = 0` decode contract holds.
    """
    if len(names) != 1:
        raise ValueError(
            f"exported model must be single-class for the v1 person detector; got {names}"
        )
    if 0 not in names:
        raise ValueError(f"exported model's single class must be at index 0; got {names}")
    if names[0].strip().lower() != "person":
        raise ValueError(
            f"exported model's class at index 0 must be 'person'; got {names[0]!r}"
        )
