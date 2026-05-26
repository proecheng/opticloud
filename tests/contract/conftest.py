"""Pytest configuration and shared contract-test exports."""

from __future__ import annotations

from tests.contract.registry import (
    CONTRACT_MAX_EXAMPLES,
    CONTRACT_SERVICES,
    FUTURE_CONTRACT_PATHS,
    REQUIRED_CONTRACT_SERVICES,
    ContractService,
    get_contract_service,
)

__all__ = [
    "CONTRACT_MAX_EXAMPLES",
    "CONTRACT_SERVICES",
    "FUTURE_CONTRACT_PATHS",
    "REQUIRED_CONTRACT_SERVICES",
    "ContractService",
    "get_contract_service",
]
