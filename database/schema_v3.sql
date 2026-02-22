-- ============================================================
-- QMS Quality 4.0 — Schema v3
-- Smart Manufacturing Extension
-- Run AFTER schema.sql and schema_v2.sql
-- ============================================================

-- ============================================================
-- IOT DEVICES & SENSOR DATA
-- ============================================================
CREATE TABLE IF NOT EXISTS iot_devices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    machine_id INTEGER REFERENCES machines(id) ON DELETE CASCADE,
    device_type VARCHAR(50) CHECK (device_type IN ('temperature','vibration','pressure','humidity','speed','vision','acoustic','torque','custom')),
    serial_number VARCHAR(100),
    location VARCHAR(150),
    is_active BOOLEAN DEFAULT TRUE,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensor_data (
    id BIGSERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES iot_devices(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(18,6) NOT NULL,
    unit VARCHAR(20),
    quality_flag VARCHAR(20) DEFAULT 'good' CHECK (quality_flag IN ('good','suspect','bad','missing')),
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE
) PARTITION BY RANGE (recorded_at);

-- Create monthly partitions for sensor_data (current + next 3 months)
CREATE TABLE IF NOT EXISTS sensor_data_default PARTITION OF sensor_data DEFAULT;

-- ── SPC: link sensor readings to defect records ──
CREATE TABLE IF NOT EXISTS sensor_defect_correlation (
    id SERIAL PRIMARY KEY,
    sensor_data_id BIGINT,
    defect_record_id INTEGER REFERENCES defect_records(id) ON DELETE CASCADE,
    correlation_score DECIMAL(6,4),
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- DIGITAL TWIN
-- ============================================================
CREATE TABLE IF NOT EXISTS digital_assets (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    virtual_model_reference TEXT,
    model_type VARCHAR(50) DEFAULT 'simulation',
    status VARCHAR(30) DEFAULT 'active' CHECK (status IN ('active','inactive','updating','error')),
    parameters JSONB DEFAULT '{}',
    last_sync_at TIMESTAMP,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS twin_simulation_runs (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES digital_assets(id) ON DELETE CASCADE,
    input_parameters JSONB NOT NULL DEFAULT '{}',
    planned_output JSONB,
    actual_output JSONB,
    deviation JSONB,
    quality_score DECIMAL(6,4),
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE
);

-- ============================================================
-- SPC — Statistical Process Control
-- ============================================================
CREATE TABLE IF NOT EXISTS spc_control_charts (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    chart_type VARCHAR(20) DEFAULT 'xbar' CHECK (chart_type IN ('xbar','r_chart','p_chart','np_chart','c_chart','u_chart')),
    ucl DECIMAL(18,6),
    lcl DECIMAL(18,6),
    center_line DECIMAL(18,6),
    sample_size INTEGER DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spc_samples (
    id BIGSERIAL PRIMARY KEY,
    chart_id INTEGER REFERENCES spc_control_charts(id) ON DELETE CASCADE,
    sample_values JSONB NOT NULL,
    sample_mean DECIMAL(18,6),
    sample_range DECIMAL(18,6),
    sample_stddev DECIMAL(18,6),
    is_out_of_control BOOLEAN DEFAULT FALSE,
    violation_rule VARCHAR(50),
    sampled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE
);

-- ============================================================
-- PREDICTIVE MAINTENANCE
-- ============================================================
CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id) ON DELETE CASCADE,
    predicted_failure_date DATE,
    confidence_score DECIMAL(6,4),
    failure_type VARCHAR(100),
    model_version VARCHAR(50),
    mtbf_days DECIMAL(10,2),
    mttr_hours DECIMAL(10,2),
    risk_level VARCHAR(20) CHECK (risk_level IN ('low','medium','high','critical')),
    recommended_action TEXT,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maintenance_events (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id) ON DELETE CASCADE,
    event_type VARCHAR(50) CHECK (event_type IN ('planned','unplanned','emergency','inspection')),
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    duration_hours DECIMAL(8,2),
    technician_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    description TEXT,
    parts_replaced JSONB DEFAULT '[]',
    cost DECIMAL(12,2),
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- RISK SCORES
-- ============================================================
CREATE TABLE IF NOT EXISTS risk_scores (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id) ON DELETE CASCADE,
    risk_level VARCHAR(20) CHECK (risk_level IN ('low','medium','high','critical')),
    probability_score DECIMAL(6,4),
    predicted_defect_type VARCHAR(100),
    contributing_factors JSONB DEFAULT '[]',
    recommendation TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE
);

-- ============================================================
-- PRODUCTION BATCHES (Traceability)
-- ============================================================
CREATE TABLE IF NOT EXISTS production_batches (
    id SERIAL PRIMARY KEY,
    batch_number VARCHAR(100) NOT NULL,
    material_supplier VARCHAR(200),
    material_type VARCHAR(150),
    production_date DATE NOT NULL,
    expiry_date DATE,
    quantity INTEGER,
    status VARCHAR(30) DEFAULT 'in_production' CHECK (status IN ('planned','in_production','completed','quarantine','rejected','released')),
    quality_grade VARCHAR(10),
    test_results JSONB DEFAULT '{}',
    certifications JSONB DEFAULT '[]',
    notes TEXT,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(batch_number, factory_id)
);

CREATE TABLE IF NOT EXISTS batch_trace_links (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER REFERENCES production_batches(id) ON DELETE CASCADE,
    machine_id INTEGER REFERENCES machines(id) ON DELETE SET NULL,
    operator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    defect_record_id INTEGER REFERENCES defect_records(id) ON DELETE SET NULL,
    production_record_id INTEGER REFERENCES production_records(id) ON DELETE SET NULL,
    corrective_action_id INTEGER REFERENCES corrective_actions(id) ON DELETE SET NULL,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE
);

-- ============================================================
-- QUALITY 4.0 KPIs
-- ============================================================
CREATE TABLE IF NOT EXISTS quality_kpis (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    kpi_date DATE NOT NULL,
    copq DECIMAL(14,2),
    risk_index DECIMAL(6,4),
    process_stability_score DECIMAL(6,4),
    ai_confidence_score DECIMAL(6,4),
    predictive_accuracy_pct DECIMAL(6,4),
    smart_compliance_index DECIMAL(6,4),
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(factory_id, kpi_date)
);

-- ============================================================
-- AI CHATBOT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS chatbot_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT,
    context_data JSONB,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- OPERATOR PERFORMANCE
-- ============================================================
CREATE TABLE IF NOT EXISTS operator_metrics (
    id SERIAL PRIMARY KEY,
    operator_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    shift VARCHAR(20),
    total_produced INTEGER DEFAULT 0,
    total_defective INTEGER DEFAULT 0,
    defect_rate DECIMAL(8,4),
    efficiency_pct DECIMAL(6,2),
    quality_score DECIMAL(6,2),
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    UNIQUE(operator_id, metric_date, shift)
);

-- ============================================================
-- PERFORMANCE INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_iot_devices_machine ON iot_devices(machine_id);
CREATE INDEX IF NOT EXISTS idx_iot_devices_factory ON iot_devices(factory_id);
CREATE INDEX IF NOT EXISTS idx_sensor_data_device ON sensor_data(device_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_factory_time ON sensor_data(factory_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_spc_samples_chart ON spc_samples(chart_id, sampled_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_pred_machine ON maintenance_predictions(machine_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_machine ON risk_scores(machine_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_production_batches_factory ON production_batches(factory_id, production_date DESC);
CREATE INDEX IF NOT EXISTS idx_batch_trace_batch ON batch_trace_links(batch_id);
CREATE INDEX IF NOT EXISTS idx_quality_kpis_factory_date ON quality_kpis(factory_id, kpi_date DESC);
CREATE INDEX IF NOT EXISTS idx_chatbot_sessions_factory ON chatbot_sessions(factory_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operator_metrics_operator ON operator_metrics(operator_id, metric_date DESC);

-- ============================================================
-- TRIGGERS
-- ============================================================
CREATE TRIGGER trigger_digital_assets_updated_at
    BEFORE UPDATE ON digital_assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_production_batches_updated_at
    BEFORE UPDATE ON production_batches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
