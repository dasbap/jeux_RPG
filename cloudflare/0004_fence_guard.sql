CREATE TRIGGER IF NOT EXISTS reject_stale_runtime_fence_update
BEFORE UPDATE OF value ON meta
WHEN OLD.key='runtime_fence' AND (
  NEW.key!='runtime_fence'
  OR CAST(NEW.value AS INTEGER)<CAST(OLD.value AS INTEGER)
)
BEGIN
  SELECT RAISE(ABORT, 'stale_runtime_fence');
END;
CREATE TRIGGER IF NOT EXISTS reject_stale_runtime_fence_delete
BEFORE DELETE ON meta
WHEN OLD.key='runtime_fence'
BEGIN
  SELECT RAISE(ABORT, 'runtime_fence_protected');
END;
