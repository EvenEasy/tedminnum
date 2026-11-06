import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID

from ted.application.ports import Store
from ted.domain.models import (
    Audit,
    Client,
    Delivery,
    Invoice,
    InvoiceLine,
    Payment,
    Project,
    Task,
    TimeEntry,
    User,
    now,
)
from ted.domain.rules import effective_rate, hourly_amount, money, require


def admin(actor: User) -> None:
    require(actor.role == "admin", "Administrator access required", 403)


class Work:
    def __init__(self, store: Store, actor: User):
        self.s = store
        self.actor = actor

    async def audit(self, action: str, id: object, detail: str = "") -> None:
        await self.s.save(
            Audit(actor_id=self.actor.id, action=action, object_id=str(id), detail=detail)
        )

    async def event(self, name: str, id: object) -> None:
        # Transactional outbox: no domain event can be sent before its mutation commits.
        for hook in await self.s.webhooks():
            if hook.enabled:
                delivery = Delivery(webhook_id=hook.id, event=name, payload="")
                delivery.payload = json.dumps(
                    {
                        "id": str(delivery.id),
                        "event": name,
                        "object_id": str(id),
                        "occurred_at": now().isoformat(),
                    },
                    separators=(",", ":"),
                )
                await self.s.save(delivery)

    async def project(self, id: UUID) -> Project:
        p = await self.s.project(id)
        require(
            self.actor.role == "admin" or self.actor.id in await self.s.members(id),
            "Not found",
            404,
        )
        return p

    async def task(self, id: UUID) -> Task:
        task = await self.s.task(id)
        await self.project(task.project_id)
        require(
            self.actor.role == "admin" or self.actor.id in await self.s.assignees(id),
            "Not found",
            404,
        )
        return task

    async def client(self, id: UUID) -> Client:
        require(id in [c.id for c in await self.s.clients(self.actor)], "Not found", 404)
        return await self.s.client(id)

    async def create_client(self, name: str, rate: Decimal) -> Client:
        admin(self.actor)
        c = Client(name=name, rate=rate)
        await self.s.save(c)
        return c

    async def update_client(self, id: UUID, name: str, rate: Decimal) -> Client:
        admin(self.actor)
        await self.s.workspace(lock=True)
        c = await self.s.client(id)
        c.name, c.rate = name, rate
        await self.s.save(c)
        await self.audit("client.updated", id)
        return c

    async def create_project(
        self, client_id: UUID, name: str, rate: Decimal | None, member_ids: list[UUID]
    ) -> Project:
        admin(self.actor)
        await self.s.client(client_id)
        for id in member_ids:
            require((await self.s.user(id)).active, "Inactive member")
        p = Project(client_id=client_id, name=name, rate=rate)
        await self.s.save(p)
        await self.s.set_members(p.id, member_ids)
        await self.audit("project.created", p.id)
        return p

    async def update_project(
        self, id: UUID, name: str, rate: Decimal | None, member_ids: list[UUID]
    ) -> Project:
        admin(self.actor)
        await self.s.workspace(lock=True)
        p = await self.s.project(id)
        for user_id in member_ids:
            require((await self.s.user(user_id)).active, "Inactive member")
        for task in await self.s.tasks(self.actor):
            if task.project_id == id:
                require(
                    set(await self.s.assignees(task.id)) <= set(member_ids),
                    "Remove task assignments before removing project membership",
                    409,
                )
        p.name, p.rate = name, rate
        await self.s.set_members(id, member_ids)
        await self.s.save(p)
        await self.audit("project.updated", id)
        return p

    async def create_task(self, project_id: UUID, assignee_ids: list[UUID], **fields: Any) -> Task:
        admin(self.actor)
        await self.s.workspace(lock=True)
        await self.s.project(project_id)
        require(
            set(assignee_ids) <= set(await self.s.members(project_id)),
            "Assignees must be project members",
        )
        require(
            fields["billing"] != "fixed" or fields.get("fixed_price") is not None,
            "Fixed tasks need a price",
        )
        task = Task(project_id=project_id, **fields)
        await self.s.save(task)
        await self.s.set_assignees(task.id, assignee_ids)
        await self.audit("task.created", task.id)
        return task

    async def update_task(self, id: UUID, version: int, fields: dict[str, Any]) -> Task:
        await self.s.workspace(lock=True)
        await self.task(id)
        task = await self.s.task(id, lock=True)
        require(task.version == version, "Task changed; refresh and try again", 409)
        if self.actor.role != "admin":
            require(
                set(fields) <= {"status", "position"},
                "Members may change task status and position only",
                403,
            )
        if "billing" in fields and fields["billing"] != task.billing:
            require(
                not any(e.task_id == id for e in await self.s.entries(self.actor)),
                "Billing mode cannot change after time is recorded",
                409,
            )
            require(
                not any(line.source_task_id == id for line in await self.s.lines()),
                "Billing mode cannot change after invoicing",
                409,
            )
        assignees = fields.pop("assignee_ids", None)
        if assignees is not None:
            require(
                set(assignees) <= set(await self.s.members(task.project_id)),
                "Assignees must be project members",
            )
            await self.s.set_assignees(id, assignees)
        for key, value in fields.items():
            setattr(task, key, value)
        require(task.billing != "fixed" or task.fixed_price is not None, "Fixed tasks need a price")
        task.version += 1
        await self.s.save(task)
        await self.audit("task.updated", id)
        await self.event("task.updated", id)
        return task

    async def move_task(self, id: UUID, version: int, direction: str) -> Task:
        await self.s.workspace(lock=True)
        task = await self.task(id)
        require(task.version == version, "Task changed; refresh and try again", 409)
        peers = sorted(
            (
                t
                for t in await self.s.tasks(self.actor)
                if t.project_id == task.project_id and t.status == task.status
            ),
            key=lambda t: (t.position, str(t.id)),
        )
        index = next(i for i, t in enumerate(peers) if t.id == id)
        target = index + (-1 if direction == "up" else 1)
        if 0 <= target < len(peers):
            peers[index], peers[target] = peers[target], peers[index]
            for position, peer in enumerate(peers):
                peer.position = position
                peer.version += 1
                await self.s.save(peer)
            await self.audit("task.moved", id)
            await self.event("task.updated", id)
        return task

    async def start_timer(
        self, key: UUID, task_id: UUID | None, kind: str, billable: bool, long_break: bool = False
    ) -> TimeEntry:
        await self.s.user(self.actor.id, lock=True)
        existing = await self.s.entry(key)
        if existing is not None:
            require(existing.user_id == self.actor.id, "Not found", 404)
            require(
                existing.task_id == task_id and existing.kind == kind,
                "Request key was used for another timer",
                409,
            )
            return existing
        if task_id is not None:
            task = await self.task(task_id)
            billable = billable and task.billing != "nonbillable"
        else:
            billable = False
        require(
            await self.s.active_entry(self.actor.id) is None, "Stop your active timer first", 409
        )
        entry = TimeEntry(
            id=key,
            user_id=self.actor.id,
            task_id=task_id,
            kind=kind,
            billable=billable and kind == "work",
            target_seconds=60
            * (
                self.actor.work_minutes
                if kind == "work"
                else self.actor.long_break
                if long_break
                else self.actor.short_break
            ),
        )
        await self.s.save(entry)
        return entry

    async def timer_command(self, id: UUID, command: str) -> TimeEntry:
        await self.s.user(self.actor.id, lock=True)
        entry = await self.s.entry(id, lock=True)
        require(entry is not None and entry.user_id == self.actor.id, "Not found", 404)
        assert entry is not None
        if entry.ended_at is not None:
            require(command == "stop", "Timer is already stopped", 409)
            return entry
        at = now()
        if command == "pause" and entry.paused_at is None:
            entry.paused_at = at
        elif command == "resume" and entry.paused_at is not None:
            entry.paused_microseconds += (at - entry.paused_at) // timedelta(microseconds=1)
            entry.paused_at = None
        elif command == "stop":
            if entry.paused_at is not None:
                entry.paused_microseconds += (at - entry.paused_at) // timedelta(microseconds=1)
                entry.paused_at = None
            entry.ended_at = at
            await self.audit("timer.stopped", id)
            await self.event("timer.stopped", id)
        await self.s.save(entry)
        return entry

    async def edit_entry(
        self, id: UUID, started_at: datetime, ended_at: datetime, billable: bool, note: str
    ) -> TimeEntry:
        await self.s.workspace(lock=True)
        entry = await self.s.entry(id)
        require(
            entry is not None and (self.actor.role == "admin" or entry.user_id == self.actor.id),
            "Not found",
            404,
        )
        assert entry is not None
        await self.s.user(entry.user_id, lock=True)
        entry = await self.s.entry(id, lock=True)
        assert entry is not None
        require(entry.ended_at is not None, "Stop the timer before editing", 409)
        require(
            not any(line.reserved and line.source_entry_id == id for line in await self.s.lines()),
            "Reserved or invoiced time cannot be edited",
            409,
        )
        require(started_at < ended_at <= now(), "Use a valid past UTC interval")
        require(
            not await self.s.overlaps(entry.user_id, started_at, ended_at, id),
            "Time entries cannot overlap",
            409,
        )
        assert entry.ended_at is not None
        before = f"{entry.started_at.isoformat()}/{entry.ended_at.isoformat()}; paused={entry.paused_microseconds}; billable={entry.billable}"
        if entry.task_id is not None:
            task = await self.s.task(entry.task_id)
            billable = billable and task.billing != "nonbillable"
        else:
            billable = False
        entry.started_at, entry.ended_at = started_at, ended_at
        entry.billable = billable and entry.kind == "work"
        entry.paused_microseconds = 0
        entry.note = note
        await self.s.save(entry)
        await self.audit(
            "time.adjusted",
            id,
            before
            + f" -> {started_at.isoformat()}/{ended_at.isoformat()}; billable={entry.billable}",
        )
        return entry


class Billing(Work):
    async def draft(
        self, client_id: UUID, key: UUID, entry_ids: list[UUID], task_ids: list[UUID]
    ) -> Invoice:
        admin(self.actor)
        workspace = await self.s.workspace(lock=True)
        fingerprint = sha256(
            json.dumps(
                [str(client_id), sorted(map(str, entry_ids)), sorted(map(str, task_ids))]
            ).encode()
        ).hexdigest()
        prior = await self.s.invoice_by_key(key)
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
        client = await self.s.client(client_id)
        reserved = [line for line in await self.s.lines() if line.reserved]
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
            entry = await self.s.entry(id, lock=True)
            require(
                entry is not None
                and entry.ended_at is not None
                and entry.billable
                and entry.kind == "work"
                and entry.task_id is not None,
                "Select completed billable work",
            )
            assert entry is not None and entry.task_id is not None
            task = await self.s.task(entry.task_id)
            project = await self.s.project(task.project_id)
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
            task = await self.s.task(id, lock=True)
            project = await self.s.project(task.project_id)
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
        await self.s.save(workspace, invoice)
        await self.s.save(*result)
        await self.audit("invoice.created", invoice.id)
        return invoice

    async def transition(self, id: UUID, command: str) -> Invoice:
        admin(self.actor)
        await self.s.workspace(lock=True)
        invoice = await self.s.invoice(id)
        if command == "issue":
            if invoice.status in {"issued", "paid", "partially_paid"}:
                return invoice
            require(invoice.status == "draft", "Only drafts can be issued", 409)
            invoice.status, invoice.issued_at = "issued", now()
            await self.event("invoice.issued", id)
        else:
            if invoice.status == "void":
                return invoice
            require(not await self.s.payments(id), "Invoices with payments cannot be voided", 409)
            invoice.status = "void"
            # Flush the void first; database immutability rules permit releasing reservations only after this.
            await self.s.save(invoice)
            for line in await self.s.lines(id):
                line.reserved = False
                await self.s.save(line)
        await self.s.save(invoice)
        await self.audit(f"invoice.{command}", id)
        return invoice

    async def describe_line(self, invoice_id: UUID, line_id: UUID, description: str) -> None:
        admin(self.actor)
        await self.s.workspace(lock=True)
        require(
            (await self.s.invoice(invoice_id)).status == "draft",
            "Only draft descriptions can change",
            409,
        )
        found = False
        for line in await self.s.lines(invoice_id):
            if line.id == line_id:
                line.description = description
                await self.s.save(line)
                found = True
        require(found, "Not found", 404)
        await self.audit("invoice.description", invoice_id)

    async def pay(
        self, id: UUID, key: UUID, amount: Decimal, currency: str, paid_on: date, reference: str
    ) -> Payment:
        admin(self.actor)
        await self.s.workspace(lock=True)
        prior = await self.s.payment_by_key(key)
        if prior is not None:
            require(
                (prior.invoice_id, prior.amount, prior.currency, prior.paid_on, prior.reference)
                == (id, amount, currency, paid_on, reference),
                "Request key was used for another payment",
                409,
            )
            return prior
        invoice = await self.s.invoice(id)
        require(
            invoice.status in {"issued", "partially_paid"},
            "Issue the invoice before recording a payment",
            409,
        )
        require(currency == invoice.currency, "Payment currency must match the invoice")
        require(paid_on <= now().date(), "Payment date cannot be in the future")
        received = sum((p.amount for p in await self.s.payments(id)), Decimal("0.00"))
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
        await self.s.save(payment)
        invoice.status = "paid" if received + amount == invoice.total else "partially_paid"
        await self.s.save(invoice)
        await self.audit("invoice.payment", id, f"{amount} {currency}; payment={payment.id}")
        await self.event("invoice.paid" if invoice.status == "paid" else "invoice.payment", id)
        return payment

    async def report(self) -> dict[str, Any]:
        admin(self.actor)
        tasks = {t.id: t for t in await self.s.tasks(self.actor)}
        projects = {p.id: p for p in await self.s.projects(self.actor)}
        clients = {c.id: c for c in await self.s.clients(self.actor)}
        lines = [line for line in await self.s.lines() if line.reserved]
        entry_ids = {line.source_entry_id for line in lines}
        task_ids = {line.source_task_id for line in lines}
        worked, uninvoiced = Decimal("0.00"), Decimal("0.00")
        for entry in await self.s.entries(self.actor):
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
        invoices = await self.s.invoices()
        received = sum((p.amount for p in await self.s.payments()), Decimal("0.00"))
        issued = sum(
            (i.total for i in invoices if i.status in {"issued", "partially_paid", "paid"}),
            Decimal("0.00"),
        )
        return {
            "currency": (await self.s.workspace()).currency,
            "worked_estimate": worked,
            "uninvoiced_estimate": uninvoiced,
            "draft_reserved": sum(
                (i.total for i in invoices if i.status == "draft"), Decimal("0.00")
            ),
            "outstanding": issued - received,
            "payments_received": received,
        }
