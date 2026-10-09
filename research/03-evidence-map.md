# 03 · Evidence Map

There are four evidence layers. Each row says **what** it is, **where** it is and **what question it answers**.
Legend: ✅ confirmed in source · 🧪 hypothesis to test in the lab (IDs refer to [08](08-experiment-plan.md))

## Layer A: the radio

Full file table and binary formats are in [02 §3](02-meshtastic-internals.md#3-files-on-the-radio-current-source).

| Question | Artifact | Status |
|---|---|---|
| Whose device is this? | `device.proto` owner long/short name; `config.proto` public/private key; NodeNum | ✅ |
| Which networks did it join? | `channels.proto` names + PSKs; `event-*.proto`; LoRa region/preset/frequency | ✅ |
| Which other radios were nearby, and when? | `nodes.proto` nodes[].last_heard, hops_away, snr_q4, via MQTT bitfield; warm ring / `warm.dat` | ✅ |
| Where were other nodes? | `nodes.proto` positions[] (precision bits matter) | ✅ |
| Where was this device? | own position in DB; `rangetest.csv`; fixed_position in config | ✅ |
| What was said? | `Messages_default.msgs` (screen devices); `device.proto` `rx_text_message` (last received text, all devices) | ✅ |
| Was it deleted? | free LittleFS blocks (carving); old warm-ring pages | 🧪 H3, H5 |
| Was it factory-reset, and what survived? | `/backups/backup.proto`, `/NicheGraphics/*`, preserved private key, LittleFS block-revision counters | 🧪 H6, H7 |
| When did it last transmit? | `transmit_history.dat` per portnum | ✅ format · 🧪 accuracy |
| Which phone or Wi-Fi did it use? | `config.proto` Wi-Fi SSID/PSK; BLE bonds in ESP32 `nvs` | ✅ / 🧪 H8 |
| Which external services? | `module.proto` MQTT server/username/password, map-report flag | ✅ |
| Can I trust "from"? | `xeddsaSigned` flag in message records and the warm ring; PKI vs channel | ✅ see [05](05-rf-mqtt-attribution.md) |
| What was in RAM at a crash? | ESP32 `coredump` partition | 🧪 H9 |

## Layer B: companion phone

### Android: `com.geeksville.mesh` (source `Meshtastic-Android@6630488`, Room schema **v64**)

Path: `/data/data/com.geeksville.mesh/` (needs root or a full-file-system extraction)

| File | Content |
|---|---|
| `databases/meshtastic_database_<h>` (+`-wal`, `-shm`) | **one database per radio**; `<h>` = first 10 hex of SHA-1 of the normalised radio address (`buildDbName()`) |
| `databases/meshtastic_database_default` | data with no device selected |
| `databases/meshtastic_database` | legacy single database (cleaned once; the `legacy_db_cleaned` key records this) |
| `files/datastore/local_config.pb`, `module_config.pb`, `local_stats.pb` | protobuf DataStore copies of the **radio's config** (keys, Wi-Fi, MQTT) and stats |
| preferences (DataStore / shared prefs; exact file 🧪) | `device_db_for:<id>`, `node_db_for:<num>`, `addr_db_for:<addr>`, `db_last_used:*`, `retired_db_names`, `node_db_cache_limit` (**maps radios to databases, records retired databases**) |

**LRU deletion:** `DEFAULT_CACHE_LIMIT = 5` (1–10). When a 6th radio is used, the least-recently-used radio's database is deleted. Recovery comes from the f2fs/ext4 free space or a backup (🧪 H11).

Tables in schema v64 (✅ from `schemas/.../64.json`):

| Table | Key columns | Evidence |
|---|---|---|
| `packet` | `uuid, myNodeNum, port_num, contact_key, received_time, read, data` (JSON `DataPacket`), `packet_id, routing_error, snr, rssi, hopsAway, filtered, message_text, translated_text` | **all messages, waypoints and telemetry** with receive time and radio metrics |
| `packet_fts` | FTS5 over `message_text` | 🧪 H12: deleted text left in FTS segments, WAL and freelist |
| `nodes` | `num, user, long_name, short_name, position, latitude, longitude, snr, rssi, last_heard, device_metrics, via_mqtt, hops_away, is_favorite, is_ignored, is_muted, public_key, notes, manually_verified, key_match, new_public_key, has_xeddsa_signed, last_transport, …` | node history and **key-change evidence** (`new_public_key`, `key_match`), **user's own notes** |
| `my_node` | `myNodeNum, model, firmwareVersion, deviceId, pioEnv, …` | which radio, which firmware |
| `log` | `uuid, type, received_date, message, from_num, port_num, from_radio` | **raw packet log** (every FromRadio), retention 🧪 |
| `contact_settings` | `contact_key, muteUntil, last_read_message_*, draft, pinned, display_name` | **unsent drafts**, renamed contacts |
| `reactions` | `reply_id, user_id, emoji, timestamp, packet_id, relays, relay_node, to, channel, xeddsa_signed, ack_proof_status` | emoji replies plus delivery proof |
| `traceroute_node_position` | `log_uuid, request_id, node_num, position` | the route the user asked about |
| `discovery_session` / `discovery_preset_result` / `discovered_node` | `timestamp, user_latitude, user_longitude, device_address, home_lora_config, ai_summary`; node `latitude, longitude, distance_from_user, hop_count` | **the phone's own GPS position** during mesh scans |
| `quick_chat`, `metadata`, `channel_set`, `merge_marker` | canned messages, device metadata, channel sets, **database merge history** (`source_db_name, merged_at`) | |

Also on Android:
- `/data/misc/bluedroid/bt_config.conf`: paired radio BLE MAC address and name
- notification history and usage stats (generic Android artifacts)

### iOS: Meshtastic app (source `Meshtastic-Apple@8425daa`)

- **SwiftData**: `<storeName>.store` + `-wal` + `-shm` in the app's **Application Support** container. Under the hood it is Core Data SQLite, so expect `Z`-prefixed tables (`ZMESSAGEENTITY`, `ZNODEINFOENTITY`, …).
- **Legacy `Meshtastic.sqlite`** (Core Data build) is **renamed, not deleted**, during migration. Old data may survive (🧪 H10).
- Entities: `MessageEntity`, `NodeInfoEntity`, `UserEntity`, `PositionEntity`, `TelemetryEntity`, `WaypointEntity`, `ChannelEntity`, `MyInfoEntity`, `DeviceMetadataEntity`, `Discovery*Entity`, …
- `MessageEntity` fields include `messageId, messageTimestamp, messagePayload, channel, portNum, pkiEncrypted, publicKey, xeddsaSigned, receivedACK, realACK, ackError, ackTimestamp, ackSNR, rssi, snr, relays, relayNode, replyID, isEmoji, read, admin, adminDescription, messagePayloadTranslated`, with relationships `fromUser` and `toUser`.
- Acquisition: an **encrypted Finder/iTunes backup** probably includes Application Support (🧪 H10), or a full file system extraction.
- iOS system artifacts: Bluetooth LE pairing database; KnowledgeC/Biome app-usage records.

### Other clients
- **Web client** (`client.meshtastic.org`, or served from the radio's `/static`): browser storage 🧪
- **Python CLI** (`meshtastic`): no history by default; shell history may contain `--set` commands with keys
- **PC**: Windows `setupapi.dev.log` / Linux syslog show CP210x/CH340/nRF USB-serial devices, which proves the radio was plugged in

## Layer C: network (MQTT and maps)

| Source | What it shows | Access |
|---|---|---|
| radio `module.proto` | broker address, username, password, `root` topic, encryption on/off, map reporting | device |
| broker topics | `msh/<REGION>/2/e/<CHANNEL>/!<gateway-id>`: packets uploaded by gateway nodes (encrypted unless the broker is configured otherwise) | broker logs (legal process) or a live subscription |
| public map reports | node info and position at reduced precision (public server limits to 10–16 bits) | public map aggregators; time-limited |
| `via_mqtt` flag (header bit 4, `nodes.via_mqtt`) | the packet travelled over the internet, not RF | **important: "heard" ≠ "nearby"** |

## Layer D: radio frequency

Passive LoRa capture (RTL-SDR + gr-lora_sdr / Meshtastic_SDR) gives:
- cleartext headers: from, to, packet id, hop_start, hop_limit, channel hash, next hop, relay node
- payloads decrypted once keys are recovered from Layer A or B (no forward secrecy)
- RSSI, SNR and time of arrival; with several receivers, **direction or location of a transmitter**

See [05](05-rf-mqtt-attribution.md).

## Cross-layer timeline (what the tool will build)

```
radio.nodes.last_heard ─┐
radio.messages          ├─► join on (NodeNum, packet_id, time ± skew) ─► one timeline
phone.packet / log      │      with per-event source, confidence and attribution score
mqtt / rf captures     ─┘
```

**packet_id is the join key across layers.** It appears in the RF header, MQTT envelopes, `packet.packet_id` and `reactions.packet_id`. Radio message records do **not** store it, so they are joined on sender + text + time.
