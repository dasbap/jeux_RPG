CREATE TABLE IF NOT EXISTS receipt_expiry (
    player_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    expires REAL NOT NULL,
    PRIMARY KEY(player_id,request_id)
);
CREATE INDEX IF NOT EXISTS receipt_expiration ON receipt_expiry(expires);
INSERT OR IGNORE INTO receipt_expiry
SELECT player_id,request_id,strftime('%s','now')+900 FROM receipts;
