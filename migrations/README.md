# Database migrations

`001_initial_schema.sql` is the baseline PostgreSQL schema for the tables used by the current Flask routes.

Apply it only to a new, empty database:

```powershell
psql -h localhost -U mtrack_app -d mtrack -f migrations/001_initial_schema.sql
```

For a database that already contains MTrack tables, back it up first and create an incremental migration instead of rerunning the baseline. Store each new migration in this directory using the next numeric prefix, for example `002_add_appraisal_comments.sql`.
