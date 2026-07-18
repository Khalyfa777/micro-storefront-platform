
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence


PRODUCT_TYPES = frozenset(
    {
        "physical",
        "digital",
        "subscription",
        "service",
        "food",
        "booking",
        "custom",
    }
)

FULFILLMENT_METHODS = frozenset(
    {
        "delivery",
        "pickup",
        "digital_delivery",
        "activation",
        "appointment",
        "on_site_service",
        "remote_service",
        "reservation",
        "seller_confirmation",
    }
)

FIELD_TYPES = frozenset(
    {
        "text",
        "textarea",
        "select",
        "radio",
        "checkbox",
        "number",
        "date",
        "time",
        "datetime",
        "phone",
        "email",
    }
)

PRODUCT_FULFILLMENT_METHODS: dict[str, tuple[str, ...]] = {
    "physical": ("delivery", "pickup", "seller_confirmation"),
    "digital": ("digital_delivery", "activation", "seller_confirmation"),
    "subscription": ("activation", "digital_delivery", "seller_confirmation"),
    "service": (
        "appointment",
        "on_site_service",
        "remote_service",
        "seller_confirmation",
    ),
    "food": ("delivery", "pickup", "seller_confirmation"),
    "booking": ("reservation", "appointment", "seller_confirmation"),
    "custom": (
        "seller_confirmation",
        "delivery",
        "pickup",
        "digital_delivery",
        "activation",
        "appointment",
        "on_site_service",
        "remote_service",
        "reservation",
    ),
}

_FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,49}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ()-]{5,28}[0-9]$")
_PROHIBITED_CREDENTIAL_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:password|passcode|pin|otp|cvv|cvc|"
    r"card[ _-]*(?:number|details?|information|info|data)|"
    r"security[ _-]*code|verification[ _-]*code|secret[ _-]*key|private[ _-]*key)"
    r"(?:$|[^a-z0-9])",
    re.IGNORECASE,
)

_LENGTH_VALIDATION_FIELD_TYPES = frozenset(
    {
        "text",
        "textarea",
        "email",
        "phone",
    }
)
_LENGTH_VALIDATION_RULES = frozenset(
    {
        "min_length",
        "max_length",
    }
)
_NUMBER_VALIDATION_RULES = frozenset(
    {
        "min",
        "max",
    }
)
_MAX_ORDER_FIELD_TEXT_LENGTH = 2000
_MAX_ORDER_FIELD_NUMBER_TEXT_LENGTH = 128


@dataclass(frozen=True)
class ResolvedItemConfiguration:
    unit_price: Decimal
    selected_options: dict[str, Any]
    configuration_snapshot: list[dict[str, Any]]


def _read(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _normalize_token(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        raise ValueError(f"{label} is required.")
    return normalized


def _decimal(value: Any, *, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a valid number.") from error

    if not number.is_finite():
        raise ValueError(f"{label} must be a finite number.")

    return number


def _render_bounded_decimal(
    number: Decimal,
    *,
    label: str,
) -> str:
    _, digits, exponent = number.as_tuple()
    digit_count = max(len(digits), 1)

    if exponent >= 0:
        rendered_length = digit_count + exponent
    elif digit_count + exponent > 0:
        rendered_length = digit_count + 1
    else:
        rendered_length = 2 - exponent

    if number.is_signed():
        rendered_length += 1

    if rendered_length > _MAX_ORDER_FIELD_NUMBER_TEXT_LENGTH:
        raise ValueError(
            f"{label} is too long."
        )

    rendered = format(number, "f")

    if len(rendered) > _MAX_ORDER_FIELD_NUMBER_TEXT_LENGTH:
        raise ValueError(
            f"{label} is too long."
        )

    return rendered


def _non_negative_decimal(
    value: Any,
    *,
    label: str,
) -> Decimal:
    number = _decimal(value, label=label)

    if number < 0:
        raise ValueError(
            f"{label} must be zero or more."
        )

    return number


def _normalize_validation_rules(
    *,
    key: str,
    field_type: str,
    raw_rules: Any,
) -> dict[str, Any]:
    if raw_rules in (None, {}):
        return {}

    if not isinstance(raw_rules, Mapping):
        raise ValueError(
            f"Validation rules for {key} must be an object."
        )

    rules = dict(raw_rules)

    if field_type in _LENGTH_VALIDATION_FIELD_TYPES:
        allowed_rules = _LENGTH_VALIDATION_RULES
    elif field_type == "number":
        allowed_rules = _NUMBER_VALIDATION_RULES
    else:
        allowed_rules = frozenset()

    unsupported_rules = sorted(
        str(rule)
        for rule in rules
        if rule not in allowed_rules
    )
    if unsupported_rules:
        raise ValueError(
            f"Unsupported validation rule(s) for {key}: "
            + ", ".join(unsupported_rules)
            + "."
        )

    normalized: dict[str, Any] = {}

    if field_type in _LENGTH_VALIDATION_FIELD_TYPES:
        for rule_name in ("min_length", "max_length"):
            if rule_name not in rules:
                continue

            rule_value = rules[rule_name]
            if (
                isinstance(rule_value, bool)
                or not isinstance(rule_value, int)
            ):
                raise ValueError(
                    f"{rule_name} for {key} must be a whole number."
                )

            minimum = 0 if rule_name == "min_length" else 1
            if not minimum <= rule_value <= _MAX_ORDER_FIELD_TEXT_LENGTH:
                raise ValueError(
                    f"{rule_name} for {key} must be between "
                    f"{minimum} and {_MAX_ORDER_FIELD_TEXT_LENGTH}."
                )

            normalized[rule_name] = rule_value

        minimum_length = normalized.get("min_length", 0)
        maximum_length = normalized.get(
            "max_length",
            _MAX_ORDER_FIELD_TEXT_LENGTH,
        )
        if minimum_length > maximum_length:
            raise ValueError(
                f"min_length for {key} cannot exceed max_length."
            )

    if field_type == "number":
        for rule_name in ("min", "max"):
            if rule_name not in rules:
                continue

            number = _decimal(
                rules[rule_name],
                label=f"{rule_name} for {key}",
            )
            normalized[rule_name] = _render_bounded_decimal(
                number,
                label=f"{rule_name} for {key}",
            )

        if (
            "min" in normalized
            and "max" in normalized
            and _decimal(
                normalized["min"],
                label=f"Minimum for {key}",
            )
            > _decimal(
                normalized["max"],
                label=f"Maximum for {key}",
            )
        ):
            raise ValueError(
                f"Minimum for {key} cannot exceed maximum."
            )

    return normalized


def normalize_fulfillment_configuration(
    product_type: str,
    default_method: str | None,
    allowed_methods: Sequence[str] | None,
) -> tuple[str, list[str]]:
    normalized_type = _normalize_token(product_type, label="Product type")
    if normalized_type not in PRODUCT_TYPES:
        raise ValueError(f"Unsupported product type: {normalized_type}.")

    compatible = PRODUCT_FULFILLMENT_METHODS[normalized_type]
    raw_allowed = (
        list(compatible)
        if allowed_methods is None
        else list(allowed_methods)
    )
    normalized_allowed: list[str] = []

    for value in raw_allowed:
        method = _normalize_token(value, label="Fulfilment method")
        if method not in FULFILLMENT_METHODS:
            raise ValueError(f"Unsupported fulfilment method: {method}.")
        if method not in compatible:
            raise ValueError(
                f"{method} is not compatible with {normalized_type} products."
            )
        if method not in normalized_allowed:
            normalized_allowed.append(method)

    if not normalized_allowed:
        raise ValueError("At least one fulfilment method is required.")

    normalized_default = (
        _normalize_token(default_method, label="Default fulfilment method")
        if default_method is not None
        else normalized_allowed[0]
    )
    if normalized_default not in normalized_allowed:
        raise ValueError("Default fulfilment method must be in the allowed list.")

    return normalized_default, normalized_allowed


def _field_identity(field: Any) -> tuple[str, str, str]:
    key = _normalize_token(_read(field, "key"), label="Order field key")
    label = str(_read(field, "label") or "").strip()
    field_type = _normalize_token(
        _read(field, "field_type"),
        label=f"Field type for {key}",
    )

    if not _FIELD_KEY_PATTERN.fullmatch(key):
        raise ValueError(
            "Order field keys must start with a letter and use lowercase "
            "letters, numbers, or underscores."
        )
    if not label:
        raise ValueError(f"Label is required for order field {key}.")
    if field_type not in FIELD_TYPES:
        raise ValueError(f"Unsupported order field type: {field_type}.")
    placeholder = str(_read(field, "placeholder") or "").strip()
    help_text = str(_read(field, "help_text") or "").strip()
    customer_prompt = " ".join(
        part
        for part in (
            key,
            label,
            placeholder,
            help_text,
        )
        if part
    )

    if _PROHIBITED_CREDENTIAL_PATTERN.search(customer_prompt):
        raise ValueError(
            f"Order field {key} requests prohibited credential information."
        )

    return key, label, field_type


def validate_order_field_definition(field: Any) -> dict[str, Any]:
    key, label, field_type = _field_identity(field)
    is_sensitive = bool(_read(field, "is_sensitive", False))
    include_in_whatsapp = bool(_read(field, "include_in_whatsapp", True))

    if is_sensitive and include_in_whatsapp:
        raise ValueError(
            f"Sensitive order field {key} cannot be included in WhatsApp."
        )

    options = list(_read(field, "options", []) or [])
    normalized_options: list[dict[str, Any]] = []
    seen_values: set[str] = set()

    for option in options:
        value = str(_read(option, "value") or "").strip()
        option_label = str(_read(option, "label") or "").strip()
        if not value or not option_label:
            raise ValueError(f"Options for {key} require both value and label.")
        if value in seen_values:
            raise ValueError(f"Duplicate option value {value!r} for {key}.")
        seen_values.add(value)
        normalized_options.append(
            {
                "value": value,
                "label": option_label,
                "price_adjustment": _non_negative_decimal(
                    _read(option, "price_adjustment", "0.00"),
                    label=f"Price adjustment for {key}",
                ),
                "is_active": bool(_read(option, "is_active", True)),
                "sort_order": int(_read(option, "sort_order", 0) or 0),
            }
        )

    if field_type in {"select", "radio"} and not any(
        option["is_active"] for option in normalized_options
    ):
        raise ValueError(f"Choice field {key} requires at least one active option.")
    if field_type not in {"select", "radio"} and normalized_options:
        raise ValueError(f"Only select and radio fields may define options ({key}).")

    validation_rules = _normalize_validation_rules(
        key=key,
        field_type=field_type,
        raw_rules=_read(field, "validation_rules", {}),
    )
    return {
        "key": key,
        "label": label,
        "field_type": field_type,
        "placeholder": (str(_read(field, "placeholder") or "").strip() or None),
        "help_text": (str(_read(field, "help_text") or "").strip() or None),
        "is_required": bool(_read(field, "is_required", False)),
        "is_sensitive": is_sensitive,
        "include_in_whatsapp": include_in_whatsapp,
        "is_active": bool(_read(field, "is_active", True)),
        "sort_order": int(_read(field, "sort_order", 0) or 0),
        "validation_rules": validation_rules,
        "options": sorted(
            normalized_options,
            key=lambda option: (option["sort_order"], option["value"]),
        ),
    }


def validate_order_field_definitions(fields: Iterable[Any]) -> list[dict[str, Any]]:
    normalized_fields: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for field in fields:
        normalized = validate_order_field_definition(field)
        if normalized["key"] in seen_keys:
            raise ValueError(f"Duplicate order field key: {normalized['key']}.")
        seen_keys.add(normalized["key"])
        normalized_fields.append(normalized)
    if len(normalized_fields) > 50:
        raise ValueError("A product may define at most 50 order fields.")
    return sorted(
        normalized_fields,
        key=lambda field: (field["sort_order"], field["key"]),
    )


def _validate_scalar_value(
    *,
    key: str,
    field_type: str,
    value: Any,
    rules: Mapping[str, Any],
) -> tuple[Any, str]:
    normalized_rules = _normalize_validation_rules(
        key=key,
        field_type=field_type,
        raw_rules=rules,
    )

    if field_type == "checkbox":
        if isinstance(value, bool):
            resolved = value
        elif str(value).strip().lower() in {"true", "1", "yes", "on"}:
            resolved = True
        elif str(value).strip().lower() in {"false", "0", "no", "off"}:
            resolved = False
        else:
            raise ValueError(f"{key} must be true or false.")
        return resolved, "Yes" if resolved else "No"

    if field_type == "number":
        number = _decimal(value, label=key)
        if normalized_rules.get("min") is not None and number < _decimal(normalized_rules["min"], label=f"{key} minimum"):
            raise ValueError(f"{key} is below the minimum allowed value.")
        if normalized_rules.get("max") is not None and number > _decimal(normalized_rules["max"], label=f"{key} maximum"):
            raise ValueError(f"{key} is above the maximum allowed value.")
        rendered = _render_bounded_decimal(
            number,
            label=key,
        )
        return rendered, rendered

    text = str(value).strip()
    if not text:
        return None, ""
    if len(text) > int(normalized_rules.get("max_length", _MAX_ORDER_FIELD_TEXT_LENGTH)):
        raise ValueError(f"{key} is too long.")
    if len(text) < int(normalized_rules.get("min_length", 0)):
        raise ValueError(f"{key} is too short.")
    if field_type == "email" and _EMAIL_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{key} must be a valid email address.")
    if field_type == "phone" and _PHONE_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{key} must be a valid phone number.")
    try:
        if field_type == "date":
            date.fromisoformat(text)
        elif field_type == "time":
            time.fromisoformat(text)
        elif field_type == "datetime":
            datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{key} must be a valid {field_type} value.") from error
    return text, text


def resolve_order_item_configuration(
    product: Any,
    submitted_options: Mapping[str, Any] | None,
) -> ResolvedItemConfiguration:
    fields = [
        field
        for field in list(_read(product, "order_fields", []) or [])
        if bool(_read(field, "is_active", True))
    ]
    submitted = dict(submitted_options or {})
    known_keys = {_field_identity(field)[0] for field in fields}
    unknown_keys = sorted(set(submitted) - known_keys)
    if unknown_keys:
        raise ValueError(
            "Unknown order option(s): " + ", ".join(unknown_keys) + "."
        )

    selected: dict[str, Any] = {}
    snapshots: list[dict[str, Any]] = []
    total_adjustment = Decimal("0.00")

    for field in sorted(
        fields,
        key=lambda item: (int(_read(item, "sort_order", 0) or 0), str(_read(item, "key"))),
    ):
        key, label, field_type = _field_identity(field)
        raw_value = submitted.get(key)
        missing = raw_value is None or (
            isinstance(raw_value, str) and not raw_value.strip()
        )
        if missing:
            if bool(_read(field, "is_required", False)):
                raise ValueError(f"{label} is required.")
            continue

        price_adjustment = Decimal("0.00")
        if field_type in {"select", "radio"}:
            requested = str(raw_value).strip()
            option = next(
                (
                    option
                    for option in list(_read(field, "options", []) or [])
                    if bool(_read(option, "is_active", True))
                    and str(_read(option, "value") or "").strip() == requested
                ),
                None,
            )
            if option is None:
                raise ValueError(f"Invalid selection for {label}.")
            resolved_value = requested
            display_value = str(_read(option, "label") or requested).strip()
            price_adjustment = _non_negative_decimal(
                _read(option, "price_adjustment", "0.00"),
                label=f"Price adjustment for {label}",
            )
        else:
            resolved_value, display_value = _validate_scalar_value(
                key=label,
                field_type=field_type,
                value=raw_value,
                rules=dict(_read(field, "validation_rules", {}) or {}),
            )
            if resolved_value is None:
                if bool(_read(field, "is_required", False)):
                    raise ValueError(f"{label} is required.")
                continue

            if (
                field_type == "checkbox"
                and bool(_read(field, "is_required", False))
                and resolved_value is not True
            ):
                raise ValueError(f"{label} must be confirmed.")

        selected[key] = resolved_value
        total_adjustment += price_adjustment
        snapshots.append(
            {
                "key": key,
                "label": label,
                "field_type": field_type,
                "value": resolved_value,
                "display_value": display_value,
                "is_sensitive": bool(_read(field, "is_sensitive", False)),
                "include_in_whatsapp": bool(
                    _read(field, "include_in_whatsapp", True)
                ),
                "price_adjustment": format(price_adjustment, ".2f"),
            }
        )

    unit_price = _decimal(_read(product, "price"), label="Product price") + total_adjustment
    if unit_price <= 0:
        raise ValueError("Configured product price must remain greater than zero.")
    return ResolvedItemConfiguration(
        unit_price=unit_price.quantize(Decimal("0.01")),
        selected_options=selected,
        configuration_snapshot=snapshots,
    )


def resolve_order_fulfillment_method(
    products: Sequence[Any],
    requested_method: str | None,
) -> str:
    if not products:
        raise ValueError("An order requires at least one product.")

    allowed_sets: list[set[str]] = []
    preferred: list[str] = []
    for product in products:
        product_type = str(_read(product, "product_type", "physical") or "physical")
        default_method, allowed_methods = normalize_fulfillment_configuration(
            product_type,
            _read(product, "default_fulfillment_method", None),
            _read(product, "allowed_fulfillment_methods", None),
        )
        preferred.append(default_method)
        allowed_sets.append(set(allowed_methods))

    common = set.intersection(*allowed_sets)
    if not common:
        raise ValueError("The selected products do not share a fulfilment method.")

    if requested_method is not None:
        requested = _normalize_token(
            requested_method,
            label="Fulfilment method",
        )
        if requested not in common:
            raise ValueError(
                "The selected fulfilment method is not available for every item."
            )
        return requested

    if len(set(preferred)) == 1 and preferred[0] in common:
        return preferred[0]
    if "seller_confirmation" in common:
        return "seller_confirmation"
    ordered = [
        "delivery",
        "pickup",
        "digital_delivery",
        "activation",
        "appointment",
        "on_site_service",
        "remote_service",
        "reservation",
    ]
    return next(method for method in ordered if method in common)


def resolve_order_location(
    fulfillment_method: str,
    submitted_location: str | None,
) -> str | None:
    method = _normalize_token(
        fulfillment_method,
        label="Fulfilment method",
    )

    if method not in FULFILLMENT_METHODS:
        raise ValueError(
            f"Unsupported fulfilment method: {method}."
        )

    location = str(
        submitted_location or ""
    ).strip()

    if method == "delivery":
        if not location:
            raise ValueError(
                "Delivery location is required."
            )
        return location

    if method == "on_site_service":
        if not location:
            raise ValueError(
                "Service location is required."
            )
        return location

    return None


def _money(currency: str, amount: Any) -> str:
    return f"{currency} {_decimal(amount, label='Amount'):,.2f}"


def build_whatsapp_order_summary(order: Any, store_name: str) -> str:
    currency = str(_read(order, "currency", "GHS") or "GHS")
    fulfillment_method = str(
        _read(
            order,
            "fulfillment_method",
            "seller_confirmation",
        )
        or "seller_confirmation"
    ).strip().lower()
    lines = [
        f"New StorePlug order for {store_name}",
        f"Order reference: {_read(order, 'order_number')}",
        f"Customer: {_read(order, 'customer_name')}",
        f"Contact: {_read(order, 'customer_phone')}",
        f"Fulfilment: {fulfillment_method.replace('_', ' ').title()}",
        "",
        "Items:",
    ]

    for index, item in enumerate(list(_read(order, "items", []) or []), start=1):
        lines.append(f"{index}. {_read(item, 'product_name')}")
        for snapshot in list(_read(item, "configuration_snapshot", []) or []):
            if snapshot.get("is_sensitive") or not snapshot.get("include_in_whatsapp", True):
                continue
            lines.append(
                f"   {snapshot.get('label')}: {snapshot.get('display_value')}"
            )
        lines.append(f"   Quantity: {_read(item, 'quantity')}")
        lines.append(
            f"   Line total: {_money(currency, _read(item, 'line_total'))}"
        )

    delivery_address = str(_read(order, "delivery_address") or "").strip()
    if delivery_address and fulfillment_method == "delivery":
        lines.extend(["", f"Delivery location: {delivery_address}"])
    elif delivery_address and fulfillment_method == "on_site_service":
        lines.extend(["", f"Service location: {delivery_address}"])
    customer_note = str(_read(order, "customer_note") or "").strip()
    if customer_note:
        lines.append(f"Customer note: {customer_note}")
    lines.extend(["", f"Total: {_money(currency, _read(order, 'total'))}"])
    return "\n".join(lines)
