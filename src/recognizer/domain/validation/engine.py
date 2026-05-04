# SPDX-License-Identifier: MIT

"""Field-level legitimacy validation engine.

This module is document-agnostic: validation rules come from config DB `validators`
and are referenced by template fields (`template_fields.validator_ids`).
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ValidationFailure:
    message: str


ValidatorFn = Callable[[Any, dict[str, Any]], Optional[ValidationFailure]]


class ValidationEngine:
    """Execute typed validators for a single value."""

    def __init__(self) -> None:
        self._registry: dict[str, ValidatorFn] = {
            "required": self._v_required,
            "regex": self._v_regex,
            "amount": self._v_amount,
            "number": self._v_number,
            "date": self._v_date,
            "range": self._v_range,
            "length": self._v_length,
            "enum": self._v_enum,
        }

    def test_value(
        self, *, validator_type: str, config: dict[str, Any], value: Any
    ) -> tuple[bool, str | None]:
        """Test a single value with a single validator."""
        fn = self._registry.get(str(validator_type or "").strip())
        if not fn:
            return False, f"Unknown validator_type: {validator_type}"
        failure = fn(value, config or {})
        return (failure is None), (None if failure is None else failure.message)

    def validate(
        self,
        *,
        common_result: dict[str, Any],
        fields: list[dict[str, Any]],
        validators_by_id: dict[int, dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate extracted fields.

        Args:
            common_result: extracted data (field_name -> value)
            fields: template field contexts. Each item should include:
              - field_name (str)
              - validator_ids (list[int]) optional
            validators_by_id: map validator_id -> {validator_type, config_json/config, name}
        """
        items: list[dict[str, Any]] = []
        invalid_fields = 0
        valid_fields = 0

        for f in fields or []:
            field_name = str(f.get("field_name") or "")
            if not field_name:
                continue
            value = common_result.get(field_name)
            validator_ids = f.get("validator_ids") or []
            if not isinstance(validator_ids, list):
                validator_ids = []

            errors: list[dict[str, Any]] = []
            for vid in validator_ids:
                try:
                    vid_int = int(vid)
                except Exception:
                    continue
                v = validators_by_id.get(vid_int)
                if not v:
                    errors.append(
                        {
                            "validator_id": vid_int,
                            "validator_type": "missing",
                            "message": "Validator not found",
                        }
                    )
                    continue

                vtype = str(v.get("validator_type") or "")
                cfg = (
                    v.get("config")
                    if isinstance(v.get("config"), dict)
                    else v.get("config_json")
                )
                if not isinstance(cfg, dict):
                    cfg = {}
                ok, msg = self.test_value(validator_type=vtype, config=cfg, value=value)
                if not ok:
                    errors.append(
                        {
                            "validator_id": vid_int,
                            "validator_type": vtype,
                            "message": msg or "Validation failed",
                        }
                    )

            is_valid = len(errors) == 0
            if is_valid:
                valid_fields += 1
            else:
                invalid_fields += 1

            items.append(
                {
                    "field": field_name,
                    "value": value,
                    "is_valid": is_valid,
                    "errors": errors,
                }
            )

        total_fields = len(items)
        return {
            "is_valid": invalid_fields == 0,
            "total_fields": total_fields,
            "valid_fields": valid_fields,
            "invalid_fields": invalid_fields,
            "items": items,
        }

    # -------------------------
    # Built-ins
    # -------------------------
    @staticmethod
    def _is_empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) == 0
        return False

    def _v_required(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        if self._is_empty(value):
            msg = str(config.get("message") or "Value is required")
            return ValidationFailure(msg)
        return None

    def _v_regex(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        if self._is_empty(value):
            return None
        pattern = config.get("pattern")
        if not pattern:
            return ValidationFailure("regex.pattern is required")
        flags = 0
        for f in config.get("flags") or []:
            if str(f).lower() in ("i", "ignorecase"):
                flags |= re.IGNORECASE
            if str(f).lower() in ("m", "multiline"):
                flags |= re.MULTILINE
            if str(f).lower() in ("s", "dotall"):
                flags |= re.DOTALL
        try:
            rx = re.compile(str(pattern), flags=flags)
        except re.error as exc:
            return ValidationFailure(f"Invalid regex: {exc}")
        ok = rx.search(str(value)) is not None
        if ok:
            return None
        return ValidationFailure(str(config.get("message") or "Regex not matched"))

    def _v_amount(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        if self._is_empty(value):
            return None
        s = str(value).strip()
        s = s.replace(",", "").replace(" ", "")
        allow_negative = bool(config.get("allow_negative", False))
        try:
            d = Decimal(s)
        except (InvalidOperation, ValueError):
            return ValidationFailure(str(config.get("message") or "Invalid amount"))
        if not allow_negative and d < 0:
            return ValidationFailure(
                str(config.get("message") or "Negative amount is not allowed")
            )
        decimals = config.get("decimals")
        if decimals is not None:
            try:
                dec = int(decimals)
                if dec >= 0:
                    tup = d.as_tuple()
                    actual = abs(tup.exponent) if tup.exponent < 0 else 0
                    if actual > dec:
                        return ValidationFailure(
                            str(config.get("message") or f"Too many decimals (>{dec})")
                        )
            except Exception:
                return ValidationFailure("amount.decimals must be int")
        if config.get("min") is not None:
            try:
                if d < Decimal(str(config["min"])):
                    return ValidationFailure(
                        str(config.get("message") or f"Amount < min ({config['min']})")
                    )
            except Exception:
                return ValidationFailure("amount.min must be numeric")
        if config.get("max") is not None:
            try:
                if d > Decimal(str(config["max"])):
                    return ValidationFailure(
                        str(config.get("message") or f"Amount > max ({config['max']})")
                    )
            except Exception:
                return ValidationFailure("amount.max must be numeric")
        return None

    def _v_number(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        if self._is_empty(value):
            return None
        s = str(value).strip().replace(",", "").replace(" ", "")
        integer = bool(config.get("integer", False))
        try:
            d = Decimal(s)
        except (InvalidOperation, ValueError):
            return ValidationFailure(str(config.get("message") or "Invalid number"))
        if integer and d != d.to_integral_value():
            return ValidationFailure(str(config.get("message") or "Must be integer"))
        if config.get("min") is not None:
            try:
                if d < Decimal(str(config["min"])):
                    return ValidationFailure(
                        str(config.get("message") or f"Number < min ({config['min']})")
                    )
            except Exception:
                return ValidationFailure("number.min must be numeric")
        if config.get("max") is not None:
            try:
                if d > Decimal(str(config["max"])):
                    return ValidationFailure(
                        str(config.get("message") or f"Number > max ({config['max']})")
                    )
            except Exception:
                return ValidationFailure("number.max must be numeric")
        return None

    def _v_date(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        if self._is_empty(value):
            return None
        formats = config.get("formats") or config.get("format") or ["%Y-%m-%d"]
        if isinstance(formats, str):
            formats = [formats]
        s = str(value).strip()
        for fmt in formats:
            try:
                _dt.datetime.strptime(s, str(fmt))
                return None
            except Exception:
                continue
        return ValidationFailure(str(config.get("message") or "Invalid date format"))

    def _v_range(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        # Alias of number range checks (kept for config readability)
        return self._v_number(value, config)

    def _v_length(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        if self._is_empty(value):
            return None
        n = len(str(value))
        if config.get("min") is not None:
            try:
                if n < int(config["min"]):
                    return ValidationFailure(
                        str(config.get("message") or f"Length < min ({config['min']})")
                    )
            except Exception:
                return ValidationFailure("length.min must be int")
        if config.get("max") is not None:
            try:
                if n > int(config["max"]):
                    return ValidationFailure(
                        str(config.get("message") or f"Length > max ({config['max']})")
                    )
            except Exception:
                return ValidationFailure("length.max must be int")
        return None

    def _v_enum(
        self, value: Any, config: dict[str, Any]
    ) -> Optional[ValidationFailure]:
        if self._is_empty(value):
            return None
        items = config.get("items") or config.get("values")
        if not isinstance(items, list) or not items:
            return ValidationFailure("enum.items must be a non-empty list")
        s = str(value)
        ok = s in {str(x) for x in items}
        if ok:
            return None
        return ValidationFailure(str(config.get("message") or "Value not in enum"))
