"""Exchange rate tool using Frankfurter API (free, no API key required)."""

import requests
from typing import Dict, Any, Optional
from ...debug import debug_log
from ..base import Tool, ToolContext
from ..types import ToolExecutionResult

_FRANKFURTER_BASE = "https://api.frankfurter.app"

# Common currency names for readable output
_CURRENCY_NAMES: Dict[str, str] = {
    "USD": "US Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "PEN": "Peruvian Sol",
    "BRL": "Brazilian Real",
    "CLP": "Chilean Peso",
    "ARS": "Argentine Peso",
    "MXN": "Mexican Peso",
    "COP": "Colombian Peso",
    "JPY": "Japanese Yen",
    "CNY": "Chinese Yuan",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
    "CHF": "Swiss Franc",
}

# Common aliases the LLM or user might say
_ALIASES: Dict[str, str] = {
    "sol": "PEN",
    "soles": "PEN",
    "dolar": "USD",
    "dólar": "USD",
    "dolares": "USD",
    "dólares": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "euro": "EUR",
    "euros": "EUR",
    "libra": "GBP",
    "libras": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "real": "BRL",
    "reales": "BRL",
    "yuan": "CNY",
    "yen": "JPY",
    "peso": "ARS",
    "pesos": "ARS",
}


def _resolve_currency(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    code = raw.strip().upper()
    if len(code) == 3:
        return code
    return _ALIASES.get(raw.strip().lower())


class ExchangeRateTool(Tool):
    """Tool for getting real-time exchange rates via Frankfurter API."""

    @property
    def name(self) -> str:
        return "getExchangeRate"

    @property
    def description(self) -> str:
        return (
            "Get real-time exchange rates between currencies. "
            "Use for questions like 'how much is 100 dollars in soles', "
            "'dólar hoy', 'tipo de cambio', 'tasa de cambio'. "
            "Supports USD, EUR, GBP, PEN, BRL, CLP, ARS, MXN, JPY, CNY and more. "
            "Defaults to USD→PEN if no currencies specified."
        )

    @property
    def inputSchema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base": {
                    "type": "string",
                    "description": "Base currency code or name (e.g. 'USD', 'EUR', 'dolar'). Defaults to USD.",
                },
                "target": {
                    "type": "string",
                    "description": "Target currency code or name (e.g. 'PEN', 'EUR', 'soles'). Defaults to PEN.",
                },
                "amount": {
                    "type": "number",
                    "description": "Amount to convert. Defaults to 1.",
                },
            },
            "required": [],
        }

    def run(self, args: Optional[Dict[str, Any]], context: ToolContext) -> ToolExecutionResult:
        context.user_print("💱 Fetching exchange rate...")

        a = args or {}
        base = _resolve_currency(a.get("base")) or "USD"
        target = _resolve_currency(a.get("target")) or "PEN"
        amount: float = float(a.get("amount") or 1)

        if base == target:
            return ToolExecutionResult(
                success=True,
                reply_text=f"1 {base} = 1 {target} (same currency).",
            )

        debug_log(f"    💱 fetching {base}→{target} rate", "tools")

        try:
            url = f"{_FRANKFURTER_BASE}/latest"
            resp = requests.get(
                url,
                params={"base": base, "symbols": target},
                timeout=8,
                headers={"User-Agent": "JARVIS/1.0"},
            )

            if resp.status_code == 404:
                return ToolExecutionResult(
                    success=False,
                    reply_text=(
                        f"Currency '{base}' or '{target}' not found. "
                        "Try using standard 3-letter codes like USD, EUR, PEN."
                    ),
                )

            resp.raise_for_status()
            data = resp.json()

            rate = data.get("rates", {}).get(target)
            if rate is None:
                return ToolExecutionResult(
                    success=False,
                    reply_text=f"Exchange rate for {base}→{target} is not available.",
                )

            converted = round(amount * rate, 4)
            date = data.get("date", "today")

            base_name = _CURRENCY_NAMES.get(base, base)
            target_name = _CURRENCY_NAMES.get(target, target)

            if amount == 1:
                summary = f"1 {base} ({base_name}) = {rate:.4f} {target} ({target_name})"
            else:
                summary = (
                    f"{amount:g} {base} ({base_name}) = {converted:g} {target} ({target_name})\n"
                    f"Rate: 1 {base} = {rate:.4f} {target}"
                )

            result = f"{summary}\nAs of: {date}"

            debug_log(f"    ✅ rate: 1 {base} = {rate} {target} ({date})", "tools")
            context.user_print(f"✅ 1 {base} = {rate:.4f} {target}")

            return ToolExecutionResult(success=True, reply_text=result)

        except requests.exceptions.Timeout:
            debug_log("exchange rate request timed out", "tools")
            context.user_print("⚠️ Exchange rate service timeout.")
            return ToolExecutionResult(
                success=False,
                reply_text="Exchange rate service is taking too long. Please try again.",
            )
        except requests.exceptions.RequestException as e:
            debug_log(f"exchange rate request failed: {e}", "tools")
            context.user_print("⚠️ Exchange rate service unavailable.")
            return ToolExecutionResult(
                success=False,
                reply_text="Exchange rate service is temporarily unavailable. Please try again later.",
            )
        except Exception as e:
            debug_log(f"exchange rate error: {e}", "tools")
            context.user_print("⚠️ Error getting exchange rate.")
            return ToolExecutionResult(
                success=False,
                reply_text=f"Error getting exchange rate: {e}",
            )
