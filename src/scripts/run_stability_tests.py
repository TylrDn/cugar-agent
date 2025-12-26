from __future__ import annotations

import asyncio
import sys

import pytest


def main() -> int:
    return pytest.main(["tests", "-q", "--disable-warnings"])


if __name__ == "__main__":
    sys.exit(main())
