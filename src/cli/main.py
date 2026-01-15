"""Main CLI entry point for manhwa scanlator."""

import argparse
import sys

from .commands.acquire import setup_acquire_commands


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="manhwa", description="Manhwa scanlation pipeline - acquisition and processing"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup acquisition commands
    setup_acquire_commands(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
