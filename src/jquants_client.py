from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

import requests


class JQuantsError(RuntimeError):
    pass


@dataclass
class JQuantsClient:
    access_token: str | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    email: str | None = None
    password: str | None = None
    base_url: str = "https://api.jquants.com/v1"
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "JQuantsClient":
        access_token = os.environ.get("JQUANTS_PRO_ACCESS_TOKEN") or None
        return cls(
            access_token=access_token,
            refresh_token=os.environ.get("JQUANTS_REFRESH_TOKEN") or None,
            email=os.environ.get("JQUANTS_EMAIL") or None,
            password=os.environ.get("JQUANTS_PASSWORD") or None,
            base_url="https://api.jquants-pro.com/v2" if access_token else "https://api.jquants.com/v1",
        )

    def enabled(self) -> bool:
        return bool(self.access_token or self.refresh_token or (self.email and self.password))

    def ensure_id_token(self) -> str:
        if self.access_token:
            return self.access_token
        if self.id_token:
            return self.id_token
        if not self.refresh_token:
            self.refresh_token = self.fetch_refresh_token()
        response = requests.post(
            f"{self.base_url}/token/auth_refresh",
            params={"refreshtoken": self.refresh_token},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise JQuantsError(f"J-Quants id token request failed: {response.status_code} {response.text[:200]}")
        self.id_token = response.json().get("idToken")
        if not self.id_token:
            raise JQuantsError("J-Quants id token response did not include idToken")
        return self.id_token

    def fetch_refresh_token(self) -> str:
        if not self.email or not self.password:
            raise JQuantsError("J-Quants credentials are not configured")
        response = requests.post(
            f"{self.base_url}/token/auth_user",
            json={"mailaddress": self.email, "password": self.password},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise JQuantsError(f"J-Quants refresh token request failed: {response.status_code} {response.text[:200]}")
        token = response.json().get("refreshToken")
        if not token:
            raise JQuantsError("J-Quants refresh token response did not include refreshToken")
        return token

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.ensure_id_token()
        response = requests.get(
            f"{self.base_url}{path}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise JQuantsError(f"J-Quants GET {path} failed: {response.status_code} {response.text[:200]}")
        return response.json()

    def fetch_earnings_announcements(self, target_date: date) -> list[dict[str, Any]]:
        data = self.get("/fins/announcement", {"date": target_date.isoformat().replace("-", "")})
        rows = data.get("announcement") or data.get("announcements") or []
        return [self._normalize_announcement(row, target_date) for row in rows]

    def fetch_prices(self, code: str, start: date, end: date) -> list[dict[str, Any]]:
        params = {
            "code": code,
            "from": start.isoformat().replace("-", ""),
            "to": end.isoformat().replace("-", ""),
        }
        data = self.get("/prices/daily_quotes", params)
        rows = data.get("daily_quotes") or data.get("DailyQuotes") or []
        return [self._normalize_price(row, code) for row in rows]

    def fetch_statements(self, code: str, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"code": code}
        if start:
            params["from"] = start.isoformat().replace("-", "")
        if end:
            params["to"] = end.isoformat().replace("-", "")
        data = self.get("/fins/statements", params)
        return data.get("statements") or data.get("Statements") or []

    def fetch_weekly_margin_interest(self, code: str) -> list[dict[str, Any]]:
        data = self.get("/markets/weekly_margin_interest", {"code": code})
        return data.get("weekly_margin_interest") or data.get("WeeklyMarginInterest") or []

    @staticmethod
    def _normalize_announcement(row: dict[str, Any], target_date: date) -> dict[str, Any]:
        return {
            "date": str(row.get("Date") or row.get("date") or target_date.isoformat())[:10],
            "code": str(row.get("Code") or row.get("LocalCode") or row.get("code") or "").strip(),
            "name": str(row.get("CompanyName") or row.get("CompanyNameEnglish") or row.get("name") or "").strip(),
            "announcement_time": str(row.get("DisclosureTime") or row.get("announcement_time") or "不明").strip(),
            "fiscal_quarter": str(row.get("TypeOfDocument") or row.get("fiscal_quarter") or "").strip(),
            "source": "jquants",
        }

    @staticmethod
    def _normalize_price(row: dict[str, Any], code: str) -> dict[str, Any]:
        close = _float(row.get("Close") or row.get("AdjustmentClose"))
        volume = _float(row.get("Volume") or row.get("AdjustmentVolume"))
        turnover = _float(row.get("TurnoverValue"))
        if turnover is None and close is not None and volume is not None:
            turnover = close * volume
        return {
            "date": str(row.get("Date") or row.get("date"))[:10],
            "code": str(row.get("Code") or row.get("code") or code),
            "open": _float(row.get("Open") or row.get("AdjustmentOpen")),
            "high": _float(row.get("High") or row.get("AdjustmentHigh")),
            "low": _float(row.get("Low") or row.get("AdjustmentLow")),
            "close": close,
            "volume": volume,
            "turnover_value": turnover,
            "source": "jquants",
        }


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
