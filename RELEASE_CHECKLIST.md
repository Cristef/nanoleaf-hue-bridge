# Release checklist

Version 4.4.0 is the release validated through two fresh Debian 12 installations. Publish only this directory.

- Run Linux Python tests, Python/JavaScript syntax checks and Bash syntax checks.
- Verify Desktop pairing window authorization, expiration and persistent tokens.
- Verify malformed/source-mismatched UDP rejection and multi-channel mapping.
- Verify installer/updater provisioning and rollback retain private identities/accounts.
- Inspect tracked files and archive for credentials and deployment-specific values.
- Keep the noncommercial license and all third-party attribution files.
- Confirm GitHub Actions passes for the published commit.
- Record limits: development hardware used two Hue lights; ten-channel mapping is
  synthetic; fresh onboarding and direct 4D registration are verified; other firmware versions need wider testing.
- Never run a second production instance against the same configuration during tests.

- Home Assistant OS: HACS installation, UI setup, five entities, switch, brightness, profile and actual Streaming state verified on one installation.
