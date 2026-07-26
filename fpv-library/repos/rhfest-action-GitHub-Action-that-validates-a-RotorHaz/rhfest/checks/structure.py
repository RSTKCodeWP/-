"""Plugin repo structure checks."""

from pathlib import Path

from const import LOGGER, MANIFEST_FILE, PLUGIN_DIR
from report import Report


class StructureCheck:
    """Structure check class, to check the structure of the plugin repo."""

    def __init__(
        self,
        base_path: Path,
        report: Report,
        show_debug_tree: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        """Initialize the structure check class."""
        self.base_path = base_path
        self.report = report
        self.errors = []
        self.plugin_path = None
        self.plugin_dir = None
        self.manifest_path = None
        self.show_debug_tree = show_debug_tree

    def _add_error(self, message: str) -> None:
        """Record an error message and log it."""
        self.errors.append(message)
        if self.show_debug_tree:
            LOGGER.info("🐛 Directory structure for debugging:")
            self.report.list_files_in_tree(self.base_path)

    def _validate_plugin_dir(self) -> None:
        """Check if the directory name exists and is correct."""
        plugin_path = self.base_path / PLUGIN_DIR
        LOGGER.info(f"🔍 Searching for '{PLUGIN_DIR}' directory in {self.base_path}")
        if not plugin_path.exists():
            self._add_error(f"No '{PLUGIN_DIR}' directory found in '{self.base_path}'.")
        else:
            self.plugin_path = plugin_path

    def _validate_single_plugin_dir(self) -> None:
        """Check if there is only one plugin domain directory."""
        if self.plugin_path is None:
            return

        plugin_dirs = list(self.plugin_path.glob("*"))
        if len(plugin_dirs) == 0:
            self._add_error(f"No plugin domain directory found in '{self.base_path}'.")
        elif len(plugin_dirs) > 1:
            self._add_error(
                f"Multiple plugin directories found: {[p.name for p in plugin_dirs]} "
                f"in '{self.plugin_path}'."
            )
        else:
            self.plugin_dir = plugin_dirs[0]

    def _validate_manifest_file(self) -> None:
        """Check if the manifest.json file exists in the plugin directory."""
        if self.plugin_dir is None:
            return

        manifest_path = self.plugin_dir / MANIFEST_FILE
        if not manifest_path.exists():
            self._add_error(f"manifest.json not found in {manifest_path}.")
        else:
            LOGGER.info(f"✅ Found manifest.json at {manifest_path}")
            self.manifest_path = manifest_path

    def run(self) -> dict[str, str]:
        """Run all structure validations and return the result."""
        self.errors = []  # Reset errors
        self._validate_plugin_dir()
        self._validate_single_plugin_dir()
        self._validate_manifest_file()

        if self.errors:
            for error in self.errors:
                LOGGER.error(error)
            return {"status": "fail", "message": "Validation failed"}

        LOGGER.info("✅ Structure validation passed.")
        return {"status": "pass", "message": "Structure is valid"}
