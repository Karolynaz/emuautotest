# Emuautotest

AI valdoma emuliatorių testavimo ir automatizavimo platforma per **Model Context Protocol (MCP)**.

## 📁 Versijavimas
Pagal projekto struktūrą, kiekviena programos versija talpinama atskirame `apps/vX.Y.Z` kataloge:
- [apps/v1.1.0/](file:///Users/karolynaz/Library/Mobile%20Documents/com~apple~CloudDocs/vibe%20coding/emuautotest/apps/v1.1.0) – Nintendo 3DS emuliatorius su vaizdo įrašymu (MP4/GIF), paskutinių 5 žaidimų automatiniu rodymu pradiniame lange ir įspėjimų nuslopinimu.
- [apps/v1.0.0/](file:///Users/karolynaz/Library/Mobile%20Documents/com~apple~CloudDocs/vibe%20coding/emuautotest/apps/v1.0.0) – Pirminis Nintendo 3DS emuliatoriaus buildas su pilnu MCP palaikymu.

## ⚡ Greitas paleidimas
Norėdami paleisti naujausios versijos MCP serverį:
```bash
./run.sh
```

Norėdami atlikti pilną integruotą sistemos testą:
```bash
apps/v1.1.0/.venv/bin/python3 apps/v1.1.0/tests/test_adapter.py
```
