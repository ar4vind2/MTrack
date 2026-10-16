-- ====================================================================
-- MIGRATION 002: Appraisal Cycles Foreign Key Architecture & Normalization
-- ====================================================================
-- Replaces legacy text/year cycle columns (appraisal_cycle, appraisal_year)
-- with normalized foreign keys referencing appraisal_cycles(cycle_id).

BEGIN;

-- 1. Ensure cycle_id exists and references appraisal_cycles on all target tables

-- self_appraisal
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='self_appraisal' AND column_name='cycle_id') THEN
        ALTER TABLE self_appraisal ADD COLUMN cycle_id INTEGER;
        UPDATE self_appraisal SET cycle_id = 1 WHERE cycle_id IS NULL;
        ALTER TABLE self_appraisal ALTER COLUMN cycle_id SET NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_self_appraisal_cycle') THEN
        ALTER TABLE self_appraisal ADD CONSTRAINT fk_self_appraisal_cycle FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='self_appraisal' AND column_name='appraisal_cycle') THEN
        ALTER TABLE self_appraisal DROP COLUMN appraisal_cycle;
    END IF;
END $$;

-- manager_appraisal
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='manager_appraisal' AND column_name='cycle_id') THEN
        ALTER TABLE manager_appraisal ADD COLUMN cycle_id INTEGER;
        UPDATE manager_appraisal SET cycle_id = 1 WHERE cycle_id IS NULL;
        ALTER TABLE manager_appraisal ALTER COLUMN cycle_id SET NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_manager_appraisal_cycle') THEN
        ALTER TABLE manager_appraisal ADD CONSTRAINT fk_manager_appraisal_cycle FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='manager_appraisal' AND column_name='appraisal_cycle') THEN
        ALTER TABLE manager_appraisal DROP COLUMN appraisal_cycle;
    END IF;
END $$;

-- behaviour_rating
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='behaviour_rating' AND column_name='cycle_id') THEN
        ALTER TABLE behaviour_rating ADD COLUMN cycle_id INTEGER;
        UPDATE behaviour_rating SET cycle_id = 1 WHERE cycle_id IS NULL;
        ALTER TABLE behaviour_rating ALTER COLUMN cycle_id SET NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_behaviour_cycle') THEN
        ALTER TABLE behaviour_rating ADD CONSTRAINT fk_behaviour_cycle FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='behaviour_rating' AND column_name='appraisal_cycle') THEN
        ALTER TABLE behaviour_rating DROP COLUMN appraisal_cycle;
    END IF;
END $$;

-- feedback_360
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='feedback_360' AND column_name='cycle_id') THEN
        ALTER TABLE feedback_360 ADD COLUMN cycle_id INTEGER;
        UPDATE feedback_360 SET cycle_id = 1 WHERE cycle_id IS NULL;
        ALTER TABLE feedback_360 ALTER COLUMN cycle_id SET NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_feedback_cycle') THEN
        ALTER TABLE feedback_360 ADD CONSTRAINT fk_feedback_cycle FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='feedback_360' AND column_name='appraisal_cycle') THEN
        ALTER TABLE feedback_360 DROP COLUMN appraisal_cycle;
    END IF;
END $$;

-- performance_result
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='performance_result' AND column_name='cycle_id') THEN
        ALTER TABLE performance_result ADD COLUMN cycle_id INTEGER;
        UPDATE performance_result SET cycle_id = 1 WHERE cycle_id IS NULL;
        ALTER TABLE performance_result ALTER COLUMN cycle_id SET NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_performance_cycle') THEN
        ALTER TABLE performance_result ADD CONSTRAINT fk_performance_cycle FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_performance_employee_cycle') THEN
        ALTER TABLE performance_result ADD CONSTRAINT uq_performance_employee_cycle UNIQUE (employee_id, cycle_id);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='performance_result' AND column_name='appraisal_year') THEN
        ALTER TABLE performance_result DROP COLUMN appraisal_year;
    END IF;
END $$;

-- kpi_records foreign key to employee_kpi
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_kpi_records_employee_kpi') THEN
        ALTER TABLE kpi_records
        ADD CONSTRAINT fk_kpi_records_employee_kpi
        FOREIGN KEY (employee_kpi_id) REFERENCES employee_kpi(employee_kpi_id)
        ON DELETE CASCADE;
    END IF;
END $$;

-- 2. Drop obsolete holidays table
DROP TABLE IF EXISTS holidays CASCADE;

COMMIT;
