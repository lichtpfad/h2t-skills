"""Project stack detection."""
from pathlib import Path

STACK_MAP = {
    "package.json":   {"name": "js",     "commands": {"test": "npm test", "audit": "npm audit", "build": "npm run build"}},
    "pyproject.toml": {"name": "python", "commands": {"test": "pytest", "audit": "pip-audit", "lint": "ruff check"}},
    "Cargo.toml":     {"name": "rust",   "commands": {"test": "cargo test", "audit": "cargo audit", "lint": "cargo clippy"}},
    "go.mod":         {"name": "go",     "commands": {"test": "go test ./...", "audit": "govulncheck ./...", "lint": "go vet ./..."}},
}

def detect_stack(cwd: str = ".") -> dict:
    root = Path(cwd)
    for marker, stack in STACK_MAP.items():
        if (root / marker).exists():
            return stack
    return {"name": "none", "commands": {}}
