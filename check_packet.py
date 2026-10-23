#!/usr/bin/env python3
"""Check packet integrity, metadata, and recorded claim fields; no enumeration.

SPDX-License-Identifier: Apache-2.0
"""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("fixture_checker", HERE / "check.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_path(name):
    require(isinstance(name, str), "path is not a string")
    parts = PurePosixPath(name)
    require(not parts.is_absolute() and name == str(parts) and
            all(p not in ("..", ".git") for p in parts.parts), "unsafe packet path")
    path = HERE / name
    require(not path.is_symlink() and path.resolve().is_relative_to(HERE), "symlink escape")
    return path


def record_matches(record):
    raw = local_path(record["path"]).read_bytes()
    require(type(record["bytes"]) is int and len(raw) == record["bytes"],
            "size mismatch: " + record["path"])
    require(hashlib.sha256(raw).hexdigest() == record["sha256"],
            "hash mismatch: " + record["path"])


def same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def main():
    try:
        manifest = checker.load_json(HERE / "manifest.json")
        require(manifest["format_version"] == 1, "manifest version")
        listed = [r["path"] for r in manifest["files"]]
        require(len(set(listed)) == len(listed), "duplicate manifest path")
        actual = set()
        for path in HERE.rglob("*"):
            relative = path.relative_to(HERE)
            if relative.parts[0] == ".git":
                continue
            require(not path.is_symlink(), "packet contains a symlink")
            if path.is_file() and relative.as_posix() != "manifest.json":
                actual.add(relative.as_posix())
        require(actual == set(listed), "packet file list differs from manifest")
        for record in manifest["files"]:
            record_matches(record)

        claims = checker.load_json(HERE / "claims.json")
        require(type(claims["format_version"]) is int and claims["format_version"] == 1,
                "claims format version")
        require(claims["release_kind"] == ["data", "tool"], "release kind")
        entries = {c["id"]: c for c in claims["claims"]}
        require(len(entries) == len(claims["claims"]) == 6, "claim count/ids")
        require(set(entries) == {"finite-fixtures", "counterexample-scope", "minimum-variable-count",
                                 "verification-independence", "regression-tests", "dagdown-scope"},
                "claim ids")
        for claim in entries.values():
            require(claim["kind"] in claims["kinds"], "unknown claim kind")
            for record in claim["evidence"]:
                record_matches(record)

        expected = checker.load_json(HERE / "expected.json")["cases"]
        numbers = []
        for name, case in expected.items():
            numbers.append(dict(id=name, variables=len(case["before"]["variables"]),
                                edges=case["conditions"]["edge_count"],
                                C1=case["conditions"]["C1"], C2=case["conditions"]["C2"],
                                maa_before=len(case["before"]["maa"]),
                                maa_after=len(case["after"]["maa"]), D1=case["D1"], D2=case["D2"]))
        finite = entries["finite-fixtures"]
        require(finite["kind"] == "finite-computation" and same(finite["cases"], numbers),
                "fixture claim numbers")
        scope = entries["counterexample-scope"]
        require(scope["case_ids"] == ["E1", "E1-canonical", "E2", "E3"] and
                scope["distinct_constructions"] == 3 and
                scope["published_controls"] == ["Pastva-7", "Pastva-8"], "fixture roles")
        for name in scope["case_ids"]:
            case = expected[name]
            require(case["eliminate"] == "a" and case["D1"] is True and case["D2"] is True and
                    not case["before"]["maa"] and len(case["after"]["maa"]) == 1,
                    "counterexample values")
            require(case["conditions"]["C2"] is True, "C2 counterexample")
            require(case["conditions"]["C1"] is (name != "E2"), "C1 counterexample")

        provenance = checker.load_json(HERE / "provenance.json")
        for name in ("networks.json", "expected.json", "check.py", "selftest.py"):
            require(hashlib.sha256((HERE / name).read_bytes()).hexdigest() ==
                    provenance["packaging_sources_sha256"][name],
                    "frozen draft science changed: " + name)
        for name, item in provenance["bundled_historical_records"].items():
            require(hashlib.sha256(local_path(name).read_bytes()).hexdigest() == item["sha256"],
                    "historical record hash")
        lower = entries["minimum-variable-count"]
        require(lower["kind"] == "earlier-computation" and lower["reproduce"] is None,
                "minimality is an earlier-computation claim")
        require(lower["minimum_original_variables"] == 4 and
                lower["conditions"] == ["C1", "C2"] and lower["enumerated_n"] == [1, 2, 3],
                "minimum-variable scope")
        count_list = []
        audit = checker.load_json(HERE / "evidence/enumeration-audit.json")
        require(audit["result"] == "PASS" and len(audit["checks"]) == 3, "historical audit")
        for n in (1, 2, 3):
            first = checker.load_json(HERE / f"evidence/n{n}-full.json")
            second = checker.load_json(HERE / f"evidence/n{n}-second-enumeration.json")
            count = n * 2 ** (2 ** (n - 1)) * (2 ** (2 ** n)) ** (n - 1)
            require(first["n"] == second["n"] == n and first["full_coverage"] is True,
                    "historical enumeration scope")
            require(first["total_self_independent_marked_deletions"] ==
                    first["visited_marked_deletions"] == count, "historical deletion count")
            require(not first["counterexamples"] and not second["counterexamples"],
                    "historical counterexample list")
            require(same(audit["checks"][n - 1], second), "historical second-audit copy")
            for condition in ("C1", "C2"):
                require(same(first[condition], second[condition]) and
                        first[condition]["D1"] == first[condition]["D2"] == 0,
                        "historical condition counts")
            count_list.append(count)
        require(same(count_list, lower["marked_deletion_counts"]) and
                same(lower["counterexamples_below_four"], {"C1": 0, "C2": 0}),
                "lower-bound claim record counts")
        independence = entries["verification-independence"]
        require(independence["kind"] == "earlier-computation" and
                independence["numerically_blind"] is False and
                independence["separate_implementation"] is True and
                independence["separate_human_review"] is False, "independence qualification")
        tests = entries["regression-tests"]
        require(tests["tests"] == 16 and tests["original_reduced_profiles"] == 12,
                "regression-test counts")

        # CITATION.cff is JSON, a subset of YAML; no YAML dependency is needed.
        citation = checker.load_json(HERE / "CITATION.cff")
        zenodo = checker.load_json(HERE / ".zenodo.json")
        require(citation["cff-version"] == "1.2.0" and citation["type"] == "dataset" and
                zenodo["upload_type"] == "dataset", "dataset metadata type")
        require(citation["title"] == zenodo["title"] == claims["title"] and
                citation["version"] == zenodo["version"] == claims["version"], "metadata title/version")
        require(citation["license"] == "CC-BY-4.0" and zenodo["license"] == "cc-by-4.0",
                "dataset licence")
        require(citation["authors"] == [{"family-names": "Takimoto", "given-names": "Tatsuhiko",
                                         "affiliation": "Independent researcher"}] and
                zenodo["creators"] == [{"name": "Tatsuhiko Takimoto", "affiliation": "Independent researcher"}],
                "authorship metadata")
        if claims["prepared_not_released"]:
            require(not any(k in citation for k in ("doi", "date-released", "repository-code")) and
                    not any(k in zenodo for k in ("doi", "publication_date")),
                    "unreleased package must not invent release metadata")
        cited = {r["url"] for r in citation["references"]}
        related = {r["identifier"] for r in zenodo["related_identifiers"]}
        require(cited == related == {"https://arxiv.org/abs/2410.03976v1",
                                     "https://arxiv.org/abs/2406.02304v3"}, "source references")
        for path in HERE.glob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if target.startswith(("https://", "#")):
                    continue
                require(local_path(target.split("#", 1)[0].rstrip("/")).exists(),
                        "missing local Markdown link: " + target)
        print(f"PASS: {len(listed)} file hashes, metadata and recorded claim fields")
        print("Historical enumeration records were checked for consistency; enumeration was not rerun.")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
