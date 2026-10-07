# kaack/elrs-joystick-control

> Картка виставки. Зал: [Радіо](../halls/radio.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [kaack/elrs-joystick-control](https://github.com/kaack/elrs-joystick-control) |
| Локальна тека | `fpv-library/repos/elrs-joystick-control-Use-USB-joysticks-to-remote-control-a-dr` |
| У бібліотеці | keep |
| Категорії каталогу | `radio`, `elrs` |
| Зірки (каталог) | 307 |
| Оновлено upstream | 2023-10-12 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This application allows you to use one or more joysticks to remote control a drone or airplane. You can use any device that identifies as a gamepad when connected to a computer over USB. (e.g. XBox Controller, ThrustMaster Warthog, etc)

_З README.md, без переказу._

## Для чого

Use USB joysticks to remote control a drone or airplane

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Use USB joysticks to remote control a drone or airplane

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `build-raspbian32-linux-armhf.sh`
- `cmd/`
- `Dockerfile.linux-amd64`
- `Dockerfile.windows-amd64`
- `go.mod`
- `go.sum`
- `go.work`
- `go.work.sum`
- `images/`
- `LICENSE`
- `LICENSE-FAIR-SOURCE`
- `LICENSE-GPL`
- `pkg/`
- `README.md`
- `scripts/`
- `webapp/`

Типи файлів за вибіркою (136 файлів, глибина до 3): Go (97), (без суфікса) (6), JavaScript (6), JSON (5), .png (5), .sum (3).

Фрагмент README про будову:

### How It Works

The application reads the raw inputs from one or more USB gamepad devices. It takes these
inputs, converts them to Crossfire format (CRSF), and sends them to an RC Transmitter (TX) module.

The TX then sends the control signals over air to the drone.  Both the USB control devices and the
RC Transmitter module must be connected to the same computer where the application is running on.

## Що треба

- Маніфести збірки: Go (go.mod).

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### How to power the ELRS transmitter module

There are a few ways you can power the transmitter module without connecting it to the JR bay of an existing radio.


  * **USB Power** - First, you can power the ELRS transmitter using the USB connector (if it has one). The RF output power will be
limited when using USB power. It's very likely that you will not be able to go over 100 milli-watts of RF output power.
That's still plenty of power for most flying. But beware, if you set the transmitter's RF output too high, it may 
exceed the power supply from the USB connection. This can cause the module to brown-out, and reboot itself. 
It will keep rebooting, and shutting down. If this happens to you, you will need to connect the module to a higher wattage power supply, and revert the settings.


  * **XT30 DC input** - The second approach is to use the module's XT30 DC input (if it has one). But beware, some modules may not have protection
to isolate the XT30 DC input from rest of the circuitry. Early versions of Radio-Master ELRS Ranger 
transmitters had this issue. Some pilots damaged their radios when they connected the XT30 input at the same time they had the module 
connected to the JR bay of the radio. So, don't do that.


  * **JR Bay VCC / GND pins** - The third and final approach is to use the JR bay `VCC` / `GND` pins. Most ELRS transmitter modules accept between 5V and 12V across the
`VCC` / `GND` pins. You can connect a 2S LiPo battery directly to the these pins. ELRS transmitter modules have an internal voltage
regulator, so it should be safe.
### How to use the application

When the application starts, it exposes a Web-UI on port 3000, and a gRPC service on port 10000.

For most use-cases, the Web-UI will give you all the functionality you will need. From there you can do things like
configure the inputs and outputs, setup telemetry widgets, and start/stop the radio control link.

Behind the scenes, the Web-UI uses the gRPC service to interact with the application itself.
You can use the gRPC service directly as well, if you want to interact with the application programmatically.
### How to use the Web-UI

When you run the application locally, you can access the Web-UI through a browser over at https://localhost:3000.

The Web-UI has multiple pages, that allow you to configure and manage the application.
### How to use the gRPC service

In order to use the gRPC service, you will need a gRPC client. There are a few of those out there like Postman, or [GRPC-UI](https://github.com/fullstorydev/grpcui/releases).

Here is are some instructions for GRPC-UI

1. Download and extract the GRPC-UI binary from their [GitHub releases](https://github.com/fullstorydev/grpcui/releases).
    * Put the `grpcui` binary somewhere in your path
2. Start the **elrs_joystick_control** application (by default it listens on port 10000)
    ```shell
    $ elrs_joystick_control
     gRPC server listenting on port 10000
    ```
3. Start GRPC-UI like this
    ```shell
    $ grpcui -plaintext localhost:10000
     gRPC Web UI available at http://127.0.0.1:53885/
    ```

From GRPC-UI, you can call the methods exposed by the application's gRPC service. The following main methods are available:

* **setConfig** - Receives (and validates) a JSON file containing the full configuration, and stores it in memory
* **getConfig** - Retrieves the full configuration from memory, and sends it as a JSON file

* **startLink** - starts the link with the RF transmitter
* **stopMixer** - stops the link with the RF transmitter

* **startHttp** - Starts the Web-UI HTTP server
* **stopHTTP** - Stops the Web-UI HTTP server

* **getGamepads** - Returns a list of raw input devices connected (joysticks, gamepads, etc)
* **getTransmitters** - Returns a list of available serial ports

There are also a few other data streaming methods available:

* **getEvalStream** - Starts a data stream with the values for all inputs/outputs as they are config is evaluated live
* **getTransmitterStream** - Starts a data stream with the values of all 16 channels as they are received live by the RF transmitter.
* **getGamepadStream** - Starts a data stream with the values of all axes, and buttons as they are output by a gamepad
* **getTelemetryStream** - Starts a data stream with the values of all telemetry frames that are output by the ELRS TX
* **getLinkStream** - Starts a data stream with values for link stats such as count of sent/received frames, and errors.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/elrs-joystick-control-Use-USB-joysticks-to-remote-control-a-dr/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/kaack__elrs-joystick-control.md`.
