"""Enforce invoice lifecycle and total/payment consistency independently of transport."""

from alembic import op

revision = "004_lifecycle"
down_revision = "003_guards"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION guard_invoice_lifecycle() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE received numeric; line_total numeric;
        BEGIN
          SELECT COALESCE(SUM(amount),0) INTO received FROM payments WHERE invoice_id=OLD.id;
          IF NOT (
            (OLD.status='draft' AND NEW.status IN ('draft','issued','void')) OR
            (OLD.status='issued' AND NEW.status IN ('issued','partially_paid','paid','void')) OR
            (OLD.status='partially_paid' AND NEW.status IN ('partially_paid','paid')) OR
            (OLD.status='paid' AND NEW.status='paid') OR
            (OLD.status='void' AND NEW.status='void'))
          THEN RAISE EXCEPTION 'Invalid invoice lifecycle' USING ERRCODE='23514'; END IF;
          IF (NEW.status IN ('issued','void') AND received != 0) OR
             (NEW.status='partially_paid' AND NOT (received>0 AND received<NEW.total)) OR
             (NEW.status='paid' AND received!=NEW.total)
          THEN RAISE EXCEPTION 'Invoice status must match payments' USING ERRCODE='23514'; END IF;
          IF OLD.status='draft' AND NEW.status='issued' THEN
            SELECT COALESCE(SUM(amount),0) INTO line_total FROM invoice_lines WHERE invoice_id=OLD.id AND reserved;
            IF NEW.total<=0 OR line_total!=NEW.total OR NEW.issued_at IS NULL THEN
              RAISE EXCEPTION 'Issued total must match reserved lines' USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER invoice_lifecycle BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION guard_invoice_lifecycle()"
    )


def downgrade():
    op.execute("DROP TRIGGER invoice_lifecycle ON invoices")
    op.execute("DROP FUNCTION guard_invoice_lifecycle()")
