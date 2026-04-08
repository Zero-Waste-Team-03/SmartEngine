from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


class ContractService:
    def __init__(self, contract_path: Path | None = None) -> None:
        self._contract_path = contract_path or Path(__file__).resolve().parents[2] / "contracts.md"

    def read_contract(self) -> str:
        with self._contract_path.open("r", encoding="utf-8") as handle:
            return handle.read()

    @lru_cache(maxsize=1)
    def channels(self) -> list[str]:
        content = self.read_contract()
        return sorted(set(re.findall(r"smart\.[a-z0-9_.-]+", content)))


contract_service = ContractService()
