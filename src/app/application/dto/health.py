from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HealthDTO:
    status: str
    version: str
