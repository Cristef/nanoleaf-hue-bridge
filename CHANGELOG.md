# Changelog

## 4.0.0 - 2026-10-12 (experimental)

- Direct 4D Sync+ UDP receiver with nine stable virtual panels; no physical Shapes
  or ARP interception required by the receiver.
- Guided Nanoleaf Desktop power-button API pairing in the installer and authenticated
  portal, with a two-minute window and persistent tokens.
- Desktop API compatibility and direct-frame telemetry integrated with Hue mapping,
  profiles, brightness, color response and diagnostics.
- Desktop-only installation guide; iPhone/iPad and HomeKit pairing unsupported.
- Public updater preserves private settings and backs up before switching to direct
  mode. Previous physical panel mappings need reassignment.
- Regression coverage for malformed UDP frames, pairing expiration/token persistence,
  direct configuration and nine panels feeding ten synthetic Hue channels.
- Fresh-container hardware onboarding remains to be independently validated.

## 3.1.1 — 2026-10-12

- English Nanoleaf Hue Bridge web portal on port 8080.
- Live panel/group assignments and global/per-light brightness.
- Saved profiles, Hue area selection, light refresh and identification.
- Stream smoothing, saturation and black threshold.
- Reviewed settings import/export without credentials.
- Guided HomeKit/Hue connection and authenticated diagnostics.
- First-visit username/password setup; 8-character password minimum; no initial key.
- Public installer integration and backup-assisted updater preserving pairings.
- Sync+ on/off, idle timeout, ARP restoration and Hue release behavior retained.

Physical Shapes remain required. No direct camera API, Android onboarding,
per-light color-response tuning or web password recovery is added.
