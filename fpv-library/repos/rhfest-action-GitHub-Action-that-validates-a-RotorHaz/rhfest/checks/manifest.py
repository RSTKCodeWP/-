"""Manifest check module."""

import json
from pathlib import Path

import voluptuous as vol
from const import (
    GIT_URL_REGEX,
    LOGGER,
    PYPI_PACKAGE_REGEX,
    VERSION_REGEX,
)

MANIFEST_SCHEMA = vol.Schema(
    {
        # Community plugin required fields
        "domain": vol.All(str, vol.Match(r"^[a-z0-9_-]+$")),
        "name": str,
        "description": str,
        "required_rhapi_version": vol.Match(r"^\d+\.\d+$"),
        "version": vol.Match(VERSION_REGEX),
        # Community plugin optional fields
        vol.Optional("documentation_uri"): vol.Any(None, vol.Url()),
        vol.Optional("dependencies"): [
            vol.Any(vol.Match(PYPI_PACKAGE_REGEX), vol.Match(GIT_URL_REGEX))
        ],
        vol.Optional("zip_filename"): vol.All(str, vol.Match(r"^[a-z0-9_-]+\.zip$")),
        # RotorHazard optional fields
        vol.Optional("author"): vol.Any(None, str),
        vol.Optional("author_uri"): vol.Any(None, vol.Url()),
        vol.Optional("info_uri"): vol.Any(None, vol.Url()),
        vol.Optional("license"): vol.Any(None, str),
        vol.Optional("license_uri"): vol.Any(None, vol.Url()),
    },
    required=True,
    extra=vol.PREVENT_EXTRA,
)


class ManifestCheck:
    """Manifest check class, to validate the manifest.json file."""

    def __init__(self, manifest_file: Path) -> None:
        """Set the manifest file path."""
        self.manifest_file = manifest_file
        self.errors = []

    def _add_error(self, path: list, message: str) -> None:
        """Add an error to the errors list.

        Args:
        ----
            path (list): The path to the error.
            message (str): The error message.

        """
        formatted_path = " > ".join(str(p) for p in path or ["root"])
        self.errors.append(f"Validation error in [{formatted_path}]: {message}")

    def _validate_schema(self, manifest_data: dict) -> None:
        """Perform schema validation.

        Args:
        ----
            manifest_data (dict): The manifest data to validate.

        """
        try:
            MANIFEST_SCHEMA(manifest_data)
        except vol.MultipleInvalid as e:
            for err in e.errors:
                self._add_error(err.path, err.msg)
        except vol.Invalid as e:
            self._add_error(e.path, e.msg)

    def _validate_domain_matches_folder(self, manifest_data: dict) -> None:
        """Validate that the manifest domain matches its parent folder name."""
        manifest_domain = manifest_data.get("domain")
        if not isinstance(manifest_domain, str):
            return

        folder_domain = self.manifest_file.parent.name
        if manifest_domain != folder_domain:
            self._add_error(
                ["domain"],
                f"Domain mismatch: Folder '{folder_domain}' vs Manifest "
                f"'{manifest_domain}'",
            )

    def _validate_custom_rules(self, manifest_data: dict) -> None:
        """Perform custom validation rules.

        Args:
        ----
            manifest_data (dict): The manifest data to validate.

        """
        if manifest_data.get("zip_release") and not manifest_data.get("zip_filename"):
            self._add_error(
                ["zip_filename"],
                "'zip_filename' is required when 'zip_release' is set to true",
            )

    def run(self) -> dict[str, str]:
        """Validate the manifest.json according to the schema.

        Returns
        -------
            dict: The validation status and message.

        """
        with Path.open(self.manifest_file, encoding="utf-8") as f:
            manifest_data = json.load(f)

        self.errors = []

        # Start validation
        self._validate_schema(manifest_data)
        self._validate_domain_matches_folder(manifest_data)
        # self._validate_custom_rules(manifest_data)  # noqa: ERA001

        if self.errors:
            for error in self.errors:
                LOGGER.error(error)
            return {"status": "fail", "message": "Validation failed"}

        LOGGER.info("✅ Manifest validation passed.")
        return {"status": "pass", "message": "Manifest is valid"}
