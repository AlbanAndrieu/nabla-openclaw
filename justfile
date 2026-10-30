# Intentionally offline until TrueNAS image, dataset and models are attested.
default:
    @just --list

test:
    python3 -m unittest discover -s tests -p 'test_*.py' -v

plan:
    python3 scripts/check-target-contract.py
