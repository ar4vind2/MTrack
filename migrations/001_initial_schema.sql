BEGIN;

CREATE TABLE IF NOT EXISTS roles (
    role_id BIGSERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO roles (role_id, role_name)
VALUES
    (1, 'Employee'),
    (2, 'Manager'),
    (3, 'HR'),
    (4, 'Admin')
ON CONFLICT (role_id) DO UPDATE SET role_name = EXCLUDED.role_name;

SELECT setval(
    pg_get_serial_sequence('roles', 'role_id'),
    (SELECT MAX(role_id) FROM roles)
);

CREATE TABLE IF NOT EXISTS departments (
    department_id BIGSERIAL PRIMARY KEY,
    department_name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS designations (
    designation_id BIGSERIAL PRIMARY KEY,
    designation_name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS branches (
    branch_id BIGSERIAL PRIMARY KEY,
    branch_name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role_id BIGINT NOT NULL REFERENCES roles(role_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE REFERENCES users(user_id) ON DELETE SET NULL,
    employee_code VARCHAR(50) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    department_id BIGINT REFERENCES departments(department_id) ON DELETE SET NULL,
    designation_id BIGINT REFERENCES designations(designation_id) ON DELETE SET NULL,
    branch_id BIGINT REFERENCES branches(branch_id) ON DELETE SET NULL,
    manager_id BIGINT REFERENCES employees(employee_id) ON DELETE SET NULL,
    employment_status VARCHAR(30) NOT NULL DEFAULT 'Active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kra_master (
    kra_id BIGSERIAL PRIMARY KEY,
    kra_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    default_weightage NUMERIC(5, 2) NOT NULL CHECK (default_weightage BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_master (
    kpi_id BIGSERIAL PRIMARY KEY,
    kpi_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    unit VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employee_kra (
    employee_kra_id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    kra_id BIGINT NOT NULL REFERENCES kra_master(kra_id) ON DELETE RESTRICT,
    assigned_weightage NUMERIC(5, 2) NOT NULL CHECK (assigned_weightage BETWEEN 0 AND 100),
    target_value TEXT,
    due_date DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'Active',
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employee_kpi (
    employee_kpi_id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    kpi_id BIGINT NOT NULL REFERENCES kpi_master(kpi_id) ON DELETE RESTRICT,
    assigned_target NUMERIC(14, 2) NOT NULL,
    appraisal_period VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Active',
    assigned_by BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS kpi_records (
    employee_kpi_id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    kpi_id BIGINT NOT NULL REFERENCES kpi_master(kpi_id) ON DELETE RESTRICT,
    achieved_value NUMERIC(14, 2) NOT NULL,
    evaluation_month DATE NOT NULL,
    remarks TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
    attendance_id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL,
    UNIQUE (employee_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS training_records (
    training_record_id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    training_name VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Assigned',
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS manager_appraisal (
    appraisal_id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    manager_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    cycle_id BIGINT NOT NULL REFERENCES appraisal_cycles(cycle_id),
    status VARCHAR(30) NOT NULL DEFAULT 'Pending',
    appraisal_date DATE,
    productivity NUMERIC(3, 1),
    quality_of_work NUMERIC(3, 1),
    teamwork NUMERIC(3, 1),
    communication NUMERIC(3, 1),
    problem_solving NUMERIC(3, 1),
    initiative NUMERIC(3, 1),
    compliance NUMERIC(3, 1),
    total_score NUMERIC(5, 2),
    manager_comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS performance_result (
    performance_id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    cycle_id BIGINT NOT NULL REFERENCES appraisal_cycles(cycle_id),
    kpi_score NUMERIC(5, 2),
    attendance_score NUMERIC(5, 2),
    manager_score NUMERIC(5, 2),
    behaviour_score NUMERIC(5, 2),
    self_appraisal_score NUMERIC(5, 2),
    training_score NUMERIC(5, 2),
    final_score NUMERIC(5, 2),
    rating VARCHAR(100),
    recommendation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_performance_employee_cycle UNIQUE (employee_id, cycle_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL DEFAULT 'system',
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS employees_manager_id_idx ON employees(manager_id);
CREATE INDEX IF NOT EXISTS employee_kra_employee_id_idx ON employee_kra(employee_id);
CREATE INDEX IF NOT EXISTS employee_kpi_employee_id_idx ON employee_kpi(employee_id);
CREATE INDEX IF NOT EXISTS kpi_records_employee_id_idx ON kpi_records(employee_id);
CREATE INDEX IF NOT EXISTS attendance_employee_id_idx ON attendance(employee_id);
CREATE INDEX IF NOT EXISTS training_records_employee_id_idx ON training_records(employee_id);
CREATE INDEX IF NOT EXISTS manager_appraisal_manager_id_idx ON manager_appraisal(manager_id);
CREATE INDEX IF NOT EXISTS manager_appraisal_employee_id_idx ON manager_appraisal(employee_id);
CREATE INDEX IF NOT EXISTS performance_result_employee_cycle_idx ON performance_result(employee_id, cycle_id DESC);
CREATE INDEX IF NOT EXISTS notifications_user_created_idx ON notifications(user_id, created_at DESC);

COMMIT;
