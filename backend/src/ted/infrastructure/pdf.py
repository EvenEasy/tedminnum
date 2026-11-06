from collections.abc import Sequence
from decimal import Decimal
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ted.domain.models import Invoice, InvoiceLine, Payment


def invoice_pdf(
    invoice: Invoice, lines: Sequence[InvoiceLine], payments: Sequence[Payment]
) -> bytes:
    output = BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape(invoice.issuer_name), styles["Title"]),
        Paragraph(f"{invoice.number} · {invoice.status.upper()}", styles["Heading1"]),
        Paragraph(f"Bill to: {escape(invoice.client_name)}", styles["Normal"]),
        Paragraph(
            f"Currency: {invoice.currency} · Created: {invoice.created_at.date()}", styles["Normal"]
        ),
        Spacer(1, 8 * mm),
    ]
    rows: list[list[Any]] = [["Description", "Hours / qty", "Rate", "Amount"]]
    for line in lines:
        rows.append(
            [
                Paragraph(escape(line.description), styles["Normal"]),
                f"{line.quantity:.6f}",
                f"{line.rate:.2f}",
                f"{line.amount:.2f}",
            ]
        )
    table = Table(rows, colWidths=[96 * mm, 28 * mm, 25 * mm, 28 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ]
        )
    )
    story.append(table)
    received = sum((p.amount for p in payments), Decimal(0))
    story.extend(
        [
            Spacer(1, 6 * mm),
            Paragraph(f"Total: {invoice.total:.2f} {invoice.currency}", styles["Heading2"]),
            Paragraph(
                f"Payments: {received:.2f} · Balance: {invoice.total - received:.2f}",
                styles["Normal"],
            ),
        ]
    )
    for payment in payments:
        story.append(
            Paragraph(
                f"{payment.paid_on}: {payment.amount:.2f} {payment.currency} · {escape(payment.reference)}",
                styles["Normal"],
            )
        )
    if invoice.status == "draft":
        story.append(
            Paragraph("DRAFT — issue this invoice before requesting payment.", styles["Heading2"])
        )
    if invoice.status == "void":
        story.append(Paragraph("VOID — no amount is due.", styles["Heading2"]))
    SimpleDocTemplate(output, title=invoice.number, author=invoice.issuer_name).build(story)
    return output.getvalue()
