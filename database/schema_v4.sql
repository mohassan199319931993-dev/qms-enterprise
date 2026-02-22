-- QMS Enterprise v4 — Supplemental Schema
-- Adds missing tables referenced by routes/services

-- ── OEE Records ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS oee_records (
    id              SERIAL PRIMARY KEY,
    factory_id      INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    machine_id      INTEGER REFERENCES machines(id)  ON DELETE SET NULL,
    record_date     DATE    NOT NULL DEFAULT CURRENT_DATE,
    shift           VARCHAR(20),
    planned_time    NUMERIC(10,2),
    downtime        NUMERIC(10,2) DEFAULT 0,
    availability_pct NUMERIC(6,2) DEFAULT 88.0,
    performance_pct  NUMERIC(6,2) DEFAULT 93.0,
    quality_pct      NUMERIC(6,2) DEFAULT 99.8,
    oee_pct          NUMERIC(6,2) GENERATED ALWAYS AS
                     (ROUND(availability_pct * performance_pct * quality_pct / 10000, 2)) STORED,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_oee_factory_date ON oee_records(factory_id, record_date);

-- ── Defect Records — ensure all needed columns ───────────────────────
ALTER TABLE defect_records
    ADD COLUMN IF NOT EXISTS operator_id      INTEGER REFERENCES users(id)    ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS shift            VARCHAR(20),
    ADD COLUMN IF NOT EXISTS severity         VARCHAR(20)  DEFAULT 'medium',
    ADD COLUMN IF NOT EXISTS status           VARCHAR(30)  DEFAULT 'open',
    ADD COLUMN IF NOT EXISTS notes            TEXT,
    ADD COLUMN IF NOT EXISTS root_cause_id    INTEGER,
    ADD COLUMN IF NOT EXISTS corrective_action_id INTEGER,
    ADD COLUMN IF NOT EXISTS updated_at       TIMESTAMP   DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS deleted_at       TIMESTAMP;

-- ── Defect Records — quantity columns ────────────────────────────────
ALTER TABLE defect_records
    ADD COLUMN IF NOT EXISTS quantity_produced  INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS quantity_defective INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS defect_date        DATE    DEFAULT CURRENT_DATE;

-- ── AI Predictions — ensure table ────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_predictions (
    id              SERIAL PRIMARY KEY,
    factory_id      INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    prediction_type VARCHAR(50),
    input_data      JSONB,
    prediction_result JSONB,
    confidence      NUMERIC(5,4),
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_pred_factory ON ai_predictions(factory_id, created_at);

-- ── AI Models — ensure all columns ───────────────────────────────────
ALTER TABLE ai_models
    ADD COLUMN IF NOT EXISTS feature_columns TEXT,
    ADD COLUMN IF NOT EXISTS is_active       BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS trained_at      TIMESTAMP DEFAULT NOW();

-- ── Machines — ensure deleted_at ─────────────────────────────────────
ALTER TABLE machines
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

-- ── Production Records — ensure columns ──────────────────────────────
ALTER TABLE production_records
    ADD COLUMN IF NOT EXISTS temperature    NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS humidity       NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS material_batch VARCHAR(100),
    ADD COLUMN IF NOT EXISTS actual_quantity INTEGER,
    ADD COLUMN IF NOT EXISTS deleted_at     TIMESTAMP;

-- ── Corrective Actions — ensure factory_id + deleted_at ──────────────
ALTER TABLE corrective_actions
    ADD COLUMN IF NOT EXISTS factory_id  INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS deleted_at  TIMESTAMP,
    ADD COLUMN IF NOT EXISTS effectiveness_rating NUMERIC(3,1);

-- ── Root Causes — ensure root_cause_id FK on corrective_actions ──────
ALTER TABLE corrective_actions
    ADD COLUMN IF NOT EXISTS root_cause_id INTEGER REFERENCES root_causes(id) ON DELETE SET NULL;

-- ── Quality KPIs cache (used by q40 kpis endpoint) ───────────────────
CREATE TABLE IF NOT EXISTS quality_kpis (
    id          SERIAL PRIMARY KEY,
    factory_id  INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    period_date DATE    NOT NULL,
    ppm         NUMERIC(12,2),
    oee_pct     NUMERIC(6,2),
    fpy_pct     NUMERIC(6,2),
    copq_usd    NUMERIC(14,2),
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE (factory_id, period_date)
);

-- ── Indexes for performance ───────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_defect_factory_date  ON defect_records(factory_id, defect_date);
CREATE INDEX IF NOT EXISTS idx_defect_machine       ON defect_records(machine_id);
CREATE INDEX IF NOT EXISTS idx_defect_deleted       ON defect_records(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_anomaly_factory      ON anomaly_alerts(factory_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sensor_device_time   ON sensor_data(device_id, recorded_at);
