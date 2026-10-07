# iNavFlight/LuaPilot_Taranis_Telemetry

> Картка виставки. Зал: [Радіо](../halls/radio.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [iNavFlight/LuaPilot_Taranis_Telemetry](https://github.com/iNavFlight/LuaPilot_Taranis_Telemetry) |
| Локальна тека | `fpv-library/repos/LuaPilot_Taranis_Telemetry-This-Script-LuaPilot-is-a-nice-Telemetry` |
| У бібліотеці | keep |
| Категорії каталогу | `radio`, `fc` |
| Зірки (каталог) | 13 |
| Оновлено upstream | 2017-10-30 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-2.0 |

## Ідея

This Script LuaPilot is a nice Telemetry screen for Taranis with OpenTX >2.17 and should work with Arducopter (Pixhawk, Fixhawk, AUAV-X2, etc.) and maybe others Flight controllers which are connected to an FrSky D-Receiver & X-Receiver.

Thanks to SockEye, Richardoe, Schicksie, lichtl, ben_&Jace25,Clooney82&fnoopdogg for they Previous Work.

Changelog:

V2: Performance & less Memory Consume, Better Hdg, Distance, Battery Percent Calculation with capacity, Resistance Calk & Voltage Compensation, better Battery Regression Curve , Audio Alerts for LipoVoltage, Consume, Flight mode, Max Average Current & GPS State

V1: Battery Consume, Vspeed, GPS Speed, Hdg, efficiency Calk, Background Task, flexible Setup.

Let’s improve it together and have one nice all in one Taranis Telemetry Script, made Pull Requests or if you have an issue please report it :)

This is Version 2 for the next Version 3…

_З Readme.md, без переказу._

## Для чого

This Script LuaPilot is a nice Telemetry screen for Taranis for INAV

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «inav».


Теми GitHub: `flight-controller`, `inav`, `taranis`, `telemetry`, `uav`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: This Script LuaPilot is a nice Telemetry screen for Taranis for INAV

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `FrSky Reciver Telemetry RS232-TTL Inverter with SPC Cable Diode Directly soldered.JPG`
- `LICENCE`
- `LuaPilot.jpg`
- `LuaPilot.Logo.jpg`
- `Readme.md`
- `SCRIPTS/`

Типи файлів за вибіркою (47 файлів, глибина до 3): .wav (23), .bmp (17), .jpg (3), Markdown (1), (без суфікса) (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Flight controller D-port Setup (only for D-receiver)

1. Connect the Arducopter with a RS232 TTL level converter (not need to be a FrSky, a cheaper one from EBay also works fine (watch for correct specifications)) and connect RS232 TTL level converter with your FrSky Receiver
2. Activate the FrSky D protocol in the parameters for the appropriate port. Baute rate 9kbs
### Flight controller S-port Setup (X-receiver with Arducopter V3.3)

1. Connect the Pixhawk with a RS232 TTL level converter (not need to be a FrSky, a cheaper one from EBay (MAX3232CSE also works fine & is better to solder) and connect RS232 TTL level converter with your FrSky Receiver
2. Buy the FrSky SPC cable, but its only one normal diode and you can soldering the diode direct to the RS 232 TTL converter like https://goo.gl/y9XCq8 and doesn’t need the SPC Adapter
3. Activate the FrSky S protocol in the parameters* for the appropriate port. Baute rate: 57kbs *(APMPlaner2)
### Taranis Setup OpenTX 2.1.6 or newer

1. Make sure you have LUA-Scripting enabled in companion
2. Download the scripts folder from here and copy to the SD card root
3. Optional: Edit with a txt Editor the Downloaded Script to Change the Setup to you own Wishes
3. Start your Taranis, go into your desired Model Settings by short pressing the Menu button
4. Navigate to the last Page by long pressing the page button
5. Delete all Sensors
6. Discovery new Sensors
7. There will be a lot of sensors listed depending on your receiver (d8r, d4r, x8r etc.)
8. Recommend is to check if the sensors Name correct. 
9. Set this lua script as Telemetry screen.
### Optional Setup LuaPilot:

open the script with an txt editor and you can modify at the beginn of the script allot of Parameters.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/LuaPilot_Taranis_Telemetry-This-Script-LuaPilot-is-a-nice-Telemetry/Readme.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/iNavFlight__LuaPilot_Taranis_Telemetry.md`.
