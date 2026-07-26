//! USB command handler for OpenFlash RP2040 firmware
//! 
//! Handles USB protocol commands for parallel NAND, SPI NAND, SPI NOR, and eMMC interfaces.
//! Requirements: 9.1

use defmt::*;
use embassy_time::Timer;
use embassy_rp::peripherals::SPI0;
use embassy_usb::class::cdc_acm::CdcAcmClass;
use embassy_usb::driver::Driver;

use crate::pio_nand::NandController;
use crate::spi_nor::SpiNorController;

const MAX_PAGE_SIZE: usize = 4352; // 4096 + 256 OOB
const PACKET_SIZE: usize = 64;

/// USB Protocol Commands
#[repr(u8)]
#[derive(Debug, Clone, Copy)]
pub enum Command {
    // General commands (0x01-0x0F)
    Ping = 0x01,
    BusConfig = 0x02,
    Reset = 0x08,
    SetInterface = 0x09,
    
    // Parallel NAND commands (legacy 0x03-0x07, new 0x10-0x1F)
    NandCmd = 0x03,
    NandAddr = 0x04,
    NandReadPage = 0x05,
    NandWritePage = 0x06,
    ReadId = 0x07,
    
    // SPI NOR commands (0x60-0x7F)
    SpiNorReadJedecId = 0x60,
    SpiNorReadSfdp = 0x61,
    SpiNorRead = 0x62,
    SpiNorFastRead = 0x63,
    SpiNorPageProgram = 0x66,
    SpiNorSectorErase = 0x67,
    SpiNorBlockErase32K = 0x68,
    SpiNorBlockErase64K = 0x69,
    SpiNorChipErase = 0x6A,
    SpiNorReadStatus1 = 0x6B,
    SpiNorReadStatus2 = 0x6C,
    SpiNorReadStatus3 = 0x6D,
    SpiNorWriteStatus1 = 0x6E,
    SpiNorWriteStatus2 = 0x6F,
    SpiNorWriteStatus3 = 0x70,
    SpiNorWriteEnable = 0x71,
    SpiNorWriteDisable = 0x72,
    SpiNorReset = 0x73,
}

impl Command {
    fn from_u8(val: u8) -> Option<Self> {
        match val {
            // General
            0x01 => Some(Command::Ping),
            0x02 => Some(Command::BusConfig),
            0x08 => Some(Command::Reset),
            0x09 => Some(Command::SetInterface),
            
            // Parallel NAND (legacy)
            0x03 => Some(Command::NandCmd),
            0x04 => Some(Command::NandAddr),
            0x05 => Some(Command::NandReadPage),
            0x06 => Some(Command::NandWritePage),
            0x07 => Some(Command::ReadId),
            
            // SPI NOR
            0x60 => Some(Command::SpiNorReadJedecId),
            0x61 => Some(Command::SpiNorReadSfdp),
            0x62 => Some(Command::SpiNorRead),
            0x63 => Some(Command::SpiNorFastRead),
            0x66 => Some(Command::SpiNorPageProgram),
            0x67 => Some(Command::SpiNorSectorErase),
            0x68 => Some(Command::SpiNorBlockErase32K),
            0x69 => Some(Command::SpiNorBlockErase64K),
            0x6A => Some(Command::SpiNorChipErase),
            0x6B => Some(Command::SpiNorReadStatus1),
            0x6C => Some(Command::SpiNorReadStatus2),
            0x6D => Some(Command::SpiNorReadStatus3),
            0x6E => Some(Command::SpiNorWriteStatus1),
            0x6F => Some(Command::SpiNorWriteStatus2),
            0x70 => Some(Command::SpiNorWriteStatus3),
            0x71 => Some(Command::SpiNorWriteEnable),
            0x72 => Some(Command::SpiNorWriteDisable),
            0x73 => Some(Command::SpiNorReset),
            
            _ => None,
        }
    }
}

#[repr(u8)]
pub enum Status {
    Ok = 0x00,
    Error = 0x01,
    UnknownCommand = 0xFF,
}

/// Flash interface type
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum FlashInterface {
    ParallelNand = 0x00,
    SpiNand = 0x01,
    Emmc = 0x02,
    SpiNor = 0x03,
}

pub struct UsbHandler<'d, D: Driver<'d>> {
    pub class: CdcAcmClass<'d, D>,
    nand: NandController<'d>,
    spi_nor: Option<SpiNorController<'d, SPI0>>,
    page_buffer: [u8; MAX_PAGE_SIZE],
    current_interface: FlashInterface,
}

impl<'d, D: Driver<'d>> UsbHandler<'d, D> {
    pub fn new(class: CdcAcmClass<'d, D>, nand: NandController<'d>) -> Self {
        Self {
            class,
            nand,
            spi_nor: None,
            page_buffer: [0xFF; MAX_PAGE_SIZE],
            current_interface: FlashInterface::ParallelNand,
        }
    }

    /// Set the SPI NOR controller
    pub fn set_spi_nor(&mut self, spi_nor: SpiNorController<'d, SPI0>) {
        self.spi_nor = Some(spi_nor);
    }

    pub async fn handle_commands(&mut self) {
        let mut cmd_buf = [0u8; PACKET_SIZE];
        
        loop {
            match self.class.read_packet(&mut cmd_buf).await {
                Ok(n) if n > 0 => {
                    self.process_command(&cmd_buf[..n]).await;
                }
                Ok(_) => {}
                Err(_) => {
                    warn!("USB connection lost");
                    break;
                }
            }
        }
    }

    async fn process_command(&mut self, cmd_data: &[u8]) {
        if cmd_data.is_empty() {
            return;
        }

        let cmd_byte = cmd_data[0];
        let args = if cmd_data.len() > 1 { &cmd_data[1..] } else { &[] };

        match Command::from_u8(cmd_byte) {
            // General commands
            Some(Command::Ping) => self.handle_ping().await,
            Some(Command::BusConfig) => self.handle_bus_config(args).await,
            Some(Command::Reset) => self.handle_reset().await,
            Some(Command::SetInterface) => self.handle_set_interface(args).await,
            
            // Parallel NAND commands
            Some(Command::NandCmd) => self.handle_nand_cmd(args).await,
            Some(Command::NandAddr) => self.handle_nand_addr(args).await,
            Some(Command::NandReadPage) => self.handle_read_page(args).await,
            Some(Command::NandWritePage) => self.handle_write_page(args).await,
            Some(Command::ReadId) => self.handle_read_id().await,
            
            // SPI NOR commands
            Some(Command::SpiNorReadJedecId) => self.handle_spi_nor_read_jedec_id().await,
            Some(Command::SpiNorReadSfdp) => self.handle_spi_nor_read_sfdp(args).await,
            Some(Command::SpiNorRead) => self.handle_spi_nor_read(args).await,
            Some(Command::SpiNorFastRead) => self.handle_spi_nor_fast_read(args).await,
            Some(Command::SpiNorPageProgram) => self.handle_spi_nor_page_program(args).await,
            Some(Command::SpiNorSectorErase) => self.handle_spi_nor_sector_erase(args).await,
            Some(Command::SpiNorBlockErase32K) => self.handle_spi_nor_block_erase_32k(args).await,
            Some(Command::SpiNorBlockErase64K) => self.handle_spi_nor_block_erase_64k(args).await,
            Some(Command::SpiNorChipErase) => self.handle_spi_nor_chip_erase().await,
            Some(Command::SpiNorReadStatus1) => self.handle_spi_nor_read_status1().await,
            Some(Command::SpiNorReadStatus2) => self.handle_spi_nor_read_status2().await,
            Some(Command::SpiNorReadStatus3) => self.handle_spi_nor_read_status3().await,
            Some(Command::SpiNorWriteStatus1) => self.handle_spi_nor_write_status1(args).await,
            Some(Command::SpiNorWriteStatus2) => self.handle_spi_nor_write_status2(args).await,
            Some(Command::SpiNorWriteStatus3) => self.handle_spi_nor_write_status3(args).await,
            Some(Command::SpiNorWriteEnable) => self.handle_spi_nor_write_enable().await,
            Some(Command::SpiNorWriteDisable) => self.handle_spi_nor_write_disable().await,
            Some(Command::SpiNorReset) => self.handle_spi_nor_reset().await,
            
            None => {
                warn!("Unknown command: 0x{:02X}", cmd_byte);
                self.send_response(&[Status::UnknownCommand as u8]).await;
            }
        }
    }

    // ========== General Command Handlers ==========

    async fn handle_ping(&mut self) {
        info!("PING");
        self.send_response(&[Command::Ping as u8, Status::Ok as u8]).await;
    }

    async fn handle_bus_config(&mut self, args: &[u8]) {
        if args.len() >= 4 {
            info!("BUS_CONFIG");
            self.send_response(&[Command::BusConfig as u8, Status::Ok as u8]).await;
        } else {
            self.send_response(&[Command::BusConfig as u8, Status::Error as u8]).await;
        }
    }

    async fn handle_reset(&mut self) {
        info!("RESET");
        self.nand.reset().await;
        self.send_response(&[Command::Reset as u8, Status::Ok as u8]).await;
    }

    async fn handle_set_interface(&mut self, args: &[u8]) {
        if !args.is_empty() {
            let iface = match args[0] {
                0x00 => FlashInterface::ParallelNand,
                0x01 => FlashInterface::SpiNand,
                0x02 => FlashInterface::Emmc,
                0x03 => FlashInterface::SpiNor,
                _ => {
                    self.send_response(&[Command::SetInterface as u8, Status::Error as u8]).await;
                    return;
                }
            };
            self.current_interface = iface;
            info!("SET_INTERFACE: {:?}", iface);
            self.send_response(&[Command::SetInterface as u8, Status::Ok as u8]).await;
        } else {
            self.send_response(&[Command::SetInterface as u8, Status::Error as u8]).await;
        }
    }

    // ========== Parallel NAND Command Handlers ==========

    async fn handle_nand_cmd(&mut self, args: &[u8]) {
        if !args.is_empty() {
            let cmd = args[0];
            info!("NAND_CMD: 0x{:02X}", cmd);
            self.nand.send_command(cmd).await;
            self.send_response(&[Command::NandCmd as u8, Status::Ok as u8]).await;
        } else {
            self.send_response(&[Command::NandCmd as u8, Status::Error as u8]).await;
        }
    }

    async fn handle_nand_addr(&mut self, args: &[u8]) {
        if !args.is_empty() {
            let addr = args[0];
            info!("NAND_ADDR: 0x{:02X}", addr);
            self.nand.send_address(addr).await;
            self.send_response(&[Command::NandAddr as u8, Status::Ok as u8]).await;
        } else {
            self.send_response(&[Command::NandAddr as u8, Status::Error as u8]).await;
        }
    }

    async fn handle_read_page(&mut self, args: &[u8]) {
        if args.len() >= 6 {
            let page_addr = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
            let page_size = u16::from_le_bytes([args[4], args[5]]) as usize;
            let size = page_size.min(MAX_PAGE_SIZE);
            
            info!("READ_PAGE: addr={}, size={}", page_addr, size);
            self.nand.read_page(page_addr, &mut self.page_buffer[..size]).await;
            self.send_data_chunked(size).await;
        } else {
            self.send_response(&[Command::NandReadPage as u8, Status::Error as u8]).await;
        }
    }

    async fn handle_write_page(&mut self, args: &[u8]) {
        if args.len() >= 6 {
            let page_addr = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
            let page_size = u16::from_le_bytes([args[4], args[5]]) as usize;
            let size = page_size.min(MAX_PAGE_SIZE);
            
            info!("WRITE_PAGE: addr={}, size={}", page_addr, size);
            
            if self.receive_data_chunked(size).await {
                let success = self.nand.program_page(page_addr, &self.page_buffer[..size]).await;
                if success {
                    self.send_response(&[Command::NandWritePage as u8, Status::Ok as u8]).await;
                } else {
                    warn!("Page program failed at {}", page_addr);
                    self.send_response(&[Command::NandWritePage as u8, Status::Error as u8]).await;
                }
            } else {
                self.send_response(&[Command::NandWritePage as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::NandWritePage as u8, Status::Error as u8]).await;
        }
    }

    async fn handle_read_id(&mut self) {
        info!("READ_ID");
        let id = self.nand.read_id().await;
        let response = [
            Command::ReadId as u8, 
            Status::Ok as u8, 
            id[0], id[1], id[2], id[3], id[4]
        ];
        self.send_response(&response).await;
    }

    // ========== SPI NOR Command Handlers ==========

    /// Handle SPI NOR Read JEDEC ID command (0x60)
    async fn handle_spi_nor_read_jedec_id(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            info!("SPI_NOR_READ_JEDEC_ID");
            let id = spi_nor.read_jedec_id();
            let response = [
                Command::SpiNorReadJedecId as u8,
                Status::Ok as u8,
                id[0], id[1], id[2],
            ];
            self.send_response(&response).await;
        } else {
            self.send_response(&[Command::SpiNorReadJedecId as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Read SFDP command (0x61)
    /// Args: [addr_lo, addr_mid, addr_hi, length_lo, length_hi]
    async fn handle_spi_nor_read_sfdp(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if args.len() >= 5 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], 0]);
                let length = u16::from_le_bytes([args[3], args[4]]) as usize;
                let size = length.min(256);  // Limit SFDP read size
                
                info!("SPI_NOR_READ_SFDP: addr={}, len={}", address, size);
                spi_nor.read_sfdp(address, &mut self.page_buffer[..size]);
                
                // Send header then data
                self.send_response(&[Command::SpiNorReadSfdp as u8, Status::Ok as u8]).await;
                self.send_data_chunked(size).await;
            } else {
                self.send_response(&[Command::SpiNorReadSfdp as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorReadSfdp as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Read command (0x62)
    /// Args: [addr_0, addr_1, addr_2, addr_3, length_lo, length_hi]
    async fn handle_spi_nor_read(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if args.len() >= 6 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                let length = u16::from_le_bytes([args[4], args[5]]) as usize;
                let size = length.min(MAX_PAGE_SIZE);
                
                info!("SPI_NOR_READ: addr=0x{:08X}, len={}", address, size);
                spi_nor.read(address, &mut self.page_buffer[..size]);
                self.send_data_chunked(size).await;
            } else {
                self.send_response(&[Command::SpiNorRead as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorRead as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Fast Read command (0x63)
    /// Args: [addr_0, addr_1, addr_2, addr_3, length_lo, length_hi]
    async fn handle_spi_nor_fast_read(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if args.len() >= 6 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                let length = u16::from_le_bytes([args[4], args[5]]) as usize;
                let size = length.min(MAX_PAGE_SIZE);
                
                info!("SPI_NOR_FAST_READ: addr=0x{:08X}, len={}", address, size);
                spi_nor.fast_read(address, &mut self.page_buffer[..size]);
                self.send_data_chunked(size).await;
            } else {
                self.send_response(&[Command::SpiNorFastRead as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorFastRead as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Page Program command (0x66)
    /// Args: [addr_0, addr_1, addr_2, addr_3, length_lo, length_hi]
    async fn handle_spi_nor_page_program(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if args.len() >= 6 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                let length = u16::from_le_bytes([args[4], args[5]]) as usize;
                let size = length.min(256);  // Page program max 256 bytes
                
                info!("SPI_NOR_PAGE_PROGRAM: addr=0x{:08X}, len={}", address, size);
                
                // Receive data from host
                if self.receive_data_chunked(size).await {
                    let success = spi_nor.page_program(address, &self.page_buffer[..size]).await;
                    if success {
                        self.send_response(&[Command::SpiNorPageProgram as u8, Status::Ok as u8]).await;
                    } else {
                        warn!("SPI NOR page program failed at 0x{:08X}", address);
                        self.send_response(&[Command::SpiNorPageProgram as u8, Status::Error as u8]).await;
                    }
                } else {
                    self.send_response(&[Command::SpiNorPageProgram as u8, Status::Error as u8]).await;
                }
            } else {
                self.send_response(&[Command::SpiNorPageProgram as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorPageProgram as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Sector Erase command (0x67) - 4KB
    /// Args: [addr_0, addr_1, addr_2, addr_3]
    async fn handle_spi_nor_sector_erase(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if args.len() >= 4 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                info!("SPI_NOR_SECTOR_ERASE: addr=0x{:08X}", address);
                
                let success = spi_nor.sector_erase(address).await;
                if success {
                    self.send_response(&[Command::SpiNorSectorErase as u8, Status::Ok as u8]).await;
                } else {
                    warn!("SPI NOR sector erase failed at 0x{:08X}", address);
                    self.send_response(&[Command::SpiNorSectorErase as u8, Status::Error as u8]).await;
                }
            } else {
                self.send_response(&[Command::SpiNorSectorErase as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorSectorErase as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Block Erase 32K command (0x68)
    /// Args: [addr_0, addr_1, addr_2, addr_3]
    async fn handle_spi_nor_block_erase_32k(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if args.len() >= 4 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                info!("SPI_NOR_BLOCK_ERASE_32K: addr=0x{:08X}", address);
                
                let success = spi_nor.block_erase_32k(address).await;
                if success {
                    self.send_response(&[Command::SpiNorBlockErase32K as u8, Status::Ok as u8]).await;
                } else {
                    warn!("SPI NOR block erase 32K failed at 0x{:08X}", address);
                    self.send_response(&[Command::SpiNorBlockErase32K as u8, Status::Error as u8]).await;
                }
            } else {
                self.send_response(&[Command::SpiNorBlockErase32K as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorBlockErase32K as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Block Erase 64K command (0x69)
    /// Args: [addr_0, addr_1, addr_2, addr_3]
    async fn handle_spi_nor_block_erase_64k(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if args.len() >= 4 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                info!("SPI_NOR_BLOCK_ERASE_64K: addr=0x{:08X}", address);
                
                let success = spi_nor.block_erase_64k(address).await;
                if success {
                    self.send_response(&[Command::SpiNorBlockErase64K as u8, Status::Ok as u8]).await;
                } else {
                    warn!("SPI NOR block erase 64K failed at 0x{:08X}", address);
                    self.send_response(&[Command::SpiNorBlockErase64K as u8, Status::Error as u8]).await;
                }
            } else {
                self.send_response(&[Command::SpiNorBlockErase64K as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorBlockErase64K as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Chip Erase command (0x6A)
    async fn handle_spi_nor_chip_erase(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            info!("SPI_NOR_CHIP_ERASE");
            let success = spi_nor.chip_erase().await;
            if success {
                self.send_response(&[Command::SpiNorChipErase as u8, Status::Ok as u8]).await;
            } else {
                warn!("SPI NOR chip erase failed");
                self.send_response(&[Command::SpiNorChipErase as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorChipErase as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Read Status Register 1 command (0x6B)
    async fn handle_spi_nor_read_status1(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            let status = spi_nor.read_status1();
            info!("SPI_NOR_READ_STATUS1: 0x{:02X}", status);
            self.send_response(&[Command::SpiNorReadStatus1 as u8, Status::Ok as u8, status]).await;
        } else {
            self.send_response(&[Command::SpiNorReadStatus1 as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Read Status Register 2 command (0x6C)
    async fn handle_spi_nor_read_status2(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            let status = spi_nor.read_status2();
            info!("SPI_NOR_READ_STATUS2: 0x{:02X}", status);
            self.send_response(&[Command::SpiNorReadStatus2 as u8, Status::Ok as u8, status]).await;
        } else {
            self.send_response(&[Command::SpiNorReadStatus2 as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Read Status Register 3 command (0x6D)
    async fn handle_spi_nor_read_status3(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            let status = spi_nor.read_status3();
            info!("SPI_NOR_READ_STATUS3: 0x{:02X}", status);
            self.send_response(&[Command::SpiNorReadStatus3 as u8, Status::Ok as u8, status]).await;
        } else {
            self.send_response(&[Command::SpiNorReadStatus3 as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Write Status Register 1 command (0x6E)
    /// Args: [value]
    async fn handle_spi_nor_write_status1(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if !args.is_empty() {
                let value = args[0];
                info!("SPI_NOR_WRITE_STATUS1: 0x{:02X}", value);
                spi_nor.write_enable();
                spi_nor.write_status1(value);
                self.send_response(&[Command::SpiNorWriteStatus1 as u8, Status::Ok as u8]).await;
            } else {
                self.send_response(&[Command::SpiNorWriteStatus1 as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorWriteStatus1 as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Write Status Register 2 command (0x6F)
    /// Args: [value]
    async fn handle_spi_nor_write_status2(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if !args.is_empty() {
                let value = args[0];
                info!("SPI_NOR_WRITE_STATUS2: 0x{:02X}", value);
                spi_nor.write_enable();
                spi_nor.write_status2(value);
                self.send_response(&[Command::SpiNorWriteStatus2 as u8, Status::Ok as u8]).await;
            } else {
                self.send_response(&[Command::SpiNorWriteStatus2 as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorWriteStatus2 as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Write Status Register 3 command (0x70)
    /// Args: [value]
    async fn handle_spi_nor_write_status3(&mut self, args: &[u8]) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            if !args.is_empty() {
                let value = args[0];
                info!("SPI_NOR_WRITE_STATUS3: 0x{:02X}", value);
                spi_nor.write_enable();
                spi_nor.write_status3(value);
                self.send_response(&[Command::SpiNorWriteStatus3 as u8, Status::Ok as u8]).await;
            } else {
                self.send_response(&[Command::SpiNorWriteStatus3 as u8, Status::Error as u8]).await;
            }
        } else {
            self.send_response(&[Command::SpiNorWriteStatus3 as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Write Enable command (0x71)
    async fn handle_spi_nor_write_enable(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            info!("SPI_NOR_WRITE_ENABLE");
            spi_nor.write_enable();
            self.send_response(&[Command::SpiNorWriteEnable as u8, Status::Ok as u8]).await;
        } else {
            self.send_response(&[Command::SpiNorWriteEnable as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Write Disable command (0x72)
    async fn handle_spi_nor_write_disable(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            info!("SPI_NOR_WRITE_DISABLE");
            spi_nor.write_disable();
            self.send_response(&[Command::SpiNorWriteDisable as u8, Status::Ok as u8]).await;
        } else {
            self.send_response(&[Command::SpiNorWriteDisable as u8, Status::Error as u8]).await;
        }
    }

    /// Handle SPI NOR Reset command (0x73)
    async fn handle_spi_nor_reset(&mut self) {
        if let Some(ref mut spi_nor) = self.spi_nor {
            info!("SPI_NOR_RESET");
            spi_nor.reset().await;
            self.send_response(&[Command::SpiNorReset as u8, Status::Ok as u8]).await;
        } else {
            self.send_response(&[Command::SpiNorReset as u8, Status::Error as u8]).await;
        }
    }

    // ========== Helper Methods ==========

    async fn send_response(&mut self, data: &[u8]) {
        let _ = self.class.write_packet(data).await;
    }

    async fn send_data_chunked(&mut self, size: usize) {
        let mut offset = 0;
        while offset < size {
            let chunk_size = (size - offset).min(PACKET_SIZE);
            let _ = self.class.write_packet(&self.page_buffer[offset..offset + chunk_size]).await;
            offset += chunk_size;
            // Small delay to prevent USB buffer overflow
            Timer::after_micros(50).await;
        }
    }

    async fn receive_data_chunked(&mut self, size: usize) -> bool {
        let mut offset = 0;
        let mut chunk_buf = [0u8; PACKET_SIZE];
        
        while offset < size {
            match self.class.read_packet(&mut chunk_buf).await {
                Ok(n) => {
                    let copy_size = n.min(size - offset);
                    self.page_buffer[offset..offset + copy_size].copy_from_slice(&chunk_buf[..copy_size]);
                    offset += copy_size;
                }
                Err(_) => return false,
            }
        }
        true
    }
}
