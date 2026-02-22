-- ============================================================
-- QMS Enterprise - Extended Schema v2
-- Industrial Quality Management Platform
-- ============================================================

-- Load base schema first (schema.sql), then run this file

-- ============================================================
-- QUALITY LIBRARY MODULE
-- ============================================================

CREATE TABLE quality_standards (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE defect_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    severity_level VARCHAR(20) CHECK (severity_level IN ('low', 'medium', 'high', 'critical')),
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE defect_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES defect_categories(id) ON DELETE SET NULL,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, factory_id)
);

CREATE TABLE root_causes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE corrective_actions (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    root_cause_id INTEGER REFERENCES root_causes(id) ON DELETE SET NULL,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    effectiveness_rating INTEGER CHECK (effectiveness_rating BETWEEN 1 AND 5),
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- DYNAMIC FORM ENGINE
-- ============================================================

CREATE TABLE forms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    module VARCHAR(50) CHECK (module IN ('inspection', 'production', 'maintenance', 'supplier', 'audit')),
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    parent_form_id INTEGER REFERENCES forms(id),
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE form_fields (
    id SERIAL PRIMARY KEY,
    form_id INTEGER REFERENCES forms(id) ON DELETE CASCADE,
    label VARCHAR(200) NOT NULL,
    field_key VARCHAR(100) NOT NULL,
    field_type VARCHAR(30) CHECK (field_type IN ('text', 'number', 'select', 'date', 'checkbox', 'textarea', 'calculated', 'file')),
    is_required BOOLEAN DEFAULT FALSE,
    order_index INTEGER DEFAULT 0,
    validation_rules JSONB DEFAULT '{}',
    options JSONB DEFAULT '[]',
    conditional_logic JSONB DEFAULT '{}',
    calculation_formula TEXT,
    placeholder TEXT,
    help_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE form_responses (
    id SERIAL PRIMARY KEY,
    form_id INTEGER REFERENCES forms(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data JSONB NOT NULL DEFAULT '{}',
    version INTEGER DEFAULT 1,
    is_draft BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- ============================================================
-- DEFECT RECORDING & PRODUCTION DATA
-- ============================================================

CREATE TABLE machines (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    location VARCHAR(150),
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, factory_id)
);

CREATE TABLE production_records (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    machine_id INTEGER REFERENCES machines(id) ON DELETE SET NULL,
    shift VARCHAR(20) CHECK (shift IN ('morning', 'afternoon', 'night')),
    operator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    production_date DATE NOT NULL,
    planned_quantity INTEGER,
    actual_quantity INTEGER,
    planned_time_minutes INTEGER,
    actual_time_minutes INTEGER,
    downtime_minutes INTEGER DEFAULT 0,
    material_batch VARCHAR(100),
    temperature DECIMAL(6,2),
    humidity DECIMAL(5,2),
    form_response_id INTEGER REFERENCES form_responses(id),
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE defect_records (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    production_record_id INTEGER REFERENCES production_records(id) ON DELETE SET NULL,
    machine_id INTEGER REFERENCES machines(id) ON DELETE SET NULL,
    defect_code_id INTEGER REFERENCES defect_codes(id) ON DELETE SET NULL,
    root_cause_id INTEGER REFERENCES root_causes(id) ON DELETE SET NULL,
    corrective_action_id INTEGER REFERENCES corrective_actions(id) ON DELETE SET NULL,
    operator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    shift VARCHAR(20),
    defect_date DATE NOT NULL,
    quantity_defective INTEGER NOT NULL,
    quantity_produced INTEGER,
    severity VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(30) DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    notes TEXT,
    form_response_id INTEGER REFERENCES form_responses(id),
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Edit history for defect records
CREATE TABLE defect_record_history (
    id SERIAL PRIMARY KEY,
    defect_record_id INTEGER REFERENCES defect_records(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    changed_fields JSONB,
    old_values JSONB,
    new_values JSONB,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- QUALITY METRICS (Computed & Cached)
-- ============================================================

CREATE TABLE quality_metrics_cache (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    machine_id INTEGER REFERENCES machines(id) ON DELETE SET NULL,
    shift VARCHAR(20),
    ppm DECIMAL(12,2),
    defect_rate DECIMAL(8,4),
    first_pass_yield DECIMAL(8,4),
    oee DECIMAL(8,4),
    availability DECIMAL(8,4),
    performance DECIMAL(8,4),
    quality DECIMAL(8,4),
    total_produced INTEGER,
    total_defective INTEGER,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(factory_id, metric_date, metric_type, machine_id, shift)
);

-- ============================================================
-- AI PREDICTIONS & ANOMALY DETECTION
-- ============================================================

CREATE TABLE ai_models (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    model_path TEXT,
    feature_columns JSONB,
    accuracy DECIMAL(6,4),
    trained_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ai_predictions (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    model_id INTEGER REFERENCES ai_models(id) ON DELETE SET NULL,
    prediction_type VARCHAR(50) NOT NULL,
    input_data JSONB NOT NULL,
    prediction_result JSONB NOT NULL,
    confidence DECIMAL(6,4),
    actual_outcome JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE anomaly_alerts (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    machine_id INTEGER REFERENCES machines(id) ON DELETE SET NULL,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT,
    data_point JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- REPORTS
-- ============================================================

CREATE TABLE report_exports (
    id SERIAL PRIMARY KEY,
    factory_id INTEGER REFERENCES factories(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    report_type VARCHAR(50) NOT NULL,
    parameters JSONB,
    file_path TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEXES - Performance
-- ============================================================

CREATE INDEX idx_production_records_factory_date ON production_records(factory_id, production_date);
CREATE INDEX idx_production_records_machine ON production_records(machine_id);
CREATE INDEX idx_defect_records_factory_date ON defect_records(factory_id, defect_date);
CREATE INDEX idx_defect_records_machine ON defect_records(machine_id);
CREATE INDEX idx_defect_records_defect_code ON defect_records(defect_code_id);
CREATE INDEX idx_defect_records_status ON defect_records(status);
CREATE INDEX idx_form_responses_factory ON form_responses(factory_id);
CREATE INDEX idx_form_responses_form ON form_responses(form_id);
CREATE INDEX idx_form_responses_submitted_at ON form_responses(submitted_at);
CREATE INDEX idx_quality_metrics_factory_date ON quality_metrics_cache(factory_id, metric_date);
CREATE INDEX idx_anomaly_alerts_factory ON anomaly_alerts(factory_id, created_at);
CREATE INDEX idx_defect_codes_factory ON defect_codes(factory_id);
CREATE INDEX idx_machines_factory ON machines(factory_id);

-- ============================================================
-- TRIGGERS
-- ============================================================

CREATE TRIGGER trigger_production_records_updated_at
    BEFORE UPDATE ON production_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_defect_records_updated_at
    BEFORE UPDATE ON defect_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_forms_updated_at
    BEFORE UPDATE ON forms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- SEED: Quality Standards & Demo Data
-- ============================================================

INSERT INTO quality_standards (name, description, factory_id) VALUES
('ISO 9001:2015', 'Quality Management Systems - Requirements', NULL),
('IATF 16949', 'Quality Management System for Automotive', NULL),
('ISO 14001', 'Environmental Management Systems', NULL);
