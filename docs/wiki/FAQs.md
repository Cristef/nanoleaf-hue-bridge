# Troubleshooting FAQs

## I opened Sync+ in the mobile app and the Hue lights stopped. Why?

On affected app versions, opening the Sync+ editor can rewrite the 4D receiver list and remove the virtual device, even if you do not save anything. The physical Shapes can continue working while the virtual receiver gets no colors.

Open **Setup** in the bridge portal. If **4D Sync+ registration** reports that the receiver is missing, click **Repair Sync+ registration**. Once the 4D is sending again, synchronization resumes if the virtual switch is on.

Repair adds this virtual receiver back and preserves the other receivers. It is explicit: the bridge does not continuously overwrite configurations made by the Nanoleaf app. If you open the mobile editor again, you may need to repair again.

If the portal requests physical 4D API pairing, run `nanoleaf-hue` in the Debian terminal, choose **Register receiver in 4D Sync+**, and follow the power-button prompt.

## Synchronization is on, but the status says Waiting for colors

The switch enables synchronization; it does not guarantee that frames are arriving. Check these in order:

1. In **Setup**, check whether the virtual receiver is registered in the 4D. Repair it if missing.
2. Start Screen Mirror on the selected 4D. A camera mirror mode must be active; playing a video on the TV alone is not enough.
3. Check the saved source IP. DHCP changes can leave it pointing to a different device.
4. If registration and source are correct, check UDP 60222 reachability and Wi-Fi client isolation.

When the 4D stops sending, Waiting for colors is expected. The bridge releases Hue Entertainment after the stream timeout and starts it again when frames return.

## Desktop paired the virtual device. Why is it still receiving no colors?

Desktop pairing authorizes a client to control the virtual device. Sync+ registration tells the physical 4D where to send colors. Both steps are needed.

Run **Register receiver in 4D Sync+** from the `nanoleaf-hue` terminal menu. After the initial physical 4D authorization, **Repair Sync+ registration** in the portal can reuse that pairing.

## Desktop tells me to use the mobile app to configure Sync+

Use Desktop for virtual-device pairing only. The installer handles Sync+ registration directly through the physical 4D API. Do not try to add the virtual device through the mobile Sync+ editor.

## The virtual device is missing or disconnected on iPhone

iPhone/iPad and HomeKit onboarding are not supported in version 4.4. There is no HomeKit QR code or PIN. Use Nanoleaf Desktop for pairing and the web portal or Home Assistant for daily control.

## Which button should I press during installation?

| Prompt | Action |
| --- | --- |
| Add the virtual device in Desktop | Choose power-button pairing in Desktop. The installer opens the virtual button's two-minute window. |
| Authorize the physical 4D API | Hold the physical 4D power button for about five seconds, until its LED flashes. |
| Pair the Hue Bridge | Press the Hue Bridge's central link button once. |

Return to the terminal and press Enter after each requested action. If a window expires, retry pairing; do not reinstall the system.

## Do I need physical Shapes or a MAC address?

No. Version 4 receives directly from the 4D using nine virtual panels. The installer generates its own receiver identity. Know the 4D and Hue Bridge IP addresses instead.

## Panel colors arrive, but Hue does not stream

Check that the selected Hue Entertainment area contains your lights, and that Hue pairing is complete. Stop another application using that area, such as Hue Sync. Only one Entertainment stream can control an area at a time.

Use **System** for the current diagnostic report and **Setup → Refresh lights** after changing the area in the Hue app. If you select a different area, save a profile first: mappings and individual brightness are cleared for its new channels.

## Preview panel assignments is disabled

Save or discard pending manual panel assignments, brightness or color-response edits before using the TV preview. The preview replaces the panel-mapping draft, so it is blocked while another draft needs attention.

Move the lights, click **Preview panel assignments**, then **Save TV mapping**. A preview does not change the running output until saved. Moving a light again requires another preview before saving.

## Turning synchronization off leaves the bulbs on

This is intentional. Off stops the stream and releases the Hue Entertainment area; it does not switch the bulbs off. They may remain at their last color. Use Hue or Home Assistant light controls for normal lighting afterward.

## I see “Invalid settings” when changing something

For mappings, select panels that exist in the current stream and save against the current Hue area. Reload if the area changed in another window. For imports, use a settings export from a compatible version.

If this occurs specifically when switching the virtual device off on an early 4.4 beta, update to 4.4.0. That installation-permissions bug is fixed in the release; it does not require resetting your mappings or pairing again.

## The short URL does not open

Try `http://DEBIAN_IP:8080/`. The `.local` name uses mDNS, which may not cross VLANs or may be blocked by your client or network. Do not run two bridge instances using the same local name.

The project serves HTTP on the trusted LAN; it does not configure router DNS or HTTPS certificates.

## Home Assistant cannot connect or shows Unavailable

Make sure the URL opens from Home Assistant's network and includes `:8080` when needed. Prefer the stable IP address when mDNS is unavailable. Check that the dedicated automation token has not been revoked.

If the address changes, use the integration's **Reconfigure** option. If the token was revoked, create a new one in the portal and use Home Assistant's reauthentication flow. Never paste the token into an issue or screenshot.

Home Assistant polls state every five seconds, so a status change can take a few seconds to appear. The standalone Debian bridge continues handling the stream independently.

## Can I use more than two Hue lights?

Yes. Channels are read from the selected Entertainment area. The mapping supports individual panels, panel groups and averages for each light. Hardware testing used two lights; automated mapping tests cover ten channels. Adding lights may require refreshing the area and reviewing their mappings.

## What survives a reboot or an update?

Saved account, pairings, virtual identity, mappings and profiles are persistent. A reboot also preserves the virtual On/Off state. New color frames resume the stream automatically when the virtual device is on.

Settings exports include mappings, TV positions, brightness, color response and profiles, but exclude passwords and device credentials. Keep a full system backup or snapshot for complete recovery, and use `update.sh` for release upgrades.

## What should I include in a bug report?

Include the bridge version, Debian version, 4D model/firmware, the status shown in the portal, the action that triggered the problem and whether Setup reports the receiver registered. Home Assistant can download credential-free integration diagnostics from the device menu.

Review logs and screenshots before attaching them. Do not share API tokens, Hue credentials, passwords, full pairing backups or private state files.
