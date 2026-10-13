DROP TABLE IF EXISTS bot_updates;
CREATE TABLE bot_updates (
    update_id        BIGINT PRIMARY KEY,
    chat_id          BIGINT NOT NULL,
    telegram_user_id BIGINT NOT NULL,
    user_id          UUID NOT NULL,
    kind             VARCHAR(12) NOT NULL DEFAULT 'text',
    status           VARCHAR(12) NOT NULL,
    payload_text     TEXT NULL,
    reply_text       TEXT NULL,
    sent_parts       SMALLINT NOT NULL DEFAULT 0,
    attempts         SMALLINT NOT NULL DEFAULT 0,
    lease_until      TIMESTAMPTZ NULL,
    error_category   VARCHAR(40) NULL,
    reply_saved_at   TIMESTAMPTZ NULL,
    received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at       TIMESTAMPTZ NULL,
    finished_at      TIMESTAMPTZ NULL,
    CONSTRAINT ck_bot_updates_status CHECK (status IN ('queued','processing','replied','failed','dropped'))
);
CREATE INDEX ix_bot_updates_chat_open ON bot_updates (chat_id, update_id) WHERE status IN ('queued','processing');
CREATE INDEX ix_bot_updates_status_received ON bot_updates (status, received_at);
CREATE INDEX ix_bot_updates_user_received ON bot_updates (user_id, received_at);
