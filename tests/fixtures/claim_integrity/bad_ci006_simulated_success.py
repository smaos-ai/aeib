# Fixture (intentionally bad): CI006 simulated marker reported with a success flag.


def attach_probe(program):
    attached = True
    return {"program": program, "attached": attached, "kernel": "simulated"}


def attest_enclave():
    return dict(mode="simulated", verified=True)
