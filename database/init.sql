CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE institutions (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    region VARCHAR(50),
    state VARCHAR(2)
);

CREATE TABLE traffic_metrics (
    time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    institution_id VARCHAR(255) NOT NULL,
    traffic_in DECIMAL(15, 2) DEFAULT 0,
    traffic_out DECIMAL(15, 2) DEFAULT 0,
    latency_ms DECIMAL(10, 2),
    packet_loss_percent DECIMAL(5, 2) DEFAULT 0,
    availability_percent DECIMAL(5, 2) DEFAULT 100,
    bandwidth_utilization_in_percent DECIMAL(5, 2) DEFAULT 0,
    bandwidth_utilization_out_percent DECIMAL(5, 2) DEFAULT 0,
    PRIMARY KEY (time, institution_id)
);

SELECT create_hypertable('traffic_metrics', 'time', chunk_time_interval => INTERVAL '1 hour');

CREATE INDEX idx_traffic_institution ON traffic_metrics (institution_id);
CREATE INDEX idx_traffic_time ON traffic_metrics (time DESC);

CREATE VIEW v_institution_current_status AS
SELECT
    i.id,
    i.name,
    i.latitude,
    i.longitude,
    i.region,
    i.state,
    tm.time as last_update,
    COALESCE(tm.availability_percent, 0) as availability_percent,
    COALESCE(tm.latency_ms, 0) as latency_ms,
    COALESCE(tm.packet_loss_percent, 0) as packet_loss_percent,
    COALESCE(tm.bandwidth_utilization_in_percent, 0) as bandwidth_utilization_in_percent,
    COALESCE(tm.bandwidth_utilization_out_percent, 0) as bandwidth_utilization_out_percent,
    CASE
        WHEN tm.availability_percent IS NULL THEN 'unknown'
        WHEN tm.availability_percent >= 99 THEN 'excellent'
        WHEN tm.availability_percent >= 95 THEN 'good'
        WHEN tm.availability_percent >= 90 THEN 'fair'
        ELSE 'poor'
    END as status_category
FROM institutions i
LEFT JOIN LATERAL (
    SELECT *
    FROM traffic_metrics tm
    WHERE tm.institution_id = i.id
    ORDER BY time DESC
    LIMIT 1
) tm ON true;

CREATE VIEW v_regional_statistics AS
SELECT
    COALESCE(i.region, 'Desconhecida') as region,
    COALESCE(i.state, 'XX') as state,
    COUNT(DISTINCT i.id) as total_institutions,
    ROUND(AVG(tm.availability_percent), 2) as avg_availability,
    ROUND(AVG(tm.latency_ms), 2) as avg_latency,
    ROUND(AVG(tm.packet_loss_percent), 2) as avg_packet_loss,
    COUNT(CASE WHEN tm.availability_percent < 95 THEN 1 END) as degraded_institutions
FROM institutions i
LEFT JOIN LATERAL (
    SELECT *
    FROM traffic_metrics tm
    WHERE tm.institution_id = i.id
    ORDER BY time DESC
    LIMIT 1
) tm ON true
GROUP BY i.region, i.state;