from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Response

from ted.application.access import admin
from ted.domain.rules import require
from ted.infrastructure.pdf import invoice_pdf
from ted.presentation import schemas as s
from ted.presentation.dependencies import (
    Actor,
    BillingRepo,
    CreateInvoiceOperation,
    FinanceReportOperation,
    InvoiceLifecycleOperation,
    Limit,
    Offset,
    RecordPaymentOperation,
)
from ted.presentation.serialization import encode, page, public

router = APIRouter()


@router.get("/api/v1/invoices")
async def invoices(
    actor: Actor,
    billing: BillingRepo,
    limit: Limit = 50,
    offset: Offset = 0,
    status: str | None = None,
) -> dict[str, Any]:
    admin(actor)
    return page(
        [public(i) for i in await billing.invoices() if status is None or i.status == status],
        limit,
        offset,
    )


@router.post("/api/v1/invoices", status_code=201)
async def draft_invoice(
    body: s.Draft, actor: Actor, create_invoice: CreateInvoiceOperation
) -> dict[str, Any]:
    return public(
        await create_invoice.execute(
            body.client_id, body.request_key, body.entry_ids, body.task_ids
        )
    )


@router.get("/api/v1/invoices/{id}")
async def invoice(id: UUID, actor: Actor, billing: BillingRepo) -> dict[str, Any]:
    admin(actor)
    i = await billing.invoice(id)
    return public(i) | {
        "lines": [public(line) for line in await billing.lines(id)],
        "payments": [public(p) for p in await billing.payments(id)],
    }


@router.post("/api/v1/invoices/{id}/{command}")
async def invoice_command(
    id: UUID, command: str, actor: Actor, lifecycle: InvoiceLifecycleOperation
) -> dict[str, Any]:
    require(command in {"issue", "void"}, "Not found", 404)
    return public(await lifecycle.transition(id, command))


@router.patch("/api/v1/invoices/{id}/lines/{line_id}")
async def describe_line(
    id: UUID, line_id: UUID, body: s.Description, actor: Actor, lifecycle: InvoiceLifecycleOperation
) -> dict[str, bool]:
    await lifecycle.describe_line(id, line_id, body.description)
    return {"ok": True}


@router.get("/api/v1/invoices/{id}/pdf")
async def pdf(id: UUID, actor: Actor, billing: BillingRepo) -> Response:
    admin(actor)
    invoice = await billing.invoice(id)
    content = invoice_pdf(invoice, await billing.lines(id), await billing.payments(id))
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.number}.pdf"'},
    )


@router.post("/api/v1/payments", status_code=201)
async def payment(
    body: s.PaymentInput, invoice_id: UUID, actor: Actor, record_payment: RecordPaymentOperation
) -> dict[str, Any]:
    return public(
        await record_payment.execute(
            invoice_id, body.request_key, body.amount, body.currency, body.paid_on, body.reference
        )
    )


@router.get("/api/v1/reports")
async def report(actor: Actor, finance_report: FinanceReportOperation) -> dict[str, Any]:
    return cast(dict[str, Any], encode(await finance_report.execute()))
