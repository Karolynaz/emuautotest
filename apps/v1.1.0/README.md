# Emuautotest v1.1.0

**Emuautotest** – tai Model Context Protocol (MCP) serveris ir testavimo aplinka, leidžianti dirbtinio intelekto agentams (Claude, Antigravity, Codex, Cursor, GPT ir kt.) programuojamai valdyti, įrašinėti ir testuoti Nintendo 3DS žaidimų emuliatorių.

## 🌟 Naujovės v1.1.0 versijoje

1. **Paskutinių 5 paleistų žaidimų rodymas pradiniame lange:**
   - Emuliatoriui startuojant pradiniame lange iš karto rodomi paskutiniai 5 žaisti žaidimai (su pavadinimais, ikonėlėmis, regionu ir failų dydžiais).
   - Nebereikia rankiniu būdu eiti į *Failai > Neseniai įkrauti failai*.
   - Integruotas automatinis `recent_games` sinchronizavimas ir naujas MCP įrankis `emulator_sync_recent_games`.
2. **Įspėjamųjų pranešimų nuslopinimas:**
   - Visiškai pašalintas pranešimas *"The 'azahar' executable is being run directly rather than via the Azahar.app bundle"*.
   - Taikytas tiesioginis binarinis apėjimas (ARM64 ir x86_64) bei adaptyvus fono modalinių langų uždarymo saugiklis.
3. **Vaizdo įrašymas ir eksportavimas (MP4 / GIF):**
   - Galimybė AI agentui pradėti/sustabdyti foninį žaidimo vaizdo įrašymą (`emulator_record_start`, `emulator_record_stop`).
   - Greitas klipų įrašymas (`emulator_record_clip`), palaikantis abu ekranus (400x480), viršutinį arba apatinį liečiamąjį ekraną.
   - Išsaugotų įrašų peržiūra (`emulator_list_recordings`).
4. **Nauja Emuautotest minimalistinė auksinio pultelio piktograma ir dock minimizavimas.**

---

## 🛠️ MCP Įrankiai (Tools)

| Įrankis | Parametrai | Aprašymas |
|---|---|---|
| `emulator_start` | `rom_path` *(nebūtinas)* | Paleidžia emuliatorių su nurodytu ROM arba atveria pradinį langą su 5 paskutiniais žaidimais. |
| `emulator_stop` | – | Saugiai ir tvarkingai sustabdo emuliatoriaus procesą. |
| `emulator_get_status` | – | Grąžina būseną, FPS, emuliacijos greitį, lango koordinates ir RPC ryšį. |
| `emulator_sync_recent_games` | `active_rom` *(nebūtinas)* | Sinchronizuoja 5 paskutinius žaidimus į pradinio lango sąrašą. |
| `emulator_screenshot` | `target`: `"both"`, `"top"`, `"bottom"` | Užfiksuoja kadrą ir grąžina PNG vaizdą tiesiai į AI kontekstą. |
| `emulator_press_button`| `button`: pvz. `"A"`, `duration_ms`: `100` | Paspaudžia nurodytą mygtuką (`A`, `B`, `X`, `Y`, `UP`, `DOWN`, `L`, `R` ir kt.). |
| `emulator_touch` | `x`: `0.0-1.0`, `y`: `0.0-1.0`, `duration_ms`: `100` | Paliečia apatinį 3DS liečiamąjį ekraną normalizuotomis koordinatėmis. |
| `emulator_circle_pad` | `direction`: `"UP"`, `duration_ms`: `200` | Pajudina analoginę vairasvirtę nurodyta kryptimi. |
| `emulator_macro` | `actions_json`: JSON masyvas | Įvykdo veiksmų seką su pauzėmis ir ekrano nuotraukomis. |
| `emulator_record_start` | `target`, `fps`, `format`, `scale`, `duration_seconds` | Pradeda foninį vaizdo įrašymą (MP4 H.264 arba GIF). |
| `emulator_record_stop` | – | Užbaigia įrašymą ir eksportuoja failą į `recordings/`. |
| `emulator_record_status` | – | Patikrina aktyvaus vaizdo įrašo eigą, kadrų skaičių ir trukmę. |
| `emulator_record_clip` | `duration_seconds`, `target`, `fps`, `format` | Sinchroniškai įrašo nurodytos trukmės vaizdo klipą. |
| `emulator_list_recordings`| – | Išvardija visus sugeneruotus MP4/GIF vaizdo įrašus. |
| `emulator_read_memory` | `hex_address`: `"0x100000"`, `size`: `16` | Nuskaito RAM baitus šešioliktaine reikšme per RPC. |
| `emulator_list_roms` | – | Parodo pasiekiamus ROM failus `roms/` aplanke. |

---

## 🔌 Prijungimas prie AI aplinkų

### 1. Codex (`~/.codex/config.toml`)
```toml
[mcp_servers.emuautotest]
command = "/Users/karolynaz/Library/Mobile Documents/com~apple~CloudDocs/vibe coding/emuautotest/apps/v1.1.0/.venv/bin/python3"
args = ["/Users/karolynaz/Library/Mobile Documents/com~apple~CloudDocs/vibe coding/emuautotest/apps/v1.1.0/run_server.py"]
```

### 2. Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "emuautotest": {
      "command": "/Users/karolynaz/Library/Mobile Documents/com~apple~CloudDocs/vibe coding/emuautotest/apps/v1.1.0/.venv/bin/python3",
      "args": [
        "/Users/karolynaz/Library/Mobile Documents/com~apple~CloudDocs/vibe coding/emuautotest/apps/v1.1.0/run_server.py"
      ]
    }
  }
}
```

---

## 🧪 Integruotas testavimas

Paleisti visą v1.1.0 integracijos testų rinkinį:
```bash
apps/v1.1.0/.venv/bin/python3 apps/v1.1.0/tests/test_adapter.py
```
