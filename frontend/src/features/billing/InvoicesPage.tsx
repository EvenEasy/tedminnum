import { Empty, Money, Status } from "../../shared/ui";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function InvoicesPage(
  props: Pick<WorkspaceController, "invoices" | "openInvoice">,
) {
  const { invoices, openInvoice } = props;

  return (
    <section className="panel">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Client</th>
              <th>Created</th>
              <th>Status</th>
              <th>Total</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((i) => (
              <tr key={i.id}>
                <td>
                  <strong>{i.number}</strong>
                </td>
                <td>{i.client_name}</td>
                <td>{new Date(i.created_at).toLocaleDateString()}</td>
                <td>
                  <Status value={i.status} />
                </td>
                <td>
                  <Money value={i.total} currency={i.currency} />
                </td>
                <td>
                  <button onClick={() => void openInvoice(i.id)}>
                    Open invoice
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {invoices.length === 0 && (
        <Empty>
          No invoices yet. Select completed billable work to create a draft.
        </Empty>
      )}
    </section>
  );
}
