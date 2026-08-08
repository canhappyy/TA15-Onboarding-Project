CREATE TABLE ingestion_checkpoint (
    dataset TEXT PRIMARY KEY,
    watermark TIMESTAMPTZ,
    last_started_at TIMESTAMPTZ NOT NULL,
    last_completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    inserted_count BIGINT NOT NULL DEFAULT 0,
    updated_count BIGINT NOT NULL DEFAULT 0,
    rejected_count BIGINT NOT NULL DEFAULT 0,
    duplicates_resolved BIGINT NOT NULL DEFAULT 0,
    error_message TEXT,
    CONSTRAINT ingestion_checkpoint_dataset_check
        CHECK (dataset IN ('sensors', 'minute', 'hourly', 'landmarks')),
    CONSTRAINT ingestion_checkpoint_status_check
        CHECK (status IN ('running', 'succeeded', 'failed')),
    CONSTRAINT ingestion_checkpoint_counts_check
        CHECK (
            inserted_count >= 0 AND
            updated_count >= 0 AND
            rejected_count >= 0 AND
            duplicates_resolved >= 0
        )
);

ALTER TABLE landmark_category
    ADD CONSTRAINT landmark_category_theme_name_key
    UNIQUE (theme_id, category_name);

CREATE UNIQUE INDEX landmark_natural_key
    ON landmark (category_id, feature_name, latitude, longitude)
    NULLS NOT DISTINCT;
