import { FinanceCards } from "./FinanceCards";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function ReportsPage(
  props: Pick<WorkspaceController, "isAdmin" | "dash">,
) {
  const { isAdmin, dash } = props;

  if (!isAdmin || !dash?.finance) return null;
  return (
    <>
      <FinanceCards finance={dash.finance} />
      <section className="panel prose">
        <h2>Understand the numbers</h2>
        <p>
          Worked value estimates completed hourly work at current rates, plus
          finished fixed-price tasks once each. Time logged on fixed-price tasks
          adds no hourly charges.
        </p>
        <p>
          Uninvoiced value excludes work reserved by drafts or included in
          issued invoices. Draft reserved value uses the draft's saved prices.
          Issued outstanding and payments received use immutable invoice
          amounts.
        </p>
        <p>
          These values describe different stages of the same work. Do not add
          them together. No tax, currency conversion, or accounting ledger is
          included.
        </p>
        <p>
          Rate precedence: task override → project override → client default.
          Money rounds half up per line to two decimal places. A time line
          calculates from exact integer seconds; displayed hours are rounded.
        </p>
      </section>
    </>
  );
}
