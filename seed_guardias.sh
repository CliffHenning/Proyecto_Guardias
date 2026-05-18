@echo off
setlocal

rem Seed rápido para insertar datos de ejemplo en la BD (ies.db)
rem y persistir guardias en la tabla 'guardias'.

python -m modules.db.seed_example_guardias --db ies.db


endlocal

