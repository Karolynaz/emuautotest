# Emuautotest

AI valdoma emuliatorių testavimo ir automatizavimo platforma per **Model Context Protocol (MCP)**.

## 📁 Versijavimas
Pagal projekto struktūrą, kiekviena programos versija talpinama atskirame `apps/vX.Y.Z` kataloge:
- [apps/v1.0.0/](file:///Users/karolynaz/Library/Mobile%20Documents/com~apple~CloudDocs/vibe%20coding/emuautotest/apps/v1.0.0) – Nintendo 3DS emuliatorius (Azahar) su pilnu MCP palaikymu.

Ateityje atnaujinant ar pridedant kitas konsoles (GBA, NDS, PS1), didinsime versijos numerį (`apps/v1.1.0`, `apps/v2.0.0` ir t. t.).

## ⚡ Greitas paleidimas
Norėdami paleisti naujausios versijos MCP serverį:
```bash
./run.sh
```

Norėdami atlikti pilną integruotą sistemos testą:
```bash
apps/v1.0.0/.venv/bin/python3 apps/v1.0.0/tests/test_adapter.py
```
