CREATE TABLE IF NOT EXISTS guilds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL UNIQUE,
    owner TEXT NOT NULL REFERENCES accounts(id),
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS guild_members (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id),
    guild_id TEXT NOT NULL REFERENCES guilds(id),
    role TEXT NOT NULL,
    joined REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS guild_invites (
    id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL REFERENCES guilds(id),
    sender TEXT NOT NULL REFERENCES accounts(id),
    recipient TEXT NOT NULL REFERENCES accounts(id),
    status TEXT NOT NULL,
    expires REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS guild_membership ON guild_members(guild_id,joined);
CREATE INDEX IF NOT EXISTS guild_invite_recipient ON guild_invites(recipient,status,expires);
