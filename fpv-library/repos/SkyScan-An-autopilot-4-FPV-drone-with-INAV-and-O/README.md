# SkyScan
An autopilot 4'' FPV drone with INAV and OpenIPC used for photogrametry!

---

**Say hello to SkyScan!** This is my personal project for [Hackclub Highway](https://highway.hackclub.com/). It will be used to take pictures and videos later to be used for photogrammetry and 3DGS.

 -> Just like this: [3DGS example](https://splatter.app/s/c07-ax0)

## Table of Ideas
- Under 250g
- 4" frame
- Digital FPV with OpenIPC
- INAV - GPS and Mission planning
- 4S battery

## Conectivity
- OpenIPC - 2.4GHz > Realtime HD video
- ELRS - 900MHz > Long range control
- GPS - 1.5GHz > Location & telemetry

## Why did I make this?
As a someone who got absolutlely obsessed with photogrammetry and 3DGS, I wanted to not be limited to taking photos from the bottom of the object or building.
I was told that I just need to get a drone, you know. Get. A. Drone. Then highway email came to me, and I was like, "I can make my own drone, and it will be better than anything you can buy!". OFC! So this is my journey how I learned about all the components, learned how to CAD and how to stay motivated for a longer period of time.

## What is this?
The idea is to create a lightweight drone, that you can just say a location and it will take photos of the object from all angles, and then you can use those photos to create a 3D model of the object.
Like something that DJI has, but with no hardware limitations and open source software!

## Custom 3D Printed Frame
Ive designed a custom frame that could be printed on all 22x22cm printers. So that you could easily replicate it. The frame is designed to be lightweight, but also strong enough to withstand crashes. It supports both 25.5x25.5mm and 30.5x30.5mm mounting patterns for the AIO flight controller and VTX. The files are fully open source and available in the [3d project files](/3d%20parts/3d%20project%20files/) folder.  **Customize it as you want!**
You can print it in any material you want. Or even use CNC machine.

![Frame](/img/Frame%203ddd.png)
![Frame drawing](/img/Frame4%20onshape.png)
![Frame shell](/img/Top%20onsape.png)

``note that the frame does not currently have a camara mount, waiting for the grant to be approved to buy a camera and make it``

# Hardware

  | **Component**                     | **Model / Specs**                                                       | **Notes**                         |
|----------------------------------|--------------------------------------------------------------------------|-----------------------------------|
| **Frame**                        |  Custom 3d printed, my design                                               | supports 25.5x25.5mm, 30.5x30.5mm |
| **Flight Controller + ESC**      | Speedybee F405 AIO 40A (25.5x25.5mm)                                     | BLHeli_32, Bluejay, 3–6S support  |
| **Motors**                       | 4x T-Motor P1604 3800KV                                                  | 4S optimized, 9x9mm mount         |
| **Receiver**                     | Radiomaster XR1 Nano Dual-Band ELRS 2.4GHz + 900MHz                      | High range redundancy             |
| **Radio Controller**             | Radiomaster Pocket (TC-style with built-in ELRS 2.4GHz)                  | No external module required       |
| **Camera & VTX**                 | EMAX Wyvern Link Alpha (OpenIPC support, 5.8GHz HD, 100mW)               | OpenIPC-compatible                |
| **Props**                        | Gemfan Hurricane 4023 / HQProp T4x2.5x3                                  | For 4" efficiency/freestyle       |
| **Battery (light)**              | 4S 850mAh Li-ion                                                         | Sub-250g compatible               |
| **Battery (long range)**         | 4S 18650 3000mAh Li-ion (e.g., VTC6 pack)                                | Up to 40+ min flight              |

This is the camera that makes this all possible. It is a 5.8GHz digital FPV camera with OpenIPC support, which allows you to stream HD video in real-time.
![](img/Video%20TX.jpg)