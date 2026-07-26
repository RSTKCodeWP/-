//! OpenFlash STM32F1 Firmware
//! Firmware for NAND flash operations via USB
//! Supports: Parallel NAND, SPI NAND, SPI NOR, eMMC

#![no_std]
#![no_main]

use defmt::*;
use embassy_executor::Spawner;
use embassy_stm32::bind_interrupts;
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::peripherals::USB;
use embassy_stm32::spi::{Spi, Config as SpiConfig};
use embassy_stm32::usb::{Driver, InterruptHandler};
use embassy_usb::class::cdc_acm::{CdcAcmClass, State};
use embassy_usb::{Builder, Config};
use {defmt_rtt as _, panic_probe as _};

mod usb_handler;
mod spi_nand;
mod spi_nor;
mod emmc;

use spi_nor::SpiNorController;
use usb_handler::UsbHandler;

bind_interrupts!(struct Irqs {
    USB_LP_CAN1_RX0 => InterruptHandler<USB>;
});

static mut DEVICE_DESCRIPTOR: [u8; 256] = [0; 256];
static mut CONFIG_DESCRIPTOR: [u8; 256] = [0; 256];
static mut BOS_DESCRIPTOR: [u8; 256] = [0; 256];
static mut CONTROL_BUF: [u8; 64] = [0; 64];
static mut STATE: Option<State> = None;

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let p = embassy_stm32::init(Default::default());
    info!("OpenFlash STM32F1 Firmware v1.26.0");

    // Initialize SPI1 for SPI NOR flash
    // STM32F1 SPI1 pins: PA5 (SCK), PA6 (MISO), PA7 (MOSI)
    let spi_config = SpiConfig::default();
    let spi = Spi::new_blocking(p.SPI1, p.PA5, p.PA7, p.PA6, spi_config);
    let cs = Output::new(p.PA4, Level::High, Speed::VeryHigh);
    let spi_nor = SpiNorController::new(spi, cs);

    let driver = Driver::new(p.USB, Irqs, p.PA12, p.PA11);

    let mut config = Config::new(0xC0DE, 0xCAFE);
    config.manufacturer = Some("OpenFlash");
    config.product = Some("OpenFlash NAND Programmer");
    config.serial_number = Some("OF-STM32-001");
    config.max_power = 250;
    config.max_packet_size_0 = 64;
    config.composite_with_iads = true;

    let (device_descriptor, config_descriptor, bos_descriptor, control_buf, state) = unsafe {
        STATE = Some(State::new());
        (
            &mut DEVICE_DESCRIPTOR,
            &mut CONFIG_DESCRIPTOR,
            &mut BOS_DESCRIPTOR,
            &mut CONTROL_BUF,
            STATE.as_mut().unwrap(),
        )
    };

    let mut builder = Builder::new(
        driver,
        config,
        device_descriptor,
        config_descriptor,
        bos_descriptor,
        control_buf,
    );

    let class = CdcAcmClass::new(&mut builder, state, 64);
    let usb = builder.build();

    spawner.spawn(usb_task(usb)).unwrap();

    info!("USB initialized");

    let mut handler = UsbHandler::new(class);
    handler.set_spi_nor(spi_nor);

    loop {
        handler.class.wait_connection().await;
        info!("Host connected");
        handler.handle_commands().await;
        info!("Host disconnected");
    }
}

#[embassy_executor::task]
async fn usb_task(mut usb: embassy_usb::UsbDevice<'static, Driver<'static, USB>>) -> ! {
    usb.run().await
}
