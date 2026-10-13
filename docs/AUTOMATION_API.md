# Automation API v1 (experimental)

Requires bridge 4.2.0 or newer; release 4.1.0 does not include it. Create/revoke tokens from authenticated portal Setup → Home Assistant integration. Only token hashes are stored. Tokens grant state reads and sync/profile/global-brightness commands, not portal administration. Requests are LAN-only, reject browser Origin headers and require a valid Host header. Use IP:8080 across VLANs where mDNS is unavailable. HTTP is unencrypted; protect your trusted LAN and backups.

Send `Authorization: Bearer TOKEN`. Never put tokens in URLs.

- `GET /api/integration/v1/state`: API version, stable deployment UUID, receiver reachability, enabled state, streaming state, fresh-frame flag, global brightness, profile names/current match and settings revision. No Hue credentials, browser CSRF or HomeKit keys.
- `POST /api/integration/v1/command`, JSON `{"command":"sync","value":true}`, `{"command":"brightness","value":75}` or `{"command":"profile","value":"Cinema"}`. Returns updated state. Global brightness preserves channel levels. Commands are serialized with portal settings updates.

Errors: 400 invalid/unsupported command; 401 invalid/revoked token; 403 invalid Host; 409 conflicting configuration; 429 authentication rate limit; 503 operation unavailable. Off releases Entertainment without restoring scenes. Profiles match exact active settings; duplicate identical profiles return the first name. API IDs and tokens are private state outside settings exports; full system backups preserve them.
