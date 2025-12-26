"""
Main entry point for NodeReaper when run as a module.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""
from nodereaper.logging import setup_logging
from nodereaper.reaper import NodeReaper


def main() -> None:
    """Run NodeReaper."""
    setup_logging()
    reaper = NodeReaper()
    reaper.run()


if __name__ == "__main__":
    main()
