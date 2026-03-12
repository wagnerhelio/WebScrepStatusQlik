@echo off
title PySQL + Evolution - Orquestrador
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar_pysql_evolution.ps1"
pause
