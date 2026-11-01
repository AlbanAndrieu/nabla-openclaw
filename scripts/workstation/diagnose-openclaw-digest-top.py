#!/usr/bin/env python3
"""Read-only, redacted audit of the daily tech digest OpenClaw cron argument.

Never prints task prompts, secrets, URLs, recipients or raw CLI output.
No cron edit, model request, job execution, service restart or quota change.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openclaw_runtime import (  # noqa: E402
    DIGEST_JOB_ID as JOB_ID, DIGEST_JOB_NAME as JOB_NAME, MAX_JSON,
    decode_job, install_issues, read_cron_job,
)
from private_files import UnsafePath, read_owned  # noqa: E402

SKILL_TEMPLATE = (Path.home() / ".openclaw/workspace/skills/tech-news-digest/"
                  "references/digest-prompt.md")
TOP_PATTERN = re.compile(r'(?<!\S)--top(?:\s+|=)(?:["\']?)([^\s"\']+)')
INVALID_RANGE = re.compile(r"^\d+[-\u2013\u2014]\d+$")
INTEGER = re.compile(r"^[0-9]+$")
ITEMS_PARAMETER = re.compile(r"(?m)^\s*-\s*ITEMS_PER_SECTION\s*=\s*([^\s]+)")
FIXED_TOP = re.compile(r"(?<!\S)--top\s+([0-9]+)(?![0-9])")
# Detect the specific natural-language range which caused the 27 Oct failure.
# Do not try to interpret arbitrary dates, version numbers or prompt contents.
NATURAL_TOP_RANGE = re.compile(r"(?<![0-9])3\s*[-\u2013\u2014]\s*5(?![0-9])")


def classify_job(job: dict | None, skill_template: str | None = None) -> tuple[str, str]:
    if job is None:
        return "unavailable", "unverified"
    if job.get("id") != JOB_ID or job.get("name") != JOB_NAME:
        return "wrong_job", "unverified"
    payload = job.get("payload")
    if not isinstance(payload, dict):
        return "unexpected_payload", "unverified"
    message = payload.get("message")
    if not isinstance(message, str) or not message:
        return "unexpected_payload", "unverified"
    # When the cron references a skill, inspect the authoritative template.
    # An explanatory '--top 5' appended to cron cannot override its script.
    if "references/digest-prompt.md" in message:
        params = ITEMS_PARAMETER.findall(message)
        if len(params) != 1:
            return "skill_items_parameter_unverified", "5"
        items = params[0]
        if skill_template is None:
            return "skill_template_unavailable", "5"
        if "--top <ITEMS_PER_SECTION>" in skill_template:
            return ("skill_template_integer_valid" if INTEGER.fullmatch(items)
                    else "skill_template_range_int_mismatch"), "5"
        if FIXED_TOP.search(skill_template):
            return "skill_template_fixed_integer", "5"
        return "skill_template_top_unverified", "5"
    # A prose sentence may end an advisory value with punctuation. Normalize
    # only trailing sentence punctuation; keep ranges and unknown values intact.
    values = [value.rstrip(".,;:!?)]}") for value in TOP_PATTERN.findall(message)]
    if not values:
        return ("natural_language_top_range" if NATURAL_TOP_RANGE.search(message)
                else "no_explicit_top_argument"), "5"
    if len(set(values)) != 1:
        return "multiple_top_arguments", "5"
    value = values[0]
    if INVALID_RANGE.fullmatch(value):
        return "invalid_top_range", "5"
    if INTEGER.fullmatch(value):
        if int(value) != 5:
            return "valid_other_integer", "5"
        # Mixing an explicit --top 5 with a 3-5 range is ambiguous to an agent.
        if NATURAL_TOP_RANGE.search(message):
            return "ambiguous_mixed_top_guidance", "5"
        return "valid_top_five", "5"
    return "invalid_top_value", "5"


def read_runtime(node: Path | None = None, cli: Path | None = None) -> tuple[str, dict | None]:
    # Pinned by the runtime contract; never PATH or a stale release.
    return read_cron_job(JOB_ID, node, cli)


def read_fixture(path: Path) -> tuple[str, dict | None]:
    try:
        raw = read_owned(path, MAX_JSON)
    except UnsafePath as exc:
        return ("invalid_report" if str(exc) == "invalid_file_size" else "unsafe_fixture"), None
    except OSError:
        return "unsafe_fixture", None
    job = decode_job(raw)
    return ("structured" if job is not None else "invalid_report"), job


def read_skill_template(path: Path = SKILL_TEMPLATE) -> tuple[str, str | None]:
    """Read only an owner-controlled regular Markdown file, never print content."""
    try:
        return "available", read_owned(path, MAX_JSON).decode("utf-8")
    except UnsafePath as exc:
        return ("invalid_file" if str(exc) == "invalid_file_size" else "unsafe_file"), None
    except (OSError, UnicodeError):
        return "unavailable", None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="Offline private job JSON fixture")
    args = parser.parse_args(argv)
    state, job = read_fixture(args.fixture) if args.fixture else read_runtime()
    template_state, template = read_skill_template()
    classification, recommendation = classify_job(job, template)
    print("openclaw_digest_audit=read_only")
    print("cron_job_read=" + state)
    if state == "unverified_installation":
        print("runtime_install=" + install_issues())
    print("skill_template_read=" + template_state)
    print("digest_top_argument=" + classification)
    print("recommended_integer_top=" + recommendation)
    print("cron_job_modified=false")
    print("model_requests_sent=0")
    print("task_prompt_printed=false")
    # Passing contracts is not proof a model will follow its prompt or a job will deliver.
    valid = ("valid_top_five", "skill_template_integer_valid",
             "skill_template_fixed_integer")
    return 0 if state == "structured" and classification in valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
