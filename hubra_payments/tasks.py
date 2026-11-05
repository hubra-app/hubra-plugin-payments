"""Celery task: ask Stripe about open checkouts, every ten minutes."""

from __future__ import annotations

from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app

from . import services


@celery_app.task(name="hubra_payments.tasks.sync_open")
@per_tenant_job("payments")
def sync_open() -> dict:
    return services.sync_open()
