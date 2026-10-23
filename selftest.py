#!/usr/bin/env python3
"""Regression and fault tests, including a second finite dynamics algorithm.

Written by the package author after seeing the results; not a blind review.
"""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("r020_checker", HERE / "check.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def reference_profile(profile):
    """Reachability SCCs and fixed-coordinate trap criterion, not Tarjan/closure."""
    n = len(profile["variables"])
    tables = profile["truth_tables"]
    universe = list(itertools.product((0, 1), repeat=n))
    index = lambda s: sum(b * 2 ** i for i, b in enumerate(s))
    outputs = {s: tuple((table >> index(s)) & 1 for table in tables) for s in universe}
    succ = {s: {s[:i] + (1 - s[i],) + s[i + 1:]
                for i in range(n) if outputs[s][i] != s[i]} for s in universe}
    reach = {s: {s} | succ[s] for s in universe}
    for k in universe:
        for s in universe:
            if k in reach[s]:
                reach[s] |= reach[k]
    components = {frozenset(t for t in universe if t in reach[s] and s in reach[t])
                  for s in universe}
    terminal = [c for c in components if all(reach[s] <= c for s in c)]
    traps = []
    for spec in itertools.product((0, 1, None), repeat=n):
        cube = frozenset(s for s in universe if all(x is None or s[i] == x for i, x in enumerate(spec)))
        if all(outputs[s][i] == x for s in cube for i, x in enumerate(spec) if x is not None):
            traps.append(("".join("*" if x is None else str(x) for x in spec), cube))
    minimal = [(p, c) for p, c in traps if not any(d < c for _, d in traps)]
    maa = [a for a in terminal if len(a) > 1 and all(not a <= c for _, c in minimal)]
    label = lambda s: "".join(map(str, s))
    groups = lambda components: sorted(sorted(map(label, c)) for c in components)
    spaces = lambda items: sorted(
        ({"pattern": p, "states": sorted(map(label, c))} for p, c in items), key=lambda x: x["pattern"])
    return {"attractors": groups(terminal), "trap_spaces": spaces(traps),
            "minimal_trap_spaces": spaces(minimal), "maa": groups(maa)}


class Checks(unittest.TestCase):
    def setUp(self):
        self.inputs = checker.load_json(HERE / "networks.json")
        self.expected = checker.load_json(HERE / "expected.json")

    def compare_changed(self, inputs=None, expected=None):
        # Temporary files remain local to this package and are removed afterwards.
        with tempfile.TemporaryDirectory(prefix="test-", dir=HERE) as directory:
            path = Path(directory)
            (path / "networks.json").write_text(json.dumps(inputs or self.inputs))
            (path / "expected.json").write_text(json.dumps(expected or self.expected))
            return checker.compare(path)

    def test_all_fixtures_and_second_algorithm(self):
        result = checker.compare(HERE)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checked"], 6)
        for name, case in result["cases"].items():
            for side in ("before", "after"):
                with self.subTest(case=name, side=side):
                    for key, value in reference_profile(case[side]).items():
                        self.assertEqual(case[side][key], value)

    def test_precedence_and_parentheses(self):
        f = checker.Formula("!a & b | c", ["a", "b", "c"])
        g = checker.Formula("!(a & (b | c))", ["a", "b", "c"])
        for a, b, c in itertools.product((0, 1), repeat=3):
            self.assertEqual(f((a, b, c)), int((not a and b) or c))
            self.assertEqual(g((a, b, c)), int(not (a and (b or c))))

    def test_invalid_formulas(self):
        for formula in ("", "a ^ b", "a b", "a |", "(a", "a)", "z", "2",
                        "__import__('os')", "a or b", "a && b"):
            with self.subTest(formula=formula), self.assertRaises(ValueError):
                checker.Formula(formula, ["a", "b"])

    def test_nonfirst_elimination_and_state_order(self):
        case = {"id": "constant", "variables": ["x", "copy", "z"],
                "eliminate": "copy", "functions": {"x": "1", "copy": "x", "z": "copy"}}
        result = checker.evaluate(case)
        self.assertEqual(result["after"]["variables"], ["x", "z"])
        self.assertEqual(result["after"]["truth_tables"], [15, 10])
        self.assertEqual(result["after"]["attractors"], [["11"]])

    def test_zero_dimensional_reduction(self):
        result = checker.evaluate({"id": "one", "variables": ["x"],
                                   "eliminate": "x", "functions": {"x": "0"}})
        self.assertEqual(result["after"]["attractors"], [[""]])
        self.assertEqual(result["after"]["minimal_trap_spaces"], [{"pattern": "", "states": [""]}])
        self.assertFalse(result["D2"])

    def test_self_regulation_rejected(self):
        case = copy.deepcopy(self.inputs["cases"][0])
        case["functions"]["a"] = "a"
        with self.assertRaisesRegex(ValueError, "self-regulation"):
            checker.evaluate(case)

    def test_essential_not_syntactic_dependency(self):
        case = {"id": "cancelled", "variables": ["a", "b"], "eliminate": "a",
                "functions": {"a": "(a & 0) | b", "b": "0"}}
        result = checker.evaluate(case)
        self.assertEqual(result["conditions"]["interaction_edges"], [["b", "a"]])

    def test_d2_uses_containment_not_equality(self):
        old = [frozenset({(0, 0), (0, 1), (1, 0)})]
        new = [frozenset({(0,), (1,)})]
        projections, created = checker.new_maa(old, new, 0)
        self.assertEqual(projections, new)
        self.assertFalse(created)
        # Strict containment in the projected MAA also counts as inherited.
        _, created = checker.new_maa(old, [frozenset({(0,)})], 0)
        self.assertFalse(created)
        _, created = checker.new_maa([frozenset({(0, 0)})], new, 0)
        self.assertTrue(created)

    def test_expected_attractor_damage_detected(self):
        self.expected["cases"]["E1"]["after"]["attractors"][0].pop()
        self.assertEqual(self.compare_changed(expected=self.expected)["failures"], ["E1"])

    def test_expected_d2_damage_detected(self):
        self.expected["cases"]["E2"]["D2"] = False
        self.assertEqual(self.compare_changed(expected=self.expected)["failures"], ["E2"])

    def test_input_formula_damage_detected(self):
        self.inputs["cases"][0]["functions"]["d"] = "d"
        self.assertIn("E1", self.compare_changed(inputs=self.inputs)["failures"])

    def test_missing_case_detected(self):
        self.inputs["cases"].pop()
        self.assertEqual(self.compare_changed(inputs=self.inputs)["failures"], ["Pastva-8"])

    def test_duplicate_case_rejected(self):
        self.inputs["cases"].append(copy.deepcopy(self.inputs["cases"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate case"):
            self.compare_changed(inputs=self.inputs)

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory(prefix="test-", dir=HERE) as directory:
            path = Path(directory) / "data.json"
            path.write_text('{"x":0,"x":1}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                checker.load_json(path)

    def test_boolean_integer_distinction(self):
        self.expected["cases"]["E1"]["D1"] = 1
        self.assertEqual(self.compare_changed(expected=self.expected)["failures"], ["E1"])

    def test_limits_and_incomplete_definitions(self):
        for change in ({"variables": ["a"] * 7}, {"variables": ["a", "a"]},
                       {"eliminate": "z"}, {"functions": {"a": "0"}}):
            case = copy.deepcopy(self.inputs["cases"][0])
            case.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                checker.evaluate(case)


if __name__ == "__main__":
    unittest.main(verbosity=2)
