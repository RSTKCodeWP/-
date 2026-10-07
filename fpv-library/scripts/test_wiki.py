#!/usr/bin/env python3
"""Dossier pages only repeat what README and manifests already say."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fpv_lib.wiki import (  # noqa: E402
    audience_from_text,
    build_dossier,
    classify_heading,
    exhibition_hall,
    parse_readme,
    render_project,
)


README = textwrap.dedent(
    """\
    # Steer

    iOS app for driving a remote controlled car from an iPhone with an IP camera FPV stream.

    ## Features

    - FPV video via RTSP
    - Dual joystick

    ## Install

    Open `Steer.xcodeproj` in Xcode.

    ## Requirements

    iOS 14 and an IP camera.
    """
)


class ParseTests(unittest.TestCase):
    def test_extracts_sections_without_adding_commands(self) -> None:
        parsed = parse_readme(README)
        self.assertEqual(parsed["title"], "Steer")
        self.assertIn("iOS app", parsed["idea"])
        self.assertEqual(parsed["feature_bullets"], ["FPV video via RTSP", "Dual joystick"])
        joined = "\n".join(parsed["buckets"]["instruction"])
        self.assertIn("Steer.xcodeproj", joined)
        self.assertNotIn("npm install", joined)
        self.assertNotIn("pio run", joined)

    def test_missing_instruction_stays_missing(self) -> None:
        parsed = parse_readme("# Widget\n\nA small OSD font.\n")
        self.assertEqual(parsed["buckets"]["instruction"], [])
        self.assertIn("OSD font", parsed["idea"])

    def test_heading_kinds(self) -> None:
        self.assertEqual(classify_heading("Getting Started"), "instruction")
        self.assertEqual(classify_heading("Інструкції по збірці"), "instruction")
        self.assertEqual(classify_heading("Инструкции по сборке"), "instruction")
        self.assertEqual(classify_heading("Для кого це"), "audience")
        self.assertIsNone(classify_heading("Changelog"))

    def test_shell_comments_inside_fences_stay_in_the_instruction(self) -> None:
        parsed = parse_readme(
            textwrap.dedent(
                """\
                # Tool

                ## Build

                ```bash
                # install deps
                make
                ```

                ## License

                MIT
                """
            )
        )
        joined = "\n".join(parsed["buckets"]["instruction"])
        self.assertIn("# install deps", joined)
        self.assertIn("make", joined)
        self.assertEqual(joined.count("```") % 2, 0)
        self.assertNotIn("# install deps", "\n".join(parsed["buckets"]["license"]))


class AudienceTests(unittest.TestCase):
    def test_marker_is_the_word_that_matched(self) -> None:
        found = audience_from_text("Ground station for MAVLink missions")
        labels = dict(found)
        self.assertIn("Оператор наземної станції", labels)
        self.assertEqual(labels["Оператор наземної станції"], "ground station")

    def test_other_catalog_uses_path_word_for_hall(self) -> None:
        hall, marker = exhibition_hall(
            {
                "path": "SkySweep32-ESP32-Drone-Detector",
                "description": "",
                "categories": ["other"],
            },
            "SkySweep32",
            "passive scanner",
        )
        self.assertEqual(hall, "detection")
        self.assertEqual(marker, "detector")

    def test_specific_catalog_category_is_kept(self) -> None:
        hall, marker = exhibition_hall(
            {
                "path": "something-detector",
                "description": "",
                "categories": ["gcs"],
            },
            "Deck",
            "",
        )
        self.assertEqual(hall, "gcs")
        self.assertEqual(marker, "")

    def test_generic_fpv_is_not_an_audience(self) -> None:
        self.assertEqual(audience_from_text("just an fpv repo"), [])


class RenderTests(unittest.TestCase):
    def test_card_quotes_readme_and_refuses_fake_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "Steer-iOS"
            project.mkdir()
            (project / "README.md").write_text(README, encoding="utf-8")
            (project / "package.json").write_text(
                '{"scripts":{"start":"node index.js"},"dependencies":{"ws":"1.0.0"}}',
                encoding="utf-8",
            )
            dossier = build_dossier(
                {
                    "source": "johnboiles/Steer",
                    "path": "Steer-iOS",
                    "description": "iOS RC car with FPV",
                    "categories": ["gcs"],
                    "verdict": "keep",
                    "stars": 12,
                    "topics": ["fpv", "ios"],
                },
                root,
            )
            self.assertIsNotNone(dossier)
            page = render_project(dossier, "johnboiles__Steer")
        self.assertIn("## Інструкція", page)
        self.assertIn("Steer.xcodeproj", page)
        self.assertIn("## Для чого", page)
        self.assertIn("iOS RC car with FPV", page)
        self.assertIn("`start`", page)
        self.assertNotIn("npm install", page)
        self.assertNotIn("git clone", page)

    def test_empty_readme_does_not_invent_a_manual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "bare"
            project.mkdir()
            (project / "main.py").write_text("print(1)\n", encoding="utf-8")
            dossier = build_dossier(
                {"source": "acme/bare", "path": "bare", "verdict": "watch", "categories": ["other"]},
                root,
            )
            page = render_project(dossier, "acme__bare")
        self.assertIn("Окремого розділу Install", page)
        self.assertIn("У джерелах цього репозиторію цього немає.", page)
        self.assertNotIn("pip install", page)


if __name__ == "__main__":
    unittest.main()
