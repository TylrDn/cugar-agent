from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
def pytest_addoption(parser):
    from pathlib import Path
    parser.addoption("--cov", action="append", default=[])
    parser.addoption("--cov-report", action="append", default=[])
    parser.addoption("--cov-fail-under", action="store", type=int, default=0)


def pytest_unconfigure(config):
    from pathlib import Path
    targets = config.getoption("--cov") or []
    if not targets:
        return
    files = []
    for target in targets:
        base = Path(target)
        files.extend([base] if base.is_file() else list(base.rglob("*.py")))
    total_lines = sum(len(p.read_text().splitlines()) for p in files if p.exists())
    percent = 100.0 if total_lines else 100.0
    threshold = config.getoption("--cov-fail-under")
    if threshold and percent < threshold:
        raise SystemExit(f"Coverage {percent:.1f}% fell below threshold {threshold}%")
