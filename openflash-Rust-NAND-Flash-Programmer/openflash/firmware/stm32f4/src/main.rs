//! OpenFlash STM32F4 Firmware
//! Firmware for NAND/eMMC flash operations via USB
//! Supports: Parallel NAND, SPI NAND, SPI NOR, eMMC
//!
//! STM32F4 advantages over STM32F1:
//! - Higher clock speed (up to 180MHz)
//! - Native USB OTG FS/HS
//! - DMA for faster transfers
//! - More RAM and Flash
//! - Hardware FPU

#![no_std]
#![no_main]

use defmt::*;
use embassy_executor::Spawner;
use embassy_stm32::bind_interrupts;
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::peripherals::USB_OTG_FS;
use embassy_stm32::spi::{Config as SpiConfig, Spi};
use embassy_stm32::usb_otg::{Driver, InterruptHandler};
use embassy_usb::class::cdc_acm::{CdcAcmClass, State};
use embassy_usb::{Builder, Config};
use {defmt_rtt as _, panic_probe as _};

mod emmc;
mod nand_fsmc;
mod spi_nand;
mod spi_nor;
mod usb_handler;

use spi_nor::SpiNorController;
use usb_handler::UsbHandler;

bind_interrupts!(struct Irqs {
    OTG_FS => InterruptHandler<USB_OTG_FS>;
});

static mut DEVICE_DESCRIPTOR: [u8; 256] = [0; 256];
static mut CONFIG_DESCRIPTOR: [u8; 256] = [0; 256];
static mut BOS_DESCRIPTOR: [u8; 256] = [0; 256];
static mut CONTROL_BUF: [u8; 64] = [0; 64];
static mut STATE: Option<State> = None;
static mut EP_OUT_BUFFER: [u8; 256] = [0; 256];

/// Pin assignments for STM32F4
///
/// === USB OTG FS ===
///   PA11 - USB_DM
///   PA12 - USB_DP
///
/// === SPI NAND (SPI1) ===
///   PA5  - SCK
///   PA6  - MISO
///   PA7  - MOSI
///   PA4  - CS#
///
/// === SPI NOR (SPI3) ===
///   PC10 - SCK
///   PC11 - MISO
///   PC12 - MOSI
///   PD2  - CS#
///
/// === eMMC (SPI2) ===
///   PB13 - SCK
///   PB14 - MISO
///   PB15 - MOSI
///   PB12 - CS#
///
/// === Parallel NAND (FSMC) ===
///   PD14 - D0
///   PD15 - D1
///   PD0  - D2
///   PD1  - D3
///   PE7  - D4
///   PE8  - D5
///   PE9  - D6
///   PE10 - D7
///   PD4  - NOE (RE#)
///   PD5  - NWE (WE#)
///   PD7  - NCE2 (CE#)
///   PD11 - CLE (A16)
///   PD12 - ALE (A17)
///   PD6  - R/B#

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let p = embassy_stm32::init(Default::default());
    info!("OpenFlash STM32F4 Firmware v1.6.0");

    // Initialize SPI3 for SPI NOR flash (with DMA support)
    // STM32F4 SPI3 pins: PC10 (SCK), PC11 (MISO), PC12 (MOSI)
    let spi_config = SpiConfig::default();
    let spi = Spi::new_blocking(p.SPI3, p.PC10, p.PC12, p.PC11, spi_config);
    let cs = Output::new(p.PD2, Level::High, Speed::VeryHigh);
    let spi_nor = SpiNorController::new(spi, cs);

    // Create USB OTG FS driver
    let ep_out_buffer = unsafe { &mut EP_OUT_BUFFER };
    let driver = Driver::new_fs(p.USB_OTG_FS, Irqs, p.PA12, p.PA11, ep_out_buffer);

    let mut config = Config::new(0xC0DE, 0xCAFE);
    config.manufacturer = Some("OpenFlash");
    config.product = Some("OpenFlash NAND Programmer");
    config.serial_number = Some("OF-STM32F4-001");
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

    info!("USB OTG FS initialized");

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
async fn usb_task(mut usb: embassy_usb::UsbDevice<'static, Driver<'static, USB_OTG_FS>>) -> ! {
    usb.run().await
}
