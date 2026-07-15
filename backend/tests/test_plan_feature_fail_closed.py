from types import SimpleNamespace

import pytest

from app.api.v1.public import (
    get_public_online_payment_flag,
)
from app.core.config import settings
from app.services.plan_features import (
    get_default_feature_value,
    get_plan_feature_value,
)


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, plan=None):
        self.plan = plan

    async def execute(self, statement):
        return ScalarResult(self.plan)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "plan_name",
    [
        None,
        "",
        "unknown",
        "legacy-invalid-plan",
    ],
)
async def test_public_payment_flag_fails_closed_for_unknown_plan(
    plan_name,
):
    store = SimpleNamespace(
        plan_name=plan_name,
    )

    result = await get_public_online_payment_flag(
        FakeSession(),
        store,
    )

    assert result is False


@pytest.mark.asyncio
async def test_public_payment_flag_keeps_defined_plan_fallback(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "PAYMENTS_ENABLED",
        True,
    )

    store = SimpleNamespace(
        plan_name="starter",
    )

    result = await get_public_online_payment_flag(
        FakeSession(),
        store,
    )

    assert result is True


@pytest.mark.parametrize(
    "plan_name",
    [
        None,
        "",
        "unknown",
        "legacy-invalid-plan",
    ],
)
@pytest.mark.parametrize(
    "feature_name",
    [
        "can_upload_images",
        "can_use_custom_domain",
        "can_receive_online_payments",
    ],
)
def test_default_features_fail_closed_for_unknown_plan(
    plan_name,
    feature_name,
):
    assert (
        get_default_feature_value(
            plan_name,
            feature_name,
        )
        is False
    )


def test_default_features_keep_defined_plan_values():
    assert (
        get_default_feature_value(
            "starter",
            "can_receive_online_payments",
        )
        is True
    )

    assert (
        get_default_feature_value(
            "starter",
            "can_use_custom_domain",
        )
        is False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "plan_name",
    [
        None,
        "",
        "unknown",
        "legacy-invalid-plan",
    ],
)
async def test_plan_feature_service_fails_closed_for_unknown_plan(
    plan_name,
):
    store = SimpleNamespace(
        plan_name=plan_name,
    )

    allowed = await get_plan_feature_value(
        FakeSession(),
        store,
        "can_receive_online_payments",
    )

    assert allowed is False


@pytest.mark.asyncio
async def test_database_plan_remains_authoritative():
    plan = SimpleNamespace(
        is_active=True,
        can_receive_online_payments=True,
    )

    store = SimpleNamespace(
        plan_name="business",
    )

    allowed = await get_plan_feature_value(
        FakeSession(plan),
        store,
        "can_receive_online_payments",
    )

    assert allowed is True
