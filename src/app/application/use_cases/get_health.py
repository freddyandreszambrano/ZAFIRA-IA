from app.application.dto.health import HealthDTO


class GetHealthUseCase:
    def __init__(self, app_name: str, version: str = "0.1.0") -> None:
        self._app_name = app_name
        self._version = version

    def execute(self) -> HealthDTO:
        return HealthDTO(status="ok", version=self._version)
