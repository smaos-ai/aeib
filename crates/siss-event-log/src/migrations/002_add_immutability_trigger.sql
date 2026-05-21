-- Create function to prevent UPDATE/DELETE on event_log (defense-in-depth)
CREATE OR REPLACE FUNCTION raise_immutable_error()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'event_log is immutable: UPDATE and DELETE are forbidden';
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to prevent UPDATE
CREATE TRIGGER prevent_update_event_log
BEFORE UPDATE ON event_log
FOR EACH ROW
EXECUTE FUNCTION raise_immutable_error();

-- Attach trigger to prevent DELETE
CREATE TRIGGER prevent_delete_event_log
BEFORE DELETE ON event_log
FOR EACH ROW
EXECUTE FUNCTION raise_immutable_error();
