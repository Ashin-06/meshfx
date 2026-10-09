# Sources

All accessed 9 Oct 2026.

## Primary source code (read directly)
| Repo | Commit | Files used |
|---|---|---|
| [meshtastic/firmware](https://github.com/meshtastic/firmware) | `40a0178` (2026-10-09) | `src/mesh/NodeDB.{h,cpp}`, `src/MessageStore.{h,cpp}`, `src/mesh/WarmNodeStore.{h,cpp}`, `src/mesh/TransmitHistory.*`, `src/mesh/CryptoEngine.cpp`, `src/mesh/Channels.{h,cpp}`, `src/mesh/RadioInterface.cpp`, `src/security/EncryptedStorage.{h,cpp}`, `src/SafeFile.h`, `src/FSCommon.*`, `src/platform/nrf52/nrf52840_s140_v7.ld`, `src/graphics/niche/InkHUD/InkHUD.cpp`, `partition-table*.csv`, `default_*MB.csv`, `bin/meshtasticd-start.sh`, `test/test_crypto/test_main.cpp` |
| [meshtastic/protobufs](https://github.com/meshtastic/protobufs) | master | `deviceonly.proto`, `config.proto`, `module_config.proto` |
| [meshtastic/Meshtastic-Android](https://github.com/meshtastic/Meshtastic-Android) | `6630488` (2026-10-09) | `core/database/.../DatabaseConstants.kt`, `MeshtasticDatabase.kt`, `Converters.kt`, `schemas/.../64.json`, `core/datastore` |
| [meshtastic/Meshtastic-Apple](https://github.com/meshtastic/Meshtastic-Apple) | `8425daa` (2026-10-05) | `Meshtastic/Persistence/Persistence.swift`, `Meshtastic/Model/MessageEntity.swift` |
| [meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore) | main | `examples/companion_radio/DataStore.cpp` |
| [adafruit/Adafruit_nRF52_Arduino](https://github.com/adafruit/Adafruit_nRF52_Arduino) | master | `libraries/InternalFileSytem/src/InternalFileSystem.cpp` |

## Documentation
- Meshtastic encryption: https://meshtastic.org/docs/overview/encryption/
- Meshtastic mesh algorithm / packet header: https://meshtastic.org/docs/overview/mesh-algo/
- Meshtastic MQTT: https://meshtastic.org/docs/software/integrations/mqtt/
- Android persistence: https://meshtastic.org/docs/software/android/developer/persistence/
- Apple SwiftData: https://meshtastic.org/docs/software/apple/developer/swiftdata/
- Meshtastic 2.6 preview (file split): https://meshtastic.org/blog/meshtastic-2-6-preview/
- Firmware releases: https://github.com/meshtastic/firmware/releases
- Android package: https://meshtastic.org/docs/software/android/installation

## Prior art
- RealWorldCTF 2024 "Long Range 2": https://blog.nanax.fr/post/2024-01-28-hardware-longrange2/ · https://sec.gd/blog/en/posts/long-distance-2/
- DEF CON 34 Ham Radio Village, "Meshtastic Beasts and Where to Find Them": https://cfp.hamvillage.org/dc34/talk/CTMAYM/
- Meshtastic at DEF CON 2025: https://meshtastic.org/blog/that-one-time-at-defcon/
- CVE-2025-52464: https://www.tenable.com/cve/CVE-2025-52464
- CVE-2025-21608: https://nvd.nist.gov/vuln/detail/CVE-2025-21608
- GHSA-h4rg-g6f3-ghh7: https://github.com/meshtastic/Meshtastic-Android/security/advisories/GHSA-h4rg-g6f3-ghh7
- Meshtastic_SDR: https://gitlab.com/crankylinuxuser/meshtastic_sdr
- gr-lora_sdr: https://github.com/tapparelj/gr-lora_sdr
- Jeff Geerling, Decoding Meshtastic with GNU Radio: https://www.jeffgeerling.com/blog/2025/decoding-meshtastic-gnuradio-on-raspberry-pi/
- RTL-SDR.com, Decoding Meshtastic in real time: https://www.rtl-sdr.com/decoding-meshtastic-in-realtime-with-an-rtl-sdr-and-gnu-radio/
- Resilience analysis of Meshtastic profiles (non-forensic): https://arxiv.org/pdf/2605.17063

## Methodology references
- Ray-Ban Meta glasses forensics, DFRWS USA 2026: https://dfrws.org/presentation/seeing-the-evidence-a-forensic-framework-for-analyzing-ray-ban-meta-ai-smart-glasses/
- Nyon Unchained (Bosch eBike forensics): https://arxiv.org/pdf/2404.12864
- Zenbo humanoid robot forensics: https://zuscholars.zu.ac.ae/works/6716
- Systematic firmware extraction for industrial embedded devices: https://www.sciencedirect.com/science/article/pii/S2665910726000447
- UF2 bootloader (CURRENT.UF2): https://github.com/Microsoft/uf2-samdx1
- littlefs tooling: https://github.com/earlephilhower/mklittlefs · littlefs-python (PyPI)
