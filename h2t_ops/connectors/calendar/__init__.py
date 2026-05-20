"""Calendar connector — package marker.

`CONNECTOR = ConnectorSpec(...)` is added by T3 once `commands.py` exists; until
then this is an empty package so that direct imports of `client` (and tests
thereof) work without requiring `commands.py`.
"""
