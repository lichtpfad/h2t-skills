"""The bootstrap of this release (spec §7.2). Written by scripts/release.py prepare; do not edit."""

BOOTSTRAP: list[str] = ["uvx", "--isolated", "--python", "3.12.11", "--managed-python", "-c", "https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/constraints.txt", "--from", "h2t-ops @ https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/h2t_ops-4.0.0-py3-none-any.whl", "h2t-setup"]
BOOTSTRAP_COMMAND = "uvx --isolated --python 3.12.11 --managed-python -c \"https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/constraints.txt\" --from \"h2t-ops @ https://github.com/lichtpfad/h2t-skills/releases/download/v4.0.0/h2t_ops-4.0.0-py3-none-any.whl\" h2t-setup"
