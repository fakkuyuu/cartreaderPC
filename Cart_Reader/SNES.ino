//******************************************
// SUPER NINTENDO MODULE
//******************************************
#ifdef ENABLE_SNES

/******************************************
  Defines
 *****************************************/
// SNES Hi and LoRom, SA is HI with different Sram dumping
#define EX 4
#define SA 3
#define HI 1
#define LO 0

/******************************************
   Variables
 *****************************************/
// Define SNES Cart Reader Variables
int romSpeed = 0;  // 0 = SlowROM, 3 = FastROM
int romChips = 0;  // 0 = ROM only, 1 = ROM & RAM, 2 = ROM & Save RAM,  3 = ROM & DSP1, 4 = ROM & RAM & DSP1, 5 = ROM & Save RAM & DSP1, 19 = ROM & SFX
// 227 = ROM & RAM & GameBoy data, 243 = CX4, 246 = ROM & DSP2
byte romSizeExp = 0;  // ROM-Size Exponent
boolean NP = false;
byte cx4Type = 0;
byte cx4Map = 0;

/******************************************
  Menu
*****************************************/
// SNES/Nintendo Power SF Memory start menu
static const char snsMenuItem1[] PROGMEM = "SNES/SFC cartridge";
static const char snsMenuItem2[] PROGMEM = "SF Memory Cassette";
static const char snsMenuItem3[] PROGMEM = "Satellaview BS-X";
static const char snsMenuItem4[] PROGMEM = "Sufami Turbo";
static const char snsMenuItem5[] PROGMEM = "Game Processor RAM";
static const char snsMenuItem6[] PROGMEM = "Flash repro";
#ifdef OPTION_CLOCKGEN_CALIBRATION
static const char snsMenuItem7[] PROGMEM = "Calibrate Clock";
static const char* const menuOptionsSNS[] PROGMEM = { snsMenuItem1, snsMenuItem2, snsMenuItem3, snsMenuItem4, snsMenuItem5, snsMenuItem6, snsMenuItem7 };
#else
static const char* const menuOptionsSNS[] PROGMEM = { snsMenuItem1, snsMenuItem2, snsMenuItem3, snsMenuItem4, snsMenuItem5, snsMenuItem6, FSTRING_RESET };
#endif

// SNES menu items
static const char SnesMenuItem4[] PROGMEM = "Test SRAM";
static const char SnesMenuItem6[] PROGMEM = "Force cart type";
static const char* const menuOptionsSNES[] PROGMEM = { FSTRING_READ_ROM, FSTRING_READ_SAVE, FSTRING_WRITE_SAVE, SnesMenuItem4, FSTRING_REFRESH_CART, SnesMenuItem6, FSTRING_RESET };

// Manual config menu items
static const char confMenuItem1[] PROGMEM = "Use header info";
static const char confMenuItem2[] PROGMEM = "4MB LoROM 256K SRAM";
static const char confMenuItem3[] PROGMEM = "4MB HiROM 64K SRAM";
static const char confMenuItem4[] PROGMEM = "6MB ExROM 256K SRAM";
static const char* const menuOptionsConfManual[] PROGMEM = { confMenuItem1, confMenuItem2, confMenuItem3, confMenuItem4, FSTRING_RESET };

#if (defined(ENABLE_FLASH) && defined(ENABLE_FLASH8))
// Repro menu items
static const char reproMenuItem1[] PROGMEM = "CFI LoROM";
static const char reproMenuItem2[] PROGMEM = "CFI HiROM";
static const char reproMenuItem3[] PROGMEM = "LoROM (P0)";
static const char reproMenuItem4[] PROGMEM = "HiROM (P0)";
static const char reproMenuItem5[] PROGMEM = "ExLoROM (P1)";
static const char reproMenuItem6[] PROGMEM = "ExHiROM (P1)";
static const char* const menuOptionsRepro[] PROGMEM = { reproMenuItem1, reproMenuItem2, reproMenuItem3, reproMenuItem4, reproMenuItem5, reproMenuItem6, FSTRING_RESET };

// CFI ROM config
static const char reproCFIItem1[] PROGMEM = "1x 2MB";
static const char reproCFIItem2[] PROGMEM = "2x 2MB";
static const char reproCFIItem3[] PROGMEM = "1x 4MB";
static const char reproCFIItem4[] PROGMEM = "2x 4MB";
static const char reproCFIItem5[] PROGMEM = "4x 2MB";
static const char reproCFIItem6[] PROGMEM = "1x 8MB";
static const char* const menuOptionsReproCFI[] PROGMEM = { reproCFIItem1, reproCFIItem2, reproCFIItem3, reproCFIItem4, reproCFIItem5, reproCFIItem6, FSTRING_RESET };

/* ROM file order
  static const char reproEXItem1[] PROGMEM = "ExROM (CDAB)";
  static const char reproEXItem2[] PROGMEM = "standard (ABCD)";
  static const char* const menuOptionsReproEX[] PROGMEM = { reproEXItem1, reproEXItem2, FSTRING_RESET };
*/

/*boolean reproEXMenu() {
  boolean fileOrder = 0;
  // create menu with title and 3 options to choose from
  unsigned char snsReproEX;
  // Copy menuOptions out of progmem
  snsReproEX = chooseFlashMenuOption(F("ROM file order"), menuOptionsReproEX, 3);

  // wait for user choice to come back from the question box menu
  switch (snsReproEX) {
    case 0:
      fileOrder = 1;
      break;
    case 1:
      fileOrder = 0;
      break;
    case 2:
      resetArduino();
      break;
  }
  return fileOrder;
  }*/

// Setup number of flashroms
void reproCFIMenu() {
  boolean reversed = 1;
  // create menu with title and 7 options to choose from
  unsigned char snsReproCFI;
  // Copy menuOptions out of progmem
  snsReproCFI = chooseFlashMenuOption(F("Select Flash Config"), menuOptionsReproCFI, 7);

  // wait for user choice to come back from the question box menu
  switch (snsReproCFI) {
    case 0:
      setupCFI();
      flashSize = 2097152;
      writeCFI_Flash(1, 1, 0);
      verifyFlash(1, 1, 0);
      break;

    case 1:
      setupCFI();
      flashSize = 4194304;
      // Write first rom chip
      writeCFI_Flash(1, 2, 0);
      verifyFlash(1, 2, 0);
      delay(300);

      // Switch to second ROM chip, see flash.ino low level functions line 811
      // LoROM
      if (mapping == 1)
        mapping = 122;
      // HiROM
      else if (mapping == 2)
        mapping = 222;

      // Write second rom chip
      display_Clear();
      writeCFI_Flash(2, 2, 0);
      verifyFlash(2, 2, 0);
      break;

    case 2:
      setupCFI();
      flashSize = 4194304;
      writeCFI_Flash(1, 1, 0);
      verifyFlash(1, 1, 0);
      break;

    case 3:
      //reversed = reproEXMenu();
      setupCFI();
      flashSize = 8388608;
      // Write first rom chip
      writeCFI_Flash(1, 2, reversed);
      verifyFlash(1, 2, reversed);
      delay(300);

      // Switch to second ROM chip, see flash.ino low level functions line 811
      // LoROM
      if (mapping == 1)
        mapping = 124;
      // HiROM
      else if (mapping == 2)
        mapping = 224;

      // Write second rom chip
      display_Clear();
      writeCFI_Flash(2, 2, reversed);
      verifyFlash(2, 2, reversed);
      break;

    case 4:
      //reversed = reproEXMenu();
      setupCFI();
      flashSize = 8388608;
      // Write first rom chip
      writeCFI_Flash(1, 4, reversed);
      verifyFlash(1, 4, reversed);
      delay(300);

      // Switch to second ROM chip, see flash.ino low level functions line 811
      // LoROM
      if (mapping == 1)
        mapping = 122;
      // HiROM
      else if (mapping == 2)
        mapping = 222;

      // Write second rom chip
      display_Clear();
      writeCFI_Flash(2, 4, reversed);
      verifyFlash(2, 4, reversed);

      // Switch to third ROM chip
      // LoROM
      if (mapping == 122)
        mapping = 124;
      // HiROM
      else if (mapping == 222)
        mapping = 224;

      // Write second rom chip
      display_Clear();
      writeCFI_Flash(3, 4, reversed);
      verifyFlash(3, 4, reversed);

      // Switch to fourth ROM chip
      // LoROM
      if (mapping == 124)
        mapping = 142;
      // HiROM
      else if (mapping == 224)
        mapping = 242;

      // Write second rom chip
      display_Clear();
      writeCFI_Flash(4, 4, reversed);
      verifyFlash(4, 4, reversed);
      break;

    case 5:
      //reversed = reproEXMenu();
      setupCFI();
      flashSize = 8388608;
      writeCFI_Flash(1, 1, reversed);
      verifyFlash(1, 1, reversed);
      break;

    case 6:
      resetArduino();
      break;
  }

  // Prints string out of the common strings array either with or without newline
  print_STR(press_button_STR, 0);
  updateDisplayAndWait();
  resetArduino();
}

// SNES repro menu
void reproMenu() {
  // create menu with title and 7 options to choose from
  unsigned char snsRepro;
  // Copy menuOptions out of progmem
  snsRepro = chooseFlashMenuOption(F("Select Repro Type"), menuOptionsRepro, 7);

  // wait for user choice to come back from the question box menu
  switch (snsRepro) {
    case 0:
      // CFI LoROM
      mapping = 1;
      reproCFIMenu();
      break;

    case 1:
      // CFI HiROM
      mapping = 2;
      reproCFIMenu();
      break;

    case 2:
      // LoRom
      clearAndUpdateDisplay();
      mapping = 1;
      setup_Flash8();
      id_Flash8();
      wait();
      mode = CORE_FLASH8;
      break;

    case 3:
      // HiRom
      clearAndUpdateDisplay();
      mapping = 2;
      setup_Flash8();
      id_Flash8();
      wait();
      mode = CORE_FLASH8;
      break;

    case 4:
      // ExLoRom
      clearAndUpdateDisplay();
      mapping = 124;
      setup_Flash8();
      id_Flash8();
      wait();
      mode = CORE_FLASH8;
      break;

    case 5:
      // ExHiRom
      clearAndUpdateDisplay();
      mapping = 224;
      setup_Flash8();
      id_Flash8();
      wait();
      mode = CORE_FLASH8;
      break;

    case 6:
      resetArduino();
      break;
  }
}
#endif

// SNES start menu
void snsMenu() {
  PcConsole.println(F("[Menu] SNES menu started"));
  // create menu with title and 7 options to choose from
  unsigned char snsCart;
  // Copy menuOptions out of progmem
  snsCart = chooseFlashMenuOption(FS(FSTRING_SELECT_CART_TYPE), menuOptionsSNS, 7);

  // wait for user choice to come back from the question box menu
  switch (snsCart) {
    case 0:
      clearAndUpdateDisplay();
      setup_Snes();
      mode = CORE_SNES;
      break;

#ifdef ENABLE_SFM
    case 1:
      clearAndUpdateDisplay();
      setup_SFM();
      mode = CORE_SFM;
      break;
#endif

#ifdef ENABLE_SV
    case 2:
      clearAndUpdateDisplay();
      setup_SV();
      mode = CORE_SV;
      break;
#endif

#ifdef ENABLE_ST
    case 3:
      clearAndUpdateDisplay();
      setup_ST();
      mode = CORE_ST;
      break;
#endif

#ifdef ENABLE_GPC
    case 4:
      clearAndUpdateDisplay();
      setup_GPC();
      mode = CORE_GPC;
      break;
#endif

#if (defined(ENABLE_FLASH) && defined(ENABLE_FLASH8))
    case 5:
      setup_FlashVoltage();
      reproMenu();
      break;
#endif

    case 6:
#ifdef OPTION_CLOCKGEN_CALIBRATION
      clkcal();
      break;

    case 7:
#endif
      resetArduino();
      break;

    default:
      print_MissingModule();  // does not return
  }
}

// SNES Menu
void snesMenu() {
  // create menu with title and 7 options to choose from
  unsigned char mainMenu;
  // Copy menuOptions out of progmem
  mainMenu = chooseFlashMenuOption(FS(SharedFlashText::textSNESCartReader), menuOptionsSNES, 7);

  // wait for user choice to come back from the question box menu
  switch (mainMenu) {
    case 0:
      {
        display_Clear();
        if (numBanks > 0) {
          // Change working dir to root
          changeToStorageRoot();
          // start reading from cart
          readROM_SNES();
          if (!PcLink::usingPcStorage()) {
            compare_checksum();
            compareCRC("snes.txt", 0, 1, 0);
          }
#ifdef ENABLE_GLOBAL_LOG
          save_log();
#endif
          display_Update();
        } else {
          print_Error(F("Does not have ROM"));
        }
      }
      break;

    case 1:
    case 2:
    case 3:
      if (sramSize > 0) {
        display_Clear();
        if (mainMenu == 3) {
          println_Msg(F("Warning:"));
          println_Msg(F("This can erase"));
          println_Msg(F("your save games"));
          printBlankLine();
          printBlankLine();
          println_Msg(F("Press any button to"));
          println_Msg(F("start sram testing"));
          updateDisplayAndWait();
          display_Clear();
        }
        changeToStorageRoot();
        if (mainMenu == 1) {
          readSRAM();
        } else {
          if (mainMenu == 3) {
            readSRAM();
            eraseSRAM(0x0F);
            eraseSRAM(0xF0);
            writeSRAM(0);
          } else {
            writeSRAM(1);
          }
          unsigned long wrErrors = verifySRAM();
          if (wrErrors != 0) {
            showVerificationErrorCount(wrErrors);
          } else if (mainMenu == 3) {
            println_Msg(F("Restored OK"));
            display_Update();
          } else {
            showVerifiedAndUpdate();
          }
        }
      } else {
        showNoSramError();
      }
      break;

    case 4:
      // For arcademaster1 (Markfrizb) multi-game carts
      // Set reset pin to output (PH0)
      DDRH |= (1 << 0);
      // Switch RST(PH0) to LOW
      PORTH &= ~(1 << 0);

      // Note: It is probably not intended to reset CIC or clocks here
      // But if that's false, uncomment this:
      // stopSnesClocks_resetCic_resetCart();

      showResettingAndUpdate();
      delay(3000);  // wait 3 secs to switch to next game
      resetArduino();
      break;

    case 5:
      confMenuManual();
      clearAndUpdateDisplay();
      break;

    case 6:
      stopSnesClocks_resetCic_resetCart();
      resetArduino();
      break;
  }
  //printBlankLine();
  // Prints string out of the common strings array either with or without newline
  promptAndWaitForButton();
}

// Menu for manual configuration
void confMenuManual() {
  // create menu with title and 5 options to choose from
  unsigned char subMenu;
  // Copy menuOptions out of progmem
  subMenu = chooseFlashMenuOption(F("Choose mapping"), menuOptionsConfManual, 5);

  // wait for user choice to come back from the question box menu
  switch (subMenu) {
    case 0:
      break;

    case 1:
    case 2:
    case 3: {
      static const uint8_t mappingTypes[] PROGMEM = { LO, HI, EX };
      static const uint8_t bankCounts[] PROGMEM = { 128, 64, 96 };
      static const char mappingNames[][6] PROGMEM = { "LoROM", "HiROM", "ExROM" };
      const byte index = subMenu - 1;
      romType = pgm_read_byte(&mappingTypes[index]);
      numBanks = pgm_read_byte(&bankCounts[index]);
      sramSize = subMenu == 2 ? 64 : 256;
      strcpy_P(romName, mappingNames[index]);
      break;
    }

    case 4:
      // Reset
      stopSnesClocks_resetCic_resetCart();
      resetArduino();
      break;
  }
}

void stopSnesClocks_resetCic_resetCart() {
  DDRG |= (1 << 1);    // Set cicrstPin(PG1) to Output
  PORTG |= (1 << 1);   // pull high = reset CIC
  DDRH |= (1 << 0);    // Set RST(PH0) pin to Output
  PORTH &= ~(1 << 0);  // Switch RST(PH0) to LOW
  if (i2c_found) {
    clockgen.output_enable(SI5351_CLK1, 0);  // CPU clock
    clockgen.output_enable(SI5351_CLK2, 0);  // CIC clock
    clockgen.output_enable(SI5351_CLK0, 0);  // master clock
  }
}

/******************************************
   Setup
 *****************************************/
void setup_Snes() {
  // Request 5V
  setVoltage(VOLTS_SET_5V);

  // Set cicrstPin(PG1) to Output
  DDRG |= (1 << 1);
  // Output a high signal until we're ready to start
  PORTG |= (1 << 1);
  // Set cichstPin(PG0) to Input
  DDRG &= ~(1 << 0);

  // Set Address Pins to Output
  //A0-A7
  setupSnesBusR49();
  // Activate Internal Pullup Resistors
  //PORTH |= (1 << 4);

  // Set expand(PG5) to Input
  DDRG &= ~(1 << 5);
  // Activate Internal Pullup Resistors
  //PORTG |= (1 << 5);

  // Set Data Pins (D0-D7) to Input
  setupSnesTailR49();
  //PORTJ &= ~(1 << 0);

  // Adafruit Clock Generator
  initializeClockOffset();

  if (i2c_found) {
    // Set clocks to 4Mhz/1Mhz for better SA-1 unlocking
    clockgen.set_freq(100000000ULL, SI5351_CLK1);  // CPU
    clockgen.set_freq(100000000ULL, SI5351_CLK2);  // CIC
    clockgen.set_freq(400000000ULL, SI5351_CLK0);  // EXT

    // Start outputting master clock, CIC clock
    clockgen.output_enable(SI5351_CLK1, 0);  // no CPU clock yet; seems to affect SA-1 success a lot
    clockgen.output_enable(SI5351_CLK2, 1);  // CIC clock (should go before master clock)
    clockgen.output_enable(SI5351_CLK0, 1);  // master clock

    // Wait for clock generator
    clockgen.update_status();
    delay(500);
  }
#ifdef ENABLE_CLOCKGEN
  else {
    showClockGeneratorMissing();
  }
#endif

  // Start CIC by outputting a low signal to cicrstPin(PG1)
  PORTG &= ~(1 << 1);

  // Wait for CIC reset
  delay(500);

  // Print all the info
  getCartInfo_SNES();

  if (i2c_found) {
    //Set clocks to standard or else SA-1 sram writing will fail
    clockgen.set_freq(2147727200ULL, SI5351_CLK0);
    clockgen.set_freq(357954500ULL, SI5351_CLK1);
    clockgen.set_freq(307200000ULL, SI5351_CLK2);
  }
}

/******************************************
   I/O Functions
 *****************************************/
// Switch control pins to write
void controlOut_SNES() {
  // Switch RD(PH6) and WR(PH5) to HIGH
  PORTH |= (1 << 6) | (1 << 5);
  // Switch CS(PH3) to LOW
  PORTH &= ~(1 << 3);
}

// Switch control pins to read
void controlIn_SNES() {
  // Switch WR(PH5) to HIGH
  PORTH |= (1 << 5);
  // Switch CS(PH3) and RD(PH6) to LOW
  PORTH &= ~((1 << 3) | (1 << 6));
}

/******************************************
   Low level functions
 *****************************************/
// Write one byte of data to a location specified by bank and address, 00:0000
void writeBank_SNES(byte myBank, word myAddress, byte myData) {
  PORTL = myBank;
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTC = myData;

  // Arduino running at 16Mhz -> one nop = 62.5ns
  // Wait till output is stable
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");

  // Switch WR(PH5) to LOW
  PORTH &= ~(1 << 5);

  // Leave WR low for at least 60ns
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");

  // Switch WR(PH5) to HIGH
  PORTH |= (1 << 5);

  // Leave WR high for at least 50ns
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");
}

// Read one byte of data from a location specified by bank and address, 00:0000
byte readBank_SNES(byte myBank, word myAddress) {
  PORTL = myBank;
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;

  // Wait for the Byte to appear on the data bus
  // Arduino running at 16Mhz -> one nop = 62.5ns
  // slowRom is good for 200ns, fastRom is <= 120ns; S-CPU best case read speed: 3.57MHz / 280ns
  // let's be conservative and use 6 x 62.5 = 375ns
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;

  // Read
  byte tempByte = PINC;
  return tempByte;
}

static void readRomBanks_SNES(unsigned int start, unsigned int total, FsFile* file, uint16_t initialAddress) __attribute__((noinline));
static void readRomBanks_SNES(unsigned int start, unsigned int total, FsFile* file, uint16_t initialAddress) {
  uint16_t c = 0;
  uint16_t currByte = initialAddress;

  //Initialize progress bar
  uint32_t processedProgressBar = 0;
  uint32_t totalProgressBar = (uint32_t)(total - start) * 1024;
  startProgressBar(totalProgressBar);

  for (word currBank = start; currBank < total; currBank++) {
    PORTL = currBank;

    // Blink led
    blinkLED();

    currByte = initialAddress;
    while (1) {
      c = 0;
      while (c < 512) {
        PORTF = (currByte & 0xFF);
        PORTK = ((currByte >> 8) & 0xFF);

        // Wait for the Byte to appear on the data bus
        // Arduino running at 16Mhz -> one nop = 62.5ns
        // slowRom is good for 200ns, fastRom is <= 120ns; S-CPU best case read speed: 3.57MHz / 280ns
        // let's be conservative and use 6 x 62.5 = 375ns
        NOP;
        NOP;
        NOP;
        NOP;
        NOP;
        NOP;

        sdBuffer[c] = PINC;
        c++;
        currByte++;
      }
      file->write(sdBuffer, 512);
      blinkLED();

      // exit while(1) loop once the uint16_t currByte overflows from 0xffff to 0 (current bank is done)
      if (currByte == 0) break;
    }

    // update progress bar
    processedProgressBar += 1024;
    draw_progressbar(processedProgressBar, totalProgressBar);
  }
}

void readLoRomBanks(unsigned int start, unsigned int total, FsFile* file) {
  readRomBanks_SNES(start, total, file, 32768);
}

void readHiRomBanks(unsigned int start, unsigned int total, FsFile* file) {
  readRomBanks_SNES(start, total, file, 0);
}

/******************************************
  SNES ROM Functions
******************************************/
static void showChecksumP17_SNES() __attribute__((noinline));
static void showChecksumP17_SNES() {
  print_Msg(FS(FSTRING_CHECKSUM));
  showChecksumAndUpdate();
}

void getCartInfo_SNES() {
  boolean manualConfig = 0;

  //Prime SA1 cartridge
  PORTL = 192;
  for (uint16_t currByte = 0; currByte < 1024; currByte++) {
    PORTF = currByte & 0xFF;
    PORTK = currByte >> 8;

    // Wait for the Byte to appear on the data bus
    // Arduino running at 16Mhz -> one nop = 62.5ns
    // slowRom is good for 200ns, fastRom is <= 120ns; S-CPU best case read speed: 3.57MHz / 280ns
    // let's be conservative and use 6 x 62.5 = 375ns
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
  }

  // Print start page
  if (checkcart_SNES() == 0) {
    // Checksum either corrupt or 0000
    manualConfig = 1;
    errorLvl = 1;
    rgbLed(red_color);

    display_Clear();
    println_Msg(FS(SharedFlashText::textERROR));
    println_Msg(FS(SharedFlashText::textRomHeaderCorrupt));
    println_Msg(FS(SharedFlashText::textOrMissing));
    printBlankLine();
    printBlankLine();
    println_Msg(FS(SharedFlashText::textPressButtonFor));
    println_Msg(F("manual configuration"));
    println_Msg(F("or powercycle if SA1"));
    updateDisplayAndWait();
    // Wait() clears errors but in this case we still have an error
    errorLvl = 1;
  }

  display_Clear();
  showRomNameLine();

  showRomRevision();

  print_Msg(FS(SharedFlashText::textType));
  if (romType == HI)
    print_Msg(FS(SharedFlashText::textHiROM));
  else if (romType == LO)
    print_Msg(FS(SharedFlashText::textLoROM));
  else if (romType == EX)
    print_Msg(F("ExHiRom"));
  else
    print_Msg(romType);
  print_Msg(FS(FSTRING_SPACE));
  if (romSpeed == 0)
    println_Msg(FS(SharedFlashText::textSlowROM));
  else if (romSpeed == 2)
    println_Msg(FS(SharedFlashText::textSlowROM));
  else if (romSpeed == 3)
    println_Msg(F("FastROM"));
  else
    println_Msg(romSpeed);

  print_Msg(F("ICs: ROM "));
  static const char chipLabel0[] PROGMEM = "ONLY";
  static const char chipLabel1[] PROGMEM = "RAM";
  static const char chipLabel2[] PROGMEM = "SAVE";
  static const char chipLabel3[] PROGMEM = "DSP1";
  static const char chipLabel4[] PROGMEM = "DSP1 RAM";
  static const char chipLabel5[] PROGMEM = "DSP1 SAVE";
  static const char chipLabel6[] PROGMEM = "SuperFX";
  static const char chipLabel7[] PROGMEM = "SA1 RAM";
  static const char chipLabel8[] PROGMEM = "SA1 RAM BATT";
  static const char chipLabel9[] PROGMEM = "SDD1";
  static const char chipLabel10[] PROGMEM = "SDD1 BATT";
  static const char chipLabel11[] PROGMEM = "SRTC RAM BATT";
  static const char chipLabel12[] PROGMEM = "RAM GBoy";
  static const char chipLabel13[] PROGMEM = "CX4";
  static const char chipLabel14[] PROGMEM = "DSP2";
  static const char chipLabel15[] PROGMEM = "SPC RAM BATT";
  static const char chipLabel16[] PROGMEM = "SPC RAM RTC";
  struct ChipLabel { byte id; const char* label; };
  static const ChipLabel chipLabels[] PROGMEM = {
    {0, chipLabel0},
    {1, chipLabel1},
    {2, chipLabel2},
    {3, chipLabel3},
    {4, chipLabel4},
    {5, chipLabel5},
    {19, chipLabel6},
    {20, chipLabel6},
    {21, chipLabel6},
    {26, chipLabel6},
    {52, chipLabel7},
    {53, chipLabel8},
    {67, chipLabel9},
    {69, chipLabel10},
    {85, chipLabel11},
    {227, chipLabel12},
    {243, chipLabel13},
    {246, chipLabel14},
    {245, chipLabel15},
    {249, chipLabel16}
  };
  byte chipIndex = 0;
  for (; chipIndex < sizeof(chipLabels) / sizeof(chipLabels[0]); ++chipIndex) {
    if (romChips == pgm_read_byte(&chipLabels[chipIndex].id)) break;
  }
  if (chipIndex < sizeof(chipLabels) / sizeof(chipLabels[0])) {
    println_Msg(FS((const char*)pgm_read_ptr(&chipLabels[chipIndex].label)));
    if (romChips == 52 || romChips == 53) romType = SA;
  } else {
    printBlankLine();
  }


  printRomSizeLabel();
  if ((romSize >> 3) < 1) {
    print_Msg(1024 * romSize >> 3);
    print_Msg(FS(SharedFlashText::unitKBWithSpace));
  } else {
    print_Msg(romSize >> 3);
    print_Msg(FS(SharedFlashText::unitMBWithSpace));
  }
  print_Msg(F(" ("));
  print_Msg(numBanks);
  println_Msg(F(" banks)"));

  //print_Msg(F("Chips: "));
  //println_Msg(romChips);

  print_Msg(FS(SharedFlashText::textSaveSize));
  print_Msg(sramSize >> 3);
  println_Msg(FS(SharedFlashText::unitKBWithSpace));

  showChecksumP17_SNES();

  // Wait for user input
#if (defined(ENABLE_LCD) || defined(ENABLE_OLED))
  // Prints string out of the common strings array either with or without newline
  promptAndWaitForButton();
#endif
#ifdef ENABLE_SERIAL
  println_Msg(FS(FSTRING_SPACE));
#endif

  // Start manual config
  if (manualConfig == 1) {
    confMenuManual();
  }
}

static bool snesSaveTitleIsUnique(const char* headerCrc) {
  char key[16];
  snprintf(key, sizeof(key), ",%s,%s,", checksumStr, headerCrc);
  uint8_t line = 0;
  uint8_t column = 0;
  bool match = true;
  while (myFile.available()) {
    const int count = myFile.read(sdBuffer, sizeof(sdBuffer));
    if (count <= 0)
      return false;
    for (int i = 0; i < count; ++i) {
      const byte c = sdBuffer[i];
      if (c == '\n') {
        line = (line + 1) % 3;
        column = 0;
        match = true;
      } else if (line == 1 && column < 23) {
        if (column >= 8 && c != key[column - 8])
          match = false;
        if (++column == 23 && match)
          return false;
      }
    }
  }
  return true;
}

void checkAltConf(char crcStr[9]) {
  char tempStr2[5];
  char tempStr3[9];

  if (myFile.open("snes.txt", O_READ)) {
    // Get cart info
    showSearchingDatabase();
    showChecksumP17_SNES();

    bool unique = true;
    const bool hostLookup = myFile.isPc() && PcLink::hasHostSnesLookup();
    if (myFile.isPc()) {
      char pcQuery[14];
      snprintf(pcQuery, sizeof(pcQuery), "%s,%s", checksumStr, crcStr);
      myFile.findRecord(255, pcQuery, nullptr, &unique);
    }
    while (myFile.available()) {
      const uint32_t titlePosition = myFile.curPosition();
      // Skip first line with name
      skip_line(&myFile);

      // Skip over the CRC checksum
      myFile.seekCur(9);

      // Get internal ROM checksum as string
      for (byte j = 0; j < 4; j++) {
        tempStr2[j] = char(myFile.read());
      }
      tempStr2[4] = '\0';

      // Check if checksum string is a match else go to next entry in database
      if (strcmp(tempStr2, checksumStr) == 0) {
        // Skip the , in the file
        myFile.seekCur(1);

        // Read the CRC32 of the SNES header out of database
        for (byte k = 0; k < 8; k++) {
          tempStr3[k] = char(myFile.read());
        }
        tempStr3[8] = '\0';

        print_Msg(F("Header CRC32: "));
        println_Msg(tempStr3);
        display_Update();

        // Skip the , in the file
        myFile.seekCur(1);

        // Read file size
        byte romSize2 = (myFile.read() - 48) * 10 + (myFile.read() - 48);

        // Skip the , in the file
        myFile.seekCur(1);

        // Read number of banks
        byte numBanks2 = (myFile.read() - 48) * 100 + (myFile.read() - 48) * 10 + (myFile.read() - 48);

        // skip CRLF
        myFile.seekCur(2);
        // skip third empty line
        skip_line(&myFile);

        // Some games have the same checksum, so compare CRC32 of header area with database too
        if (strcmp(tempStr3, crcStr) == 0) {
          if ((hostLookup ? unique : snesSaveTitleIsUnique(crcStr)) && myFile.seekSet(titlePosition)) {
            get_line(fileName, &myFile, FILENAME_LENGTH);
            setDbSaveTitle(fileName);
          }
          println_Msg(F("Found"));
          display_Update();
          // Game found, check if ROM sizes differ but only change ROM size if non- standard size found in database, else trust the header to be right and the database to be wrong
          if (((romSize != romSize2) || (numBanks != numBanks2)) && ((romSize2 == 10) || (romSize2 == 12) || (romSize2 == 20) || (romSize2 == 24) || (romSize2 == 40) || (romSize2 == 48))) {
            // Correct size
            println_Msg(F("Correcting size"));
            print_Msg(FS(FSTRING_SIZE));
            print_Msg(romSize);
            print_Msg(F(" -> "));
            print_Msg(romSize2);
            println_Msg(F("Mbit"));
            print_Msg(FS(SharedFlashText::textBanks));
            print_Msg(numBanks);
            print_Msg(F(" -> "));
            println_Msg(numBanks2);
            display_Update();
            delay(1000);
            romSize = romSize2;
            numBanks = numBanks2;
          }
          break;
        }
      }
      // If no match go to next entry
      else {
        // skip rest of line
        myFile.seekCur(18);
        // skip third empty line
        skip_line(&myFile);
      }
    }
    // Close the file:
    closeCurrentFile();
  }
}

// Read header
boolean checkcart_SNES() {
  dbSaveTitle[0] = '\0';
  // set control to read
  dataIn();

  uint16_t headerStart = 0xFFB0;
  byte snesHeader[80];
  PORTL = 0;
  for (uint16_t c = 0, currByte = headerStart; c < 80; c++, currByte++) {
    PORTF = (currByte & 0xFF);
    PORTK = ((currByte >> 8) & 0xFF);

    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;

    snesHeader[c] = PINC;
  }

  // Calculate CRC32 of header
  char crcStr[9];
  formatFixedHex(crcStr, calculateCRC(snesHeader, 80), 8);

  // Get Checksum as string
  formatFixedHex(checksumStr, (uint16_t(snesHeader[0xFFDF - headerStart]) << 8) | snesHeader[0xFFDE - headerStart], 4);

  romType = snesHeader[0xFFD5 - headerStart];
  if ((romType >> 5) != 1) {  // Detect invalid romType byte due to too long ROM name (22 chars)
    romType = LO;             // LoROM   // Krusty's Super Fun House (U) 1.0 & Contra 3 (U)
  } else if (romType == 0x35) {
    romType = EX;  // Check if ExHiROM
  } else if (romType == 0x3A) {
    romType = HI;                                 // Check if SPC7110
  } else if (strcmp("3BB0", checksumStr) == 0) {  // invalid romType due to too long ROM name (Yuyu no Quiz de GO!GO!)
    romType = LO;
  } else {
    romType &= 1;  // Must be LoROM or HiROM
  }

  // Check RomSpeed
  romSpeed = (snesHeader[0xFFD5 - headerStart] >> 4);

  // Check RomChips
  romChips = snesHeader[0xFFD6 - headerStart];

  if (romChips == 69) {
    romSize = 48;
    numBanks = 96;
    romType = HI;
  } else if (romChips == 67) {
    romSize = 32;
    numBanks = 64;
    romType = HI;
  } else if (romChips == 243) {
    cx4Type = snesHeader[0xFFC9 - headerStart] & 0xF;
    if (cx4Type == 2) {  // X2
      romSize = 12;
      numBanks = 48;
    } else if (cx4Type == 3) {  // X3
      romSize = 16;
      numBanks = 64;
    }
  } else if ((romChips == 245) && (romType == HI)) {
    romSize = 24;
    numBanks = 48;
  } else if ((romChips == 249) && (romType == HI)) {
    romSize = 40;
    numBanks = 80;
  } else {
    // Check RomSize
    byte romSizeExp = snesHeader[0xFFD7 - headerStart] - 7;
    romSize = 1;
    while (romSizeExp--)
      romSize *= 2;

    if ((romType == EX) || (romType == SA)) {
      numBanks = long(romSize) * 2;
    } else {
      numBanks = (long(romSize) * 1024 * 1024 / 8) / (32768 + (long(romType) * 32768));
    }
  }

  //Check SD card for alt config, pass CRC32 of snesHeader but filter out 0000 and FFFF checksums
  if (!(strcmp(checksumStr, "0000") == 0) && !(strcmp(checksumStr, "FFFF") == 0)) {
    checkAltConf(crcStr);
  }

  // Get name
  byte myLength = buildRomName(romName, &snesHeader[0xFFC0 - headerStart], 21);

  // If name consists out of all japanese characters use game code
  if (myLength == 0) {
    // Get rom code
    romName[0] = 'S';
    romName[1] = 'H';
    romName[2] = 'V';
    romName[3] = 'C';
    romName[4] = '-';
    for (unsigned int i = 0; i < 4; i++) {
      byte myByte;
      myByte = snesHeader[0xFFB2 + i - headerStart];
      if (((myByte >= '0' && myByte <= '9') || (myByte >= 'A' && myByte <= 'z')) && myLength < 4) {
        romName[myLength + 5] = myByte;
        myLength++;
      }
    }
    if (myLength == 0) {
      strcpy(romName, "UNKNOWN");
    } else {
      romName[myLength + 5] = 0;
    }
  }

  // Read sramSizeExp
  byte sramSizeExp;
  if ((romChips == 19) || (romChips == 20) || (romChips == 21) || (romChips == 26)) {
    // SuperFX
    if (snesHeader[0xFFDA - headerStart] == 0x33) {
      sramSizeExp = snesHeader[0xFFBD - headerStart];
    } else {
      if (strncmp(romName, "STARFOX2", 8) == 0) {
        sramSizeExp = 6;
      } else {
        sramSizeExp = 5;
      }
    }
  } else {
    // No SuperFX
    sramSizeExp = snesHeader[0xFFD8 - headerStart];
  }

  // Calculate sramSize
  // Fail states usually have sramSizeExp at 255 (no cart inserted, SA-1 failure, etc)
  if (sramSizeExp != 0 && sramSizeExp != 255) {
    sramSizeExp = sramSizeExp + 3;
    sramSize = 1;
    while (sramSizeExp--)
      sramSize *= 2;
  } else {
    sramSize = 0;
  }

  // Check Cart Country
  //int cartCountry = snesHeader[0xFFD9 - headerStart];

  // ROM Version
  romVersion = snesHeader[0xFFDB - headerStart];

  // Test if checksum is equal to reverse checksum
  if (((word(snesHeader[0xFFDC - headerStart]) + (word(snesHeader[0xFFDD - headerStart]) * 256)) + (word(snesHeader[0xFFDE - headerStart]) + (word(snesHeader[0xFFDF - headerStart]) * 256))) == 65535) {
    if (strcmp("0000", checksumStr) == 0) {
      return 0;
    } else {
      return 1;
    }
  }
  // Either rom checksum is wrong or no cart is inserted
  else {
    return 0;
  }
}

// One block sum, with the original 16-bit wraparound and file-read behavior.
static unsigned int checksumBlock_SNES() __attribute__((noinline));
static unsigned int checksumBlock_SNES() {
  readSdBufferBlock();
  unsigned int sum = 0;
  for (unsigned int c = 0; c < 512; c++) {
    sum += sdBuffer[c];
  }
  return sum;
}

unsigned int calc_checksum(char* fileName, char* folder) {
  unsigned int calcChecksum = 0;
  unsigned int calcChecksumChunk = 0;
  int calcFilesize = 0;
  unsigned long i = 0;
  unsigned long j = 0;

  if (strcmp(folder, "root") != 0)
    sd.chdir(folder);

  // If file exists
  if (myFile.open(fileName, O_READ)) {
    calcFilesize = myFile.fileSize() * 8 / 1024 / 1024;

    // Nintendo Power (SF Memory Cassette)
    // Read up to 0x60000 then add FFs to 0x80000
    if (NP == true) {
      for (i = 0; i < (0x60000 / 512); i++) {
        calcChecksumChunk += checksumBlock_SNES();
        calcChecksum = calcChecksumChunk;
      }
      calcChecksum += 0xF47C;  // FFs from 0x60000-0x80000
    } else if ((calcFilesize == 10) || (calcFilesize == 12) || (calcFilesize == 20) || (calcFilesize == 24)) {
      unsigned long calcBase = 0;
      unsigned long calcMirror = 0;
      byte calcMirrorCount = 0;
      if (calcFilesize > 16)
        calcBase = 2097152;
      else
        calcBase = 1048576;
      calcMirror = myFile.fileSize() - calcBase;
      calcMirrorCount = calcBase / calcMirror;

      // Momotarou Dentetsu Happy Fix 3MB (24Mbit)
      if ((calcFilesize == 24) && (romChips == 245)) {
        for (i = 0; i < (myFile.fileSize() / 512); i++) {
          calcChecksumChunk += checksumBlock_SNES();
        }
        calcChecksum = 2 * calcChecksumChunk;
      } else {
        // Base 8/16 Mbit chunk
        for (j = 0; j < (calcBase / 512); j++) {
          calcChecksumChunk += checksumBlock_SNES();
        }
        calcChecksum = calcChecksumChunk;
        calcChecksumChunk = 0;
        // Add the mirrored chunk
        for (j = 0; j < (calcMirror / 512); j++) {
          calcChecksumChunk += checksumBlock_SNES();
        }
        calcChecksum += calcMirrorCount * calcChecksumChunk;
      }
    } else if (((calcFilesize == 40) && (romChips == 85)) || calcFilesize == 48) {
      // Daikaijuu Monogatari 2 (5MB), Star Ocean/Tales of Phantasia (6MB)
      for (j = 0; j < (4194304 / 512); j++) {
        calcChecksumChunk += checksumBlock_SNES();
        calcChecksum = calcChecksumChunk;
      }
      calcChecksumChunk = 0;
      const unsigned long mirrorBlocks = calcFilesize == 40 ? (1048576UL / 512) : (2097152UL / 512);
      for (j = 0; j < mirrorBlocks; j++) {
        calcChecksumChunk += checksumBlock_SNES();
      }
      if (calcFilesize == 40)
        calcChecksum += 4 * calcChecksumChunk;
      else
        calcChecksum += 2 * calcChecksumChunk;
    } else {
      //calcFilesize == 2 || 4 || 8 || 16 || 32 || 40 || etc
      for (i = 0; i < (myFile.fileSize() / 512); i++) {
        calcChecksumChunk += checksumBlock_SNES();
        calcChecksum = calcChecksumChunk;
      }
    }
    closeCurrentFile();
    resetStorageDirectory();
    return (calcChecksum);
  } else {
    // Else show error
    print_Error(FS(SharedFlashText::textDUMPROM1ST));
    return 0;
  }
}

boolean compare_checksum() {
  print_Msg(F("Checksum... "));
  display_Update();

  char calcsumStr[5];
  formatFixedHex(calcsumStr, calc_checksum(fileName, folder), 4);
  print_Msg(calcsumStr);

  if (strcmp(calcsumStr, checksumStr) == 0) {
    println_Msg(FS(SharedFlashText::textOK));
    display_Update();
    return 1;
  } else {
    showInvalidChecksumTail();
    display_Update();
    return 0;
  }
}

// Read rom to SD card
static uint16_t sharedRetryAddressR40_SNES;

static void readLoRomRetryWord_SNES(uint8_t* output) {
  for (uint8_t i = 0; i < 2; ++i) {
    const uint16_t address = sharedRetryAddressR40_SNES++;
    PORTF = (uint8_t)address;
    PORTK = (uint8_t)(address >> 8);
    NOP; NOP; NOP; NOP; NOP; NOP;
    output[i] = PINC;
  }
}

// SA-1 and standard HiROM both expose their linear ROM image through
// banks C0-FF. Re-establish the bank and 16-bit address for every 512-byte
// retry chunk, including the transition from one 64 KiB bank to the next.
static void beginC0BankRetry_SNES(uint32_t offset) {
  PORTL = (uint8_t)(0xC0U + (offset >> 16));
  sharedRetryAddressR40_SNES = (uint16_t)offset;
}


// LoROM layouts used by the legacy reader:
// 0 = banks 00+, 1 = banks 80+ for ROMs larger than 3 MiB,
// 2 = the 24-Mbit Derby Stallion/Sound Novel split (00-3F, 80-9F).
static uint8_t loRomRetryLayout;
static void beginExtendedLoRomRetry_SNES(uint32_t offset) {
  const uint32_t bankIndex = offset >> 15;
  uint8_t bank = (uint8_t)bankIndex;
  if (loRomRetryLayout == 1) {
    bank = (uint8_t)(0x80U + bankIndex);
  } else if (loRomRetryLayout == 2 && bankIndex >= 64) {
    bank = (uint8_t)(0x80U + bankIndex - 64U);
  }
  PORTL = bank;
  sharedRetryAddressR40_SNES = (uint16_t)(0x8000U | (offset & 0x7fffU));
}


// ExHiROM retains the legacy physical bank sequence C0-FF then 00-3F.
// The byte cast intentionally matches PORTL's 8-bit bank output.

// S-RTC uses C0-FF for the first 4 MiB and 40+ for the remaining banks,
// matching the two readHiRomBanks() calls in the legacy path.
static void beginSrtcRetry_SNES(uint32_t offset) {
  if (offset < 0x400000UL) {
    PORTL = (uint8_t)(0xC0U + (offset >> 16));
  } else {
    PORTL = (uint8_t)(offset >> 16);
  }
  sharedRetryAddressR40_SNES = (uint16_t)offset;
}


static void setBusInput_SNES() __attribute__((noinline));
static void setBusInput_SNES() {
  dataIn();
  controlIn_SNES();
}

static void writeSnesRegister_SNES(word address, byte value) {
  dataOut();
  controlOut_SNES();
  writeBank_SNES(0, address, value);
  setBusInput_SNES();
}

// S-DD1's legacy reader selects one 1 MiB ROM page in the F0-FF window
// using SOMap ($4807), then reads all sixteen 64 KiB banks from that page.
static uint8_t sdd1RetryMap = 0xff;
static void beginSdd1Retry_SNES(uint32_t offset) {
  const uint8_t map = (uint8_t)(offset >> 20);
  if (map != sdd1RetryMap) {
    writeSnesRegister_SNES(0x4807, map);
    sdd1RetryMap = map;
  }
  PORTL = (uint8_t)(0xF0U + ((offset >> 16) & 0x0fU));
  sharedRetryAddressR40_SNES = (uint16_t)offset;
}


static uint8_t spc7110OriginalDMap;
static uint8_t spc7110OriginalEMap;
static uint8_t spc7110OriginalFMap;
static uint8_t spc7110OriginalSramMap;
static uint8_t spc7110RetryMode = 0xff;

// SPC7110 exposes D0-DF, E0-EF and F0-FF as separate 1 MiB windows.
// Reapply the captured baseline and the appropriate F-window page whenever
// the requested frame moves to a different part of the ROM.
static void setSpc7110RetryMode_SNES(uint8_t mode) {
  if (mode == spc7110RetryMode) return;
  const uint8_t fMap = (mode == 2) ? 3 : spc7110OriginalFMap;
  const uint8_t sramMap = (mode == 0) ? spc7110OriginalSramMap : 0xff;
  writeSnesRegister_SNES(0x4831, spc7110OriginalDMap);
  writeSnesRegister_SNES(0x4832, spc7110OriginalEMap);
  writeSnesRegister_SNES(0x4833, fMap);
  writeSnesRegister_SNES(0x4834, sramMap);
  spc7110RetryMode = mode;
}

static void beginSpc7110Retry_SNES(uint32_t offset) {
  uint8_t bank;
  if (offset < 0x100000UL) {
    setSpc7110RetryMode_SNES(0);
    bank = (uint8_t)(0xC0U + (offset >> 16));
  } else if (offset < 0x200000UL) {
    setSpc7110RetryMode_SNES(0);
    bank = (uint8_t)(0xD0U + ((offset - 0x100000UL) >> 16));
  } else if (offset < 0x300000UL) {
    setSpc7110RetryMode_SNES(1);
    bank = (uint8_t)(0xE0U + ((offset - 0x200000UL) >> 16));
  } else if (offset < 0x400000UL) {
    setSpc7110RetryMode_SNES(1);
    bank = (uint8_t)(0xF0U + ((offset - 0x300000UL) >> 16));
  } else {
    setSpc7110RetryMode_SNES(2);
    bank = (uint8_t)(0xF0U + ((offset - 0x400000UL) >> 16));
  }
  PORTL = bank;
  sharedRetryAddressR40_SNES = (uint16_t)offset;
}

static void writeCx4Mapping_SNES(byte value) __attribute__((noinline));
static void writeCx4Mapping_SNES(byte value) {
  writeSnesRegister_SNES(0x7F52, value);
}
static void prepareCx4Mapping_SNES() __attribute__((noinline));
static void prepareCx4Mapping_SNES() {
  cx4Map = readBank_SNES(0, 32594);
  if ((cx4Type == 2) && (cx4Map != 0)) {
    writeCx4Mapping_SNES(0);
  } else if ((cx4Type == 3) && (cx4Map == 0)) {
    writeCx4Mapping_SNES(1);
  }
}

void readROM_SNES() {
  // Set control
  setBusInput_SNES();

  // Get name, add extension and convert to char array for sd lib
  createFolderAndOpenFile("SNES", "ROM", romName, "sfc");

  // SA-1 ROM is read linearly from banks C0-FF (64 KiB per bank).
  // The retry callback restores the exact bank/address for each 512-byte
  // chunk, including chunks requested again after a CRC16 failure.
  if (((romType == SA && (romChips == 52 || romChips == 53)) ||
       (romType == HI && romChips != 67 && romChips != 69 &&
        romChips != 85 && romChips != 245 && romChips != 249)) &&
      numBanks > 0 && numBanks <= 64 &&
      myFile.romRetry2M((uint32_t)numBanks * 65536UL,
                       beginC0BankRetry_SNES, readLoRomRetryWord_SNES, true)) {
    closeCurrentFile();
    return;
  }

  // Extended/special LoROM layouts and CX4 can also use the common
  // 512-byte CRC16 retry stream. Keep the exact bank order of the legacy
  // readers and retain CX4's original map-register setup/restore.
  if (romType == LO && numBanks > 0 && numBanks <= 256 &&
      (numBanks > 64 || romChips == 243)) {
    const bool isCx4 = (romChips == 243);
    if (isCx4) {
      prepareCx4Mapping_SNES();
    }

    if (numBanks == 96 &&
        ((strcmp("CC86", checksumStr) == 0) ||
         (strcmp("A77B", checksumStr) == 0))) {
      loRomRetryLayout = 2;
    } else if (romSize > 24) {
      loRomRetryLayout = 1;
    } else {
      loRomRetryLayout = 0;
    }

    const bool transferred = myFile.romRetry2M(
        (uint32_t)numBanks * 32768UL,
        beginExtendedLoRomRetry_SNES, readLoRomRetryWord_SNES, true, isCx4 || loRomRetryLayout != 0);
    loRomRetryLayout = 0;

    if (isCx4) {
      // Restore the mapping register exactly as the legacy CX4 path does.
      writeCx4Mapping_SNES(cx4Map);
    }
    if (transferred) {
      closeCurrentFile();
      return;
    }
  }

  // Ordinary LoROM only. The full existing path handles unusual bank maps.
  if (romType == LO && romChips <= 2 && numBanks > 0 && numBanks <= 64) {
    loRomRetryLayout = 0;
    if (myFile.romRetry2M((uint32_t)numBanks * 32768UL,
                         beginExtendedLoRomRetry_SNES, readLoRomRetryWord_SNES, true)) {
      closeCurrentFile();
      return;
    }
  }

  //Dump Derby Stallion '96 (Japan) and Sound Novel Tsukuru (Japan) - Actual Size is 24Mb
  if ((romType == LO) && (numBanks == 96) && ((strcmp("CC86", checksumStr) == 0) || (strcmp("A77B", checksumStr) == 0))) {
    // First 2 MiB: banks 0x00-0x3F; last 1 MiB: banks 0x80-0x9F.
    for (uint8_t bank = 0; bank < 96; bank++) {
      uint8_t currBank = bank < 64 ? bank : bank + 64;
      // Dump the bytes to SD 512B at a time
      for (long currByte = 32768; currByte < 65536; currByte += 512) {
        for (int c = 0; c < 512; c++) {
          sdBuffer[c] = readBank_SNES(currBank, currByte + c);
        }
        writeSdBufferBlock();
      }
    }
  }

  //Dump Low-type ROM
  else if (romType == LO) {
    if (romChips == 243) {                    //0xF3
      prepareCx4Mapping_SNES();
    }
    if (romSize > 24) {
      // ROM > 96 banks (up to 128 banks)
      readLoRomBanks(0x80, numBanks + 0x80, &myFile);
    } else {
      // Read up to 96 banks starting at bank 0×00.
      readLoRomBanks(0, numBanks, &myFile);
    }
    if (romChips == 243) {  //0xF3
      // Restore CX4 Mapping Register
      writeCx4Mapping_SNES(cx4Map);
    }
  }

  // S-DD1: restore the selected 1 MiB SOMap page whenever a retry chunk
  // is read, so a frame does not depend on the previously selected page.
  if (romType == HI && (romChips == 67 || romChips == 69) &&
      (numBanks == 64 || numBanks == 96)) {
    controlIn_SNES();
    const byte originalSOMap = readBank_SNES(0, 0x4807);
    sdd1RetryMap = 0xff;
    const bool transferred = myFile.romRetry2M(
        (uint32_t)numBanks * 65536UL,
        beginSdd1Retry_SNES, readLoRomRetryWord_SNES, true, true);
    if (transferred) {
      writeSnesRegister_SNES(0x4807, originalSOMap);
      sdd1RetryMap = originalSOMap;
      closeCurrentFile();
      return;
    }
    sdd1RetryMap = originalSOMap;
  }

  // Dump SDD1 High-type ROM
  else if ((romType == HI) && (romChips == 69 || romChips == 67)) {
    println_Msg(F("Dumping SDD1 HiRom"));
    display_Update();
    controlIn_SNES();
    byte initialSOMap = readBank_SNES(0, 18439);

    for (word currMemmap = 0; currMemmap < (numBanks / 16); currMemmap++) {

      dataOut();
      controlOut_SNES();

      writeBank_SNES(0, 18439, currMemmap);

      setBusInput_SNES();

      readHiRomBanks(240, 256, &myFile);
      if (currMemmap == 2) display_Clear();  // need more space for the progress bars
    }

    dataOut();
    controlOut_SNES();

    writeBank_SNES(0, 18439, initialSOMap);

    setBusInput_SNES();
  }

  // SPC7110: rebuild the relevant ROM window mapping from the file offset.
  // 245 exposes 3 MiB (C0-DF + E0-EF); 249 exposes 5 MiB
  // (C0-DF + E0-EF + F0-FF mapped first to page 2, then page 3).
  if (romType == HI &&
      ((romChips == 245 && numBanks == 48) ||
       (romChips == 249 && numBanks == 80))) {
    controlIn_SNES();
    spc7110OriginalDMap = readBank_SNES(0, 0x4831);
    spc7110OriginalEMap = readBank_SNES(0, 0x4832);
    spc7110OriginalFMap = readBank_SNES(0, 0x4833);
    spc7110OriginalSramMap = readBank_SNES(0, 0x4834);
    spc7110RetryMode = 0xff;

    const bool transferred = myFile.romRetry2M(
        (uint32_t)numBanks * 65536UL,
        beginSpc7110Retry_SNES, readLoRomRetryWord_SNES, true, true);
    if (spc7110RetryMode != 0xff) {
      // Restore every mapping register to the value present before dumping.
      writeSnesRegister_SNES(0x4831, spc7110OriginalDMap);
      writeSnesRegister_SNES(0x4832, spc7110OriginalEMap);
      writeSnesRegister_SNES(0x4833, spc7110OriginalFMap);
      writeSnesRegister_SNES(0x4834, spc7110OriginalSramMap);
    }
    spc7110RetryMode = 0xff;
    if (transferred) {
      closeCurrentFile();
      return;
    }
  }

  // Dump SPC7110 High-type ROM
  else if ((romType == HI) && ((romChips == 245) || (romChips == 249))) {
    println_Msg(F("Dumping SPC7110 HiRom"));
    display_Update();

    // 0xC00000-0xDFFFFF
    //print_Msg(F("Part 1"));
    display_Update();
    readHiRomBanks(192, 224, &myFile);

    if (numBanks > 32) {
      dataOut();
      controlOut_SNES();
      // Set 0x4834 to 0xFF
      writeBank_SNES(0, 0x4834, 0xFF);

      setBusInput_SNES();

      // 0xE00000-0xEFFFFF
      //print_Msg(F(" 2"));
      display_Update();
      readHiRomBanks(224, 240, &myFile);

      if (numBanks > 48) {
        // 0xF00000-0xFFFFFF
        //print_Msg(F(" 3"));
        display_Update();
        readHiRomBanks(240, 256, &myFile);

        dataOut();
        controlOut_SNES();

        // Set 0x4833 to 3
        writeBank_SNES(0, 0x4833, 3);

        setBusInput_SNES();

        // 0xF00000-0xFFFFFF
        //print_Msg(F(" 4"));
        display_Update();
        readHiRomBanks(240, 256, &myFile);
      }
      //printBlankLine();
      display_Clear();  // need more space due to the 4 progress bars

      // Return mapping registers to initial settings...
      dataOut();
      controlOut_SNES();

      writeBank_SNES(0, 0x4833, 2);
      writeBank_SNES(0, 0x4834, 0);

      setBusInput_SNES();
    }
  }

  // ExHiROM: preserve the legacy C0-FF, then 00-xx physical bank order.
  if (romType == EX && numBanks > 0 && numBanks <= 128 &&
      myFile.romRetry2M((uint32_t)numBanks * 65536UL,
                       beginC0BankRetry_SNES, readLoRomRetryWord_SNES, true, true)) {
    closeCurrentFile();
    return;
  }

  // S-RTC has a split physical layout: C0-FF always contributes the first
  // 4 MiB, then banks 40 onward contribute any remaining ROM banks.
  if (romType == HI && romChips == 85) {
    const uint32_t srtcBanks = (numBanks < 64) ? 64UL : (uint32_t)numBanks;
    if (myFile.romRetry2M(srtcBanks * 65536UL,
                          beginSrtcRetry_SNES, readLoRomRetryWord_SNES, true, true)) {
      closeCurrentFile();
      return;
    }
  }

  // Dump standard High-type ROM
  else if ((romType == HI) || (romType == SA) || (romType == EX)) {
    println_Msg(FS(SharedFlashText::textDumpingHiRom));
    display_Update();

    if (romChips == 85) {
      // Daikaijuu Monogatari 2, keeps out S-RTC register area
      readHiRomBanks(192, 192 + 64, &myFile);
      readHiRomBanks(64, numBanks, &myFile);  // (64 + (numBanks - 64))
    } else {
      readHiRomBanks(192, numBanks + 192, &myFile);
    }
  }

  // Close the file:
  closeCurrentFile();
}

/******************************************
  SNES SRAM Functions
*****************************************/
// Write file to SRAM
void writeSramFileRange_SNES(byte bank, long start, long end, byte) {
  for (long address = start; address < end; ++address) {
    writeBank_SNES(bank, address, myFile.read());
  }
}

void readSramFileRange_SNES(byte bank, long start, long end, byte) {
  for (long address = start; address < end; ++address) {
    myFile.write(readBank_SNES(bank, address));
  }
}

void visitSramBanks_SNES(byte bank, long start, long capacity, long size,
                         void (*visit)(byte, long, long, byte), byte value) {
  if (size <= capacity) {
    visit(bank, start, start + size, value);
    return;
  }
  // Preserve the original whole-bank count for large SRAM.
  while (size >= capacity) {
    visit(bank++, start, start + capacity, value);
    size -= capacity;
  }
}

// Change the SPC7110 SRAM register and restore the data bus to input.
static void setSpc7110SramAccess_SNES(byte value) __attribute__((noinline));
static void setSpc7110SramAccess_SNES(byte value) {
  dataOut();
  writeBank_SNES(0, 0x4830, value);
  dataIn();
}

// Shared SRAM mapping. Write callers already have the data bus set to output.
// SA1 writes use their separate BW-RAM bank setup.
static void visitSramMapping_SNES(void (*visit)(byte, long, long, byte), byte value, bool writing) __attribute__((noinline));
static void visitSramMapping_SNES(void (*visit)(byte, long, long, byte), byte value, bool writing) {
  if (romType == LO) {
    // Sram size
    long lastByte = (long(sramSize) * 128);
    if ((romChips == 19) || (romChips == 20) || (romChips == 21) || (romChips == 26)) {  // SuperFX
      visitSramBanks_SNES(0x70, 0x0000, 0x10000L, lastByte, visit, value);
    } else visitSramBanks_SNES(0x70, 0x0000, 0x8000L, lastByte, visit, value);
  } else if (romType == HI) {
    if ((romChips == 245) || (romChips == 249)) {  // SPC7110 SRAM
      // Configure SPC7110 SRAM Register
      if (writing) writeBank_SNES(0, 0x4830, 0x80);
      else setSpc7110SramAccess_SNES(0x80);
      // Sram size
      long lastByte = (long(sramSize) * 128) + 0x6000;
      visit(0x30, 0x6000, lastByte, value);
      setSpc7110SramAccess_SNES(0);
    } else {
      // Dumping SRAM on HiRom needs CS(PH3) to be high
      PORTH |= (1 << 3);
      // Sram size
      long lastByte = (long(sramSize) * 128);
      visitSramBanks_SNES(0x30, 0x6000, 0x2000L, lastByte, visit, value);
    }
  } else if (romType == EX) {
    // Dumping SRAM on HiRom needs CS(PH3) to be high
    PORTH |= (1 << 3);
    // Sram size
    long lastByte = (long(sramSize) * 128);
    visitSramBanks_SNES(0xB0, 0x6000, 0x2000L, lastByte, visit, value);
  } else if (romType == SA && !writing) {
    // Dumping SRAM on HiRom needs CS(PH3) to be high
    PORTH |= (1 << 3);
    // Sram size
    long lastByte = (long(sramSize) * 128);
    visitSramBanks_SNES(0x40, 0, 0x10000L, lastByte, visit, value);
  }
}

static void writeSa1SramBlocks_SNES(bool fromFile, byte value) __attribute__((noinline));
static void enableSa1BlockZeroP16_SNES() __attribute__((noinline));
static void enableSa1BlockZeroP16_SNES() {
  writeBank_SNES(0, 0x2224, 0);
  writeBank_SNES(0, 0x2226, 0x80);
}

static void writeSa1SramBlocks_SNES(bool fromFile, byte value) {
  long lastByte = (long(sramSize) * 128);
  if (i2c_found) {
    // Enable CPU Clock
    clockgen.output_enable(SI5351_CLK1, 1);
    if (fromFile) clockgen.update_status();
  }

  // Direct writes to BW-RAM (SRAM) in banks 0x40-0x43 don't work
  // Break BW-RAM (SRAM) into 0x2000 blocks
  byte lastBlock = 0;
  lastBlock = lastByte / 0x2000;

  // Writing SRAM on SA1 needs CS(PH3) to be high
  // PORTH |=  (1 << 3);

  // Setup BW-RAM
  // Set 0x2224 (SNES BMAPS) to map SRAM Block 0 to 0x6000-0x7FFF
  enableSa1BlockZeroP16_SNES();
  // Set 0x2228 (SNES BWPA) to 0x00 BW-RAM Write-Protected Area
  writeBank_SNES(0, 0x2228, 0);
  delay(1000);

  // Use $2224 (SNES) to map BW-RAM block to 0x6000-0x7FFF
  // Use $2226 (SNES) to write enable the BW-RAM
  for (byte currBlock = 0; currBlock < lastBlock; currBlock++) {
    // Set 0x2224 (SNES BMAPS) to map SRAM Block to 0x6000-0x7FFF
    writeBank_SNES(0, 0x2224, currBlock);
    // Set 0x2226 (SNES SBWE) to 0x80 Write Enable
    writeBank_SNES(0, 0x2226, 0x80);
    for (long currByte = 0x6000; currByte < 0x8000; currByte += 512) {
      if (fromFile) readSdBufferBlock();
      for (int c = 0; c < 512; c++) {
        writeBank_SNES(0, currByte + c, fromFile ? sdBuffer[c] : value);
      }
    }
  }
}

void writeSRAM(boolean browseFile) {
  if (browseFile) {
    browseRootFileWithPathAndClear(FS(SharedFlashText::textSelectSrmFile));
  } else
    sprintf(filePath, "%s", fileName);

  //open file on sd card
  if (openSelectedFileForRead()) {

    // Set pins to output
    dataOut();

    // Set RST RD WR to High and CS to Low
    controlOut_SNES();

    // LoRom
    visitSramMapping_SNES(writeSramFileRange_SNES, 0, true);
    // SA1
    if (romType == SA) {
      writeSa1SramBlocks_SNES(true, 0);
      // Rewrite first 16 bytes since they often get written incorrectly(fixes Super Bomberman Panic Bomber W), first byte needs to be written last(fixes PGA Tour 96)
      rewindCurrentFile();
      myFile.read(sdBuffer, 16);
      enableSa1BlockZeroP16_SNES();
      for (int c = 15; c >= 0; c--) {
        writeBank_SNES(0, 0x6000 + c,  sdBuffer[c]);
      }
      if (i2c_found) {
        // Disable CPU clock
        clockgen.output_enable(SI5351_CLK1, 0);
      }
    }

    // Set pins to input
    dataIn();

    // Close the file:
    closeAndShowSramWritten();

  } else {
    reportMissingFile();
  }
}

void readSRAM() {
  const uint32_t startedAt = PcLink::hostTime();
  // set control
  controlIn_SNES();

  // Get name, add extension and convert to char array for sd lib
  createDbSaveFolder("SNES", "srm");

  //open file on sd card
  if (!openNamedOutputFile()) {
    fatalSdError();
  }
  visitSramMapping_SNES(readSramFileRange_SNES, 0, false);

  // Close the file:
  closeCurrentFile();

  // Signal end of process
  display_Clear();
  showDbSaveFolder(FS(SharedFlashText::textSavedTo));
  finishDbSaveLog(startedAt);
}

// Check if the SRAM was written without any error
void verifySramFileRange_SNES(byte bank, long start, long end, byte) {
  for (long address = start; address < end; address += 512) {
    readSdBufferBlock();
    for (int c = 0; c < 512; ++c) {
      if (readBank_SNES(bank, address + c) != sdBuffer[c]) ++writeErrors;
    }
  }
}

void verifySramFillRange_SNES(byte bank, long start, long end, byte value) {
  for (long address = start; address < end; address += 512) {
    for (int c = 0; c < 512; ++c) {
      if (readBank_SNES(bank, address + c) != value) ++writeErrors;
    }
  }
}

void fillSramRange_SNES(byte bank, long start, long end, byte value) {
  for (long address = start; address < end; ++address) {
    writeBank_SNES(bank, address, value);
  }
}

unsigned long verifySRAM() {
  //open file on sd card
  if (openSelectedFileForRead()) {

    // Variable for errors
    writeErrors = 0;

    // Set control
    controlIn_SNES();

    visitSramMapping_SNES(verifySramFileRange_SNES, 0, false);
    if (romType == SA) {
      // Reset SA1
      // Set pins to input
      dataIn();
      // Close the file:
      closeCurrentFile();
      if (writeErrors == 0) {
        println_Msg(FS(SharedFlashText::textVerifiedOK));
      } else {
        showVerificationErrorCount(writeErrors);
      }
      updateDisplayAndWait();

      stopSnesClocks_resetCic_resetCart();

      showResettingAndUpdate();
      delay(3000);  // wait 3 secs
      resetArduino();
    }
    // Close the file:
    closeCurrentFile();
    return writeErrors;
  } else {
    print_Error(open_file_STR);
    return 1;
  }
}

// Overwrite the entire SRAM
boolean eraseSRAM(byte b) {
  print_Msg(F("0x"));
  print_Msg(b, HEX);
  print_Msg(F(": "));
  display_Update();

  // Set pins to output
  dataOut();

  // Set control pins
  controlOut_SNES();

  visitSramMapping_SNES(fillSramRange_SNES, b, true);
  // SA1
  if (romType == SA) {
    writeSa1SramBlocks_SNES(false, b);
    // Rewrite First Byte
    enableSa1BlockZeroP16_SNES();
    writeBank_SNES(0, 0x6000, b);

    if (i2c_found) {
      // Disable CPU clock
      clockgen.output_enable(SI5351_CLK1, 0);
    }
  }

  dataIn();

  // Variable for errors
  writeErrors = 0;

  // Set control
  controlIn_SNES();

  visitSramMapping_SNES(verifySramFillRange_SNES, b, false);
  if (writeErrors == 0) {
    printOkLine();
    return 1;
  } else {
    println_Msg(FS(SharedFlashText::textERROR));
    return 0;
  }
  display_Update();
}

#endif

//******************************************
// End of File
//******************************************
