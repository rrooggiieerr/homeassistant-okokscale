# Home Assistant integration for OKOK Scales

![Python][python-shield]
[![GitHub Release][releases-shield]][releases]
[![Licence][license-shield]][license]
[![Maintainer][maintainer-shield]][maintainer]  
[![Home Assistant][homeassistant-shield]][homeassistant]  
[![Github Sponsors][github-shield]][github]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]

## Introduction

Home Assistant integration to read Bluetooth scales which can be used with the *OKOK international*
app and identify themselves on Bluetooth as *Chipsea-BLE*.

> [!IMPORTANT]
> As of Home Assistant 2026.11 the OKOK Scale integration is part of Home Assistant Core, see the
> [OKOK Scale integration documentation](https://www.home-assistant.io/integrations/okok_scale/).
>
> If you use this custom integration in Home Assistant 2026.11 or later, Home Assistant will show a
> repair issue to move your scales to the built-in integration. Afterwards you can remove this
> custom integration from the Marketplace.

## Features

- Installation/Configuration through auto detection
- Read weight and battery status

## Hardware

### Supported scales

The following scale is known to work:

* Tristar WG-2440

Please let me know if your scale works with this Home Assistant integration so I can
improve the overview of supported scales.

## Installation

> [!NOTE]
> This custom integration is only needed for Home Assistant versions older than 2026.11. As of
> 2026.11 use the built-in [OKOK Scale integration](https://www.home-assistant.io/integrations/okok_scale/).

### Manually

- Copy the `custom_components/okokscale` directory of this repository into the
`config/custom_components/` directory of your Home Assistant installation
- Restart Home Assistant

## Adding a new OKOK Scale

> [!NOTE]
> As of Home Assistant 2026.11 new OKOK Scales are detected by the built-in
> [OKOK Scale integration](https://www.home-assistant.io/integrations/okok_scale/). This custom
> integration no longer adds them. On older Home Assistant versions this custom integration detects
> new OKOK Scales automatically. If your scale is not detected it's not supported.

## Support my work

I'm putting a lot of time and effort into developing and maintaining this and other integrations.
If you find it useful, please consider supporting its continued development by
[sponsoring me on GitHub][github] or [buying me a coffee ☕️][buymecoffee].

Your support is greatly appreciated and helps keep me motivated to continue developing and
maintaining integrations!

[![GitHub Sponsors][github-shield]][github]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]

### Home Assistant support

Need some hands-on help with Home Assistant? [Book a one-hour Q&A session](https://buymeacoffee.com/rrooggiieerr/e/447353)
and I'll help you solve your Home Assistant-related questions.

Examples of what we can cover in one hour:
- Home Assistant walkthrough, I'll explain where to find things in the Home Assistant UI
- Installing and configuring a Home Assistant integration
- Explaining and creating scenes
- Explaining and creating a simple automation
- Install a ZHA quirk to make an unsupported Zigbee device work with Home Assistant

For more complex issues, such as recovering a crashed Home Assistant installation or providing
support for Home Assistant integration developers, I may be able to help as well. These requests
can require more than one hour and may need to be arranged separately.

### Hire me

Would you like a Home Assistant integration developed for your product, or do you need an
experienced Python developer for your project?

I'm available for freelance development work. You can find my contact details on
[my GitHub profile](https://github.com/rrooggiieerr).

[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[releases]: https://github.com/rrooggiieerr/homeassistant-okokscale/releases
[releases-shield]: https://img.shields.io/github/v/release/rrooggiieerr/homeassistant-okokscale?style=for-the-badge
[license]: ./LICENSE.md
[license-shield]: https://img.shields.io/github/license/rrooggiieerr/homeassistant-okokscale?style=for-the-badge
[maintainer]: https://github.com/rrooggiieerr
[maintainer-shield]: https://img.shields.io/badge/MAINTAINER-%40rrooggiieerr-41BDF5?style=for-the-badge
[homeassistant]: https://www.home-assistant.io/
[homeassistant-shield]: https://img.shields.io/badge/home%20assistant-%2341BDF5.svg?style=for-the-badge&logo=home-assistant&logoColor=white
[buymecoffee]: https://www.buymeacoffee.com/rrooggiieerr
[buymecoffee-shield]: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black
[github]: https://github.com/sponsors/rrooggiieerr
[github-shield]: https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=%23EA4AAA