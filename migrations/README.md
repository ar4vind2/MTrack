# Database migrations

`001_initial_schema.sql` is the baseline PostgreSQL schema for the tables used by the current Flask routes.

Apply it only to a new, empty database:

```powershell
psql -h localhost -U mtrack_app -d mtrack -f migrations/001_initial_schema.sql
```

For a database that already contains MTrack tables, back it up first and create an incremental migration instead of rerunning the baseline. Store each new migration in this directory using the next numeric prefix.

- `002_cycle_id_migration.sql`: Migrates appraisal and performance tables (`self_appraisal`, `manager_appraisal`, `behaviour_rating`, `feedback_360`, `performance_result`) from legacy textual `appraisal_cycle` / `appraisal_year` columns to foreign key `cycle_id` referencing `appraisal_cycles(cycle_id)`. Also ensures `uq_performance_employee_cycle` unique constraint and `fk_kpi_records_employee_kpi` foreign key constraint.
