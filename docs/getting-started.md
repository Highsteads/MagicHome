---
title: Getting started
nav_order: 2
---

# Getting started

This takes about five minutes, and you only do it once.

## What you need

- Indigo 2022.1 or later, on a Mac that is on the same home network as your lights.
- One or more Magic Home controllers already joined to your wifi, which you do with the Magic Home Pro app when you first unbox them. Do the Bluetooth check on the [Home](index.md) page first, as a Bluetooth-only controller cannot be reached from Indigo.
- The controllers on the **same part of your network** as the Mac that runs Indigo. The plugin finds them by calling out across your network, and that call does not pass through a router. If you keep smart devices on a separate network of their own, see [When something goes wrong](when-something-goes-wrong.md).

It helps to ask your router to keep giving each controller the same network address, which most routers call a **reserved address** or **DHCP reservation**. The plugin copes if an address changes, but it copes faster if it never does.

## 1. Install the plugin

1. Go to the [Releases page](https://github.com/Highsteads/MagicHome/releases/latest) and download `MagicHome.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `MagicHome.indigoPlugin`
3. Double-click `MagicHome.indigoPlugin` — Indigo will install it automatically

Indigo asks whether to enable the plugin. Say yes. As it starts, the plugin searches your network, and the Event Log has a line saying how many controllers it found.

There is nothing you have to fill in under **Plugins → MagicHome → Configure** to begin with. Every setting is explained on the [Settings](settings.md) page.

## 2. Find your controllers

Choose **Plugins → MagicHome → Discover Controllers**. Every controller that answers is listed in the Event Log with its name, its network address — the four numbers such as `192.168.1.40` — and its MAC address, the number it was made with.

The name is the last six characters of the MAC address, which is how the Magic Home app names the controller too, followed in brackets by its hardware code.

If nothing answers, run it again before concluding anything, because the odd missed answer is normal on wifi. If it still finds nothing, see [When something goes wrong](when-something-goes-wrong.md).

## 3. Add a light

1. In Indigo, choose **New Device**.
2. Set **Type** to **MagicHome**, and the model to **Magic Home Light**.
3. Leave **Find the controller by** on **Discovery (recommended — survives a changed IP)**.
4. Pick your controller from the **Controller** list. Each one shows its name and its current network address.
5. Click **Save**.

If you would rather type in an address, choose **A fixed IP address** instead and fill in **IP address**. Only do that if your router has a reserved address for the controller, because a light set this way stops working the day its address changes.

## 4. Check it works

Within a few seconds the new light shows its state in Indigo's device list, on or off with its brightness. The Event Log says the light is answering, with its network address, and the light's **Controller Model** state shows which kind of controller it is.

Now switch the light on and off from Indigo, drag the brightness slider, and pick a colour.

For a fuller check, open **Plugins → MagicHome → Configure**, choose the light under **Demo this light**, and click **Run Demo**. It shows red, green and blue one at a time, then warm white, then cool white, then a fade, and puts the light back exactly as it was, all in about 13 seconds. If red shows as green, or similar, your strip is wired in a different order, which the [When something goes wrong](when-something-goes-wrong.md) page covers.

If the light never answers, the same page goes through the usual causes.
