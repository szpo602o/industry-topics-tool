@echo off

cd /d C:\Users\szpo6\src\commit-report-tool\industry-topics-tool

python src\run_daily.py

cd /d C:\Users\szpo6\src\commit-report-tool\industry-topics-tool\output

surge . medical-topics-ryo.surge.sh