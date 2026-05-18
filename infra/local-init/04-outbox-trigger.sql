-- OptiCloud — Outbox NOTIFY trigger (Story M2.1 T4)
-- Fires pg_notify('outbox_new', NEW.id::text) on each INSERT into outbox.
-- Lets the relayer wake up immediately instead of waiting for the 100ms poll.

CREATE OR REPLACE FUNCTION notify_outbox_new() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('outbox_new', NEW.id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_outbox_notify ON outbox;
CREATE TRIGGER trigger_outbox_notify
    AFTER INSERT ON outbox
    FOR EACH ROW
    EXECUTE FUNCTION notify_outbox_new();

DO $$
BEGIN
    RAISE NOTICE 'OptiCloud outbox NOTIFY trigger installed';
END $$;
