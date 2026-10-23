@echo off
python test_accuracy.py 2025-11-01 --end-date 2025-11-26 > test_result.txt 2>&1
type test_result.txt | findstr /C:"总场次" /C:"推荐场次" /C:"全赢" /C:"全输" /C:"引擎胜率"
