"""Main entry point for the metadata generation process."""

import asyncio

from const import GITHUB_TOKEN, OUTPUT_DIR, PLUGIN_LIST_FILE
from summary_generator import SummaryGenerator

if __name__ == "__main__":
    asyncio.run(SummaryGenerator(PLUGIN_LIST_FILE, OUTPUT_DIR).generate(GITHUB_TOKEN))
