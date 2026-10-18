CREATE TABLE pix_analysis_status(
    id SERIAL PRIMARY KEY,
    enumerator VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO pix_analysis_status (enumerator) VALUES
('approved'),
('two_factor_required'),
('rejected');

CREATE TABLE pix_transaction(
    id SERIAL PRIMARY KEY,
    analysis_key CHAR(36) NOT NULL,
    pix_id VARCHAR(255) NOT NULL,
    status_id INTEGER NOT NULL REFERENCES pix_analysis_status(id),
    amount BIGINT NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    source_branch VARCHAR(20) NOT NULL,
    source_account_number VARCHAR(50) NOT NULL,
    source_document VARCHAR(20) NOT NULL,
    destination_document VARCHAR(20) NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    declared_income VARCHAR(100),
    income_consulted_at TIMESTAMPTZ,
    payload_hash CHAR(64) NOT NULL,
    transaction_data JSONB NOT NULL,
    analysis_metadata JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(analysis_key),
    UNIQUE(pix_id)
);

CREATE INDEX idx_pix_tx_source_acc_status_date
ON pix_transaction(source_account_number, status_id, transaction_date DESC, id DESC);

CREATE INDEX idx_pix_tx_source_acc_device
ON pix_transaction(source_account_number, device_id);

CREATE INDEX idx_pix_tx_source_dest_doc
ON pix_transaction(source_document, destination_document);

CREATE INDEX idx_pix_tx_source_doc_received
ON pix_transaction(source_document, received_at DESC, id DESC);

CREATE TABLE pix_transaction_status_event(
    id SERIAL PRIMARY KEY,
    pix_transaction_id INTEGER NOT NULL REFERENCES pix_transaction(id),
    status_id INTEGER NOT NULL REFERENCES pix_analysis_status(id),
    event_datetime TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT(NOW())
);
