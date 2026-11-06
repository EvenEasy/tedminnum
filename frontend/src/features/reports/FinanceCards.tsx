import type { Finance } from "../../shared/types";
import { Money } from "../../shared/ui";
export function FinanceCards({ finance: f }: { finance: Finance }) {
  return (
    <div className="stats finance">
      <article className="stat">
        <span>Worked value · estimate</span>
        <strong>
          <Money value={f.worked_estimate} currency={f.currency} />
        </strong>
        <small>Current rates + completed fixed tasks</small>
      </article>
      <article className="stat">
        <span>Uninvoiced · estimate</span>
        <strong>
          <Money value={f.uninvoiced_estimate} currency={f.currency} />
        </strong>
        <small>Excludes draft reservations</small>
      </article>
      <article className="stat">
        <span>Drafts reserved</span>
        <strong>
          <Money value={f.draft_reserved} currency={f.currency} />
        </strong>
        <small>Not yet an issued liability</small>
      </article>
      <article className="stat">
        <span>Outstanding</span>
        <strong>
          <Money value={f.outstanding} currency={f.currency} />
        </strong>
        <small>Issued total minus received</small>
      </article>
      <article className="stat accent">
        <span>Payments received</span>
        <strong>
          <Money value={f.payments_received} currency={f.currency} />
        </strong>
        <small>Recorded manual payments</small>
      </article>
    </div>
  );
}
