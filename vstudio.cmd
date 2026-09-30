@echo off
rem vstudio - skrót na Windows. Używa systemowego Pythona 3.13 w trybie izolowanym.
rem Przykłady:  vstudio.cmd doctor
rem              vstudio.cmd new moj-film --brand "AI EVOLUTION"
py -3 -I "%~dp0vstudio.py" %*
