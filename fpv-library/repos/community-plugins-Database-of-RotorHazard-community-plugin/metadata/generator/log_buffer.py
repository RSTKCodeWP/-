"""Log buffering functionality for plugin metadata generation."""

from const import LOGGER


class PluginLogBuffer:
    """Buffer logs per plugin before printing them grouped."""

    def __init__(self, repo: str) -> None:
        """Initialize the log buffer for a specific plugin repository."""
        self.repo = repo
        self.buffer: list[tuple[int, str]] = []

    def log(self, level: int, message: str) -> None:
        """Buffer a log message with its level."""
        self.buffer.append((level, message))

    def flush(self) -> None:
        """Flush the buffered logs to the logger."""
        LOGGER.info(f"::group::🔧 {self.repo}")
        for level, message in self.buffer:
            LOGGER.log(level, f"<{self.repo}> {message}")
        LOGGER.info("::endgroup::")
