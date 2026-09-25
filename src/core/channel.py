"""Distribution channel of this build.

Two channels exist:

- ``"direct"`` — every build except the Play Store AAB: the GitHub APK,
  Windows, Linux. Kiri License premium is offered here, because Google
  Play cannot bill a sideloaded install no matter what the app does.
- ``"play"`` — the AAB that ships through the Play Store. Premium does
  not exist on this channel: no purchase UI, no license-worker requests,
  nothing for Play policy to look at. Users get the free tier with ads.

The committed default is ``direct``. The AAB job in build-all.yml
overwrites this file with ``CHANNEL = "play"`` right before packaging, so
the marker is decided by which pipeline built the artifact — not by a
runtime guess.

Why a marker at all: the Play Console in use has no Google Payments
merchant profile, so in-app products cannot even be created. Play
Billing stays in the code, dormant; the day a merchant profile exists
on an account we can use, the products are created and this marker is
the only thing to change.
"""

CHANNEL = "direct"
