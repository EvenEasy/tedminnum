import json
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID

from ted.application.access import admin
from ted.application.activity import Activity
from ted.application.ports import (
    BillingRepository,
    TrackingQueries,
    WorkQueries,
    WorkspaceRepository,
)
from ted.domain.models import (
    Invoice,
    InvoiceLine,
    Payment,
    User,
    now,
)
from ted.domain.rules import effective_rate, hourly_amount, money, require


class CreateInvoice:
    def __init__(
        self,
        billing: BillingRepository,
        work: WorkQueries,
        tracking: TrackingQueries,
        workspace: WorkspaceRepository,
        activity: Activity,
        actor: User,
    ):
        self.billing = billing
        self.work = work
        self.tracking = tracking
        self.workspace = workspace
        self.activity = activity
        self.actor = actor

    async def execute(
        self, client_id: UUID, key: UUID, entry_ids: list[UUID], task_ids: list[UUID]
    ) -> Invoice:
        admin(self.actor)
        workspace = await self.workspace.workspace(lock=True)
        fingerprint = sha256(
            json.dumps(
                [str(client_id), sorted(map(str, entry_ids)), sorted(map(str, task_ids))]
            ).encode()
        ).hexdigest()
        prior = await self.billing.invoice_by_key(key)
        if prior is not None:
            require(
                prior.request_fingerprint == fingerprint,
                "Request key was used for another invoice",
                409,
            )
            return prior
        require(bool(entry_ids or task_ids), "Select time entries or fixed-price tasks")
        require(
            len(entry_ids) == len(set(entry_ids)) and len(task_ids) == len(set(task_ids)),
            "Duplicate invoice sources",
        )
        client = await self.work.client(client_id)
        reserved = [line for line in await self.billing.lines() if line.reserved]
        invoice = Invoice(
            client_id=client_id,
            request_key=key,
            request_fingerprint=fingerprint,
            currency=workspace.currency,
            client_name=client.name,
            issuer_name=workspace.name,
            number=f"INV-{workspace.next_invoice:06d}",
        )
        result: list[InvoiceLine] = []
        for id in sorted(entry_ids):
            entry = await self.tracking.entry(id, lock=True)
            require(
                entry is not None
                and entry.ended_at is not None
                and entry.billable
                and entry.kind == "work"
                and entry.task_id is not None,
                "Select completed billable work",
            )
            assert entry is not None and entry.task_id is not None
            task = await self.work.task(entry.task_id)
            project = await self.work.project(task.project_id)
            require(
                project.client_id == client_id and task.billing == "hourly",
                "Time must be hourly and belong to this client",
            )
            require(
                not any(line.source_entry_id == id for line in reserved),
                "Time is already reserved or invoiced",
                409,
            )
            rate = effective_rate(task.rate, project.rate, client.rate)
            amount = hourly_amount(entry.seconds(), rate)
            require(
                amount <= Decimal("99999999999999.99"), "Line amount exceeds supported invoice size"
            )
            result.append(
                InvoiceLine(
                    invoice_id=invoice.id,
                    description=f"{task.title} · {entry.started_at.date()}",
                    quantity=(Decimal(entry.seconds()) / Decimal(3600)).quantize(
                        Decimal("0.000000001")
                    ),
                    rate=rate,
                    amount=amount,
                    source_entry_id=id,
                )
            )
        for id in sorted(task_ids):
            task = await self.work.task(id, lock=True)
            project = await self.work.project(task.project_id)
            require(
                project.client_id == client_id
                and task.billing == "fixed"
                and task.status == "done"
                and task.fixed_price is not None,
                "Select finished fixed-price tasks for this client",
            )
            require(
                not any(line.source_task_id == id for line in reserved),
                "Fixed task is already reserved or invoiced",
                409,
            )
            assert task.fixed_price is not None
            result.append(
                InvoiceLine(
                    invoice_id=invoice.id,
                    description=task.title,
                    quantity=Decimal(1),
                    rate=task.fixed_price,
                    amount=money(task.fixed_price),
                    source_task_id=id,
                )
            )
        invoice.total = sum((line.amount for line in result), Decimal("0.00"))
        require(
            Decimal(0) < invoice.total <= Decimal("99999999999999.99"),
            "Invoice total must be positive and within supported limits",
        )
        workspace.next_invoice += 1
        await self.workspace.save(workspace)
        await self.billing.save(invoice)
        await self.billing.save(*result)
        await self.activity.audit(self.actor, "invoice.created", invoice.id)
        return invoice


class InvoiceLifecycle:
    def __init__(
        self,
        billing: BillingRepository,
        workspace: WorkspaceRepository,
        activity: Activity,
        actor: User,
    ):
        self.billing = billing
        self.workspace = workspace
        self.activity = activity
        self.actor = actor

    async def transition(self, id: UUID, command: str) -> Invoice:
        admin(self.actor)
        await self.workspace.workspace(lock=True)
        invoice = await self.billing.invoice(id)
        if command == "issue":
            if invoice.status in {"issued", "paid", "partially_paid"}:
                return invoice
            require(invoice.status == "draft", "Only drafts can be issued", 409)
            invoice.status, invoice.issued_at = "issued", now()
            await self.activity.event("invoice.issued", id)
        else:
            if invoice.status == "void":
                return invoice
            require(
                not await self.billing.payments(id), "Invoices with payments cannot be voided", 409
            )
            invoice.status = "void"
            # Flush the void first; database immutability rules permit releasing reservations only after this.
            await self.billing.save(invoice)
            for line in await self.billing.lines(id):
                line.reserved = False
                await self.billing.save(line)
        await self.billing.save(invoice)
        await self.activity.audit(self.actor, f"invoice.{command}", id)
        return invoice

    async def describe_line(self, invoice_id: UUID, line_id: UUID, description: str) -> None:
        admin(self.actor)
        await self.workspace.workspace(lock=True)
        require(
            (await self.billing.invoice(invoice_id)).status == "draft",
            "Only draft descriptions can change",
            409,
        )
        found = False
        for line in await self.billing.lines(invoice_id):
            if line.id == line_id:
                line.description = description
                await self.billing.save(line)
                found = True
        require(found, "Not found", 404)
        await self.activity.audit(self.actor, "invoice.description", invoice_id)


class RecordPayment:
    def __init__(
        self,
        billing: BillingRepository,
        workspace: WorkspaceRepository,
        activity: Activity,
        actor: User,
    ):
        self.billing = billing
        self.workspace = workspace
        self.activity = activity
        self.actor = actor

    async def execute(
        self, id: UUID, key: UUID, amount: Decimal, currency: str, paid_on: date, reference: str
    ) -> Payment:
        admin(self.actor)
        await self.workspace.workspace(lock=True)
        prior = await self.billing.payment_by_key(key)
        if prior is not None:
            require(
                (prior.invoice_id, prior.amount, prior.currency, prior.paid_on, prior.reference)
                == (id, amount, currency, paid_on, reference),
                "Request key was used for another payment",
                409,
            )
            return prior
        invoice = await self.billing.invoice(id)
        require(
            invoice.status in {"issued", "partially_paid"},
            "Issue the invoice before recording a payment",
            409,
        )
        require(currency == invoice.currency, "Payment currency must match the invoice")
        require(paid_on <= now().date(), "Payment date cannot be in the future")
        received = sum((p.amount for p in await self.billing.payments(id)), Decimal("0.00"))
        require(
            Decimal(0) < amount <= invoice.total - received,
            "Payment exceeds outstanding balance or is invalid",
        )
        payment = Payment(
            invoice_id=id,
            request_key=key,
            amount=amount,
            currency=currency,
            paid_on=paid_on,
            reference=reference,
        )
        await self.billing.save(payment)
        invoice.status = "paid" if received + amount == invoice.total else "partially_paid"
        await self.billing.save(invoice)
        await self.activity.audit(
            self.actor, "invoice.payment", id, f"{amount} {currency}; payment={payment.id}"
        )
        await self.activity.event(
            "invoice.paid" if invoice.status == "paid" else "invoice.payment", id
        )
        return payment


class FinanceReport:
    def __init__(
        self,
        billing: BillingRepository,
        work: WorkQueries,
        tracking: TrackingQueries,
        workspace: WorkspaceRepository,
        actor: User,
    ):
        self.billing = billing
        self.work = work
        self.tracking = tracking
        self.workspace = workspace
        self.actor = actor

    async def execute(self) -> dict[str, Any]:
        admin(self.actor)
        tasks = {t.id: t for t in await self.work.tasks(self.actor)}
        projects = {p.id: p for p in await self.work.projects(self.actor)}
        clients = {c.id: c for c in await self.work.clients(self.actor)}
        lines = [line for line in await self.billing.lines() if line.reserved]
        entry_ids = {line.source_entry_id for line in lines}
        task_ids = {line.source_task_id for line in lines}
        worked, uninvoiced = Decimal("0.00"), Decimal("0.00")
        for entry in await self.tracking.entries(self.actor):
            if entry.ended_at is None or not entry.billable or entry.task_id is None:
                continue
            task = tasks[entry.task_id]
            if task.billing != "hourly":
                continue
            project = projects[task.project_id]
            amount = hourly_amount(
                entry.seconds(),
                effective_rate(task.rate, project.rate, clients[project.client_id].rate),
            )
            worked += amount
            if entry.id not in entry_ids:
                uninvoiced += amount
        for task in tasks.values():
            if task.billing == "fixed" and task.status == "done" and task.fixed_price is not None:
                worked += task.fixed_price
                if task.id not in task_ids:
                    uninvoiced += task.fixed_price
        invoices = await self.billing.invoices()
        received = sum((p.amount for p in await self.billing.payments()), Decimal("0.00"))
        issued = sum(
            (i.total for i in invoices if i.status in {"issued", "partially_paid", "paid"}),
            Decimal("0.00"),
        )
        return {
            "currency": (await self.workspace.workspace()).currency,
            "worked_estimate": worked,
            "uninvoiced_estimate": uninvoiced,
            "draft_reserved": sum(
                (i.total for i in invoices if i.status == "draft"), Decimal("0.00")
            ),
            "outstanding": issued - received,
            "payments_received": received,
        }
