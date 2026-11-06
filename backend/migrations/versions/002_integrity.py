"""PostgreSQL overlap protection and historical immutability."""

from alembic import op

revision = "002_integrity"
down_revision = "4895a42831c2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO workspace (id, name, currency, next_invoice) VALUES (1, 'Tedminnum', 'USD', 1)"
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        "ALTER TABLE time_entries ADD CONSTRAINT no_overlapping_sessions EXCLUDE USING gist (user_id WITH =, tstzrange(started_at, ended_at, '[)') WITH &&)"
    )
    op.execute("""
        CREATE FUNCTION protect_invoice() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Invoice history cannot be deleted'; END IF;
          IF OLD.status != 'draft' AND
            (NEW.total,NEW.currency,NEW.client_id,NEW.client_name,NEW.issuer_name,NEW.number,NEW.issued_at)
              IS DISTINCT FROM
            (OLD.total,OLD.currency,OLD.client_id,OLD.client_name,OLD.issuer_name,OLD.number,OLD.issued_at)
          THEN RAISE EXCEPTION 'Issued invoice snapshots are immutable'; END IF;
          IF OLD.status = 'void' AND NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION 'Void invoice is immutable'; END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER invoice_immutable BEFORE UPDATE OR DELETE ON invoices FOR EACH ROW EXECUTE FUNCTION protect_invoice()"
    )
    op.execute("""
        CREATE FUNCTION protect_invoice_line() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE state text;
        BEGIN
          SELECT status INTO state FROM invoices WHERE id = OLD.invoice_id FOR UPDATE;
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Invoice lines cannot be deleted'; END IF;
          IF (NEW.invoice_id,NEW.quantity,NEW.rate,NEW.amount,NEW.source_entry_id,NEW.source_task_id)
             IS DISTINCT FROM (OLD.invoice_id,OLD.quantity,OLD.rate,OLD.amount,OLD.source_entry_id,OLD.source_task_id)
          THEN RAISE EXCEPTION 'Line prices and sources are immutable'; END IF;
          IF state != 'draft' AND NEW.description IS DISTINCT FROM OLD.description
          THEN RAISE EXCEPTION 'Issued descriptions are immutable'; END IF;
          IF NEW.reserved IS DISTINCT FROM OLD.reserved AND NOT (state = 'void' AND NOT NEW.reserved)
          THEN RAISE EXCEPTION 'Only void invoices release sources'; END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER line_immutable BEFORE UPDATE OR DELETE ON invoice_lines FOR EACH ROW EXECUTE FUNCTION protect_invoice_line()"
    )
    op.execute("""
        CREATE FUNCTION protect_payment() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Payments are append-only'; END $$
    """)
    op.execute(
        "CREATE TRIGGER payment_immutable BEFORE UPDATE OR DELETE ON payments FOR EACH ROW EXECUTE FUNCTION protect_payment()"
    )


def downgrade():
    op.execute("DROP TRIGGER payment_immutable ON payments")
    op.execute("DROP FUNCTION protect_payment()")
    op.execute("DROP TRIGGER line_immutable ON invoice_lines")
    op.execute("DROP FUNCTION protect_invoice_line()")
    op.execute("DROP TRIGGER invoice_immutable ON invoices")
    op.execute("DROP FUNCTION protect_invoice()")
    op.execute("ALTER TABLE time_entries DROP CONSTRAINT no_overlapping_sessions")
