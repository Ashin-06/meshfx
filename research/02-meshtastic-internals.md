# 02 · Meshtastic Internals (What an Examiner Must Know)

Everything here was read from source unless marked otherwise.
Firmware: `meshtastic/firmware master@40a0178` (9 Oct 2026). Docs: meshtastic.org (accessed 9 Oct 2026).

## 1. System overview

```
 [Phone app]──BLE / USB serial / Wi-Fi TCP / HTTP──[Radio node]~~~~LoRa~~~~[Other nodes]
  Android / iOS / Web / Python CLI                    │                         │
                                                      └──(optional) MQTT over Wi-Fi/phone──[MQTT broker, public map]
```

- **Radio node**: an MCU plus a LoRa transceiver (SX1262/SX1276/LR11xx). It holds the identity, config, channel keys, node DB and (on screen devices) recent messages.
- **Phone app**: the user interface. It holds the long-term message history and node history, and is the richest evidence source.
- **MQTT**: an optional bridge that uploads packets to a broker. Map reports send node info and position (precision limited on the public server).

## 2. Hardware and storage per platform

| Platform | Example boards | Filesystem | Where it lives | Notes |
|---|---|---|---|---|
| ESP32 / S3 / C3 / C6 / P4 | Heltec V3/V4, T-Beam, T-Deck, Station G2 | LittleFS **v2** (ESP32 Arduino core) | `spiffs` data partition: `0x300000`+1 MB (4 MB flash), `0x670000`+1.5 MB (8 MB), `0xC90000`+3.4 MB (16 MB) | Also `nvs` at `0x9000` (BLE bonds etc., to verify) and `coredump` at the end of 8/16 MB layouts (**a RAM snapshot after a crash**, to verify) |
| nRF52840 | RAK4631, T-Echo, T1000-E, Heltec T114 | LittleFS **v1** (Adafruit `InternalFS`) | `0xED000`, 28 KB (7 × 4 KB pages), **128-byte lfs blocks** | Warm-node ring in raw flash `0xEA000–0xED000` (outside the FS). Optional lockdown encryption. |
| nRF54L15 | new boards | LittleFS wrapper | to verify | very new in 2026 |
| RP2040 / RP2350 | RAK11310, Pico + LoRa hat | LittleFS (arduino-pico) | end of flash, `filesystem_size = 0.5m` | BOOTSEL USB mode can read flash with `picotool` |
| STM32WL | RAK3172, Wio-E5 | LittleFS v1 (in-tree port) | to verify | tiny, few artifacts expected |
| Linux native (`meshtasticd`) | Raspberry Pi + LoRa hat | host directory | `--fsdir` (Docker: `/var/lib/meshtasticd`; service: `${VFS_DIR}/meshtasticd-<instance>`) | config `/etc/meshtasticd/config.yaml`; ordinary disk forensics |

Why LittleFS matters:
- **copy-on-write** with metadata pairs: an old version of a file survives until its blocks are reused
- **v1 vs v2** have different on-disk formats; `littlefs-python` reads v2 only, so nRF52 needs its own v1 reader (not part of the current tool; see README known gaps)
- nRF52's 128-byte blocks mean a 239-byte message record **always spans blocks**, and v1 CTZ skip-list pointers are interleaved, so naive carving fails there

## 3. Files on the radio (current source)

| Path | Content (protobuf / struct) | Forensic value |
|---|---|---|
| `/prefs/device.proto` | `DeviceState`: `my_node`, `owner` (long/short name, public key), `rx_text_message` (**last text received**), `rx_waypoint`, `receive_queue` | owner identity, last message |
| `/prefs/nodes.proto` | `NodeDatabase`: `nodes[]` (num, last_heard, names, hw_model, role, public_key, hops_away, snr_q4, next_hop, channel), `positions[]` (lat/lon/alt/time/precision), `telemetry[]`, `environment[]`, `status[]` | **who was heard, when, how far (hops/SNR), where** |
| `/prefs/db.proto` | legacy (≤2.5): `DeviceState` *including* the node DB | read only during migration; on old devices it is the main file |
| `/prefs/config.proto` | `LocalConfig`: LoRa region/preset/frequency, `security.private_key/public_key/admin_key[]`, `network.wifi_ssid/wifi_psk`, `bluetooth.fixed_pin`, position settings, device role | keys, **Wi-Fi password**, BLE PIN |
| `/prefs/channels.proto` | `ChannelFile`: up to 8 channels (name, **PSK**, role, uplink/downlink, position precision) | keys to decrypt RF/MQTT captures |
| `/prefs/module.proto` | `LocalModuleConfig`: **MQTT address/username/password**, map reporting, store-and-forward, range test, canned messages | external accounts and servers |
| `/prefs/uiconfig.proto` | `DeviceUIConfig` | UI settings, low value |
| `/prefs/event-config.proto`, `event-channels.proto` | event-edition firmware profiles | which event network the device joined |
| `/backups/backup.proto`, `event-backup.proto` | `BackupPreferences`: timestamp, config, module config, channels, owner | **not touched by factory reset** (see "What reset erases" below) |
| `/Messages_default.msgs` | message history (struct below) | **message content** |
| `/prefs/transmit_history.dat` | last broadcast time per portnum (magic + version + entries; flag for boot-relative time) | when the device last sent position/telemetry/nodeinfo |
| `/prefs/warm.dat` (non-nRF52) | warm node tier: 40-byte entries (num, last_heard + packed role/flags, public key) | long-tail nodes evicted from the main DB |
| `/prefs/hopScalingState.bin`, `gps_probe_cache.dat`, sensor `.dat`, game scores, `cannedConf.proto`, `ringtone.proto` | misc | GPS presence, usage habits |
| `/static/rangetest.csv` (ESP32) | Range Test log: sender, position, SNR, timestamps | **location trail** |
| `/NicheGraphics/*` | InkHUD (e-ink) settings; legacy `latest.msgs` and per-channel message files (migrated, then deleted) | deleted legacy files → carving |
| `/prefs/.dek`, `.unlock_token`, `.backoff`, `.tokmono` | lockdown builds only (§6) | shows encryption is in use; `.backoff` records failed passphrase attempts |

### Message record (`src/MessageStore.cpp`)

The file is a 1-byte `count` followed by `count` packed little-endian records of **239 bytes**:

```
off size field
  0   4  timestamp        epoch seconds, or uptime seconds if isBootRelative
  4   4  sender           NodeNum
  8   1  channelIndex
  9   4  dest             0xFFFFFFFF = broadcast
 13   1  isBootRelative   1 = timestamp is seconds since boot (no RTC/GPS time)
 14   1  ackStatus        0 NONE 1 ACKED 2 NACKED 3 TIMEOUT 4 RELAYED
 15   1  type             0 BROADCAST 1 DM
 16   1  xeddsaSigned     1 = signature verified (2.8.1+)
 17   2  textLength
 19 220  text             NUL-terminated, rest zero-filled
```

- Capacity: **10** on nRF52840 and original ESP32, **20** on ESP32-S3/C3/S2 and others. Only on builds with a screen (`HAS_SCREEN` or niche graphics).
- Written by: autosave every **2 h** (`MESSAGE_AUTOSAVE_INTERVAL_SEC`), shutdown (`Power.cpp`), deep sleep / reboot hooks and some menu actions.
- "Clear messages" rewrites the file as a single `0x00` byte through `SafeFile` (write temp → verify → rename). The old blocks are freed, not erased, so **carving can recover them** (hypothesis H3).
- `isBootRelative=1` timestamps must be anchored to a known boot time. The firmware upgrades them once the RTC is valid; the examiner must handle the rest.

### Warm node ring (nRF52840, `src/mesh/WarmNodeStore.*`)

- 3 × 4 KB pages at `0xEA000–0xED000`, each with a page header (magic `WRN3`/`WRN2`/`WRNG`, plus a sequence number)
- Then 40-byte entries, written append-only; tombstones have `last_heard = 0xFFFFFFFF`
- Compacted on page rotation
- `last_heard` low 7 bits hold role (4), protected category (2) and an XEdDSA-signed flag (1); the high 25 bits are epoch time with **128 s resolution**
- An append log means **older sightings can stay in un-compacted pages** (hypothesis H5)
- On other platforms the same data goes to `/prefs/warm.dat` (magic `WRM3`/`WRM2`/`WRM1`)

### What reset erases (`NodeDB::factoryReset`, `NodeDB.cpp:920`)

| Erased | Not erased |
|---|---|
| the whole `/prefs` directory (`rmDir`) | **`/backups/backup.proto`** (owner, all channel PSKs, Wi-Fi PSK, MQTT credentials) |
| `/static/rangetest.csv` | `/NicheGraphics/*` (InkHUD settings) |
| message store rewritten as "0 messages" (old blocks freed, not wiped) | free LittleFS blocks holding older file versions |
| waypoint store, warm store (cleared and re-saved), transmit history | the **private key**, when called with `eraseBleBonds=false` ("reset config"): `installDefaultConfig(!eraseBleBonds)` restores it, so the node identity carries over |

`resetNodes()` (reset node DB) keeps the local node and, optionally, favourites, then rewrites `nodes.proto`. A **full erase** during reflash (`InternalFS.format()` / web-flasher erase) is the only action expected to remove everything. Lab tests H3, H6 and H7 will confirm.

## 4. Radio layer

- LoRa with sync word `0x2B` and a 16-symbol preamble (sub-GHz)
- Default preset **LongFast**: 250 kHz bandwidth, SF11, CR 4/5
- Frequency slot = `djb2(channel name) % numSlots` for the region, unless `channel_num` or `override_frequency` is set (`RadioInterface.cpp`). Knowing the channel name therefore tells you where to listen.

## 5. Packet format

The 16-byte header is **always in cleartext**, even when the payload is encrypted:

```
0x00 u32 LE  to (destination NodeNum; 0xFFFFFFFF broadcast)
0x04 u32 LE  from (sender NodeNum)
0x08 u32 LE  packet id
0x0C u8      flags: bits0-2 hop_limit, bit3 want_ack, bit4 via_mqtt, bits5-7 hop_start
0x0D u8      channel hash  = xor(name bytes) ^ xor(key bytes) [^0xAE if AEAD]
0x0E u8      next hop (low byte of NodeNum)
0x0F u8      relay node (low byte of NodeNum)
0x10 ..      payload: encrypted protobuf `Data` (≤ 239 bytes)
```

- `hop_start − hop_limit` = hops already travelled, so passive capture yields **distance in hops without any key**
- Node IDs are written `!xxxxxxxx` (hex NodeNum). Before 2.8 the NodeNum came from the MAC address; **from 2.8 it is CRC-32 of the public key**, so the node is renumbered after an upgrade or re-key (the Android app tracks this; see `DatabaseConstants.kt`)

## 6. Cryptography

| Traffic | Algorithm | Key | Nonce / IV | Integrity |
|---|---|---|---|---|
| Channel (default) | AES-128/256-**CTR** | channel PSK. 1-byte PSK `n` = default key `d4f1bb3a20290759f0bcffabcf4e6901` with last byte `+n−1`; `0` = no encryption; short keys zero-padded | 16-byte counter block = `packet_id (u64 LE) ‖ from (u32 LE) ‖ 0x00000000` | **none**: malleable, forgeable by any key holder |
| Channel, "Use AEAD" (2.8.1+) | AES-CCM, 12-byte tag | PSK | to document (`encryptPacketCCM`, includes `to`) | yes |
| Direct message (PKI, 2.5+) | X25519 → SHA-256 → **AES-256-CCM**, 8-byte tag + 4-byte extraNonce appended | sender private + recipient public | 13 bytes = `id (low u32) ‖ extraNonce ‖ from ‖ 0x00` | yes (pairwise) |
| Broadcast signing (2.8.1+) | **XEdDSA** over the whole `Data` envelope plus from/id/to, +66 bytes | node's Curve25519 key | – | sender authenticity; 2.8.0 signatures were revoked and are incompatible |
| Admin | PKI plus a session passkey valid 5 min; up to 3 admin keys | – | – | – |

- There is no forward secrecy (per the docs). **Anyone who later gets a channel PSK or a private key can decrypt old captures.** This matters for evidence: captures made before seizure become readable after it.
- The `meshfx` tool does not decrypt captured traffic: it parses data recovered from a device (see README, "Tool"). The early prototype that did is kept only in the git history.
- **Lockdown builds** (`MESHTASTIC_ENABLE_LOCKDOWN`, nRF52):
  - key hierarchy: FICR device IDs + passphrase → KEK → DEK (`/prefs/.dek`)
  - each proto file is stored as `MENC` + 13-byte nonce + length + AES-128-CTR ciphertext + HMAC-SHA256
  - an unlock token allows N boots / M hours
  - APPROTECT is burned once provisioned (on chip revisions that are not glitch-vulnerable)
  - the code comment says this layer has "never shipped", so it is expected to be rare. Detect `MENC` and report.

## 7. Firmware versions that change the evidence

| Version | Change | Impact |
|---|---|---|
| ≤ 2.5.x | `db.proto` = DeviceState + node DB | parse the old layout |
| 2.5.0 | PKI DMs introduced | DMs are no longer decryptable with a channel key |
| 2.5.0–2.6.10 | CVE-2025-52464 duplicate keys | key ≠ unique identity |
| 2.6 | device state and node DB split into separate files ([2.6 preview](https://meshtastic.org/blog/meshtastic-2-6-preview/)) | new file names |
| 2.6.11 / 2.6.12 | key generation delayed until region is set; known-bad keys wiped | |
| 2.7.26 (24 Jun 2026) | last stable before 2.8 | |
| 2.8.0 (30 Aug / 1 Sep 2026) | **revoked**: storage-format break, NodeDB redesign, warm store, NodeNum from public key, signing (flawed) | migration artifacts |
| 2.8.1 alpha (1 Oct 2026) | fixed signing, AEAD channels, signed ACK proofs, **write-behind LFS cache on nRF52/STM32WL**, unified message store | more data held in RAM before flush |

The release that first shipped `MessageStore` persistence is not pinned yet. Lab task: flash each release from 2.6 onward and check.

## 8. Phone and other clients (summary; details in [03](03-evidence-map.md))

- **Android** (`com.geeksville.mesh`): Room KMP SQLite, schema v64, **one database per radio**, LRU of 5
- **iOS**: SwiftData `.store` (+ `-wal`/`-shm`) in Application Support; a legacy Core Data `Meshtastic.sqlite` is renamed during migration
- **Web client / Python CLI**: browser storage / no history by default
