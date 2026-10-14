# Installation and pairing

## Before you start

Prepare a fresh Debian 12 system with systemd, a stable IPv4 address and Internet access. Allow at least 1 CPU, 512 MB RAM and 4 GB disk space. A physical machine, VM or LXC can host it; Proxmox is optional.

Set up and calibrate the 4D in the Nanoleaf app first. Create a Hue Entertainment area with the lights you want to synchronize. Keep Debian, the 4D, Hue Bridge and Nanoleaf Desktop on the same LAN for installation.

You will need the 4D and Hue Bridge addresses, access to both physical controllers, and Nanoleaf Desktop. Physical Shapes, MAC addresses and HomeKit codes are not required.

Stop any previous bridge instance or other Entertainment application using the same Hue area.

## Install 4.4.0

Run as root:

```bash
apt-get update && apt-get install -y ca-certificates curl
curl -fL https://raw.githubusercontent.com/Cristef/nanoleaf-hue-bridge/v4.4.0/bootstrap.sh -o /root/nanoleaf-hue-bootstrap.sh
bash /root/nanoleaf-hue-bootstrap.sh
```

The installer updates Debian, installs the libraries and creates the services. Select the LAN interface, the 4D source, the Hue Bridge address and a name for your virtual device.

## Three pairing steps

1. **Virtual device in Desktop:** add the named virtual device in Nanoleaf Desktop using power-button pairing. The installer opens a two-minute window and acts as the virtual button. Return to the terminal and press Enter once Desktop shows the device online.
2. **Physical 4D API:** when prompted, hold the physical 4D power button for about five seconds, until its LED flashes, then press Enter in the terminal. The installer registers the virtual receiver directly in Sync+. It preserves the other receivers and screen dimensions and saves a private backup.
3. **Hue Bridge:** press its central link button when prompted, press Enter in the terminal, and choose your Entertainment area.

These are separate authorizations. Pairing the virtual device in Desktop alone does not make the 4D send it colors. Desktop does not provide the Sync+ configuration editor; registration is handled by the installer.

If you finish Desktop pairing later, use **Setup → Open Desktop pairing (120 seconds)** in the portal. Then run `nanoleaf-hue` in the terminal and choose **Register receiver in 4D Sync+**. There is no need to reinstall Debian.

## First use

Open `http://DEBIAN_IP:8080/` or `http://nanoleaf-hue.local/` and create your account. The minimum password length is eight characters. No initial access key is needed.

Start Screen Mirror on the 4D. The portal should report **Streaming** when Synchronization is on and Hue output has started.

In **Mapping**, arrange the Hue lights around the TV, preview the assignments and save. Alternatively, choose panels manually: one panel, a group or the average of all panels. Save a profile to reuse the configuration.

Services start automatically with Debian. Enable host or VM/container autostart separately if needed.

## Home Assistant

Install the [separate integration](https://github.com/Cristef/nanoleaf-hue-bridge-ha) through a HACS custom repository. Create a dedicated token in **Setup → Home Assistant integration**, then enter the bridge URL and token in Home Assistant. Use the IP address when `.local` does not resolve across VLANs.

## Updates

Take a snapshot or full backup, download and extract the new release, then run `bash update.sh` as root. The updater preserves account, pairings, profiles and settings and creates a rollback backup. Settings exports are useful for mappings and profiles, but do not contain credentials.

For symptoms and recovery steps, see the [FAQs](https://github.com/Cristef/nanoleaf-hue-bridge/wiki/FAQs).
