# Install and pair version 4

## Prepare the devices

Create a fresh Debian 12 LXC with systemd, Internet access, 1 CPU, 512 MB RAM
and at least 4 GB disk space. Give it a stable address on the same LAN as your
Nanoleaf 4D, Hue Bridge and computer running Nanoleaf Desktop. Configure VLANs
and DHCP reservations before installation. The installer does not change your
router, Proxmox bridge or access point settings.

Know the 4D and Hue Bridge IPv4 addresses. The container address and interface
are detected. You do not need physical device MAC addresses, physical Shapes,
MCP, a HomeKit code or an iPhone. Create a Hue Entertainment area in the Hue app
and include the lights you want to synchronize.

## Install

Download and extract the release ZIP in the container, then run `bash install.sh`
as root. Alternatively, use the bootstrap instructions in the README. The
installer updates Debian, installs dependencies, creates the Python environment
and service user, detects the network interface, and asks for the 4D address,
Hue Bridge address and virtual name. A unique virtual identity is generated.

## Nanoleaf Desktop pairing

The terminal wizard opens a two-minute API pairing window. On a computer on the
same LAN, open Nanoleaf Desktop, find the virtual device, and use its power-button
pairing option. The virtual button is already pressed; there is no physical
button to hold. Complete pairing within two minutes. The wizard verifies that
an external API client obtained a token. It preserves tokens on restart.

You can finish pairing later: open the portal, create your login, go to
**Settings & pairing**, and click **Start Nanoleaf pairing**. Each click opens
another two-minute window. Only an authenticated portal user can request it.

In Nanoleaf Desktop, include the virtual receiver in your 4D Sync+ configuration,
set its placement and save. Start Screen Mirror on the 4D. Pairing the API client
alone does not register a Sync+ recipient: the configuration step is required.

**iPhone/iPad and HomeKit pairing are not supported.** Do not configure the
virtual receiver's Sync+ placement in the iPhone app. In the tested installation,
that editor displayed the virtual as selected but removed it from the actual
4D receiver configuration when saving. Version 4 does not start a HomeKit
accessory service and does not provide a HomeKit QR code or PIN.

## Hue and portal

Press the Hue Bridge's physical link button when requested. Select an existing
Entertainment area from the list. Set the LXC to start at boot in Proxmox.
Open `http://CONTAINER_IP:8080/` and create a username and password (at least
eight characters). No portal access key is required on first use.

The nine virtual panel IDs are stable. Assign a panel or a group to each Hue
light. Groups use their average color; multiple lights can share a panel.
Use brightness controls, smoothing, saturation and black threshold to adjust
the output, then save a profile. Hue Bridge v2 Entertainment supports up to
ten lights in an area; the bridge's channel mapping is not limited to two.

The virtual On/Off control is available in the portal and Desktop. On waits for
real colors before starting Hue Entertainment. Off releases the area without
automatically switching off the bulbs. Two seconds without frames stops the
stream; new frames resume it if the virtual is on.

## Diagnostics

- **API not paired:** reopen the window and finish power-button pairing in Desktop.
- **Paired, no colors:** check Desktop's 4D Sync+ recipient selection, Screen Mirror,
  source IP, local UDP 60222 reachability and Wi-Fi client isolation.
- **Colors visible, Hue waiting/error:** verify Hue pairing, area membership and
  that another application is not using the same Entertainment area.
- **Disconnected on iPhone:** expected; use Desktop and the portal.

Use `nanoleaf-hue` for pairing, status, diagnostics, changing area, restarting or
deactivating services. Credentials stay on the container and are excluded from
settings exports. Do not expose the unencrypted LAN portal to the Internet.
