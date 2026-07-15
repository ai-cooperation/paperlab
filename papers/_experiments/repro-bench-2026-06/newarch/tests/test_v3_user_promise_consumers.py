"""Class-level drift guard: every user-promise contract field must be consumed.

Product gap (first external user, 2026-07-15, v3_4dc73d199e17): notify_email
sat in every v3 contract while ZERO v3 code consumed it — the promised
completion email never fired. test_v3_user_notification.py pins that ONE
field's loop; this file guards the CLASS, so the next promise field cannot be
silently unconsumed.

The set of user-promise fields is enumerated from the served contract schema,
never from a hand-written list in a test (feedback_enumerate_the_set_from_code):

- Registry: PaperPack().contract_schema() — the exact object the b-side
  negotiates against via GET /v3/schema/paper/contract_v3.schema.json. A
  property carrying the "x-user-promise" marker declares a user-facing
  delivery obligation.
- Forward guard (the incident class): every marked field must have a consumer
  call site in a module import-reachable from EVERY v3 terminal driver — a
  job can end via any driver, so one unwired driver re-opens the original bug.
- Reverse guard (registry honesty): every contract field the v3 delivery
  module reads must be declared in the schema. notify_email was consumed but
  undeclared for exactly one commit; this direction makes the registry unable
  to fall behind the code.

Candidates audit (2026-07-15, for the next reader): job_runner.py's legacy
v1/v2 delivery also consumed repo_url/repo_owner/repo_name (GitHub repo sync)
and status_url (email body link). Neither is a v3 promise today: v3 delivers
through the public progress page composed from job_id alone (notify.py
PROGRESS_URL_TEMPLATE), and no v3 schema/doc/b-side surface offers a repo.
The day either becomes a v3 promise, mark it in the schema and this file
demands the consumer.
"""
from __future__ import annotations

import ast
from pathlib import Path

from engine_v3.packs.paper import PaperPack

NEWARCH = Path(__file__).resolve().parent.parent

# The v3 terminal drivers: the HTTP job thread + human-review approve endpoint
# (both in engine_v3/routes.py) and the CLI/timer revalidate batch. Kept in
# lockstep with the behavioral pins in test_v3_user_notification.py;
# test_terminal_driver_roots_are_wired_delivery_drivers fails if this list
# rots (file moved, delivery call removed).
TERMINAL_DRIVER_ROOTS = (
    NEWARCH / "engine_v3" / "routes.py",
    NEWARCH / "revalidate_v3_batch.py",
)

PROMISE_MARKER = "x-user-promise"


# --------------------------------------------------------------------------
# Checker primitives (pure, deterministic, stdlib-only — no network, no exec)
# --------------------------------------------------------------------------


def promised_fields(schema: dict) -> dict[str, dict]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return {
        name: spec
        for name, spec in properties.items()
        if isinstance(spec, dict) and PROMISE_MARKER in spec
    }


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_candidates(dotted: str, root: Path) -> list[Path]:
    base = root.joinpath(*dotted.split("."))
    return [base.with_suffix(".py"), base / "__init__.py"]


def _package_of(file: Path, root: Path) -> list[str]:
    relative = file.relative_to(root)
    parts = list(relative.parts[:-1])
    if relative.name == "__init__.py" and parts:
        parts = parts[:-1]
    return parts


def local_imports(file: Path, root: Path) -> set[Path]:
    """Files under `root` that `file` imports (absolute or relative)."""
    found: set[Path] = set()

    def _add(dotted: str) -> None:
        for candidate in _module_candidates(dotted, root):
            if candidate.is_file():
                found.add(candidate.resolve())

    package = _package_of(file, root)
    for node in ast.walk(_parse(file)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                prefix = package[: len(package) - (node.level - 1)]
                module = ".".join(prefix + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            if module:
                _add(module)
            for alias in node.names:
                if module:
                    _add(f"{module}.{alias.name}")
                elif node.level:
                    _add(".".join(package[: len(package) - (node.level - 1)] + [alias.name]))
    return found


def reachable_modules(driver: Path, root: Path) -> set[Path]:
    seen: set[Path] = set()
    queue = [driver.resolve()]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(local_imports(current, root) - seen)
    return seen


def expression_string_constants(file: Path) -> set[str]:
    """String literals used inside real expressions — a consumer witness.

    Two exclusions keep witnesses honest:
    - bare-statement strings (docstrings, stray string statements): prose
      mentioning a field name must never count as consuming it;
    - everything inside a `contract_schema` function: the registry declaring
      a field is import-reachable from the drivers, so without this the
      declaration would witness itself and the guard would never bite.
    """
    tree = _parse(file)
    excluded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            excluded.add(id(node.value))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "contract_schema":
            excluded.update(
                id(inner) for inner in ast.walk(node) if isinstance(inner, ast.Constant)
            )
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in excluded
    }


def unconsumed_promises(schema: dict, drivers: tuple[Path, ...], root: Path) -> list[str]:
    """[(field, driver)] rendered as strings, for every promised field with no
    consumer witness in any module import-reachable from that driver."""
    missing: list[str] = []
    for driver in drivers:
        witnessed: set[str] = set()
        for module in reachable_modules(driver, root):
            witnessed |= expression_string_constants(module)
        for field in sorted(promised_fields(schema)):
            if field not in witnessed:
                missing.append(f"{field} has no consumer reachable from {driver.name}")
    return missing


def delivery_module() -> Path:
    """The v3 user-delivery module, located by code (defines ensure_user_notified)."""
    hits = [
        candidate
        for candidate in sorted((NEWARCH / "engine_v3").glob("*.py"))
        if any(
            isinstance(node, ast.FunctionDef) and node.name == "ensure_user_notified"
            for node in ast.walk(_parse(candidate))
        )
    ]
    assert len(hits) == 1, f"expected exactly one ensure_user_notified definition, found {hits}"
    return hits[0]


def contract_field_reads(file: Path) -> set[str]:
    """Fields read off the loaded contract: contract.get("x") / contract["x"]."""
    fields: set[str] = set()
    for node in ast.walk(_parse(file)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "contract"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            fields.add(node.args[0].value)
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "contract"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            fields.add(node.slice.value)
    return fields


# --------------------------------------------------------------------------
# Live-tree drift guards
# --------------------------------------------------------------------------


def test_notify_email_is_a_declared_user_promise():
    """Floor pin: the enumeration must never silently come back empty — the
    schema declares at least the promise that already burned us."""
    promised = promised_fields(dict(PaperPack().contract_schema()))
    assert "notify_email" in promised


def test_every_user_promise_has_a_consumer_reachable_from_every_terminal_driver():
    missing = unconsumed_promises(
        dict(PaperPack().contract_schema()), TERMINAL_DRIVER_ROOTS, NEWARCH
    )
    assert missing == []


def test_terminal_driver_roots_are_wired_delivery_drivers():
    """Guards the root list itself: each root must exist and actually call the
    delivery primitive, or the reachability walk above starts from a corpse."""
    for driver in TERMINAL_DRIVER_ROOTS:
        assert driver.is_file(), f"terminal driver moved: {driver}"
        assert "ensure_user_notified(" in driver.read_text(encoding="utf-8"), (
            f"{driver.name} no longer calls ensure_user_notified — "
            "re-point TERMINAL_DRIVER_ROOTS at the real v3 terminal drivers"
        )


def test_delivery_module_reads_only_schema_declared_contract_fields():
    """Reverse direction: a contract field consumed by the delivery module but
    absent from the served schema is an undeclared interface — the b-side
    cannot discover it and the registry has fallen behind the code."""
    declared = set((dict(PaperPack().contract_schema()).get("properties") or {}).keys())
    undeclared = contract_field_reads(delivery_module()) - declared
    assert undeclared == set()


# --------------------------------------------------------------------------
# Checker red-path proof (synthetic tree: the guard must bite on the next
# promise field that ships without a consumer)
# --------------------------------------------------------------------------


def _synthetic_tree(tmp_path: Path) -> Path:
    (tmp_path / "driver.py").write_text(
        "import helper\nimport registry\n\ndef finish(contract):\n    return helper.deliver(contract)\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.py").write_text(
        '"""Mentions postal_award only in prose — must not count."""\n'
        "def deliver(contract):\n"
        '    return contract.get("notify_email")\n',
        encoding="utf-8",
    )
    # The registry module declares every field INSIDE contract_schema and is
    # imported by the driver — reproducing the live layout where the schema
    # would witness itself if declaration-site constants counted.
    (tmp_path / "registry.py").write_text(
        "def contract_schema():\n"
        '    return {"properties": {"notify_email": {}, "postal_award": {}}}\n',
        encoding="utf-8",
    )
    return tmp_path


def test_checker_goes_red_when_a_new_promise_field_has_no_consumer(tmp_path: Path):
    root = _synthetic_tree(tmp_path)
    schema = {
        "properties": {
            "notify_email": {"type": "string", PROMISE_MARKER: "completion email"},
            "postal_award": {"type": "string", PROMISE_MARKER: "mailed certificate"},
            "topic": {"type": "string"},
        }
    }
    missing = unconsumed_promises(schema, (root / "driver.py",), root)
    assert missing == ["postal_award has no consumer reachable from driver.py"]


def test_checker_is_green_when_every_promise_is_consumed(tmp_path: Path):
    root = _synthetic_tree(tmp_path)
    schema = {
        "properties": {"notify_email": {"type": "string", PROMISE_MARKER: "email"}}
    }
    assert unconsumed_promises(schema, (root / "driver.py",), root) == []


def test_docstring_mention_is_not_a_consumer(tmp_path: Path):
    root = _synthetic_tree(tmp_path)
    schema = {
        "properties": {"postal_award": {"type": "string", PROMISE_MARKER: "cert"}}
    }
    missing = unconsumed_promises(schema, (root / "driver.py",), root)
    assert missing == ["postal_award has no consumer reachable from driver.py"]
