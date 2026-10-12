# Release checklist

Version 4.1.0 is an experimental prerelease. Publish only this directory.

- Run Linux Python tests, Python/JavaScript syntax checks and Bash syntax checks.
- Verify Desktop pairing window authorization, expiration and persistent tokens.
- Verify malformed/source-mismatched UDP rejection and multi-channel mapping.
- Verify installer/updater provisioning and rollback retain private identities/accounts.
- Inspect tracked files and archive for credentials and deployment-specific values.
- Keep the noncommercial license and all third-party attribution files.
- Confirm GitHub Actions passes for the published commit.
- Record limits: development hardware used two Hue lights; ten-channel mapping is
  synthetic; complete fresh Debian Desktop-only onboarding still needs hardware testing.
- Never run a second production instance against the same configuration during tests.
