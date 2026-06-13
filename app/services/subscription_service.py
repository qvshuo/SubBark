from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from app.services.config_loader import Config, SubscriptionConfig


YEARLY_MULTIPLIERS = {
    "week": 52,
    "month": 12,
    "quarter": 4,
    "year": 1,
}

CYCLE_DELTAS = {
    "week": relativedelta(days=7),
    "month": relativedelta(months=1),
    "quarter": relativedelta(months=3),
    "year": relativedelta(years=1),
}


def now_display(timezone_name: str) -> str:
    current = datetime.now(ZoneInfo(timezone_name))
    return f"{current.year}年{current.month}月{current.day}日{current.hour}点{current.minute:02d}分"


def next_renewal_date(payment_date: date, billing_cycle: str, today: date) -> date:
    delta = CYCLE_DELTAS[billing_cycle]
    renewal_date = payment_date + delta
    while renewal_date < today:
        renewal_date = renewal_date + delta
    return renewal_date


def current_period_start(payment_date: date, billing_cycle: str, renewal_date: date) -> date:
    period_start = payment_date
    delta = CYCLE_DELTAS[billing_cycle]
    while period_start + delta < renewal_date:
        period_start = period_start + delta
    return period_start


def build_subscription_id(subscription: SubscriptionConfig) -> str:
    source = "|".join(
        [
            subscription.name,
            subscription.payment_date,
            subscription.billing_cycle,
            f"{subscription.amount:.8f}",
            subscription.currency,
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def build_dashboard(config: Config, rates_cache: dict, amount_to_cny, today: date, last_check_at: str | None = None) -> dict:
    items = []
    expiring_count = 0
    monthly_due_cny = 0.0
    yearly_estimated_cny = 0.0

    for subscription in config.subscriptions:
        item = build_subscription_item(subscription, config.app.remind_before_days, rates_cache, amount_to_cny, today)
        items.append(item)
        if item["status"] == "expiring":
            expiring_count += 1
        if item["renewal_date"][:7] == today.isoformat()[:7] and item["amount_cny"] is not None:
            monthly_due_cny += item["amount_cny"]
        if item["yearly_estimated_cny"] is not None:
            yearly_estimated_cny += item["yearly_estimated_cny"]

    category_groups = build_category_groups(items)
    summary = {
        "total_subscription_count": len(items),
        "total_category_count": len(category_groups),
        "expiring_subscription_count": expiring_count,
        "remind_before_days": config.app.remind_before_days,
        "monthly_due_cny": round(monthly_due_cny, 2),
        "yearly_estimated_cny": round(yearly_estimated_cny, 2),
        "last_check_at": last_check_at,
        "last_check_display": now_display(config.app.timezone),
        "exchange_rate_updated_at": rates_cache.get("updated_at"),
    }
    return {"summary": summary, "category_groups": category_groups}


def build_subscription_item(subscription: SubscriptionConfig, remind_before_days: int, rates_cache: dict, amount_to_cny, today: date) -> dict:
    payment_date = date.fromisoformat(subscription.payment_date)
    renewal_date = next_renewal_date(payment_date, subscription.billing_cycle, today)
    period_start = current_period_start(payment_date, subscription.billing_cycle, renewal_date)
    total_days = max((renewal_date - period_start).days, 1)
    used_days = (today - period_start).days
    progress_percent = round(max(0, min(used_days / total_days * 100, 100)), 2)
    days_left = (renewal_date - today).days
    reminder_start = renewal_date - timedelta(days=remind_before_days)

    amount_cny = amount_to_cny(subscription.amount, subscription.currency, rates_cache)
    yearly_estimated_cny = None if amount_cny is None else round(amount_cny * YEARLY_MULTIPLIERS[subscription.billing_cycle], 2)
    return {
        "subscription_id": build_subscription_id(subscription),
        "name": subscription.name,
        "category": subscription.category,
        "billing_cycle": subscription.billing_cycle,
        "payment_date": payment_date.isoformat(),
        "period_start": period_start.isoformat(),
        "renewal_date": renewal_date.isoformat(),
        "days_left": days_left,
        "progress_percent": progress_percent,
        "status": "expiring" if today >= reminder_start else "active",
        "amount": round(subscription.amount, 2),
        "currency": subscription.currency,
        "amount_cny": amount_cny,
        "yearly_estimated_cny": yearly_estimated_cny,
    }


def build_category_groups(items: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for item in items:
        grouped[item["category"]].append(item)

    groups = []
    for category_name in sorted(grouped):
        subscription_items = sorted(grouped[category_name], key=lambda item: (item["renewal_date"], item["name"]))
        groups.append(
            {
                "category_name": category_name,
                "subscription_count": len(subscription_items),
                "yearly_estimated_cny": round(sum(item["yearly_estimated_cny"] or 0 for item in subscription_items), 2),
                "subscription_items": subscription_items,
            }
        )
    return groups
