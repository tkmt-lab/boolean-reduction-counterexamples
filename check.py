#!/usr/bin/env python3
"""Check finite asynchronous Boolean-network fixtures; standard library only.

Dynamics methods organized from R020 engine_b.py (see provenance.json).
No fixture generation, file writes, network calls, or repository imports.
"""
import argparse
import itertools
import json
from pathlib import Path
import re
import sys

MAX_VARIABLES = 6
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
TOKEN = re.compile(r"\s*([A-Za-z_][A-Za-z_0-9]*|[01!&|()])")


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


class Formula:
    """Recursive descent: ! binds before &, which binds before |; no eval."""

    def __init__(self, text, names):
        if not isinstance(text, str) or not 0 < len(text.strip()) <= 512:
            raise ValueError("formula must contain 1..512 characters")
        self.names = names
        self.tokens = []
        position = 0
        text = text.strip()
        while position < len(text):
            match = TOKEN.match(text, position)
            if not match:
                raise ValueError(f"invalid formula token at position {position}")
            self.tokens.append(match[1])
            position = match.end()
        if len(self.tokens) > 128:
            raise ValueError("formula exceeds 128 tokens")
        self.position = 0
        self.tree = self.expression("|")
        if self.position != len(self.tokens):
            raise ValueError(f"unexpected token: {self.tokens[self.position]}")

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def expression(self, operator):
        operand = (lambda: self.expression("&")) if operator == "|" else self.atom
        tree = operand()
        while self.peek() == operator:
            self.position += 1
            tree = (operator, tree, operand())
        return tree

    def atom(self):
        token = self.peek()
        self.position += 1
        if token == "!":
            return ("!", self.atom())
        if token == "(":
            tree = self.expression("|")
            if self.peek() != ")":
                raise ValueError("missing closing parenthesis")
            self.position += 1
            return tree
        if token in ("0", "1"):
            return ("constant", int(token))
        if token in self.names:
            return ("variable", self.names.index(token))
        raise ValueError(f"unknown variable or missing operand: {token}")

    def __call__(self, state):
        def run(tree):
            op = tree[0]
            if op == "constant":
                return tree[1]
            if op == "variable":
                return state[tree[1]]
            if op == "!":
                return 1 - run(tree[1])
            if op == "&":
                return run(tree[1]) & run(tree[2])
            return run(tree[1]) | run(tree[2])
        return run(self.tree)


def states(n):
    return list(itertools.product((0, 1), repeat=n))


def label(state):
    return "".join(map(str, state))


def groups(sets):
    return sorted(sorted(label(s) for s in group) for group in sets)


def terminal_scc(successors):
    # At most 64 states: recursive Tarjan stays below Python's recursion limit.
    indices, low, stack, active, components = {}, {}, [], set(), []

    def visit(v):
        indices[v] = low[v] = len(indices)
        stack.append(v)
        active.add(v)
        for w in successors[v]:
            if w not in indices:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in active:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            component = set()
            while True:
                w = stack.pop()
                active.remove(w)
                component.add(w)
                if w == v:
                    break
            components.append(frozenset(component))

    for state in successors:
        if state not in indices:
            visit(state)
    return [c for c in components if all(w in c for v in c for w in successors[v])]


def analyse(names, functions):
    n = len(names)
    universe = states(n)
    successors = {s: [s[:i] + (1 - s[i],) + s[i + 1:]
                      for i, f in enumerate(functions) if f[s] != s[i]] for s in universe}
    attractors = terminal_scc(successors)
    traps = []
    for spec in itertools.product(("0", "1", "*"), repeat=n):
        cube = frozenset(s for s in universe
                         if all(c == "*" or int(c) == s[i] for i, c in enumerate(spec)))
        if all(t in cube for s in cube for t in successors[s]):
            traps.append(("".join(spec), cube))
    minimal = [(p, c) for p, c in traps if not any(d < c for _, d in traps)]
    maa = [a for a in attractors if len(a) > 1 and not any(a <= c for _, c in minimal)]
    spaces = lambda items: sorted(
        ({"pattern": p, "states": sorted(map(label, c))} for p, c in items),
        key=lambda item: item["pattern"])
    tables = [sum(f[s] << sum(b << i for i, b in enumerate(s)) for s in universe)
              for f in functions]
    return {
        "variables": list(names), "truth_tables": tables,
        "transitions": sorted([label(s), label(t)] for s in universe for t in successors[s]),
        "attractors": groups(attractors), "trap_spaces": spaces(traps),
        "minimal_trap_spaces": spaces(minimal), "maa": groups(maa),
    }, maa


def conditions(names, functions, v):
    n = len(names)
    signs = {}
    for i, f in enumerate(functions):
        for j in range(n):
            changes = {f[s[:j] + (1,) + s[j + 1:]] - f[s]
                       for s in f if s[j] == 0} - {0}
            if changes:
                signs[j, i] = changes
    edges = set(signs)
    if (v, v) in edges:
        raise ValueError("eliminated variable has essential self-regulation")
    regs = sorted(j for j, i in edges if i == v)
    targets = sorted(i for j, i in edges if j == v)
    seen, todo = set(), targets.copy()
    while todo:
        u = todo.pop()
        if u not in seen:
            seen.add(u)
            todo.extend(i for j, i in edges if j == u)
    acyc = v not in seen
    med = not any((j, i) in edges for j in regs for i in targets)
    inmon = all(len(signs[j, v]) == 1 for j in regs)
    outmon = all(len(signs[v, i]) == 1 for i in targets)
    return {
        "ACYC": acyc, "MED": med, "INMON": inmon, "OUTMON": outmon,
        "C1": acyc, "C2": med and inmon and outmon,
        "regulators": [names[j] for j in regs], "targets": [names[i] for i in targets],
        "interaction_edges": sorted([names[j], names[i]] for j, i in edges),
        "edge_count": len(edges),
        "max_indegree": max(sum((j, i) in edges for j in range(n)) for i in range(n)),
        "TNOSELF": all((i, i) not in edges for i in targets),
        "LMON": all(len(change) == 1 for change in signs.values()),
    }


def new_maa(original, reduced, v):
    projected = [frozenset(s[:v] + s[v + 1:] for s in a) for a in original]
    new = [a for a in reduced if not any(a <= p for p in projected)]
    return projected, new


def evaluate(case):
    if not isinstance(case, dict) or set(case) != {"id", "variables", "eliminate", "functions"}:
        raise ValueError("case must have id, variables, eliminate, functions")
    names = case["variables"]
    if not isinstance(names, list) or not 1 <= len(names) <= MAX_VARIABLES:
        raise ValueError(f"require 1..{MAX_VARIABLES} variables")
    if any(not isinstance(x, str) or not IDENTIFIER.fullmatch(x) for x in names):
        raise ValueError("invalid variable name")
    if len(set(names)) != len(names):
        raise ValueError("duplicate variable name")
    if not isinstance(case["id"], str) or not case["id"]:
        raise ValueError("case id must be a nonempty string")
    if case["eliminate"] not in names:
        raise ValueError("eliminate must name a declared variable")
    equations = case["functions"]
    if not isinstance(equations, dict) or set(equations) != set(names):
        raise ValueError("functions must define each variable exactly once")
    parsers = [Formula(equations[name], names) for name in names]
    functions = [{s: formula(s) for s in states(len(names))} for formula in parsers]
    v = names.index(case["eliminate"])
    predicates = conditions(names, functions, v)
    remaining = names[:v] + names[v + 1:]
    reduced = []
    for i, f in enumerate(functions):
        if i == v:
            continue
        table = {}
        for y in states(len(remaining)):
            x0 = y[:v] + (0,) + y[v:]
            x = y[:v] + (functions[v][x0],) + y[v:]
            table[y] = f[x]
        reduced.append(table)
    before, original_maa = analyse(names, functions)
    after, reduced_maa = analyse(remaining, reduced)
    projections, created = new_maa(original_maa, reduced_maa, v)
    return {
        "eliminate": case["eliminate"], "before": before, "after": after,
        "conditions": predicates,
        "D1": not original_maa and bool(reduced_maa), "D2": bool(created),
        "original_maa_projections": groups(projections), "new_maa": groups(created),
    }


def compare(data_dir):
    inputs = load_json(data_dir / "networks.json")
    oracle = load_json(data_dir / "expected.json")
    for value in (inputs, oracle):
        if not isinstance(value, dict) or set(value) != {"format_version", "cases"}:
            raise ValueError("expected format_version and cases")
        if type(value["format_version"]) is not int or value["format_version"] != 1:
            raise ValueError("unsupported format_version")
    if not isinstance(inputs["cases"], list) or not inputs["cases"]:
        raise ValueError("input cases must be a nonempty list")
    if not isinstance(oracle["cases"], dict):
        raise ValueError("expected cases must be an object")
    actual = {}
    for case in inputs["cases"]:
        result = evaluate(case)
        if case["id"] in actual:
            raise ValueError("duplicate case id")
        actual[case["id"]] = result
    expected = oracle["cases"]
    # Compare canonical JSON so booleans and integers are not interchangeable.
    same = lambda a, b: json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    failures = sorted(key for key in set(actual) | set(expected)
                      if key not in actual or key not in expected or not same(actual[key], expected[key]))
    return {"status": "FAIL" if failures else "PASS", "checked": len(actual),
            "failures": failures, "cases": actual}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parent,
                        help="directory containing networks.json and expected.json")
    parser.add_argument("--json", action="store_true", help="print full recomputed profiles")
    args = parser.parse_args(argv)
    try:
        result = compare(args.data)
    except (ValueError, OSError, TypeError, RecursionError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for name in sorted(result["cases"]):
            case = result["cases"][name]
            outcome = "FAIL" if name in result["failures"] else "PASS"
            print(f"{outcome} {name}: MAA {len(case['before']['maa'])} -> "
                  f"{len(case['after']['maa'])}; D1={int(case['D1'])} D2={int(case['D2'])}")
        if result["failures"]:
            print("Mismatched or missing cases: " + ", ".join(result["failures"]))
        print(f"{result['status']}: {result['checked']} cases")
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
