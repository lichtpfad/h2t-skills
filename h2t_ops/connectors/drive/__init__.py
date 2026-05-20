"""Drive connector — populated in T2 (registry entry).

T1 ships the package marker + client.py only; T2 wires CONNECTOR and commands.
This split lets T1 client tests import the package without commands.py existing.
"""
