# Changelog

## 4.2.0 - 2026-10-13 (experimental)

- Versioned automation API for Home Assistant with limited, hashed, revocable tokens.
- Portal Setup token creation, one-time display and revocation.
- State, synchronization, saved profiles and global brightness commands.
- Preserve individual brightness, account security and streaming architecture.
- Dedicated experimental integration: https://github.com/Cristef/nanoleaf-hue-bridge-ha

## 4.1.0 - 2026-10-12 (experimental)

- Six dedicated portal views with Auto/Light/Dark themes and preserved unsaved drafts.
- Live hexagon preview, RGB glow and immersive mode, keyboard exit and reduced-motion transitions.
- Relative/absolute position mapping suggestions; repeat preview after axis/mirror changes.
- Per-light saturation, smoothing, black threshold and RGB gains.
- Bounded temporary solid/sequence/identify tests with automatic return to streaming.
- Guided 4D discovery/source selection and existing Desktop/Hue pairing.
- Connection diagnostics, release notes and verified locally staged maintenance/recovery.
- Built-in HTTP port 80 and nanoleaf-hue.local alias; port 8080 retained.
- Updated installer/services, upgrade path, English guide and synthetic screenshots.
- HomeKit/iPhone onboarding remains unsupported; no HTTPS is enabled.

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
