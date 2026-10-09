# 04 · Acquisition (Draft SOPs, to be validated in the lab)

Every step marked 🧪 must be proven on lab devices (hash before and after) before it is recommended for casework.

## 1. Order of volatility (specific to Meshtastic)

| Most volatile → least | Why it matters |
|---|---|
| **RAM message history**: up to 2 h of messages not yet autosaved (`MESSAGE_AUTOSAVE_INTERVAL_SEC = 7200`) | lost on battery pull; saved on clean shutdown or sleep |
| **2.8.1 write-behind LFS cache** (nRF52 / STM32WL) | recent file writes may still be in RAM |
| RAM node DB / telemetry newer than the last `saveToDisk` | same |
| **Radio keeps receiving** while powered: new packets update `last_heard`, push old messages out of a 10/20-slot ring and can overwrite free flash | evidence changes every minute in a busy mesh |
| Flash files | stable until written |
| Free LittleFS blocks (deleted data) | overwritten when the filesystem allocates them |
| Phone databases | stable, but the app syncs with the radio when they reconnect |

## 2. First response at the scene (draft)

1. **Photograph the screen** (T-Deck, Heltec, T-Echo show messages and node lists). Note the wall-clock time.
2. **Isolate from RF**: Faraday bag *with* a USB pass-through if possible. This stops new packets (ring eviction, `last_heard` churn) while keeping the device powered.
3. **Do not connect the companion app.** The app pushes the phone's time, position and config to the radio and pulls its queued packets. That changes both sides.
4. Record the device model, label, battery state and any visible node ID (`!xxxxxxxx`).
5. Decide: logical-then-physical (preferred, see §3) or immediate power-off. Document the reason.

## 3. Logical acquisition over USB serial (radio running)

Use the Python CLI (`pip install meshtastic`) read-only commands:

```bash
meshtastic --port COM5 --info
```

```bash
meshtastic --port COM5 --export-config > config.yaml
```

`--info` returns owner, MyNodeInfo, metadata, **node DB from RAM (newer than flash)**, channels with keys and config. `--export-config` writes the config as YAML.

- Before casework use, prove 🧪 **H2: CLI read-only commands change no flash files.** Image, run the CLI, image again, diff.
- Capture the device's `uptime_seconds` from the info output. It is needed to convert `isBootRelative` timestamps.
- Then trigger a **clean shutdown** from the device menu (or the CLI `--shutdown`). This flushes RAM messages and the node DB to flash. Doing so is a *documented, intentional change*, justified by preserving up to 2 h of messages. Test 🧪 H4 to confirm the flush happens.

## 4. Physical acquisition per chip

### ESP32 family: ROM bootloader, no firmware runs ✅ non-invasive

1. Enter download mode: hold BOOT, tap RESET (or let esptool auto-reset via DTR/RTS).
2. Read the whole flash:
   ```bash
   esptool.py --port COM5 --baud 921600 read_flash 0 ALL flash.bin
   ```
3. Read twice and compare SHA-256 to rule out read instability.
4. Parse the partition table at `0x8000`. Carve `spiffs` (LittleFS v2, 4096-byte blocks), `nvs` and `coredump`.
5. Mount read-only with `littlefs-python` (`block_size=4096`, `block_count=size/4096`) or `mklittlefs -u`.

Caveat: if Secure Download Mode or flash encryption is enabled (not in stock Meshtastic) reads are blocked or encrypted. Report it.

### nRF52840: SWD debug probe

1. Probe options: Raspberry Pi Pico with `debugprobe`, J-Link, or ST-Link v2 clone with OpenOCD. Pads: SWDIO, SWCLK, GND, 3V3 (RAK4631 exposes them).
2. Read all flash and the UICR:
   ```bash
   pyocd cmd -t nrf52840 -c "savemem 0x0 0x100000 flash.bin" -c "savemem 0x10001000 0x1000 uicr.bin"
   ```
3. Memory map (S140 v7 + Meshtastic linker script):
   ```
   0x00000–0x26FFF  SoftDevice
   0x27000–0xE9FFF  application
   0xEA000–0xECFFF  warm-node ring (3 × 4 KB pages)   ← outside the filesystem
   0xED000–0xF3FFF  LittleFS v1, 28 KB, 128-byte blocks
   0xF4000–0xFFFFF  UF2 bootloader + settings
   ```
4. **APPROTECT**: stock builds leave debug access open (🧪 confirm per chip revision). Lockdown builds burn APPROTECT. Older chip revisions are glitch-vulnerable (LimitedResults, 2020); that is lab research only and needs legal sign-off.
5. Alternative with no probe: double-tap RESET → UF2 USB drive → copy `CURRENT.UF2`. 🧪 **H1: does CURRENT.UF2 cover `0xEA000–0xF4000`?** If yes, this is the easiest nRF52 method.
6. Halting the core with SWD stops the firmware. Halt **before** reading to freeze the state, and you can also dump **RAM** (`0x20000000`, 256 KB), which holds the unsaved messages. 🧪 This would be the best capture possible: RAM plus flash without a reboot.

### RP2040 / RP2350: BOOTSEL ROM, no firmware runs ✅

Hold BOOTSEL while plugging in, then:
```bash
picotool save -a flash.bin
```

### STM32WL
SWD with ST-Link. If readout protection (RDP) is set, reading is blocked. Expect few artifacts.

### Linux `meshtasticd`
Image the host disk normally. Evidence is in `--fsdir` (Docker default `/var/lib/meshtasticd`) and `/etc/meshtasticd/`.

### Damaged devices
ESP32 modules have an **external SPI flash chip** under the shield: chip-off plus an SPI reader (CH341A / FlashcatUSB). nRF52 flash is internal: SWD or nothing.

## 5. Phones

| OS | Method | Gets |
|---|---|---|
| Android (lab) | rooted test phone: `adb shell su -c 'tar -C /data/data -cf - com.geeksville.mesh' > app.tar` | everything in `/data/data/com.geeksville.mesh` |
| Android (casework) | commercial full-file-system extraction | same, plus `bt_config.conf` |
| iOS | encrypted backup: `idevicebackup2 backup --full .` (libimobiledevice), or full-file-system extraction | 🧪 H10: Application Support store in the backup |

Copy SQLite databases **with** their `-wal` and `-shm` files and never open the originals in a writing tool. The WAL holds recent and deleted rows.

## 6. Integrity and documentation (every acquisition)

- SHA-256 of every image, read twice
- Tool names and versions (esptool, pyOCD, picotool, meshfx); host OS; probe firmware
- Wall-clock time and device uptime at acquisition (for boot-relative timestamps)
- Firmware version (from `--info` metadata, or the app header string in the image)
- Chain of custody form
- Any deliberate change (clean shutdown, Faraday transfer) with the reason

## 7. What the parser does after acquisition

```
flash.bin ──► detect platform (partition table / vector table / memory map)
          ──► extract FS (lfs v2 ESP32 | lfs v1 nRF52 | RP2040)
          ──► decode /prefs/*.proto with the protobufs pinned to the detected firmware version
          ──► parse .msgs, transmit_history, warm.dat / warm ring
          ──► carve free blocks (msg records, protobuf fragments, warm entries)
          ──► detect MENC (encrypted storage) and report
          ──► timeline + report (JSON / CSV / HTML) with hashes
```
