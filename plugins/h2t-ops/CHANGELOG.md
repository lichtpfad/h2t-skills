# h2t-ops Changelog

## Unreleased

- fix(research): the screenshot step no longer names `h2t-tools:screenshot`, a Windows-only
  skill hardcoded to `C:/dev/h2t-tools/.venv/Scripts/python.exe`. It points at a browser
  agent when one is installed and, when none is, says the capture is missing rather than
  substituting prose for it (#460)
