from app.schemas.accounting.bank_reconciliation import (
    AutomaticReconciliationApplyResponse,
    AutomaticReconciliationPreviewResponse,
    AutomaticReconciliationRequest,
    AutomaticReconciliationSuggestion,
    BankReconciliationResponse,
)
from app.services.accounting.bank_reconciliation_service import (
    BankReconciliationService,
)
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


class AutomaticBankReconciliationService:
    """Safely applies only deterministic exact bank-to-ledger matches."""

    def __init__(self, session: AsyncSession) -> None:
        self.manual_service = BankReconciliationService(session)

    async def preview(
        self, organization_id: str, data: AutomaticReconciliationRequest
    ) -> AutomaticReconciliationPreviewResponse:
        transactions = await self.manual_service.list_transactions(
            organization_id, data.bank_account_id, reconciled=False
        )
        claimed_entry_ids: set[str] = set()
        suggestions: list[AutomaticReconciliationSuggestion] = []
        for transaction in sorted(
            transactions, key=lambda item: (item.transaction_date, item.external_id)
        ):
            candidates = await self.manual_service.candidate_entries(
                organization_id, transaction.id, data.date_window_days
            )
            if not candidates:
                suggestions.append(
                    AutomaticReconciliationSuggestion(
                        bank_transaction_id=transaction.id,
                        external_id=transaction.external_id,
                        status="UNMATCHED",
                        reason="NO_EXACT_CANDIDATE",
                    )
                )
                continue
            if len(candidates) != 1:
                suggestions.append(
                    AutomaticReconciliationSuggestion(
                        bank_transaction_id=transaction.id,
                        external_id=transaction.external_id,
                        status="AMBIGUOUS",
                        reason="MULTIPLE_EXACT_CANDIDATES",
                    )
                )
                continue
            candidate = candidates[0]
            if candidate.journal_entry_id in claimed_entry_ids:
                suggestions.append(
                    AutomaticReconciliationSuggestion(
                        bank_transaction_id=transaction.id,
                        external_id=transaction.external_id,
                        status="AMBIGUOUS",
                        candidate=candidate,
                        reason="CANDIDATE_CLAIMED_BY_ANOTHER_TRANSACTION",
                    )
                )
                continue
            claimed_entry_ids.add(candidate.journal_entry_id)
            suggestions.append(
                AutomaticReconciliationSuggestion(
                    bank_transaction_id=transaction.id,
                    external_id=transaction.external_id,
                    status="AUTO_ELIGIBLE",
                    candidate=candidate,
                )
            )
        return AutomaticReconciliationPreviewResponse(
            bank_account_id=data.bank_account_id,
            date_window_days=data.date_window_days,
            suggestions=suggestions,
        )

    async def apply(
        self,
        organization_id: str,
        actor_user_id: str,
        data: AutomaticReconciliationRequest,
    ) -> AutomaticReconciliationApplyResponse:
        preview = await self.preview(organization_id, data)
        reconciliations: list[BankReconciliationResponse] = []
        suggestions: list[AutomaticReconciliationSuggestion] = []
        for suggestion in preview.suggestions:
            if suggestion.status != "AUTO_ELIGIBLE" or suggestion.candidate is None:
                suggestions.append(suggestion)
                continue
            try:
                reconciliation = await self.manual_service.reconcile(
                    organization_id,
                    suggestion.bank_transaction_id,
                    suggestion.candidate.journal_entry_id,
                    actor_user_id,
                    match_method="AUTO_EXACT",
                )
            except HTTPException as exc:
                if exc.status_code != 409:
                    raise
                suggestions.append(
                    suggestion.model_copy(
                        update={
                            "status": "SKIPPED_CONCURRENTLY",
                            "reason": "MATCH_CHANGED_DURING_APPLICATION",
                        }
                    )
                )
            else:
                reconciliations.append(
                    BankReconciliationResponse.model_validate(reconciliation)
                )
                suggestions.append(suggestion)
        return AutomaticReconciliationApplyResponse(
            bank_account_id=data.bank_account_id,
            reconciliations=reconciliations,
            suggestions=suggestions,
        )
