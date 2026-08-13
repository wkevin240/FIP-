from typing import ClassVar


class FixedAssetLifecycleRules:
    _ASSET_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        "DRAFT": frozenset({"ACQUIRED"}),
        "ACQUIRED": frozenset({"IN_SERVICE"}),
        "IN_SERVICE": frozenset({"DISPOSED"}),
        "DISPOSED": frozenset(),
    }

    @classmethod
    def validate_asset_transition(cls, current_status: str, target_status: str) -> None:
        if target_status not in cls._ASSET_TRANSITIONS.get(current_status, frozenset()):
            raise ValueError(
                f"Fixed asset status {current_status} cannot transition to {target_status}"
            )

    @staticmethod
    def validate_asset_mutation(status: str) -> None:
        if status != "DRAFT":
            raise ValueError("Fixed asset can only be modified while status is DRAFT")

    @staticmethod
    def validate_component_mutation(asset_status: str, component_status: str) -> None:
        if asset_status not in {"DRAFT", "ACQUIRED"} or component_status != "DRAFT":
            raise ValueError(
                "Fixed asset component can only be modified before asset commissioning"
            )

    @staticmethod
    def validate_schedule_posting(
        asset_status: str, plan_status: str, line_status: str
    ) -> None:
        if asset_status != "IN_SERVICE":
            raise ValueError("Depreciation posting requires an in-service fixed asset")
        if plan_status != "ACTIVE":
            raise ValueError("Depreciation posting requires an active plan")
        if line_status != "PLANNED":
            raise ValueError("Depreciation schedule line has already been processed")

    @staticmethod
    def validate_disposal(asset_status: str, existing_disposal: bool) -> None:
        if asset_status != "IN_SERVICE":
            raise ValueError("Only an in-service fixed asset can be disposed")
        if existing_disposal:
            raise ValueError("Fixed asset already has a disposal")
