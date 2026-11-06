"""Database guards for source reservations, payment totals, and least privilege."""

from alembic import op

revision = "003_guards"
down_revision = "002_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION guard_time_adjustment() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM invoice_lines WHERE source_entry_id=OLD.id AND reserved)
            AND NEW IS DISTINCT FROM OLD
          THEN RAISE EXCEPTION 'Reserved time is immutable' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER reserved_time BEFORE UPDATE ON time_entries FOR EACH ROW EXECUTE FUNCTION guard_time_adjustment()"
    )
    op.execute("""
        CREATE FUNCTION guard_payment() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE inv invoices; received numeric;
        BEGIN
          SELECT * INTO inv FROM invoices WHERE id=NEW.invoice_id FOR UPDATE;
          SELECT COALESCE(SUM(amount),0) INTO received FROM payments WHERE invoice_id=NEW.invoice_id;
          IF inv.status NOT IN ('issued','partially_paid') OR NEW.currency != inv.currency
            OR NEW.amount <= 0 OR received + NEW.amount > inv.total OR NEW.paid_on > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date
          THEN RAISE EXCEPTION 'Invalid payment' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER payment_guard BEFORE INSERT ON payments FOR EACH ROW EXECUTE FUNCTION guard_payment()"
    )
    op.execute("""
        CREATE FUNCTION guard_line_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE inv invoices;
        BEGIN
          SELECT * INTO inv FROM invoices WHERE id=NEW.invoice_id FOR UPDATE;
          IF inv.status != 'draft' OR NOT NEW.reserved
          THEN RAISE EXCEPTION 'Only draft invoices accept reserved sources' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER line_insert_guard BEFORE INSERT ON invoice_lines FOR EACH ROW EXECUTE FUNCTION guard_line_insert()"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ted_app') THEN
            REVOKE UPDATE, DELETE ON audit, payments FROM ted_app;
            REVOKE DELETE ON invoices, invoice_lines, time_entries FROM ted_app;
            REVOKE ALL ON alembic_version FROM ted_app;
          END IF;
        END $$
    """)


def downgrade():
    op.execute("DROP TRIGGER line_insert_guard ON invoice_lines")
    op.execute("DROP FUNCTION guard_line_insert()")
    op.execute("DROP TRIGGER payment_guard ON payments")
    op.execute("DROP FUNCTION guard_payment()")
    op.execute("DROP TRIGGER reserved_time ON time_entries")
    op.execute("DROP FUNCTION guard_time_adjustment()")
