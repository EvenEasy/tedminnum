import { formData, text, today } from "../../shared/format";
import { ErrorMessage, Field, Modal, Money, Status } from "../../shared/ui";
import { billingApi } from "./api";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function InvoiceDetail(
  props: Pick<
    WorkspaceController,
    | "busy"
    | "detail"
    | "error"
    | "mutate"
    | "openInvoice"
    | "paymentKey"
    | "setDetail"
  >,
) {
  const { busy, detail, error, mutate, openInvoice, paymentKey, setDetail } =
    props;

  if (!detail) return null;
  return (
    <Modal title={detail.number} onClose={() => setDetail(null)}>
      <ErrorMessage error={error} />
      <div className="row">
        <div>
          <h3>{detail.client_name}</h3>
          <p className="muted">
            {new Date(detail.created_at).toLocaleDateString()}
          </p>
        </div>
        <Status value={detail.status} />
      </div>
      <div className="invoice-lines">
        {detail.lines?.map((line) => (
          <div key={line.id}>
            <div>
              <strong>{line.description}</strong>
              <small>
                {Number(line.quantity).toFixed(6)} × {line.rate}{" "}
                {detail.currency}
              </small>
              {detail.status === "draft" && (
                <button
                  className="text-button"
                  onClick={async () => {
                    const description = prompt(
                      "Line description",
                      line.description,
                    );
                    if (
                      description &&
                      (await mutate(
                        () =>
                          billingApi.describe(detail.id, line.id, {
                            description,
                          }),
                        "Description saved",
                      ))
                    )
                      await openInvoice(detail.id);
                  }}
                >
                  Edit description
                </button>
              )}
            </div>
            <strong>
              <Money value={line.amount} currency={detail.currency} />
            </strong>
          </div>
        ))}
      </div>
      <div className="invoice-total">
        <span>Total</span>
        <strong>
          <Money value={detail.total} currency={detail.currency} />
        </strong>
      </div>
      <div className="invoice-total">
        <span>Received</span>
        <span>
          <Money
            value={String(
              detail.payments?.reduce(
                (sum, p) => sum + Math.round(Number(p.amount) * 100),
                0,
              )! / 100 || 0,
            )}
            currency={detail.currency}
          />
        </span>
      </div>
      <div className="form-actions">
        <a
          className="button"
          href={`/api/v1/invoices/${detail.id}/pdf`}
          download
        >
          Download PDF
        </a>
        {detail.status === "draft" && (
          <button
            className="primary"
            disabled={busy}
            onClick={async () => {
              if (
                confirm(
                  `Issue ${detail.number} for ${detail.total} ${detail.currency}? Amounts will be immutable.`,
                ) &&
                (await mutate(
                  () => billingApi.transition(detail.id, "issue"),
                  "Invoice issued",
                ))
              )
                await openInvoice(detail.id);
            }}
          >
            Issue invoice
          </button>
        )}
        {!["void", "paid", "partially_paid"].includes(detail.status) && (
          <button
            className="danger"
            disabled={busy}
            onClick={async () => {
              if (
                confirm(
                  "Void this invoice and release its work for rebilling?",
                ) &&
                (await mutate(
                  () => billingApi.transition(detail.id, "void"),
                  "Invoice voided",
                ))
              )
                await openInvoice(detail.id);
            }}
          >
            Void
          </button>
        )}
      </div>
      {["issued", "partially_paid"].includes(detail.status) && (
        <form
          className="payment-form"
          onSubmit={async (e) => {
            e.preventDefault();
            const f = formData(e);
            if (
              await mutate(
                () =>
                  billingApi.payment(detail.id, {
                    request_key: paymentKey.current,
                    amount: text(f, "amount"),
                    currency: detail.currency,
                    paid_on: text(f, "paid_on"),
                    reference: text(f, "reference"),
                  }),
                "Payment recorded",
              )
            )
              await openInvoice(detail.id);
          }}
        >
          <h3>Record a payment</h3>
          <div className="form-grid">
            <Field title={`Amount (${detail.currency})`}>
              <input
                name="amount"
                type="number"
                step="0.01"
                min="0.01"
                required
                defaultValue={(
                  (Math.round(Number(detail.total) * 100) -
                    (detail.payments || []).reduce(
                      (sum, p) => sum + Math.round(Number(p.amount) * 100),
                      0,
                    )) /
                  100
                ).toFixed(2)}
              />
            </Field>
            <Field title="Payment date">
              <input
                name="paid_on"
                type="date"
                defaultValue={today()}
                required
              />
            </Field>
          </div>
          <Field title="Reference (optional)">
            <input name="reference" maxLength={200} />
          </Field>
          <button className="primary" disabled={busy}>
            Record payment
          </button>
        </form>
      )}
      {detail.payments?.map((p) => (
        <div className="activity" key={p.id}>
          <div>
            <strong>Payment · {p.paid_on}</strong>
            <small>{p.reference || "No reference"}</small>
          </div>
          <span>
            <Money value={p.amount} currency={p.currency} />
          </span>
        </div>
      ))}
    </Modal>
  );
}
