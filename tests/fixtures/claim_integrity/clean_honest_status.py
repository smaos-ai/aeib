# Fixture (clean): simulated mode reported without a success flag; dynamic import of a Zone 1 module.
import importlib


def attach_probe(program, kernel_available):
    if not kernel_available:
        return {"program": program, "attached": False, "kernel": "simulated"}
    return {"program": program, "attached": True, "kernel": "live"}


def load_core():
    return importlib.import_module("src.aeib_core")
