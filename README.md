# MeshFX: Forensics for Off-Grid LoRa Mesh Radios

**Project 1 of 5** · Status: research complete, parser built and tested (19 tests), lab work not started
Research cut-off: 9 Oct 2026 (Meshtastic firmware `master@40a0178`, Android app `6630488`, iOS app `8425daa`)

## What this is

There is no forensic method, tool or paper for **Meshtastic** (or MeshCore / Reticulum). Protesters, search-and-rescue teams, hikers, preppers and increasingly criminals use these cheap (~$25) LoRa radios to send text messages and positions with no cell network.

When a radio or a paired phone is seized, investigators have no documented answers to basic questions:

- What evidence is on the radio, and where on its flash memory?
- How do you copy that evidence without changing it?
- What survives "delete messages", "reset node DB" or "factory reset"?
- What can be recovered from the paired phone?
- Who was near whom, and when?
- Can you trust the sender name on a message? (Often not; see [research/05](research/05-rf-mqtt-attribution.md).)

MeshFX answers these questions with:
- a documented **evidence map**
- **acquisition procedures** for each chip family
- an open-source **parser and carver**
- a **paper** built on a controlled lab study, using the same methodology as the DFRWS 2026 Ray-Ban Meta glasses paper

## Why it is novel (summary of [research/01-prior-art.md](research/01-prior-art.md))

| What exists | What it covers | What is missing |
|---|---|---|
| RealWorldCTF 2024 "Long Range 2" write-ups | One ESP32 flash dump: extract 3 prefs files, decrypt one capture | No method, no nRF52, no phone, no deletion recovery, no attribution, pre-2.6 file layout |
| DEF CON 34 "Meshtastic Beasts" (Aug 2026) | Offensive: forgery, eavesdropping, DB flooding | Explicitly no forensics |
| Meshtastic_SDR, gr-lora_sdr, Jeff Geerling blog | Receiving and decoding LoRa traffic | Not evidence handling, no device acquisition |
| Generic flash / IoT forensics papers | Methods in general | Nothing Meshtastic-, MeshCore- or Reticulum-specific |

## Key findings so far (from reading the source; lab confirmation pending)

1. **Radios with screens keep message history on flash.** It is stored in `/Messages_default.msgs`: 10 records on nRF52840 and original ESP32, 20 on ESP32-S3/C3/S2 and others, each a fixed 239-byte record. Screenless builds keep none. The format is fixed and zero-padded, so the records can be carved from raw flash.
2. **Factory reset does not erase everything.**
   - It deletes `/prefs`, empties the message file and wipes the "warm" node ring.
   - It does **not** touch `/backups/backup.proto`, which holds the owner name, every channel key, Wi-Fi password and MQTT credentials.
   - "Reset config" keeps the private key, so the node's identity (and on 2.8+ its node number) can link the device before and after the reset.
   - LittleFS is copy-on-write, so deleted data stays physically on flash until those blocks are reused.
3. **Up to 2 hours of messages exist only in RAM.** The autosave interval is 2 h; a clean shutdown flushes, a battery pull does not. This dictates the seizure procedure (see [research/04](research/04-acquisition.md)).
4. **nRF52840 keeps a raw-flash ring of node identities outside the filesystem** at `0xEA000–0xED000` (node number, last-heard time, public key, role). It is easy to miss with a filesystem-only tool.
5. **The Android app keeps one SQLite database per radio**, `meshtastic_database_<sha1(address)[:10]>`. Only the 5 most recently used are kept (LRU), and older ones are deleted silently. Preference keys map radio addresses to these database files.
6. **Sender identity is weak evidence.** Anyone holding a channel key can forge the "from" field. Only 2.8.1+ signed packets (XEdDSA) and PKI DMs give real attribution, and both are visible as flags in the stored data.
7. **"Lockdown" builds encrypt storage** (nRF52 only: AES-128-CTR + HMAC, files start with `MENC`). It is opt-in and off in normal builds, but the tool must detect it.

## Repository layout

```
01-meshtastic-forensics/
├── README.md                      ← you are here
├── research/
│   ├── 01-prior-art.md            what exists, where the gap is
│   ├── 02-meshtastic-internals.md radio, packet format, crypto, firmware versions
│   ├── 03-evidence-map.md         every artifact: radio flash, phone apps, MQTT, RF
│   ├── 04-acquisition.md          how to image ESP32 / nRF52 / RP2040 / phones, order of volatility
│   ├── 05-rf-mqtt-attribution.md  SDR capture, MQTT/map OSINT, how far to trust "from"
│   ├── 06-meshcore-reticulum.md   phase-2 targets
│   ├── 07-legal-ethics.md         radio, interception and evidence law, dual-use
│   ├── 08-experiment-plan.md      lab design, scenarios, hypotheses H1–H12, metrics
│   ├── 09-paper-outline.md        target venue and paper skeleton
│   └── sources.md                 every source with access date
├── meshfx/                       Python package (read-only parsers)
│   ├── cli.py                     `meshfx` command
│   ├── flash.py                   ESP32 partition table + LittleFS v2 extraction
│   ├── prefs.py                   decode /prefs + /backups protobufs, transmit history, MENC detect
│   ├── msgstore.py                on-device message history + carving
│   ├── apps.py                    Android/iOS companion-app DBs (read-only)
│   ├── report.py                  merge into one timeline, attribution, JSON/CSV/HTML
│   └── proto/                     generated bindings, meshtastic/protobufs @ 95c5f8c
├── tests/                         pytest suite (19 tests)
└── pyproject.toml
```

Planned: `lab/` (device inventory, hashes, scenario logs), `datasets/` (published reference images).

## Tool

```bash
python -m venv .venv && .venv/Scripts/pip install -e .[test]   # Linux/macOS: .venv/bin/pip
pytest -q
```

Every command only reads its inputs. Run it on a hash-verified copy, never on original evidence.

```bash
meshfx parts    flash.bin                         # ESP32 partition table
meshfx extract  flash.bin -o out/                 # pull files out of the LittleFS data partition
meshfx decode   out/prefs/config.proto            # decode a stored prefs/backups file
meshfx msgs     out/Messages_default.msgs         # on-device message history
meshfx carve    flash.bin                         # message records anywhere in an image, incl. deleted
meshfx app      meshtastic_database_<hash>        # Android/iOS companion-app DB
meshfx timeline --flash flash.bin --app DB --format html > case.html   # one merged, attributed timeline
```

| Feature | Checked against | Status |
|---|---|---|
| ESP32 partition table + LittleFS v2 extract | real 4 MB image built in tests | ✅ tests; ⏳ real device image is lab task L3 |
| prefs/backups protobuf decode | round-trip against the bindings | ✅ tests |
| transmit-history + MENC detect | firmware struct / magic | ✅ tests |
| `.msgs` parse + carve | records built from `MessageStore.cpp` struct | ✅ tests; ⏳ real device image is lab task L3 |
| Android/iOS DB read (read-only, incl. write-rejection) | synthetic Room + Core Data DBs | ✅ tests; ⏳ real extraction is lab task L10/L11 |
| merged timeline + attribution + reports | mixed ms/s ordering, HTML escaping | ✅ tests |

### Known gaps (by design or pending)
- **nRF52 LittleFS v1** (128-byte blocks) and the **warm-node ring** at `0xEA000`: `littlefs-python` reads v2 only; needs a v1 reader. Until then, `carve` still finds message records in an nRF52 dump.
- **Decrypting captured traffic / verifying signatures**: out of scope for the tool. Attribution reads the stored `xeddsa_signed` flag; it does not re-verify signatures. The research docs cover the crypto.
- **`device.proto` `rx_text_message`** (last text on screenless radios): not yet surfaced.
- **Lab validation**: every parser is tested against synthetic data built from the firmware structs; none has been run on a real seized device yet (phase 1).

## Roadmap

| Phase | Deliverable | Needs |
|---|---|---|
| 0 ✅ | Research, evidence map | this repo |
| 3 ✅ (ESP32) | Parser: ESP32 LittleFS v2, all prefs/backups protobufs, `.msgs`+carve, app databases → one attributed timeline | done; nRF52 v1 + warm ring pending |
| 1 | Lab build: 4 radios + 2 phones, populate per [08](research/08-experiment-plan.md) | ~$250 hardware |
| 2 | Acquisition SOPs proven on ESP32 + nRF52; hash-verified images | debug probe |
| 3b | nRF52 LittleFS v1 reader + warm-node ring | Python |
| 4 | Anti-forensics study: delete, reset node DB, factory reset, reflash | lab |
| 5 | RF/MQTT correlation + attribution confidence scoring | RTL-SDR |
| 6 | Paper (DFRWS / FSI: Digital Investigation) + public reference dataset | – |
| 7 | MeshCore + Reticulum extension | – |

## Hardware shopping list (approximate, Oct 2026)

| Item | Why | ~USD |
|---|---|---|
| Heltec WiFi LoRa 32 V3 or V4 (ESP32-S3, OLED) | most common ESP32 node; screen → message store | 20–30 |
| LilyGO T-Deck (ESP32-S3, keyboard, screen) | standalone messenger, 20-message history | 50–70 |
| RAK WisBlock 4631 starter kit (nRF52840) | most common nRF52 node; SWD pads | 35–45 |
| LilyGO T-Echo or SenseCAP T1000-E (nRF52840) | InkHUD e-ink UI or tracker; nRF52 message store | 40–60 |
| Raspberry Pi Pico running `debugprobe` (or J-Link EDU Mini) | SWD flash readout for nRF52 | 5–60 |
| RTL-SDR Blog V4 + 868/915 MHz antenna | passive RF capture | 40 |
| Spare Android phone (rootable) | full app data extraction | used |
| iPhone (any supported) | backup-based extraction | used |

## Ethics in one line

Lab work uses only our own devices on our own channels. Never decrypt or keep third-party traffic beyond what a lawful process allows. Details in [research/07](research/07-legal-ethics.md).
