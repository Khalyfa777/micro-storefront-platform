
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.product_order_field import (
    ProductOrderFieldOption,
)
from app.schemas.product_order_field import (
    ProductOrderFieldCreate,
    ProductOrderFieldOptionCreate,
)
from app.services.conversational_ordering import (
    build_whatsapp_order_summary,
    normalize_fulfillment_configuration,
    resolve_order_fulfillment_method,
    resolve_order_item_configuration,
    resolve_order_location,
    validate_order_field_definition,
)
from app.services.order_idempotency import build_order_request_fingerprint


def option(value, label, adjustment="0.00", active=True):
    return SimpleNamespace(
        value=value,
        label=label,
        price_adjustment=Decimal(adjustment),
        is_active=active,
        sort_order=0,
    )


def field(**overrides):
    values = {
        "key": "size",
        "label": "Size",
        "field_type": "select",
        "placeholder": None,
        "help_text": None,
        "is_required": True,
        "is_sensitive": False,
        "include_in_whatsapp": True,
        "is_active": True,
        "sort_order": 0,
        "validation_rules": {},
        "options": [option("43", "EU 43", "20.00")],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def product(**overrides):
    values = {
        "name": "Black Puma Suede",
        "product_type": "physical",
        "price": Decimal("400.00"),
        "default_fulfillment_method": "delivery",
        "allowed_fulfillment_methods": ["delivery", "pickup"],
        "order_fields": [field()],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_physical_fulfillment_defaults_are_category_aware():
    default_method, allowed = normalize_fulfillment_configuration(
        "physical", None, None
    )
    assert default_method == "delivery"
    assert allowed == ["delivery", "pickup", "seller_confirmation"]


def test_explicit_empty_fulfillment_list_is_rejected():
    with pytest.raises(
        ValueError,
        match="At least one fulfilment method is required",
    ):
        normalize_fulfillment_configuration(
            "physical",
            None,
            [],
        )


def test_incompatible_fulfillment_is_rejected():
    with pytest.raises(ValueError, match="not compatible"):
        normalize_fulfillment_configuration(
            "digital", "delivery", ["delivery"]
        )


@pytest.mark.parametrize(
    "method,message",
    [
        ("delivery", "Delivery location is required"),
        ("on_site_service", "Service location is required"),
    ],
)
def test_location_is_required_for_location_based_fulfillment(
    method,
    message,
):
    with pytest.raises(ValueError, match=message):
        resolve_order_location(method, "   ")


@pytest.mark.parametrize(
    "method",
    [
        "pickup",
        "digital_delivery",
        "activation",
        "appointment",
        "remote_service",
        "reservation",
        "seller_confirmation",
    ],
)
def test_irrelevant_location_is_discarded(method):
    assert (
        resolve_order_location(
            method,
            "Stale hidden location",
        )
        is None
    )


@pytest.mark.parametrize(
    "key,label",
    [
        ("password", "Account password"),
        ("security_code", "Security code"),
        ("verification", "OTP verification code"),
        ("card_number", "Card number"),
    ],
)
def test_credential_collection_fields_are_rejected(key, label):
    with pytest.raises(ValueError, match="prohibited credential"):
        validate_order_field_definition(
            {
                "key": key,
                "label": label,
                "field_type": "text",
                "options": [],
            }
        )


@pytest.mark.parametrize(
    "field_property,field_value",
    [
        ("placeholder", "Enter your password"),
        ("help_text", "Type the OTP sent to your phone"),
        ("placeholder", "Enter your PIN"),
        ("help_text", "Enter the card CVV"),
        ("help_text", "Provide the full card number"),
    ],
)
def test_credential_collection_in_customer_prompt_is_rejected(
    field_property,
    field_value,
):
    definition = {
        "key": "account_details",
        "label": "Account details",
        "field_type": "text",
        "placeholder": None,
        "help_text": None,
        "options": [],
    }
    definition[field_property] = field_value

    with pytest.raises(
        ValueError,
        match="prohibited credential",
    ):
        validate_order_field_definition(
            definition
        )


@pytest.mark.parametrize(
    "wording",
    [
        "Enter your card details",
        "Provide your card information",
        "Add your card info",
        "Type your card data",
    ],
)
def test_card_information_wording_is_rejected(wording):
    with pytest.raises(
        ValueError,
        match="prohibited credential",
    ):
        validate_order_field_definition(
            {
                "key": "payment_details",
                "label": "Payment details",
                "field_type": "text",
                "help_text": wording,
                "options": [],
            }
        )


def test_required_confirmation_checkbox_rejects_false():
    confirmation_field = field(
        key="terms_confirmed",
        label="Confirm the order terms",
        field_type="checkbox",
        is_required=True,
        options=[],
    )

    with pytest.raises(
        ValueError,
        match="Confirm the order terms must be confirmed",
    ):
        resolve_order_item_configuration(
            product(
                order_fields=[
                    confirmation_field
                ]
            ),
            {
                "terms_confirmed": False,
            },
        )


def test_optional_checkbox_can_record_false():
    optional_field = field(
        key="gift_wrap",
        label="Add gift wrap",
        field_type="checkbox",
        is_required=False,
        options=[],
    )

    resolved = resolve_order_item_configuration(
        product(
            order_fields=[
                optional_field
            ]
        ),
        {
            "gift_wrap": False,
        },
    )

    assert resolved.selected_options == {
        "gift_wrap": False,
    }
    assert (
        resolved.configuration_snapshot[0][
            "display_value"
        ]
        == "No"
    )


def test_sensitive_field_cannot_be_sent_to_whatsapp():
    with pytest.raises(ValueError, match="cannot be included"):
        validate_order_field_definition(
            {
                "key": "account_email",
                "label": "Account email",
                "field_type": "email",
                "is_sensitive": True,
                "include_in_whatsapp": True,
                "options": [],
            }
        )


def test_backend_resolves_option_price_and_snapshot():
    resolved = resolve_order_item_configuration(
        product(),
        {"size": "43"},
    )
    assert resolved.unit_price == Decimal("420.00")
    assert resolved.selected_options == {"size": "43"}
    assert resolved.configuration_snapshot[0]["display_value"] == "EU 43"


def test_required_order_field_is_enforced():
    with pytest.raises(ValueError, match="Size is required"):
        resolve_order_item_configuration(product(), {})


def test_multi_item_fulfillment_requires_common_method():
    physical = product()
    digital = product(
        product_type="digital",
        default_fulfillment_method="digital_delivery",
        allowed_fulfillment_methods=["digital_delivery"],
        order_fields=[],
    )
    with pytest.raises(ValueError, match="do not share"):
        resolve_order_fulfillment_method([physical, digital], None)


def test_whatsapp_summary_is_structured_and_excludes_sensitive_fields():
    order_item = SimpleNamespace(
        product_name="Black Puma Suede",
        quantity=1,
        line_total=Decimal("420.00"),
        configuration_snapshot=[
            {
                "label": "Size",
                "display_value": "EU 43",
                "is_sensitive": False,
                "include_in_whatsapp": True,
            },
            {
                "label": "Account email",
                "display_value": "private@example.com",
                "is_sensitive": True,
                "include_in_whatsapp": False,
            },
        ],
    )
    order = SimpleNamespace(
        order_number="ORD-SP4821",
        customer_name="Ama Mensah",
        customer_phone="233241234567",
        fulfillment_method="delivery",
        delivery_address="Accra",
        customer_note=None,
        currency="GHS",
        total=Decimal("420.00"),
        items=[order_item],
    )
    summary = build_whatsapp_order_summary(order, "TG Digital Hub")
    assert "Order reference: ORD-SP4821" in summary
    assert "Size: EU 43" in summary
    assert "Quantity: 1" in summary
    assert "Delivery location: Accra" in summary
    assert "Total: GHS 420.00" in summary
    assert "private@example.com" not in summary


def test_whatsapp_summary_labels_on_site_service_location():
    order = SimpleNamespace(
        order_number="ORD-SERVICE",
        customer_name="Ama Mensah",
        customer_phone="233241234567",
        fulfillment_method="on_site_service",
        delivery_address="East Legon",
        customer_note=None,
        currency="GHS",
        total=Decimal("200.00"),
        items=[],
    )

    summary = build_whatsapp_order_summary(
        order,
        "TG Digital Hub",
    )

    assert "Service location: East Legon" in summary
    assert "Delivery location:" not in summary


def test_whatsapp_summary_omits_stale_location_for_pickup():
    order = SimpleNamespace(
        order_number="ORD-PICKUP",
        customer_name="Ama Mensah",
        customer_phone="233241234567",
        fulfillment_method="pickup",
        delivery_address="Stale hidden location",
        customer_note=None,
        currency="GHS",
        total=Decimal("200.00"),
        items=[],
    )

    summary = build_whatsapp_order_summary(
        order,
        "TG Digital Hub",
    )

    assert "Stale hidden location" not in summary
    assert "Delivery location:" not in summary
    assert "Service location:" not in summary


def test_idempotency_fingerprint_covers_configuration_and_handoff():
    base = {
        "store_slug": "demo-store",
        "customer_name": "Customer",
        "customer_phone": "233241234567",
        "handoff_channel": "whatsapp",
        "items": [
            {
                "product_id": "00000000-0000-0000-0000-000000000001",
                "quantity": 1,
                "selected_options": {"size": "43"},
            }
        ],
    }
    changed = {
        **base,
        "items": [
            {
                **base["items"][0],
                "selected_options": {"size": "44"},
            }
        ],
    }
    assert build_order_request_fingerprint(base) != build_order_request_fingerprint(changed)

def test_request_schema_rejects_arbitrary_pattern_rule():
    with pytest.raises(ValidationError):
        ProductOrderFieldCreate.model_validate(
            {
                "key": "reference",
                "label": "Reference",
                "field_type": "text",
                "validation_rules": {
                    "pattern": r"^(a+)+$",
                },
                "options": [],
            }
        )


def test_legacy_pattern_rule_is_rejected_before_value_validation():
    unsafe_field = field(
        key="reference",
        label="Reference",
        field_type="text",
        validation_rules={
            "pattern": r"^(a+)+$",
        },
        options=[],
    )

    with pytest.raises(
        ValueError,
        match="Unsupported validation rule",
    ):
        resolve_order_item_configuration(
            product(order_fields=[unsafe_field]),
            {
                "reference": "a" * 2000 + "!",
            },
        )


def test_supported_text_length_rules_are_normalized_and_enforced():
    normalized = validate_order_field_definition(
        {
            "key": "engraving",
            "label": "Engraving",
            "field_type": "text",
            "validation_rules": {
                "min_length": 2,
                "max_length": 5,
            },
            "options": [],
        }
    )

    assert normalized["validation_rules"] == {
        "min_length": 2,
        "max_length": 5,
    }

    engraving_field = field(
        key="engraving",
        label="Engraving",
        field_type="text",
        validation_rules=normalized["validation_rules"],
        options=[],
    )

    with pytest.raises(ValueError, match="too short"):
        resolve_order_item_configuration(
            product(order_fields=[engraving_field]),
            {
                "engraving": "A",
            },
        )

    resolved = resolve_order_item_configuration(
        product(order_fields=[engraving_field]),
        {
            "engraving": "AMG",
        },
    )

    assert resolved.selected_options == {
        "engraving": "AMG",
    }


def test_number_value_rejects_extreme_exponent():
    number_field = field(
        key="guest_count",
        label="Guest count",
        field_type="number",
        options=[],
        validation_rules={},
    )

    with pytest.raises(
        ValueError,
        match="Guest count is too long",
    ):
        resolve_order_item_configuration(
            product(
                order_fields=[
                    number_field
                ]
            ),
            {
                "guest_count": "1e100000",
            },
        )


def test_number_validation_rules_require_a_valid_range():
    with pytest.raises(
        ValueError,
        match="cannot exceed maximum",
    ):
        validate_order_field_definition(
            {
                "key": "guest_count",
                "label": "Guest count",
                "field_type": "number",
                "validation_rules": {
                    "min": 10,
                    "max": 2,
                },
                "options": [],
            }
        )


def test_validation_rules_are_restricted_by_field_type():
    with pytest.raises(
        ValueError,
        match="Unsupported validation rule",
    ):
        validate_order_field_definition(
            {
                "key": "size",
                "label": "Size",
                "field_type": "select",
                "validation_rules": {
                    "max_length": 20,
                },
                "options": [
                    {
                        "value": "44",
                        "label": "44",
                        "price_adjustment": "0.00",
                        "is_active": True,
                        "sort_order": 0,
                    }
                ],
            }
        )

def test_option_price_schema_rejects_unsafe_adjustments():
    for unsafe_value in (
        "-0.01",
        "NaN",
        "Infinity",
        "-Infinity",
    ):
        with pytest.raises(ValidationError):
            ProductOrderFieldOptionCreate.model_validate(
                {
                    "value": "priority",
                    "label": "Priority",
                    "price_adjustment": unsafe_value,
                }
            )


def test_order_field_definition_rejects_negative_option_charge():
    with pytest.raises(
        ValueError,
        match="must be zero or more",
    ):
        validate_order_field_definition(
            {
                "key": "delivery_speed",
                "label": "Delivery speed",
                "field_type": "select",
                "options": [
                    {
                        "value": "priority",
                        "label": "Priority",
                        "price_adjustment": "-1.00",
                    }
                ],
            }
        )


def test_order_resolution_rejects_legacy_negative_option_charge():
    unsafe_field = field(
        options=[
            option(
                "43",
                "EU 43",
                "-1.00",
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match="must be zero or more",
    ):
        resolve_order_item_configuration(
            product(order_fields=[unsafe_field]),
            {
                "size": "43",
            },
        )


def test_zero_and_positive_option_charges_remain_supported():
    zero = ProductOrderFieldOptionCreate.model_validate(
        {
            "value": "standard",
            "label": "Standard",
            "price_adjustment": "0.00",
        }
    )
    positive = ProductOrderFieldOptionCreate.model_validate(
        {
            "value": "priority",
            "label": "Priority",
            "price_adjustment": "25.50",
        }
    )

    assert zero.price_adjustment == Decimal("0.00")
    assert positive.price_adjustment == Decimal("25.50")

    resolved = resolve_order_item_configuration(
        product(),
        {
            "size": "43",
        },
    )

    assert resolved.unit_price == Decimal("420.00")


def test_option_price_model_exposes_database_safety_constraint():
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in (
            ProductOrderFieldOption.__table__.constraints
        )
        if getattr(constraint, "sqltext", None) is not None
    }

    constraint_sql = constraints[
        (
            "ck_product_order_option_price_"
            "non_negative_finite"
        )
    ]

    assert "price_adjustment >= 0" in constraint_sql
    assert "Infinity" in constraint_sql
