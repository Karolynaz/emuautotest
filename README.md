# Emuautotest

**Emuautotest** – AI valdoma Nintendo 3DS emuliatoriaus (Azahar) testavimo, automatizavimo ir žaidimo platforma macOS sistemai, jungianti **Model Context Protocol (MCP)** serverį ir **native macOS darbalaukio UI**.

## ✨ Ką programa daro

- **Native macOS darbalaukio UI (`run_ui.sh` / `Emuautotest.app`)**:
  - Šoninis meniu su tikru macOS frosted glass (`NSVisualEffectView`) efektu, **Apple SF Symbols** piktogramomis ir automatiniu Light/Dark režimu.
  - Žaidimų biblioteka (`All Games`, `Recently Played`) su tinklelio ir sąrašo rodiniais, tiesiogine paieška, kortelių dydžio keitimu ir SMDH ikonų/metaduomenų išgavimu.
  - Integruotas 3DS dviejų ekranų žaidimo langas su naršyklės stiliaus tab'ais (`+`), greitu išsaugojimu/įkėlimu (`⌘C` / `⌘V`), garso valdymu (`⌘M`), pilno ekrano režimu ir klaviatūros/lietimo įvestimi.
  - Vaizdo įrašymo nustatymai (MP4 / GIF, 15 / 30 / 60 fps, 1× / 2× mastelis).
- **MCP Serveris AI agentams (`run.sh`)**:
  - Leidžia AI agentams programuojamai paleisti/sustabdyti emuliatorių, spausti mygtukus, valdyti Circle Pad ir apatinį liečiamąjį ekraną, vykdyti makrokomandas, skaityti RAM atmintį bei įrašinėti MP4/GIF vaizdo klipus.

## 📁 Versijavimas
Pagal projekto struktūrą, kiekviena programos versija talpinama atskirame `apps/vX.Y.Z` kataloge:
- [apps/v1.1.0/](apps/v1.1.0/) – Nintendo 3DS emuliatorius su native macOS UI, vaizdo įrašymu (MP4/GIF), paskutinių 5 žaidimų automatiniu rodymu ir įspėjimų nuslopinimu.
- [apps/v1.0.0/](apps/v1.0.0/) – Pirminis Nintendo 3DS emuliatoriaus buildas su pilnu MCP palaikymu.

## ⚡ Greitas paleidimas

Paleisti grafinį macOS UI:
```bash
./run_ui.sh
```

Paleisti naujausios versijos MCP serverį:
```bash
./run.sh
```

Atlikti pilną integruotą sistemos testą:
```bash
apps/v1.1.0/.venv/bin/python3 apps/v1.1.0/tests/test_adapter.py
```
