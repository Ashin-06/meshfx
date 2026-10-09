# 08 · Experiment Plan

The design follows the controlled-experiment pattern of recent DFRWS device papers: known devices → scripted activity with ground truth → acquisition → anti-forensic actions → re-acquisition → measure what survives.

## Hypotheses

| ID | Hypothesis | Test | Status |
|---|---|---|---|
| H1 | nRF52 UF2 `CURRENT.UF2` includes `0xEA000–0xF4000` (warm ring + LittleFS) | compare against a SWD dump | 🧪 |
| H2 | CLI `--info` / `--export-config` change no flash files | image → CLI → image → diff | 🧪 |
| H3 | cleared or rotated message records can be carved from free LittleFS blocks (ESP32 directly; nRF52 needs an lfs-v1-aware pass) | send N messages, clear, image, carve | 🧪 |
| H4 | clean shutdown flushes RAM messages and node DB; battery pull loses everything since the last autosave | send, wait < 2 h, shut down vs pull battery, image | 🧪 |
| H5 | un-compacted warm-ring pages keep earlier node sightings (nRF52840) | fill the hot DB past capacity, image repeatedly | 🧪 |
| H6 | `/backups/backup.proto` survives factory reset | create a backup, factory reset, image | 🧪 (source says yes) |
| H7 | "reset config" keeps the private key, so the node identity links before and after (2.8: same NodeNum) | reset config vs reset device, compare keys | 🧪 (source says yes) |
| H8 | ESP32 `nvs` holds BLE bond records identifying paired phones | pair 2 phones, parse NVS | 🧪 |
| H9 | the ESP32 `coredump` partition can hold message text from RAM | force a crash in the lab (debug build), parse the core | 🧪 |
| H10 | an iOS encrypted backup includes the SwiftData store; legacy `Meshtastic.sqlite` survives migration | backup + FFS comparison | 🧪 |
| H11 | an Android per-radio database deleted by the LRU limit (6th radio) is recoverable from free space or other copies | use 6 radios, extract, search | 🧪 |
| H12 | messages deleted in the Android app remain in the WAL, FTS5 segments or freelist | delete, extract with WAL, carve | 🧪 |

## Lab tasks

| ID | Task | Produces |
|---|---|---|
| L1 | RTL-SDR capture of lab traffic, decrypted with meshfx | first live proof of the channel-decrypt path |
| L2 | acquisition SOP validation per chip (ESP32, nRF52 SWD, nRF52 UF2, RP2040) | proven SOPs + hash logs |
| L3 | real `.msgs` + full images from each device | parser test corpus |
| L4 | **version sweep**: flash 2.5.x, 2.6.x, 2.7.26, 2.8.1; record file layout per version; pin when `MessageStore` persistence first shipped | version → format table |
| L5 | anti-forensics matrix (below) | survival table for the paper |
| L6 | channel-hash dictionary (presets × default-key indices) | offline channel identification |
| L7 | forged channel message on own devices; compare stored artifacts | evidence for attribution levels |

## Devices and roles (fictional personas)

| Device | Chip | Screen → message store | Paired with | Persona |
|---|---|---|---|---|
| D1 Heltec V3/V4 | ESP32-S3 | yes (20) | Android A | "Alice" |
| D2 LilyGO T-Deck | ESP32-S3 | yes (20), standalone keyboard | none | "Bob" |
| D3 RAK4631 | nRF52840 | no | iPhone | "Carol" |
| D4 T-Echo or T1000-E | nRF52840 | yes (10, InkHUD) / no | Android A (2nd radio) | "Dan" |
| D5–D7 (cheap ESP32 boards) | ESP32 | – | Android A | only to trigger H11 (6 radios) |

## Scenario script (per run, 3 runs per firmware version)

**Day 1: activity (all logged by a ground-truth script with UTC timestamps)**
1. Fresh flash → region set → a private channel `LabNet` with a random PSK; a second channel `Ops`.
2. Owners named; positions on: fixed positions at 4 surveyed points, GPS on D3/D4 while walking a route.
3. 30 broadcast messages, 15 DMs (PKI), 5 reactions, 3 waypoints, 2 traceroutes, a range test D1↔D3 (CSV on D1).
4. Admin change on D3 from D1 (admin key).
5. Backup preferences on D1 and D2 (creates `/backups`).
6. RF capture running throughout (L1).

**Acquire everything** (logical + physical + phones) → baseline.

**Day 2: anti-forensic actions** (one per device clone, or re-run the scenario before each):

| Action | Where |
|---|---|
| A1 delete single conversation / clear messages | radio menu, Android app, iOS app |
| A2 reset node DB | CLI / app |
| A3 factory reset **config** | admin |
| A4 factory reset **device** | admin |
| A5 reflash same firmware (no erase) | web flasher |
| A6 full erase + flash | web flasher "full erase" |
| A7 app: clear data / uninstall | phones |
| A8 battery pull with < 2 h of unsaved messages | radios (H4) |

**Acquire again** after each action.

## Metrics

- **Survival rate** per artifact class (messages, nodes, positions, keys, channels, config, backups) × action × platform. This is the paper's main table.
- **Carving precision/recall** against ground truth (H3, H12).
- **Timestamp error**: recovered vs ground truth; handle boot-relative records using the uptime anchor.
- **Attribution**: share of recovered messages at each confidence level (A–D) and the forgery demonstration (L7).
- **Repeatability**: 3 runs; report variance.
- **Tool validation**: run meshfx on all images; compare against manual decoding with `protoc --decode` on a sample (a NIST CFTT-style known-answer approach).

## Schedule (about 14 weeks part-time)

| Weeks | Work |
|---|---|
| 1–2 | buy hardware, build the lab, ground-truth logger, private channels |
| 3–4 | L2 acquisition SOPs (H1, H2, H4) |
| 5–7 | parser: lfs v1/v2, protobuf decode per version, warm ring, app databases, timeline |
| 8–10 | L4 version sweep + L5 anti-forensics (H3, H5–H12) |
| 11 | L1, L6, L7 RF/MQTT/attribution |
| 12–14 | paper, dataset, tool release, user guide |
