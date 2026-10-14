# Version 4.4 release validation

Two fresh Debian 12 installations completed Desktop pairing, physical 4D API authorization, direct Sync+ registration and Hue Entertainment pairing. The second installation used the published beta.3 archive without application patches.

| Check | Result |
| --- | --- |
| Direct receiver | Nine virtual panels registered; other receivers and screen dimensions preserved |
| Hue output | Two physical lights followed the TV stream |
| Portal controls | On/Off, TV mapping, profiles and brightness verified |
| Restart | Services started automatically; account, pairings, identity and saved settings persisted |
| Stream interruption | Entertainment released when frames stopped and resumed when they returned |
| Home Assistant | Synchronization, brightness and profile commands verified on Home Assistant OS |
| Documentation screenshots | English portal rendered with synthetic device data; no browser warnings or errors |

Automated Linux tests cover API authorization, malformed UDP rejection, ten-channel mapping, configuration validation, installer permissions and receiver registration. GitHub Actions runs the suite on Python 3.11 and 3.12, together with syntax checks.

Hardware validation used two Hue lights. Larger physical areas and other Nanoleaf firmware versions need wider testing. Opening the mobile Sync+ editor can remove the virtual receiver; the explicit portal repair action restores registration. iPhone and HomeKit onboarding are unsupported.
