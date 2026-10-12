# Release checklist

Publish only this directory as the repository root; exclude local prototype files,
SSH credentials, container state, private snapshots and packet captures.

- Run all Python tests and Bash syntax checks.
- Check installer/update provisioning and preservation of identities and accounts.
- Inspect staged files for credentials and deployment-specific addresses.
- Keep PolyForm Noncommercial license and third-party notices unchanged.
- Confirm GitHub Actions passes before publishing the tagged release.
- Record hardware testing limits in README and release notes.
- Test a fresh Debian 12 installation with physical pairing separately; run only
  one relay for a given 4D/Shapes pair at a time.
