@echo off
setlocal

rem Seed rápido para insertar datos de ejemplo en la BD (ies.db)
rem y persistir guardias en la tabla 'guardias'.

python -m modules.db.test_guardias.py --db ies.db


endlocal

