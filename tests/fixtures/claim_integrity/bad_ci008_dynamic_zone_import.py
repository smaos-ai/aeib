# Fixture (intentionally bad): CI008 dynamic import of a Zone 2 module.
import importlib


def load_enterprise_backend():
    return importlib.import_module("enterprise.secret_backend")


def load_probe():
    return __import__("aeib_postgresql_probe.collector")
