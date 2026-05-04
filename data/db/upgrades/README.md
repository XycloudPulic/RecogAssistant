# Database upgrades (reserved)

Place future incremental DDL/DML or Python migration helpers here.

Version-to-version upgrades are **not** executed automatically yet; current installs rely on:

- `data/db/scripts/init_recognition_db.sql` — full initial DDL
- `data/db/scripts/insert_recognition_db.sql` — initial seed DML

Wire new upgrade steps from application or `service.bat` when you introduce them.
