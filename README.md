# Nanoleaf Hue Bridge

Use a **Nanoleaf 4D camera to synchronize Philips Hue lights** through a virtual
Shapes receiver. Version **4.2.0** receives Sync+ UDP colors directly from the
4D, with nine virtual panels, guided Debian 12 installation and an English web portal.
Physical Shapes are no longer required by the receiver, and no ARP relay is started.

**Pair and configure the virtual device only in Nanoleaf Desktop on the same LAN.**
iPhone/iPad and HomeKit pairing are currently unsupported. Version 4 does not
advertise a HomeKit accessory or provide a QR code/PIN. Do not use the iPhone
Sync+ placement editor for this virtual device: in the tested setup, saving there
removed it from the 4D's actual receiver configuration.

This is an **experimental prerelease**. Direct reception and Hue output work on
the development installation, including operation after removing HomeKit.
The complete fresh-system Desktop-only onboarding still needs an independent
hardware installation test. Nanoleaf app/firmware compatibility is not guaranteed.

## How it works

```text
4D camera -> Sync+ UDP colors -> virtual Shapes (nine panels)
                                   -> Hue Entertainment -> Hue lights
Desktop / web portal On/Off --------> enable / release Hue stream
```

The virtual device implements the tested Desktop API handshake and extControl v2
UDP reception on port 60222. Hue uses HueStream v2 over DTLS rather than per-frame
REST commands. API pairing and adding the virtual device to the 4D Sync+ setup are
two separate steps; both are required. This project does not access the camera's video.

## Before installing

**Proxmox is not required.** Debian 12 can run on a physical machine, a VM,
or an LXC/system container on any suitable platform. It must run systemd and
allow LAN discovery and incoming TCP/UDP traffic. A minimal Docker-style
application container without systemd is not supported by this installer.
Hardware testing so far used Debian 12 in LXC; other hosts have not yet been
independently validated.

- A fresh Debian 12 system running systemd: 1 CPU, 512 MB RAM, at least 4 GB disk,
  Internet access and a stable IPv4 address.
- A Nanoleaf 4D and its IPv4 address; Screen Mirror must be available.
- Nanoleaf Desktop on a computer on the **same LAN** as the Debian system and 4D.
- A Hue Bridge supporting Entertainment, its IPv4 address, and an Entertainment
  area created in the Hue app with the lights you want to use.
- Access to the Hue Bridge's physical link button for initial authorization.

The installer detects the Debian system address/interface and generates the virtual
identity. Physical device MAC addresses, physical Shapes and HomeKit codes are not
needed. Configure VLANs, DHCP reservations and Wi-Fi client isolation beforehand;
the installer does not configure your virtualization platform, routers or access points. Allow mDNS
discovery (UDP 5353), the virtual API (TCP 16021), Sync+ (UDP 60222), and the
portal (TCP 80 and 8080) on your trusted LAN. Run one bridge instance for this configuration.

## Install on a fresh Debian 12 system

Run this block as root on the Debian 12 system:

```bash
apt-get update && apt-get install -y ca-certificates curl
curl -fL https://raw.githubusercontent.com/Cristef/nanoleaf-hue-bridge/v4.2.0/bootstrap.sh -o /root/nanoleaf-hue-bootstrap.sh
bash /root/nanoleaf-hue-bootstrap.sh
```

The bootstrap downloads this release. The installer upgrades Debian packages,
installs libraries and a Python environment, creates services, and guides you
through addresses, virtual name, Desktop pairing, Hue authorization and area selection.
Alternatively, extract the [release ZIP](https://github.com/Cristef/nanoleaf-hue-bridge/releases/tag/v4.2.0)
and run `bash install.sh` from its directory.

During Nanoleaf pairing, choose the **power-button method in Desktop** within
the two-minute window opened by the wizard. The virtual button is already pressed.
Then add the receiver to the 4D Sync+ configuration in Desktop, set its position,
save and start Screen Mirror. If necessary, finish pairing later in the portal.
Press the physical Hue Bridge button when prompted and select your Entertainment area.

Ensure the Debian system starts automatically if you want continuous operation.
For a VM or container, enable autostart in your hosting platform (for example,
**Start at boot** in Proxmox). The installer enables the bridge services at boot.
Open `http://DEBIAN_IP:8080/`
and create your username and password (minimum eight characters). No access key
is required on first use. See the [complete installation and pairing guide](docs/INSTALLATION_V4.md).

## Use the web portal

Open **http://nanoleaf-hue.local/** on the same LAN, or use
`http://DEBIAN_IP:8080/` as a fallback. The short name uses mDNS and port 80;
client/network mDNS support is required. No router DNS changes or HTTPS are configured.
For multiple installations, set a unique `portal_name` ending in `.local` in
`/etc/nanoleaf-hue/config.json` before provisioning/restarting the services.

Create your username and password on first use (minimum eight characters).
The portal has six separate, bookmarkable views. Unsaved drafts survive switching
between pages; they become active only after saving.

| Page | What to do |
| --- | --- |
| Live | Watch nine hexagons and the last RGB output sent to each Hue. Open Immersive preview for a full-viewport glow display; exit with Esc or the exit button. Run a temporary solid, sequence or identify test for up to 60 seconds. |
| Mapping | Select a light and its panels. Preview an automatic suggestion from Hue channel positions. Spread mode expands relative positions; change axis/mirror and preview repeatedly, then explicitly save. Identical positions can share a panel. |
| Color | Adjust global/individual brightness, smoothing, saturation, black threshold and per-light RGB gains. |
| Profiles | Save and apply area, mapping, brightness and color-response presets. |
| Setup | Discover/change the 4D source, open the 120-second Desktop pairing window, authorize Hue, select an Entertainment area, and export/review/import settings. Source selection does not register Sync+ recipients automatically: complete that in Desktop. |
| System | Inspect connection diagnostics and release notes. Complete releases are installed with `update.sh`; GUI update/recovery handles compatible locally staged bundles only. |

Choose **Auto**, **Light** or **Dark** in the header. Auto follows your system
appearance; the preference stays in your browser. Page and feedback transitions
respect reduced-motion preferences. Immersive mode fills the page, while browser
chrome remains visible; it does not alter the actual lamp colors or configuration.
Temporary color tests do take over the selected Hue area, respect saved brightness
and response, and automatically return to the previous synchronization mode.

Mapping supports all channels in the selected area; automated and browser checks
include ten synthetic channels. Real hardware validation used two Hue lights.
Desktop placement controls what the 4D sends to the virtual panels. The portal
mapping then chooses which of those colors each Hue follows. The decorative
hexagon layout is not a physical-position editor for the 4D.

These screenshots show version 4.1 with synthetic lights, panel IDs and addresses:

![Live overview in dark mode](docs/images/portal-live-v41.png)
![Immersive live preview](docs/images/portal-immersive-v41.png)
![Select lights and map the hexagon panels](docs/images/portal-mapping-v41.png)
![Desktop pairing and Hue setup](docs/images/portal-setup-v41.png)

## Daily operation

Keep the Debian system and services running. Turn the virtual device on/off in
Desktop or the portal. On waits for incoming colors before claiming the Hue area;
Off releases it without switching off the bulbs. Two seconds without fresh frames
releases the stream; new frames resume it while the virtual device is on.
The maintenance menu is `nanoleaf-hue`. Pairings and settings survive service restarts.
Avoid other applications streaming to the same Hue Entertainment area.

## Upgrade from version 3 or 4

Take a full system backup or VM/container snapshot first. Download/extract version 4.1 and run:

```bash
bash update.sh
```

The updater supports `/opt/nanoleaf-hue` installations created by the public
installer. It makes a private backup in `/root/nanoleaf-hue-backups`, preserves
accounts, identities, API tokens, Hue credentials and profiles, disables HomeKit,
and upgrades the portal. When upgrading from version 3, it also replaces ARP
capture with direct reception. Version 4.0 mappings remain valid. Startup failure
triggers rollback.
Private prototype installations at `/opt/nanoleaf-probe` are not supported by it.

Use Desktop to pair if necessary and register the virtual recipient in 4D Sync+.
Review existing mappings: physical panel IDs from version 3 do not match the new
virtual IDs 1-9. Reassign groups before using saved old profiles. Changing area
also clears active channel groups and individual brightness for that area.

## Troubleshooting and security

For missing colors, verify Desktop pairing **and** 4D Sync+ recipient selection,
Screen Mirror, source IP, UDP reachability and Wi-Fi isolation. A disconnected
iPhone entry does not indicate Desktop/API failure; iPhone pairing is unsupported.
For Hue problems, verify link-button authorization, area membership and competing
streams. Consult portal diagnostics or `nanoleaf-hue` -> Diagnostics.

The portal uses password hashing, authenticated sessions and origin/CSRF checks.
It is HTTP on a trusted LAN: do not expose it to the Internet. First-login setup
is available until the initial account is created; finish it promptly. Internal
API tokens and Hue credentials stay on the Debian system and are excluded from exports.

## Development and license

On Linux with Python 3.11/3.12, install `requirements.txt` and run
`python tests/run.py` and `bash -n install.sh bootstrap.sh update.sh`.
The tests use synthetic addresses and isolated state. Archived relay/HomeKit
modules remain for compatibility/regression coverage; public version 4 services
do not enable them. This is not an official Nanoleaf or Philips Hue product.

This project is **source-available for noncommercial use** under
[PolyForm Noncommercial 1.0.0](LICENSE). Commercial-use rights are not granted.
Third-party libraries retain their own licenses: see [NOTICE.md](NOTICE.md) and
[LICENSE_AUDIT.md](LICENSE_AUDIT.md).

## Home Assistant (experimental)

Version 4.2 introduces automation API v1. Install the separate [Home Assistant integration](https://github.com/Cristef/nanoleaf-hue-bridge-ha) through a HACS custom repository. The Debian bridge keeps running independently; Home Assistant controls synchronization, saved profiles and global brightness, and monitors stream state and recent Sync+ frames. It does not process the color stream or duplicate Hue lights.

Create a token under **Setup → Home Assistant integration**, copy it once and enter it into the integration along with the bridge URL. Revoke access from the portal. Use an IP URL across VLANs without mDNS. Tokens are hashed locally, excluded from settings exports and cannot administer the portal, pair devices or install updates. HTTP is unencrypted: use a trusted LAN only. Read the [API guide](docs/AUTOMATION_API.md). Home Assistant hardware validation remains pending.
