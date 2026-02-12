"""
JSE market data integration via Yahoo Finance.

Fetches share price, market cap, sector, and other details
for JSE-listed companies using the .JO ticker suffix.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.integrations.base import BaseIntegrationClient
from apps.integrations.models import IntegrationStatus, IntegrationSystem, JSECompany

logger = logging.getLogger(__name__)


class JSEClient(BaseIntegrationClient):
    """
    Client for fetching JSE company data from Yahoo Finance.
    Inherits logging, error handling, and sanitisation from BaseIntegrationClient.
    """

    system = IntegrationSystem.JSE

    def health_check(self) -> bool:
        """Check if Yahoo Finance is reachable."""
        try:
            import yfinance as yf

            ticker = yf.Ticker("SOL.JO")
            info = ticker.info
            return bool(info.get("symbol"))
        except Exception:
            return False

    def enrich_jse_company(
        self,
        jse_company: JSECompany,
        *,
        force: bool = False,
        max_age_hours: int = 24,
    ) -> dict[str, Any]:
        """
        Fetch live data for a JSE company and cache it on the model.

        Args:
            jse_company: The JSECompany record to enrich.
            force: If True, fetch even if recently enriched.
            max_age_hours: Skip fetch if enriched within this many hours.

        Returns:
            dict with the enriched data.
        """
        if (
            not force
            and jse_company.last_enriched_at
            and jse_company.last_enriched_at > timezone.now() - timedelta(hours=max_age_hours)
        ):
            return {
                "status": "cached",
                "share_price": str(jse_company.share_price),
                "market_cap": jse_company.market_cap,
                "sector": jse_company.sector,
            }

        log = self._create_log(
            operation="enrich_jse_company",
            request_data={"ticker": jse_company.yahoo_ticker},
            reference_model="JSECompany",
            reference_id=str(jse_company.pk),
        )

        try:
            import yfinance as yf

            ticker = yf.Ticker(jse_company.yahoo_ticker)
            info = ticker.info

            share_price = info.get("currentPrice") or info.get("regularMarketPrice")
            market_cap_val = info.get("marketCap")
            sector = info.get("sector", "")

            update_fields = ["last_enriched_at", "share_price", "market_cap"]
            jse_company.last_enriched_at = timezone.now()
            jse_company.share_price = Decimal(str(share_price)) if share_price else None
            jse_company.market_cap = market_cap_val

            if sector and not jse_company.sector:
                jse_company.sector = sector
                update_fields.append("sector")

            jse_company.save(update_fields=update_fields)

            result = {
                "status": "success",
                "share_price": str(jse_company.share_price),
                "market_cap": market_cap_val,
                "sector": jse_company.sector,
                "company_name": info.get("longName", jse_company.company_name),
                "currency": info.get("currency", "ZAR"),
            }

            self._complete_log(
                log,
                status=IntegrationStatus.SUCCESS,
                response_data=result,
                response_code=200,
            )
            return result

        except Exception as e:
            self._handle_error(log, e, allow_retry=False)
            return {
                "status": "error",
                "message": str(e),
            }
