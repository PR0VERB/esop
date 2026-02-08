"""
Velocity Trade / JSE integration client (STUB).

Provides stub implementations for:
- Executing share trades
- Retrieving trade schedules
- Getting JSE contract notes
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from apps.integrations.base import BaseIntegrationClient
from apps.integrations.models import IntegrationStatus, IntegrationSystem


class TradeStatus(str, Enum):
    """Status of a share trade."""
    PENDING = "pending"
    EXECUTED = "executed"
    SETTLED = "settled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class TradeRequest:
    """Request to execute a share trade."""
    beneficiary_id: str
    shares: int
    trade_type: str = "SELL"  # SELL or BUY
    price_type: str = "MARKET"  # MARKET or LIMIT
    limit_price: Optional[Decimal] = None


@dataclass
class TradeResponse:
    """Response from trade execution."""
    trade_reference: str
    status: TradeStatus
    executed_price: Optional[Decimal] = None
    executed_shares: int = 0
    trade_date: Optional[date] = None
    settlement_date: Optional[date] = None
    message: str = ""


@dataclass
class ContractNote:
    """JSE contract note details."""
    contract_number: str
    trade_reference: str
    trade_date: date
    settlement_date: date
    shares: int
    price_per_share: Decimal
    gross_value: Decimal
    fees: Decimal
    net_value: Decimal


class VelocityTradeClient(BaseIntegrationClient):
    """
    Velocity Trade client (STUB implementation).
    
    In production, this would connect to Velocity Trade / JSE API.
    For now, returns mock data and logs all calls.
    """

    system = IntegrationSystem.VELOCITY_TRADE

    def health_check(self) -> bool:
        """Check if Velocity Trade API is reachable."""
        log = self._create_log("health_check", {})
        self._complete_log(log, status=IntegrationStatus.SUCCESS, response_code=200)
        return True

    def execute_trade(
        self,
        request: TradeRequest,
        *,
        idempotency_key: str = "",
    ) -> TradeResponse:
        """
        Execute a share trade via Velocity Trade.
        
        STUB: Returns mock pending trade response.
        """
        log = self._create_log(
            "execute_trade",
            {
                "beneficiary_id": request.beneficiary_id,
                "shares": request.shares,
                "trade_type": request.trade_type,
                "price_type": request.price_type,
            },
            reference_model="beneficiaries.Beneficiary",
            reference_id=request.beneficiary_id,
            idempotency_key=idempotency_key,
        )
        
        # STUB: Generate mock trade reference
        mock_ref = f"VT-{datetime.now().strftime('%Y%m%d')}-{request.beneficiary_id[:6]}"
        
        response = TradeResponse(
            trade_reference=mock_ref,
            status=TradeStatus.PENDING,
            executed_shares=request.shares,
            message="Trade submitted (STUB)",
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={
                "trade_reference": response.trade_reference,
                "status": response.status.value,
            },
            response_code=200,
        )
        return response

    def get_trade_status(self, trade_reference: str) -> TradeResponse:
        """
        Check status of a submitted trade.
        
        STUB: Returns executed status with mock price.
        """
        log = self._create_log(
            "get_trade_status",
            {"trade_reference": trade_reference},
        )
        
        # STUB: Return executed status
        today = date.today()
        response = TradeResponse(
            trade_reference=trade_reference,
            status=TradeStatus.EXECUTED,
            executed_price=Decimal("150.00"),  # Mock price
            executed_shares=100,
            trade_date=today,
            settlement_date=today,
            message="Trade executed (STUB)",
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={
                "trade_reference": response.trade_reference,
                "status": response.status.value,
                "executed_price": str(response.executed_price),
            },
            response_code=200,
        )
        return response

    def get_contract_note(self, trade_reference: str) -> Optional[ContractNote]:
        """
        Retrieve JSE contract note for a settled trade.
        
        STUB: Returns mock contract note.
        """
        log = self._create_log(
            "get_contract_note",
            {"trade_reference": trade_reference},
        )
        
        # STUB: Return mock contract note
        today = date.today()
        note = ContractNote(
            contract_number=f"JSE-{trade_reference}",
            trade_reference=trade_reference,
            trade_date=today,
            settlement_date=today,
            shares=100,
            price_per_share=Decimal("150.00"),
            gross_value=Decimal("15000.00"),
            fees=Decimal("150.00"),
            net_value=Decimal("14850.00"),
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={"contract_number": note.contract_number},
            response_code=200,
        )
        return note

