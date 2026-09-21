# PowerView Gen 3 BLE protocol reference

Source of truth for anything ambiguous below: the openHAB binding
`org.openhab.binding.bluetooth.hdpowerview` (author: Andrew Fiddian-Green,
EPL-2.0), in `bundles/org.openhab.binding.bluetooth.hdpowerview/` at
https://github.com/openhab/openhab-addons. Reimplementing the protocol from
reading that binding is fine; its code is not copied here (different
license).

This file is the implementation-facing summary that `:protocol`'s KDoc
comments point back to. It does not repeat everything in the original
implementation spec — see that for the app architecture, onboarding UX, build
order, and open unknowns.

## 1. Identification

BLE manufacturer (company) ID for Hunter Douglas: **`0x0819`**. Any
advertiser with that company ID is a PowerView Gen 3 device.

Standard GATT services are also present:
- Device Information (`0x180A`) — vendor/model/hw/fw/serial.
- Battery (`0x180F`, characteristic `0x2A19`) — needs a GATT connection but no
  encryption key.

  **Corrected 2026-09-17 against real hardware.** This section previously said
  the value was a coarse 10/50/100 bucket rather than a real percentage, which
  is what the openHAB binding's behaviour suggested. A Duette TDBU returned
  **65**, which is not one of those buckets. `0x2A19` is defined by the
  Bluetooth SIG as a uint8 percentage, 0..100, and the evidence so far is
  consistent with these shades simply honouring that. Treat it as a percentage.
  The old claim may still describe some units or older firmware — if you ever
  see a device that only ever reports 10, 50 or 100, that is worth recording
  here rather than assuming this note is wrong.

## 2. Reading state — advertisements, unencrypted, no connection

Shade position is broadcast continuously and unencrypted in the
manufacturer-specific advertisement. **No connection, no pairing, no key.**

Android's `ScanRecord.getManufacturerSpecificData(0x0819)` returns the
payload **without** the 2-byte company ID. Offsets below are for that
stripped payload (`AdvertisementParser.parseAndroidPayload`); add 2 to every
offset if you have a raw payload that still carries the company ID
(`AdvertisementParser.parseFullPayload` handles that case).

| Field | Offset (stripped) | Type | Decode |
|---|---|---|---|
| homeId | 0 | uint16 LE | identifies the "home"; shares one write keystream |
| typeId | 2 | uint8 | shade type → capabilities, see §5 |
| primary | 3 | uint16 LE | `percent = clamp(raw / 40.0, 0, 100)` |
| secondary | 5 | uint16 LE | `percent = clamp(raw / 40.0, 0, 100)` |
| tilt | 7 | uint8 | `percent = clamp(raw, 0, 100)` (already a percent) |
| velocity | 8 | uint8 | semantics unconfirmed — see §8, and note it is probably not a velocity |

Fields are unaligned — read bytes manually (`AdvertisementParser` does this
with explicit offsets, not a struct view). `secondary`/`tilt`/`velocity` are
optional trailing fields; a short payload just omits them.

**Confirmed against real hardware 2026-09-17.** A Duette TDBU broadcast
`3C F8 08 00 00 09 00 00 C0` (9 bytes, company ID already stripped), which
decodes as homeId 63548, typeId 8, primary 0.0%, secondary 0.225%, tilt 0,
velocity 192 — and 9 bytes is exactly what the table above consumes, with no
byte left over and none missing. A layout shifted by one would not fit. This
payload is pinned as a regression test in `AdvertisementParserTest`.

Keep one long-lived scan running rather than stopping/starting — matching
advertisements arrive continuously, and Android throttles apps that
start/stop scans repeatedly.

## 3. Writing position — GATT, encrypted

- Service: `0000FDC1-0000-1000-8000-00805F9B34FB`
- Command characteristic: `CAFE1001-C0FF-EE01-8000-A110CA7AB1E0`
- A second characteristic, `CAFE1002-C0FF-EE01-8000-A110CA7AB1E0`, exists
  with unconfirmed purpose — enumerate it during hardware bring-up (§8).

### Frame layout (13 bytes, 0-indexed)

This layout was derived empirically by XOR-decoding the five sniffed
ciphertext vectors in `FrameCipherTest` against each other using the shared
AES-CTR keystream, and cross-checked by re-encrypting with the real AES key
and confirming an exact byte match against all five ciphertexts (see
`FrameCipherTest.kt`). It disagrees slightly with an inline hex-template
annotation that appeared in an earlier draft of this spec, which grouped the
primary field one byte later than it actually sits — the layout below is
the one that reproduces the real ciphertext, so it's the one implemented in
`CommandFrameBuilder`.

```
0     : 0xF7        constant
1     : 0x01        constant
2     : sequence    uint8, increments per command sent
3     : 0x09        constant
4..5  : primary     uint16 LE, round(percent * 100); unset sentinel = [0x00, 0x80]
6..7  : secondary   uint16 LE, round(percent * 100); unset sentinel = [0x00, 0x80]
8..9  : reserved    always [0x00, 0x80] — no known field uses this
10    : tilt        uint8 percent (0..100) when active
11    : tilt marker 0x00 when tilt is set, 0x80 when unset
12    : 0x00        constant
```

Set only the field(s) you're commanding; leave the rest at the unset
sentinel. `CommandFrameBuilder.build(sequence, primaryPercent, secondaryPercent, tiltPercent)`
does this.

Note the asymmetry: **writes scale percent × 100** (0..10000), **reads scale
raw ÷ 40** (0..4000 covers 0..100%). Tilt is a plain 0..100 percent in both
directions. This is not a typo — it's how the device works.

## 4. Encryption — AES-128-CTR with a fixed IV

- Algorithm: AES/CTR/NoPadding
- Key: 16 bytes, per-`homeId`
- IV: **16 zero bytes, constant, never varied**

Fixed key + fixed IV under CTR means a fixed keystream, so encryption is
just `ciphertext = plaintext XOR keystream[0..12]`. Consequences, both
implemented in `:protocol`:

1. **The AES key is not needed once you have the keystream.** Given one
   sniffed `(ciphertext, plaintext)` pair, `keystream = ciphertext XOR
   plaintext` (`KeystreamDeriver.derive`). Store the keystream per `homeId`
   and XOR from then on (`FrameCipher.xorWithKeystream`) — this is the fast
   path for every real command.
2. `FrameCipher.deriveKeystreamFromKey` exists only for the "import a known
   AES key" onboarding path and for testing against key-based vectors — it's
   never on the hot path.

**If a shade isn't enrolled in the PowerView app at all, no encryption is
used** — send the frame in the clear. Useful for a factory-reset shade or a
dedicated test unit.

### Test vectors

Key `02c2efcbd4064d59409c980e627e2fc7` (from the openHAB binding's own unit
tests). `FrameCipherTest` verifies `CommandFrameBuilder` + `FrameCipher`
reproduce all five exactly:

| Command | Expected ciphertext (hex) |
|---|---|
| blank frame | `1F70847E5C07AD03100E0FB3DA` |
| sequence = 0x01 | `1F70857E5C07AD03100E0FB3DA` |
| primary = 100% | `1F70847E4CA0AD03100E0FB3DA` |
| tilt = 40% | `1F70847E5C07AD03100E2733DA` |
| seq 0xA6, primary 30%, secondary 10% | `1F70227EE48C4580100E0FB3DA` |

## 5. Capabilities (which controls to show)

`typeId` maps to a capability number controlling which of primary rail,
secondary rail, and/or tilt to show. Implemented in `Capabilities.kt`,
ported from the openHAB binding's `ShadeCapabilitiesDatabase`. Unknown
`typeId` falls back to primary-only with `isKnownType = false` so the caller
can log it rather than silently mis-rendering.

Capabilities: 0 bottom-up · 1 bottom-up + tilt 90° · 2 bottom-up + tilt 180°
· 3 vertical · 4 vertical + tilt 180° · 5 tilt only · 6 top-down (primary
inverted) · 7 top-down/bottom-up (secondary) · 8 dual overlapped · 9 dual
overlapped + tilt 90° · 10 dual overlapped + tilt 180°.

Known type IDs are listed in `Capabilities.TYPE_TO_CAPABILITY`.

## 6. Realistic expectations

- Control is local BLE only. No remote access without something always-on
  in the house (Pi/ESPHome proxy/HD Gateway) if remote control or
  away-from-home automations are wanted later.
- Range is plain BLE range.
- Firmware updates from Hunter Douglas can change any of this without
  notice.
- Position reads carry zero reverse-engineering risk; only writes need the
  keystream.

## 7. Onboarding a keystream (no key on hand)

Three paths (spec §2.4; UI not yet built — see build order):

1. **Unenrolled shade** — no key needed, send frames in the clear.
2. **Import a known key** — 32-char hex AES key (same format as the
   openHAB `encryptionKey` config) →
   `FrameCipher.deriveKeystreamFromKey`.
3. **Derive from a capture** — enable *Developer options → Bluetooth HCI
   snoop log*, reproduce a known command in the official app, pull
   `btsnoop_hci.log`, find the ATT write to `CAFE1001...`, build the
   plaintext you believe was sent (`CommandFrameBuilder.build`), and
   `KeystreamDeriver.derive(plaintext, ciphertext)`. Verify with
   `KeystreamDeriver.looksLikeValidFrame` against a *second*, different
   capture decrypted with the derived keystream — bytes 0/1/3 must read
   `0xF7 0x01 .. 0x09`. If not, the plaintext guess was wrong; retry.

Keystream is per `homeId`, so one derivation covers every shade in the
house.

## 8. Unknowns to resolve on real hardware

- Purpose of characteristic `CAFE1002-...`.
- Whether the command characteristic wants a write response
  (`ShadeGattClient.writeCommand` probes `PROPERTY_WRITE_NO_RESPONSE` at
  runtime and picks accordingly — confirm what's actually seen).
- Whether the sequence byte is validated (replay protection) or ignored.
- Meaning of the `velocity` byte, and whether it's writable. **The name is
  probably wrong.** A stationary Duette TDBU reported `0xC0` (192) for it —
  `0b1100_0000`, both high bits set, which reads like a flags/status byte
  rather than any kind of speed. Worth watching what it does while a shade is
  actually moving before trusting the label.
- Whether frames longer than 13 bytes exist for other command classes.
- Whether the shade rejects writes from an un-bonded central once enrolled.
- Whether `0x2A19` (battery level) supports Notify (check
  `properties & PROPERTY_NOTIFY` and a CCCD `0x2902`) — the openHAB binding
  only ever does a plain read.
- Whether mains-powered Gen 3 shades expose `0x2A19` at all.
