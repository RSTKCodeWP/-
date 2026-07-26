# Project-Nitro 🏎️💨

### FPV RC Racing Car with Game Effects

Have you ever wondered about having a **FPV RC Racing Car** with game effects such as:
- Boost
- Gun
- Health
- Drift (Bad effects and more)

Well, I have made this with the help of **NFC TAGS**. How it works is simple: when each car has an NFC reader underneath, and when it passes over a NFC tag, it will detect the code and look for what power or bad effect it is. Then I can pull that effect whenever we want. Beat your opponent and win with super powers using our own strategy to win the game!

## Zine
[zine](/doc/zine.pdf)
![zine](/image/doc/zine.png)

## Hardware Showcase 🛠️
### Photos of Car and Remote 📸

#### Car 

![Car](/image/cad/car/C1.png)  
![Car 2](/image/cad/car/C2.png)  
![Car 3](/image/cad/car/C3.png)

#### Remote

![Remote](/image/cad/rc/R1.png)  
![Remote 2](/image/cad/rc/R2.png)  
![Remote 3](/image/cad/rc/R3.png)

### Circuit & Diagram

#### Car Schematics

![Car Schematics](/image/schematic/car/CAR.png)

#### Remote PCB & Schematics

 ![Remote Schematics](/image/schematic/rc/RC.png) 
![PCB 1](/image/pcb/rc/pcb-1.png)  
![PCB 2](/image/pcb/rc/pcb-2.png)

## Motivation

I have always wondered to play **RC car** like in games with boost, power, win, health etc.. because that all make more fun for the world and playing with friends makes it even more fun. So I built this car - it will give you a game vibe with RC FPV cars in real life, bringing more fun and joy to the world!
## How to Build 🛠️

### Car Assembly

After 3D printing, check the tolerance of each part and sand it smoothly for better look and placement. Then solder everything with wires, place each component in its designated position as shown in the `.step` files, glue the IR receiver and transmitter, tape or glue the batteries in their places, place ESP32 on the ESP tray and screw it well, then mount to the car body as shown.
## Car Assembly

1. 3D print all STL files from `/cad/car`.
2. Sand the parts until they fit smoothly.
3. Insert all M3 heat inserts
4. Mount the N20 motor using two M3 screws.
5. Install the steering servo.
6. Mount the ESP32.
7. Install the PN532 NFC module.
8. Connect all electronics according to wiring diagram.
9. Mount FPV cam.
10. Install battery
11. scraw body

### Remote Assembly
## Car Assembly

1. 3D print all STL files from `/cad/remote`.
2. Sand the parts until they fit smoothly.
3. Insert all M3 heat inserts.
4. place the batter.
5. Mound the ESP32.
6. Mount PCB after soldering all switchs and LED.
7. Insert the button.
8. Connect all electronics according to wiring diagram.
9. Slide in the sreen and screw.
10. Slide the bottom case.
11. Close body.

After 3D printing, check the tolerance of each part and sand it smoothly for better look and placement. Then solder everything with wires, place the battery first followed by ESP32, solder the switch to PCB and connect the GPIOs Don't forget to place the LCD screen holders to screw for better holding, slide down the bottom part and screw it also then paint everything.

## How to Play/Setup 🎮

When you turn on the remote and car, it will connect (if it's your first time,you may need to pair them) You'll get a web interface in phone or laptop for FPV. Once connected you have two modes:

### Free Ride Mode
You can drive it as normal RC car without any special features.

### Race Mode  
In this mode, you need an opponent to play with. One of you will host the game and that person's car becomes the controller of the game also. The remote looks for players  when a player is found:
- Flip the car and reegister all NFC tags again
- Accept the win gate tag and pit lane
- Place everthing in place as you want
- Everywhere, you can make your own track with anything you have
- Play and win the game
## Game Effects ⚡

### Good Power-ups
- **Boost** - Speed boost to move faster  
- **Health** - Get more health  
- **Shield** - Protection from enemy bullets  
- **Bullets** - Shoot projectiles  

### Bad Effects
- **Drift** - The car gets drift randomly  
- **Random Control** - Controls switch randomly (forward becomes backward)  
- **Slowness** - Car goes slowly  
- **Damage** - Low health  

### Bonus Feature
All bad effects can be cleared by going to your own pit lane.
## How It Works ⚙️

This all works with ESP-NOW protocol. The host's car maintains the rules and everything:

- `car ↔ remote` - Direct communication between each unit  
- `car(host) ↔ car(client)` - Host communicates with client cars  
- `camera → WiFi web → phone, laptop...` - Video stream to viewer devices

## Folder Structure 📁
```
cad/

├── car/
│   └── car.step

├── remote/
│   └── Remote.step

├── nfc/
│   └── nfc tag sticker.step

firmware/

├── car/
│   └── Car firmware

├── remote/
│   └── Remote firmware

├── camera/
│   └── FPV camera firmware
```

### Car Section
- [Car CAD](/cad/car/) - 3D models and designs  
- [Car Firmware](/firmware/car/) - Embedded code for the Car  
- [FPV Camera](/firmware/car_cam/) - Camera firmware  
- [Car Circuit](/circuit/car/) - Schematic diagrams  

### Remote Section
- [Remote CAD](/cad/remote/) - 3D models and designs  
- [Remote Firmware](/firmware/remote/) - Embedded code for the remote  
- [Remote circuit](/circuit/remote/) - Schematic diagrams

## BOM (Bill of Material)
[BOM](/doc/BOM.csv.csv)

## Car Components 🛒

|**Item**|Number|Approx. Price|Link|
|--------|-------------|-------------|---|
|5mm 940nm IR Emitter Transmitter|2|₹140|[Amazon](https://amzn.in/d/03gj3whx)|
|MPU6050 IMU|1|₹174|[Amaz](https://amzn.in/d/0gS9H64g)|
|PN532 NFC RFID Module|1|₹425|[Robokit](https://robokits.co.in/wireless-solutions/rfid/pn532-nfc-rfid-module-v3-kit-reader-writer-breakout-board?srsltid=AfmBOooBJS2DFnuWBIGC9mB0mO7za8Ql3MFEb6kDh34OEwg5jFQdKodmrjA)|
|ESP32S3-Sense|1|₹1800|[SeeedStudio](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html?srsltid=AfmBOooVpv6VY6S8HZ8RSQHJR3o-OCpF9PW-xqElodKlTDqwqZxqCzhl)|
|ESP32 WiFi Bluetooth|1|₹299|[Amazon](https://amzn.in/d/0fkaqaUV)|
|6V N20 600 RPM Motor|1|₹149|[Robocraz](https://robocraze.com/products/6v-n20-600-rpm-miniature-gear-motor)|
|3.7V 2500mAh 18650 Li-Ion Battery|2|₹500|[Robocraze](https://robocraze.com/products/3-7v-2500mah-18650-li-ion-battery)|
|TP4056 Type-C Mini Charger|1|₹49|[Robocraz](https://robocraze.com/products/tp4056-battery-charger-c-type-module-with-protection-1)|
|LM2596 DC-DC Buck Converter|1|₹79|[Robocraze](https://robocraze.com/products/lm2596-dc-dc-buck-module)|
|SG90 Micro Servo Motor|1|₹99|[robocraze](https://robocraze.com/products/sg90-micro-servo-motor)|
|DRV8833 2-Channel Driver|1|₹99|[Robocraze](https://robocraze.com/products/drv8833-2-channel-dc-motor-driver)|
|TSOP38238 IR Receiver Diode|2|₹50|[QuartzComponents](https://quartzcomponents.com/products/tsop38238-ir-receiver-diode-38khz)|
|M3x4mm Heat Set Inserts|20|₹80|[Robu](https://robu.in/product/m3-x-4-mm-brass-heat-set-knurl-threaded-round-insert-nut-25-pcs/)|
|M3 x 6mm Screw|20|₹60|[RoboticsDNA](roboticsdna.in/product/m3-x-6mm-bolt-ss-304-csk-countersunk-philips-head-25-pcs/)|

#### Approximate Car Cost: **₹4,000**

### Remote

|**Item**|Number|Approx. Price|Link|
|--------|-----|-------------|---|
|ESP32 WiFi Bluetooth|1|₹299|[Amazon](https://amzn.in/d/03HUoLg3)|
|Tactile momentary push button|12|₹36|[amazon](https://amzn.in/d/093r9Vyk)|
|3.7V 1500mAh LiPo Rechargeable Battery Model|1|₹350|[robocraze](https://robocraze.com/products/3-7v-1500mah-lipo-rechargeable-battery-model-uk-523450p?_pos=1&_sid=d113ab62b&_ss=r)|
|TP4056 Type-C Mini|1|₹49|[robocraze](https://robocraze.com/products/tp4056-battery-charger-c-type-module-with-protection-1)|
|3.3V Small Piezo Buzzer|1|₹30|https://robocraze.com/products/3-volts-buzzer-small|
|5mm Common Anode RGB LED 4Pin Through Hole White Diffused LED|1|₹15|[robocraze](https://robocraze.com/products/5mm-common-anode-rgb-led-4pin-pack-of-10)|
|2.8 Inch TFT LCD Display|1|₹780|[robocraze](https://robocraze.com/products/smartelex-2-8-inch-tft-lcd-display-240x320-color-lcd-screen-for-diy-electronics)|
|m3x4mm heat set inserts|12|₹80|[Rubu](https://robu.in/product)|m3-x-4-mm-brass-heat-set-knurl-threaded-round-insert-nut-25-pcs/|
|M3 x 6mm screw|12|₹60|[RoboticsDNA](roboticsdna.in/product/m3-x-6mm-bolt-ss-304-csk-countersunk-philips-head-25-pcs/)
#### Approximate Remote Cost
**₹1700**

### Total Approximate Cost

|Part|Cost|
|-----|-----|
|Car|₹4000|
|Remote|₹1700|

# Future Upgrade ⏫

* Leader Board 
* Anti-Cheat
* challenge etc

Thats it for now.
> **NOTE:** you need to place a black transparent plastic thin sheet or something on the front window where the camera is placed and in the remote for the switch you can either use this Prototyping PCB or you can custom print a pcb board everything on car and remote is either snap fit or screwable and only the led , ir and batter need glue-gun/tap
