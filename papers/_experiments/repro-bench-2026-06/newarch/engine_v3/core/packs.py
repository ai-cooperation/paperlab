from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Protocol

from .contracts import PhaseSpec


class ToolProvider(Protocol):
    """Domain-owned deterministic tool boundary."""

    name: str

    def capabilities(self) -> Mapping[str, Any]:
        ...

    def run(self, tool_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


class DomainPack(Protocol):
    name: str

    def contract_schema(self) -> Mapping[str, Any]:
        ...

    def parse_contract(self, raw: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def canonicalize_contract(self, contract: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def contract_hash(self, contract: Mapping[str, Any]) -> str:
        ...

    def skill_bundle(self) -> List[str]:
        ...

    def tool_provider(self) -> ToolProvider:
        ...

    def pipeline_plan(self) -> List[PhaseSpec]:
        ...

    def gate_registry(self) -> Iterable[Mapping[str, Any]]:
        ...

    def status_projection(
        self,
        dossier: Mapping[str, Any],
        run_dir: Path,
    ) -> Mapping[str, Any]:
        ...


class PackRegistry:
    def __init__(self) -> None:
        self._factories: Dict[str, Callable[[], DomainPack]] = {}

    def register(self, name: str, factory: Callable[[], DomainPack]) -> None:
        if not name:
            raise ValueError("pack name is required")
        if name in self._factories:
            raise ValueError("pack already registered: %s" % name)
        self._factories[name] = factory

    def create(self, name: str) -> DomainPack:
        try:
            return self._factories[name]()
        except KeyError as exc:
            raise KeyError("unknown domain pack: %s" % name) from exc

    def names(self) -> list:
        return sorted(self._factories)
