from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import update

from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository
from app.modules.request_logs.mappers import to_request_log_entry
from app.modules.request_logs.repository import RequestLogsRepository
from app.modules.usage.repository import UsageRepository
from app.modules.usage.service import UsageService

pytestmark = pytest.mark.integration


def _make_account(account_id: str, email: str) -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        email=email,
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access"),
        refresh_token_encrypted=encryptor.encrypt("refresh"),
        id_token_encrypted=encryptor.encrypt("id"),
        last_refresh=utcnow(),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("tier,multiplier", [(None, 1), ("default", 1), ("flex", 0.5), ("priority", 2), ("fast", 2)])
@pytest.mark.parametrize(
    "model,input_tokens,input_usd,cached_input_usd,output_usd,expected",
    [
        ("gpt-6.1-sol", 200_000, 0.2, 0.01, 0.1, 0.31),
        ("GPT-6.1-SOL-2026-09-30", 300_000, 0.8, 0.02, 0.15, 0.97),
    ],
)
async def test_usage_summary_includes_persisted_sol_6_1_cost(
    db_setup,
    tier: str | None,
    multiplier: float,
    model: str,
    input_tokens: int,
    input_usd: float,
    cached_input_usd: float,
    output_usd: float,
    expected: float,
) -> None:
    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        logs_repo = RequestLogsRepository(session)
        service = UsageService(UsageRepository(session), logs_repo, accounts_repo)
        await accounts_repo.upsert(_make_account("sol-6-1", "sol-6-1@example.com"))
        saved = await logs_repo.add_log(
            account_id="sol-6-1",
            request_id="sol_6_1_cost",
            model=model,
            input_tokens=input_tokens,
            cached_input_tokens=100_000,
            output_tokens=10_000,
            service_tier=tier,
            latency_ms=100,
            status="success",
            error_code=None,
            requested_at=utcnow() - timedelta(minutes=1),
        )
        assert saved.cost_usd == pytest.approx(expected * multiplier)
        entry = to_request_log_entry(saved, include_sensitive_metadata=False)
        assert entry.cost_usd == pytest.approx(expected * multiplier)
        assert entry.cost_breakdown.input_usd == pytest.approx(input_usd * multiplier)
        assert entry.cost_breakdown.cached_input_usd == pytest.approx(cached_input_usd * multiplier)
        assert entry.cost_breakdown.output_usd == pytest.approx(output_usd * multiplier)
        assert entry.cost_breakdown.total_usd == pytest.approx(expected * multiplier)
        summary = await service.get_usage_summary()
        assert summary.cost.total_usd_7d == pytest.approx(expected * multiplier)


@pytest.mark.asyncio
async def test_usage_summary_includes_persisted_astra_priority_cost(db_setup):
    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        logs_repo = RequestLogsRepository(session)
        service = UsageService(UsageRepository(session), logs_repo, accounts_repo)
        await accounts_repo.upsert(_make_account("astra", "astra@example.com"))
        saved = await logs_repo.add_log(
            account_id="astra",
            request_id="astra_priority_cost",
            model="gpt-6-astra",
            input_tokens=300_000,
            cached_input_tokens=200_000,
            output_tokens=10_000,
            service_tier="priority",
            latency_ms=100,
            status="success",
            error_code=None,
            requested_at=utcnow() - timedelta(minutes=1),
        )
        assert saved.cost_usd == pytest.approx(6.3)
        summary = await service.get_usage_summary()
        assert summary.cost.total_usd_7d == pytest.approx(6.3)


@pytest.mark.asyncio
async def test_usage_summary_cost_includes_cached_tokens(db_setup):
    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        logs_repo = RequestLogsRepository(session)
        usage_repo = UsageRepository(session)
        service = UsageService(usage_repo, logs_repo, accounts_repo)

        await accounts_repo.upsert(_make_account("acc1", "cached@example.com"))

        now = utcnow()
        await logs_repo.add_log(
            account_id="acc1",
            request_id="req_summary_1",
            model="gpt-5.1",
            input_tokens=1000,
            output_tokens=500,
            cached_input_tokens=200,
            reasoning_tokens=None,
            latency_ms=100,
            status="success",
            error_code=None,
            requested_at=now - timedelta(minutes=5),
        )

        summary = await service.get_usage_summary()
        cost = summary.cost

        expected_raw = (800 / 1_000_000) * 1.25 + (200 / 1_000_000) * 0.125 + (500 / 1_000_000) * 10.0
        expected = round(expected_raw, 6)
        assert cost.total_usd_7d == pytest.approx(expected)


@pytest.mark.asyncio
async def test_usage_summary_metrics(db_setup):
    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        logs_repo = RequestLogsRepository(session)
        usage_repo = UsageRepository(session)
        service = UsageService(usage_repo, logs_repo, accounts_repo)

        await accounts_repo.upsert(_make_account("acc2", "metrics@example.com"))

        now = utcnow()
        await logs_repo.add_log(
            account_id="acc2",
            request_id="req_summary_2",
            model="gpt-5.1",
            input_tokens=10,
            output_tokens=20,
            latency_ms=100,
            status="success",
            error_code=None,
            requested_at=now - timedelta(hours=2),
        )
        await logs_repo.add_log(
            account_id="acc2",
            request_id="req_summary_3",
            model="gpt-5.1",
            input_tokens=5,
            output_tokens=0,
            latency_ms=50,
            status="error",
            error_code="rate_limit_exceeded",
            requested_at=now - timedelta(hours=1),
        )
        # Regression for #1552: cancelled (client-disconnect) terminals stay
        # in the request total but leave the error numerator and top_error,
        # even when they outnumber genuine errors.
        for index in range(2):
            await logs_repo.add_log(
                account_id="acc2",
                request_id=f"req_summary_cancelled_{index}",
                model="gpt-5.1",
                input_tokens=1,
                output_tokens=0,
                latency_ms=10,
                status="cancelled",
                error_code="client_disconnected",
                requested_at=now - timedelta(minutes=30 + index),
            )

        summary = await service.get_usage_summary()
        metrics = summary.metrics
        assert metrics is not None
        assert metrics.requests_7d == 4
        assert metrics.tokens_secondary_window == 37
        assert metrics.error_rate_7d == pytest.approx(0.25)
        assert metrics.top_error == "rate_limit_exceeded"
        assert metrics.cancelled_7d == 2


@pytest.mark.asyncio
async def test_usage_summary_uses_persisted_request_log_cost(db_setup):
    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        logs_repo = RequestLogsRepository(session)
        usage_repo = UsageRepository(session)
        service = UsageService(usage_repo, logs_repo, accounts_repo)

        await accounts_repo.upsert(_make_account("acc3", "persisted-cost@example.com"))

        now = utcnow()
        log = await logs_repo.add_log(
            account_id="acc3",
            request_id="req_summary_persisted_cost",
            model="gpt-5.1",
            input_tokens=1000,
            output_tokens=500,
            cached_input_tokens=200,
            reasoning_tokens=None,
            latency_ms=100,
            status="success",
            error_code=None,
            requested_at=now - timedelta(minutes=5),
        )
        await session.execute(update(log.__class__).where(log.__class__.id == log.id).values(cost_usd=9.876543))
        await session.commit()

        summary = await service.get_usage_summary()

        assert summary.cost.total_usd_7d == pytest.approx(9.876543)
