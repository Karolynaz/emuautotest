# Emuautotest v1.0.0

**Emuautotest** – tai Model Context Protocol (MCP) serveris ir testavimo aplinka, leidžianti dirbtinio intelekto agentams (Claude, Antigravity, Cursor, GPT-4o ir kt.) programuojamai valdyti bei testuoti Nintendo 3DS žaidimų emuliatorių.

## 🌟 Galimybės

- **Azahar (Citra tęsinio) integracija:** tiesioginis RPC ryšys su emuliatoriaus branduoliu (60 FPS, našumo statistika, kadrų fiksavimas).
- **Vaizdo analizė (Multimodal Vision):**
  - Viršutinis 3DS ekranas (400x240)
  - Apatinis liečiamasis ekranas (320x240)
  - Bendras dvigubas ekranas (400x480)
- **Valdymas:**
  - Fiziniai mygtukai: `A`, `B`, `X`, `Y`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `L`, `R`, `START`, `SELECT`, `HOME`.
  - Analoginis „Circle Pad“ vairasvirtės judėjimas (`UP`, `DOWN`, `LEFT`, `RIGHT`, `UP_LEFT` ir t. t.).
  - Ekrano lietimas: normalizuotos koordinatės `(x, y)` nuo `0.0` iki `1.0`.
- **Meniu makro komandos:** AI gali vienu iškvietimu atlikti kelių veiksmų seką su pauzėmis (`press`, `wait`, `touch`, `screenshot`), taip sutaupant laiką ir tinklo užklausas.
- **RAM atminties nuskaitymas/įrašymas:** Tiesioginė prieiga prie emuliatoriaus atminties reikšmių.

---

## 🛠️ MCP Įrankiai (Tools)

| Įrankis | Parametrai | Aprašymas |
|---|---|---|
| `emulator_start` | `rom_path` *(nebūtinas)* | Paleidžia Azahar emuliatorių su nurodytu ROM (pagal nutylėjimą `2048-3D.3dsx`). |
| `emulator_stop` | – | Saugiai sustabdo emuliatoriaus procesą. |
| `emulator_get_status` | – | Grąžina būseną, FPS, emuliacijos greitį, lango koordinates ir RPC ryšį. |
| `emulator_screenshot` | `target`: `"both"`, `"top"`, `"bottom"` | Užfiksuoja kadrą ir grąžina PNG vaizdą tiesiai į AI kontekstą. |
| `emulator_press_button`| `button`: pvz. `"A"`, `duration_ms`: `100` | Paspaudžia nurodytą mygtuką. |
| `emulator_touch` | `x`: `0.0-1.0`, `y`: `0.0-1.0`, `duration_ms`: `100` | Paliečia apatinį 3DS liečiamąjį ekraną. |
| `emulator_circle_pad` | `direction`: `"UP"`, `duration_ms`: `200` | Pajudina analoginį vairasvirtę nurodyta kryptimi. |
| `emulator_macro` | `actions_json`: JSON masyvas | Įvykdo veiksmų seką (pvz., eiti per meniu). |
| `emulator_read_memory` | `hex_address`: `"0x100000"`, `size`: `16` | Nuskaito RAM baitus šešioliktaine reikšme. |
| `emulator_list_roms` | – | Parodo visus pasiekiamus ROM failus `roms/` aplanke. |

---

## 🔌 Kaip prijungti prie AI

### 1. Claude Desktop (`claude_desktop_config.json`)
Failo vieta: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "emuautotest": {
      "command": "/Users/karolynaz/Library/Mobile Documents/com~apple~CloudDocs/vibe coding/emuautotest/apps/v1.0.0/.venv/bin/python3",
      "args": [
        "/Users/karolynaz/Library/Mobile Documents/com~apple~CloudDocs/vibe coding/emuautotest/apps/v1.0.0/run_server.py"
      ]
    }
  }
}
```

### 2. Antigravity / Cursor / Kitos MCP programos
Nurodykite:
- **Command:** `<kelias_iki_projekto>/apps/v1.0.0/.venv/bin/python3`
- **Args:** `["<kelias_iki_projekto>/apps/v1.0.0/run_server.py"]`

---

## 🧪 Integruotas testavimas

Paleisti pilną testą galite komanda:
```bash
apps/v1.0.0/.venv/bin/python3 apps/v1.0.0/tests/test_adapter.py
```
Šis testas automatiškai:
1. Paleidžia Azahar su `2048-3D` žaidimu.
2. Patikrina RPC ir našumą (60 FPS).
3. Padaro viršutinio, apatinio ir viso ekrano nuotraukas.
4. Išbando mygtukus (pajudina kaladėles).
5. Išbando ekrano paspaudimą.
6. Įvykdo makro seką.
7. Užveria emuliatorių.
