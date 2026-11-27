//******************************************
// SEGA MEGA DRIVE MODULE
//******************************************
// Writes to Sega CD Backup RAM Cart require an extra wire from MRES (B02) to VRES (B27)
#ifdef ENABLE_MD

/******************************************
   Variables
 *****************************************/
unsigned long sramEnd;
word eepSize;
word addrhi;
word addrlo;
word chksum;
boolean is32x = 0;
boolean isSVP = 0;
#if (!defined(ENABLE_FLASH8) && defined(ENABLE_FLASH))
unsigned long flashSize;
unsigned long blank;
#endif
#ifdef ENABLE_FLASH
unsigned long flashSizeCFI[] = {0, 0};
unsigned long totalFlashSizeCFI = 0;
unsigned long chipIdLowCFI[] = {0, 0};
unsigned long chipIdHighCFI[] = {0, 0};
byte totalChipsCFI = 0;
#endif

//***********************************************
// EEPROM SAVE TYPES
// 1 = Acclaim Type 1    [24C02]
// 2 = Acclaim Type 2    [24C02/24C16/24C65]
// 3 = Capcom/SEGA       [24C01]
// 4 = EA                [24C01]
// 5 = Codemasters       [24C08/24C16/24C65]
//***********************************************
byte eepType;

//*********************************************************
// SERIAL EEPROM LOOKUP TABLE
// Format = {chksum, eepType | eepSize}
// chksum is located in ROM at 0x18E (0xC7)
// eepType and eepSize are combined to conserve memory
//*********************************************************
const byte MDSize[] PROGMEM = { 1, 2, 4, 8, 12, 16, 20, 24, 32, 40, 72, 120 };

static const word PROGMEM eepid[] = {
  // ACCLAIM TYPE 1
  0x5B9F, 0x101,  // NBA Jam (J)
  0x694F, 0x101,  // NBA Jam (UE) (Rev 0)
  0xBFA9, 0x101,  // NBA Jam (UE) (Rev 1)
  // ACCLAIM TYPE 2
  0x16B2, 0x102,   // Blockbuster World Videogame Championship II (U)   [NO HEADER SAVE DATA]
  0xCC3F, 0x102,   // NBA Jam Tournament Edition (W) (Rev 0)            [NO HEADER SAVE DATA]
  0x8AE1, 0x102,   // NBA Jam Tournament Edition (W) (Rev 1)            [NO HEADER SAVE DATA]
  0xDB97, 0x102,   // NBA Jam Tournament Edition 32X (W)
  0x7651, 0x102,   // NFL Quarterback Club (W)
  0xDFE4, 0x102,   // NFL Quarterback Club 32X (W)
  0x3DE6, 0x802,   // NFL Quarterback Club '96 (UE)
  0xCB78, 0x2002,  // Frank Thomas Big Hurt Baseball (UE)
  0x6DD9, 0x2002,  // College Slam (U)
  // CAPCOM
  0xAD23, 0x83,  // Mega Man:  The Wily Wars (E)
  0xEA80, 0x83,  // Rockman Megaworld (J)
  // SEGA
  0x760F, 0x83,  // Evander "Real Deal" Holyfield Boxing (JU)
  0x95E7, 0x83,  // Greatest Heavyweights of the Ring (E)
  0x0000, 0x83,  // Greatest Heavyweights of the Ring (J)             [BLANK CHECKSUM 0000]
  0x7270, 0x83,  // Greatest Heavyweights of the Ring (U)
  0xBACC, 0x83,  // Honoo no Toukyuuji Dodge Danpei (J)
  0xB939, 0x83,  // MLBPA Sports Talk Baseball (U)                    [BAD HEADER SAVE DATA]
  0x487C, 0x83,  // Ninja Burai Densetsu (J)
  0x740D, 0x83,  // Wonder Boy in Monster World (B)
  0x0278, 0x83,  // Wonder Boy in Monster World (J)
  0x9D79, 0x83,  // Wonder Boy in Monster World (UE)
  // EA
  0x8512, 0x84,  // Bill Walsh College Football (UE)                  [BAD HEADER SAVE DATA]
  0xA107, 0x84,  // John Madden Football '93 (UE)                     [NO HEADER SAVE DATA]
  0x246A, 0x84,  // John Madden Football '93 (U) (EA Sports)          [NO HEADER SAVE DATA]
  0x5807, 0x84,  // John Madden Football '93 Championship Edition (U) [NO HEADER SAVE DATA]
  0x2799, 0x84,  // NHLPA Hockey '93 (UE) (Rev 0)                     [NO HEADER SAVE DATA]
  0xFA57, 0x84,  // NHLPA Hockey '93 (UE) (Rev 1)                     [NO HEADER SAVE DATA]
  0x8B9F, 0x84,  // Rings of Power (UE)                               [NO HEADER SAVE DATA]
  // CODEMASTERS
  0x7E65, 0x405,   // Brian Lara Cricket (E)                            [NO HEADER SAVE DATA]
  0x9A5C, 0x2005,  // Brian Lara Cricket 96 (E) (Rev 1.0)               [NO HEADER SAVE DATA]
  0xC4EE, 0x2005,  // Brian Lara Cricket 96 (E) (Rev 1.1)               [NO HEADER SAVE DATA]
  0x7E50, 0x805,   // Micro Machines 2 (E) (J-Cart)                     [NO HEADER SAVE DATA]
  0x165E, 0x805,   // Micro Machines '96 (E) (J-Cart) (Rev 1.0/1.1)     [NO HEADER SAVE DATA]
  0x168B, 0x405,   // Micro Machines Military (E) (J-Cart)              [NO HEADER SAVE DATA]
  0x12C1, 0x2005,  // Shane Warne Cricket (E)                           [NO HEADER SAVE DATA]
};

byte eepcount = (sizeof(eepid) / sizeof(eepid[0])) / 2;
word eepdata;

// CD BACKUP RAM
unsigned long bramSize = 0;

// REALTEC MAPPER
boolean realtec = 0;

#if defined(ENABLED_CONFIG)

int segaSram16bit = 0;

#else /* !ENABLED_CONFIG */

#ifndef OPTION_MD_DEFAULT_SAVE_TYPE
#define OPTION_MD_DEFAULT_SAVE_TYPE 0
#endif /* !OPTION_MD_DEFAULT_SAVE_TYPE */

int segaSram16bit = OPTION_MD_DEFAULT_SAVE_TYPE;

#endif /* ENABLED_CONFIG */

//*****************************************
// SONIC & KNUCKLES LOCK-ON MODE VARIABLES
// SnKmode :
// 0 = Not Sonic & Knuckles
// 1 = Only Sonic & Knucles
// 2 = Sonic & Knucles + Sonic1
// 3 = Sonic & Knucles + Sonic2
// 4 = Sonic & Knucles + Sonic3
// 5 = Sonic & Knucles + Other game
//*****************************************
static byte SnKmode = 0;
static unsigned long cartSizeLockon;
static unsigned long cartSizeSonic2 = 262144;
static word chksumLockon;
static word chksumSonic2 = 0x0635;

/******************************************
   Configuration
 *****************************************/
#if defined(use_md_conf) && !defined(ENABLE_CONFIG)

#warning "DEPRECATED: use_md_conf is deprecated. You should use ENABLE_CONFIG instead."

void mdLoadConf() {
  if (myFile.open("mdconf.txt", O_READ)) {
    char line[64];
    unsigned int n;
    unsigned int i;
    while ((n = myFile.fgets(line, sizeof(line) - 1)) > 0) {
      // preprocess
      for (i = 0; i < n; i++) {
        if (line[i] == ';') {
          // comments
          line[i] = '\0';
          n = i;
          break;
        } else if (line[i] == '\n' || line[i] == '\r') {
          // EOL
          line[n] = '\0';
          n = i;
          break;
        }
      }
      //print_Msg(F("read line: "));
      //println_Msg(line);
      if (line[0] == '[') {
        char* name;
        char* value;
        i = 1;
        name = line + i;
        for (; i < sizeof(line); i++) {
          if (line[i] == ']') {
            line[i] = '\0';
            i++;
            break;
          }
        }
        if (line[i] != '\0') {
          for (; i < sizeof(line); i++) {
            if (line[i] != ' ') {
              value = line + i;
              i++;
              break;
            }
          }
          for (; i < sizeof(line) && line[i] != '\0'; i++) {
            if (line[i] == ' ') {
              line[i] = '\0';
              break;
            }
          }
        }
        //print_Msg(F("read name: "));
        //println_Msg(name);
        //print_Msg(F("value: "));
        //println_Msg(value);
        if (!strcmp("segaSram16bit", name)) {
          // Retrode compatible setting
          // [segaSram16bit] 1   ; 0=no, 1=yes, 2=y+large
          // 0: Output each byte once. Not supported by most emulators.
          // 1: Duplicate each byte. Usable by Kega Fusion.
          // 2: Duplicate each byte. Pad with 0xFF so that the file size is 64KB.
          segaSram16bit = atoi(value);
          if (segaSram16bit != 0 && segaSram16bit != 1 && segaSram16bit != 2) {
            segaSram16bit = DEFAULT_VALUE_SAVE_TYPE;
          }
          print_Msg(F("segaSram16bit: "));
          println_Msg(segaSram16bit);
        }
      }
    }
    closeCurrentFile();
  }
}
#endif

void pulse_clock(int n) {
  for (int i = 0; i < n; i++)
    PORTH ^= (1 << 1);
}

/******************************************
   Menu
 *****************************************/
// MD menu items
static const char MDMenuItem1[] PROGMEM = "Game Cartridge";
static const char MDMenuItem2[] PROGMEM = "SegaCD RamCart";
static const char MDMenuItem3[] PROGMEM = "Flash Repro";
static const char MDMenuItem4[] PROGMEM = "Flash CFI";
static const char* const menuOptionsMD[] PROGMEM = { MDMenuItem1, MDMenuItem2, MDMenuItem3, MDMenuItem4, FSTRING_RESET };

// Cart menu items
static const char MDCartMenuItem4[] PROGMEM = "Force ROM size";
static const char* const menuOptionsMDCart[] PROGMEM = { FSTRING_READ_ROM, FSTRING_READ_SAVE, FSTRING_WRITE_SAVE, MDCartMenuItem4, FSTRING_REFRESH_CART, FSTRING_RESET };

// Sega CD Ram Backup Cartridge menu items
static const char SCDMenuItem1[] PROGMEM = "Read Backup RAM";
static const char SCDMenuItem2[] PROGMEM = "Write Backup RAM";
static const char* const menuOptionsSCD[] PROGMEM = { SCDMenuItem1, SCDMenuItem2, FSTRING_RESET };

// Sega start menu
static void prepareCartP21_MD() __attribute__((noinline));
static void prepareCartP21_MD() {
  clearAndUpdateDisplay();
  setup_MD();
}

void mdMenu() {
  // create menu with title and 4 options to choose from
  unsigned char mdDev;
  // Copy menuOptions out of progmem
  mdDev = chooseFlashMenuOption(FS(SharedFlashText::textSelectMDDevice), menuOptionsMD, 5);

  // wait for user choice to come back from the question box menu
  switch (mdDev) {
    case 0:
    case 1:
      prepareCartP21_MD();
      mode = mdDev == 0 ? CORE_MD_CART : CORE_SEGA_CD;
      break;

#ifdef ENABLE_FLASH
    case 2:
      prepareCartP21_MD();
      mode = CORE_MD_CART;
      // Change working dir to root
      browseRootFileAndClear();
      // Setting CS(PH3) LOW
      PORTH &= ~(1 << 3);

      // ID flash
      resetFlash_MD();
      idFlash_MD();
      resetFlash_MD();
      if (flashid == 0xC2F1) {
        println_Msg(FS(SharedFlashText::textMX29F1610Detected));
        flashSize = 2097152;
      } else if (flashid == 0x017E) {
        println_Msg(F("S29GL064N detected"));
        flashSize = 4194304;
      } else {
        print_Msg(FS(SharedFlashText::textFlashID));
        println_Msg(flashid_str);
        print_FatalError(F("Error: Unknown flashrom"));
      }
      println_Msg("Erasing...");
      display_Update();
      eraseFlash_MD();
      resetFlash_MD();
      blankcheck_MD();
      if (flashid == 0xC2F1)
        write29F1610_MD();
      else if (flashid == 0x017E)
        write29GL_MD();
      resetFlash_MD();
      delay(1000);
      resetFlash_MD();
      delay(1000);
      println_Msg("Verifying...");
      verifyFlash_MD();
      // Set CS(PH3) HIGH
      PORTH |= (1 << 3);
      // Prints string out of the common strings array either with or without newline
      promptAndWaitForButton();
      break;

    case 3:
      prepareCartP21_MD();
      mode = CORE_MD_CART;
      // Change working dir to root
      browseRootFileAndClear();
      appendSelectedFilePath();
      // Setting CS(PH3) LOW
      PORTH &= ~(1 << 3);
      display_Clear();
      // Ensure the SRAM is not enabled
      enableSram_MD(0);
      identifyFlashCFI_MD();
      eraseFlashCFI_MD();
      writeCFI_MD();
      resetFlashCFI_MD();
      delay(1000);
      display_Clear();
      println_Msg(FS(SharedFlashText::textVerifying));
      verifyFlashCFI_MD();
      // Set CS(PH3) HIGH
      PORTH |= (1 << 3);
      // Prints string out of the common strings array either with or without newline
      promptAndWaitForButton();
      break;

#endif

    case 4:
      resetArduino();
      break;

    default:
      print_MissingModule();  // does not return
  }
}

void mdCartMenu() {
  // create menu with title and 6 options to choose from
  unsigned char mainMenu;
  // Copy menuOptions out of progmem
  mainMenu = chooseFlashMenuOption(FS(SharedFlashText::textMEGADRIVEReader), menuOptionsMDCart, 6);

  // wait for user choice to come back from the question box menu
  if (mainMenu <= 3) display_Clear();
  switch (mainMenu) {
    case 0:

      // common ROM read fail state: no cart inserted - tends to report impossibly large cartSize
      // largest known game so far is supposedly "Paprium" at 10MB, so cap sanity check at 16MB
      if (cartSize != 0 && cartSize <= 16777216) {
        // Change working dir to root
        changeToStorageRoot();
        if (realtec) {
          readRealtec_MD();
        } else {
          readROM_MD();
          // Calculate and compare CRC32 with database
          if (is32x)
            //database, crcString, renamerom, offset
            compareCRC("32x.txt", 0, 1, 0);
          else
            compareCRC("md.txt", 0, 1, 0);
        }
      } else {
        print_Error(F("Cart has no ROM"));
      }
#ifdef ENABLE_GLOBAL_LOG
      save_log();
#endif
      break;

    case 1:
    case 2:
      if ((saveType == 1) || (saveType == 2) || (saveType == 3)) {
        changeToStorageRoot();
        if (mainMenu == 1) {
          println_Msg(F("Reading Sram..."));
          display_Update();
          enableSram_MD(1);
          readSram_MD();
          enableSram_MD(0);
        } else {
          fileBrowser(FS(SharedFlashText::textSelectSrmFile));
          display_Clear();
          enableSram_MD(1);
          writeSram_MD();
          writeErrors = verifySram_MD();
          enableSram_MD(0);
          if (writeErrors == 0) {
            println_Msg(FS(SharedFlashText::textSramVerifiedOK));
            display_Update();
          } else {
            showVerificationErrorCount(writeErrors);
          }
        }
      } else if (saveType == 4) {
        if (mainMenu == 1) {
          readEEP_MD();
        } else {
          fileBrowser(FS(SharedFlashText::textSelectEepFile));
          display_Clear();
          writeEEP_MD();
        }
      } else {
        print_Error(FS(SharedFlashText::textCartHasNoSave));
      }
      break;

    case 3:
      force_cartSize_MD();
      break;

    case 4:
      // For multi-game carts
      // Set reset pin to output (PH0)
      DDRH |= (1 << 0);
      // Switch RST(PH0) to LOW
      PORTH &= ~(1 << 0);

      showResettingAndUpdate();
      delay(3000);  // wait 3 secs to switch to next game
      resetArduino();
      break;

    case 5:
      // Reset
      resetArduino();
      break;
  }
  // Prints string out of the common strings array either with or without newline
  promptAndWaitForButton();
}

void segaCDMenu() {
  // create menu with title and 3 options to choose from
  unsigned char scdMenu;
  // Copy menuOptions out of progmem
  scdMenu = chooseFlashMenuOption(F("SEGA CD RAM"), menuOptionsSCD, 3);

  // wait for user choice to come back from the question box menu
  switch (scdMenu) {
    case 0:
    case 1:
      display_Clear();
      if (bramSize > 0) {
        if (scdMenu == 0) {
          readBram_MD();
        } else {
          fileBrowser(F("Select brm file"));
          display_Clear();
          writeBram_MD();
        }
      } else {
        print_Error(FS(SharedFlashText::textNotCDBackupRAMCart));
      }
      break;

    case 2:
      // Reset
      resetArduino();
      break;
  }
  printBlankLine();
  // Prints string out of the common strings array either with or without newline
  promptAndWaitForButton();
}

/******************************************
   Setup
 *****************************************/
void setup_MD() {
  // Request 5V
  setVoltage(VOLTS_SET_5V);

#if defined(ENABLE_CONFIG)
  segaSram16bit = configGetLong(F("md.saveType"));
#elif defined(use_md_conf)
  mdLoadConf();
#endif /*ENABLE_CONFIG*/

  // Set Address Pins to Output
  //A0-A7
  DDRF = 0xFF;
  //A8-A15
  DDRK = 0xFF;
  //A16-A23
  DDRL = 0xFF;

  // Set Control Pins to Output RST(PH0) CLK(PH1) CS(PH3) WRH(PH4) WRL(PH5) OE(PH6)
  DDRH |= (1 << 0) | (1 << 1) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6);

  // Set TIME(PJ0), AS(PJ1) to Output
  DDRJ |= (1 << 0) | (1 << 1);

  //set ASEL(PG5) to Output
  DDRG |= (1 << 5);

  // Set Data Pins (D0-D15) to Input
  DDRC = 0x00;
  DDRA = 0x00;

  // Setting RST(PH0) CS(PH3) WRH(PH4) WRL(PH5) OE(PH6) HIGH
  PORTH |= (1 << 0) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6);

  // Setting TIME(PJ0) AS(PJ1) HIGH
  PORTJ |= (1 << 0) | (1 << 1);

  // setting ASEL(PG5) HIGH
  PORTG |= (1 << 5);

  delay(200);

  // Print all the info
  getCartInfo_MD();
}

/******************************************
   I/O Functions
 *****************************************/

/******************************************
  Low level functions
*****************************************/
void writeWord_MD(unsigned long myAddress, word myData) {
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTL = (myAddress >> 16) & 0xFF;
  PORTC = myData;
  PORTA = (myData >> 8) & 0xFF;

  // Arduino running at 16Mhz -> one nop = 62.5ns
  // Wait till output is stable
  __asm__("nop\n\t"
          "nop\n\t");

  // Switch WR(PH5) to LOW
  PORTH &= ~(1 << 5);
  // Setting CS(PH3) LOW
  PORTH &= ~(1 << 3);

  // Leave WR low for at least 200ns
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
          "nop\n\t");

  // Setting CS(PH3) HIGH
  PORTH |= (1 << 3);
  // Switch WR(PH5) to HIGH
  PORTH |= (1 << 5);

  // Leave WR high for at least 50ns
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");
}

word readWord_MD(unsigned long myAddress) {
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTL = (myAddress >> 16) & 0xFF;

  // Arduino running at 16Mhz -> one nop = 62.5ns
  NOP;

  // Setting CS(PH3) LOW
  PORTH &= ~(1 << 3);
  // Setting OE(PH6) LOW
  PORTH &= ~(1 << 6);
  // Setting AS(PJ1) LOW
  PORTJ &= ~(1 << 1);
  // Setting ASEL(PG5) LOW
  PORTG &= ~(1 << 5);
  // Pulse CLK(PH1), needed for SVP enhanced carts
  pulse_clock(10);

  // most MD ROMs are 200ns, comparable to SNES > use similar access delay of 6 x 62.5 = 375ns
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;

  // Read
  word tempWord = ((PINA & 0xFF) << 8) | (PINC & 0xFF);

  // Setting CS(PH3) HIGH
  PORTH |= (1 << 3);
  // Setting OE(PH6) HIGH
  PORTH |= (1 << 6);
  // Setting AS(PJ1) HIGH
  PORTJ |= (1 << 1);
  // Setting ASEL(PG5) HIGH
  PORTG |= (1 << 5);
  // Pulse CLK(PH1), needed for SVP enhanced carts
  pulse_clock(10);

  // these 6x nop delays have been here before, unknown what they mean
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;

  return tempWord;
}

void writeFlash_MD(unsigned long myAddress, word myData) {
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTL = (myAddress >> 16) & 0xFF;
  PORTC = myData;
  PORTA = (myData >> 8) & 0xFF;

  // Arduino running at 16Mhz -> one nop = 62.5ns
  // Wait till output is stable
  __asm__("nop\n\t");

  // Switch WE(PH5) to LOW
  PORTH &= ~(1 << 5);

  // Leave WE low for at least 60ns
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");

  // Switch WE(PH5)to HIGH
  PORTH |= (1 << 5);

  // Leave WE high for at least 50ns
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");
}

word readFlash_MD(unsigned long myAddress) {
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTL = (myAddress >> 16) & 0xFF;

  // Arduino running at 16Mhz -> one nop = 62.5ns
  __asm__("nop\n\t");

  // Setting OE(PH6) LOW
  PORTH &= ~(1 << 6);

  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");

  // Read
  word tempWord = ((PINA & 0xFF) << 8) | (PINC & 0xFF);

  __asm__("nop\n\t");

  // Setting OE(PH6) HIGH
  PORTH |= (1 << 6);
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");

  return tempWord;
}

// Switch data pins to write
void dataOut_MD() {
  DDRC = 0xFF;
  DDRA = 0xFF;
}

// Switch data pins to read
void dataIn_MD() {
  DDRC = 0x00;
  DDRA = 0x00;
  // Enable Internal Pullups (needed for games like Batman Forever that are open bus with random bytes on the last 1MB, so we get a clean 0xFF padding)
  PORTC = 0xFF;
  PORTA = 0xFF;
}

/******************************************
  MEGA DRIVE functions
*****************************************/
byte copyToRomName_MD(char* output, const byte* input, byte length) {
  byte myLength = 0;

  for (byte i = 0; i < 48; i++) {
    if (((input[i] >= '0' && input[i] <= '9') || (input[i] >= 'A' && input[i] <= 'z')) && myLength < length) {
      output[myLength++] = input[i];
    }
  }

  return myLength;
}

static const struct {
  uint16_t checksum, correctedChecksum;
  uint8_t original64KiB;
  uint32_t correctedSize;
} mdSizeFixes[] PROGMEM = {
  {0xCE25, 0xCE25, 64, 0x500000},  // Super Street Fighter 2 (J) 40Mbit
  {0xE41D, 0xE41D, 64, 0x500000},  // Super Street Fighter 2 (E) 40Mbit
  {0xE017, 0xE017, 64, 0x500000},  // Super Street Fighter 2 (U) 40Mbit
  {0x0000, 0x0000, 64, 0xEAF2F4},  // Demons of Asteborg v1.0 (W) 120Mbit
  {0xBCBF, 0xBCBF, 64, 0xEA0000},  // Demons of Asteborg v1.1 (W) 120Mbit
  {0x6E1E, 0x6E1E, 64, 0xEA0000},  // Demons of Asteborg v1.11 (W) 120Mbit
  {0xBC5F, 0xBC5F, 48, 0x400000},  // Batman Forever (World)
  {0x3CDD, 0x3CDD, 48, 0x400000},  // Donald in Maui Mallard (Brazil) (En)
  {0x44AD, 0x44AD, 48, 0x400000},  // Donald in Maui Mallard (Europe) (Rev A)
  {0x2D9A, 0x2D9A, 48, 0x400000},  // Foreman for Real (World)
  {0x5648, 0x5648, 48, 0x400000},  // Justice League Task Force (World)
  {0x0A29, 0x0A29, 48, 0x400000},  // Mega 6 Vol. 3 (Europe)
  {0x7651, 0x7651, 48, 0x400000},  // NFL Quarterback Club (World)
  {0x74CA, 0x74CA, 48, 0x400000},  // WWF RAW (World)
  {0x2078, 0x9877, 32, 0},  // Dynamite Headdy (USA, Europe)
  {0xAE95, 0x56A0, 32, 0},  // Winter Olympic Games (USA)
  {0xFFE2, 0xFFE2, 24, 0x200000},  // Cannon Fodder (Europe)
  {0xF418, 0xF418, 24, 0x200000},  // Chaos Engine, The (Europe)
  {0xF71D, 0xF71D, 24, 0x200000},  // Fatal Fury (Europe, Korea) (En)
  {0xA884, 0xA884, 24, 0x200000},  // Flashback (Europe) (En,Fr)
  {0x7D68, 0x7D68, 24, 0x200000},  // Flashback - The Quest for Identity (USA) (En,Fr)
  {0x030D, 0x030D, 24, 0x200000},  // Shining Force (Europe)
  {0xE975, 0xE975, 24, 0x200000},  // Shining Force (USA)
  {0xCDF5, 0x603A, 16, 0x400000},  // Life on Mars (Aftermarket)
  {0xF85F, 0x6965, 16, 0x200000},  // Metal Dragon (Aftermarket)
  {0x4581, 0x0694, 16, 0x400000},  // True Galactic Mission (Aftermarket)
  {0x9D79, 0x9D79, 12, 0x100000},  // Wonder Boy in Monster World (USA, Europe)
  {0x06C1, 0x8473, 8, 0x200000},  // Madden NFL 98 (USA)
  {0x5B3A, 0x5613, 8, 0x200000},  // NHL 98 (USA)
  {0xD07D, 0xF204, 8, 0x100000},  // Zero Wing (Japan)
  {0x95C9, 0x95C9, 8, 0x100000},  // Zero Wing (Europe)
  {0x9144, 0x9144, 8, 0x100000},  // Zoop (Europe)
  {0xB8D4, 0xB8D4, 8, 0x100000},  // Zoop (USA)
  {0xC422, 0xC751, 8, 0},  // Jeopardy! (USA)
  {0x0C6A, 0xE1AA, 8, 0},  // Monopoly (USA)
  {0xA760, 0x97CD, 8, 0},  // Gain Ground (USA)
  {0x1404, 0x53B9, 8, 0},  // Wonder Boy III - Monster Lair (Japan, Europe) (En)
  {0x8BC6, 0x8BC6, 4, 0x100000},  // Pac-Attack (USA)
  {0xB344, 0xB344, 4, 0x100000},  // Pac-Panic (Europe)
  {0x7E50, 0xD074, 2, 0x100000},  // Micro Machines 2 - Turbo Tournament (Europe)
  {0x168B, 0xCEE0, 2, 0x100000},  // Micro Machines - Military (Europe)
};

void applyMdSizeFixes() {
  for (const auto& fix : mdSizeFixes) {
    if (chksum != pgm_read_word(&fix.checksum)) continue;
    if (cartSize != ((uint32_t)pgm_read_byte(&fix.original64KiB) << 16)) continue;
    chksum = pgm_read_word(&fix.correctedChecksum);
    const uint32_t size = pgm_read_dword(&fix.correctedSize);
    if (size) cartSize = size;
    break;
  }
}

static const struct {
  char prefix[15];
  uint16_t checksum, correctedChecksum;
  uint8_t sizeIn64KiB;
} mdIdFixes[] PROGMEM = {
  {"SF-001", 0x3E08, 0x3E08, 64},  // Beggar Prince (Rev 1)
  {"SF-002", 0x12B0, 0x45C6, 0},  // Legend of Wukong
  {"GM 10101010", 0xC439, 0x21B0, 16},  // YM2612 Instrument Editor
  {"MU REMUTE01", 0x0000, 0xB55C, 64},  // Technoptimistic
  {"GM REMUTE02", 0x0000, 0x5426, 64},  // Decoder
  {"GM HHARVYSG", 0x0000, 0xD9D2, 16},  // Handy Harvy
  {"GM T-107036", 0x0000, 0xAA28, 0},  // Jim Power - The Lost Dimension in 3D
  {"GM 00000000-43", 0x0000, 0x921B, 64},  // mikeyeldey95
  {"GM 00000000-00", 0x1E0C, 0xE7E5, 64},  // Enryuu Seiken Xiao-Mei
  {"GM 00000000-00", 0x6BD5, 0x1FEA, 64},  // Life on Earth - Reimagined
  {"GM 00000005-00", 0x9F34, 0xA094, 64},  // Sasha Darko's Sacred Line I
  {"GM 00000005-00", 0x0E9B, 0x6B4B, 64},  // Sasha Darko's Sacred Line II
  {"GM T-574323-00", 0xAEDD, 0xAEDD, 64},  // Sasha Darko's Sacred Line (Watermelon Release)
  {"GM MK-0000 -00", 0xC536, 0xFAB1, 32},  // Kromasphere
  {"GM CSET0001-02", 0x0000, 0xE3A9, 0},  // YM2017
  {"1774          ", 0x0000, 0x6E34, 64},  // The Curse of Illmore Bay
  {"JN-20160131-03", 0x0000, 0x8040, 64},  // Coffee Crisis
};

void applyMdIdFixes(const char* id) {
  for (const auto& fix : mdIdFixes) {
    if (chksum != pgm_read_word(&fix.checksum)) continue;
    if (strncmp_P(id, fix.prefix, strlen_P(fix.prefix)) != 0) continue;
    chksum = pgm_read_word(&fix.correctedChecksum);
    const byte units = pgm_read_byte(&fix.sizeIn64KiB);
    if (units) cartSize = (uint32_t)units << 16;
  }
}

static void showUnknownSramBase_MD(word sramType) __attribute__((noinline, noreturn));
static void showUnknownSramBase_MD(word sramType) {
  print_Msg(("sramType: "));
  print_Msg_PaddedHex16(sramType);
  printBlankLine();
  print_Msg(("sramBase: "));
  print_Msg_PaddedHex32(sramBase);
  printBlankLine();
  print_Msg(("sramEnd: "));
  print_Msg_PaddedHex32(sramEnd);
  printBlankLine();
  print_FatalError(FS(SharedFlashText::textUnknownSramBase));
}

void getCartInfo_MD() {
  // Set control
  dataIn_MD();

  // Get cart size
  cartSize = ((long(readWord_MD(0xD2)) << 16) | readWord_MD(0xD3)) + 1;

  // Check for 32x compatibility
  if ((readWord_MD(0x104 / 2) == 0x2033) && (readWord_MD(0x106 / 2) == 0x3258))
    is32x = 1;
  else
    is32x = 0;

  // Get cart checksum
  chksum = readWord_MD(0xC7);

  // Get cart ID
  char id[15];
  memset(id, 0, 15);
  for (byte c = 0; c < 14; c += 2) {
    // split word
    word myWord = readWord_MD((0x180 + c) / 2);
    byte loByte = myWord & 0xFF;
    byte hiByte = myWord >> 8;

    // write to buffer
    id[c] = hiByte;
    id[c + 1] = loByte;
  }

  // Get cart name
  for (byte c = 0; c < 48; c += 2) {
    // split word
    word myWord = readWord_MD((0x150 + c) / 2);
    byte loByte = myWord & 0xFF;
    byte hiByte = myWord >> 8;

    // write to buffer
    sdBuffer[c] = hiByte;
    sdBuffer[c + 1] = loByte;
  }
  romName[copyToRomName_MD(romName, sdBuffer, sizeof(romName) - 1)] = 0;

  // Identify games using SVP chip
  if (!strncmp("GM MK-1229 ", id, 11) || !strncmp("GM G-7001  ", id, 11))  // Virtua Racing (E/U/J)
    isSVP = 1;
  else
    isSVP = 0;

  // Fix cartridge sizes and checksums according to no-intro database
  applyMdSizeFixes();

  // Fatman (Japan)
  if (!strncmp("GM T-44013 ", id, 11) && (chksum == 0xFFFF)) {
    chksum = 0xC560;
    cartSize = 0xA0000;
  }

  // Slaughter Sport (USA)
  if (!strncmp("GMT5604600jJ", romName, 12) && (chksum == 0xFFFF)) {
    strcpy(romName, "SLAUGHTERSPORT");
    chksum = 0x6BAE;
  }

  applyMdIdFixes(id);
  // Romeow & Julicat
  if (!strncmp("ROMEOWJULICAT", romName, 13) && (chksum == 0x0000)) {
    chksum = 0xB094;
    cartSize = 0x200000;
  }

  // Sonic & Knuckles checks
  SnKmode = 0;
  if (!strcmp("GM MK-1563 -00", id) && (chksum == 0xDFB3)) {
    char labelLockon[17];
    memset(labelLockon, 0, 17);

    // Get labelLockon
    for (byte c = 0; c < 16; c += 2) {
      // split word
      word myWord = readWord_MD((0x200100 + c) / 2);
      byte loByte = myWord & 0xFF;
      byte hiByte = myWord >> 8;

      // write to buffer
      labelLockon[c] = hiByte;
      labelLockon[c + 1] = loByte;
    }

    // check Lock-on game presence
    if (!(strcmp("SEGA MEGA DRIVE ", labelLockon) & strcmp("SEGA GENESIS    ", labelLockon))) {
      char idLockon[15];
      memset(idLockon, 0, 15);

      // Lock-on cart checksum
      chksumLockon = readWord_MD(0x1000C7);
      // Lock-on cart size
      cartSizeLockon = ((long(readWord_MD(0x1000D2)) << 16) | readWord_MD(0x1000D3)) + 1;

      // Get IdLockon
      for (byte c = 0; c < 14; c += 2) {
        // split word
        word myWord = readWord_MD((0x200180 + c) / 2);
        byte loByte = myWord & 0xFF;
        byte hiByte = myWord >> 8;

        // write to buffer
        idLockon[c] = hiByte;
        idLockon[c + 1] = loByte;
      }

      if (!strncmp("GM 00001009-0", idLockon, 13) || !strncmp("GM 00004049-0", idLockon, 13)) { // Sonic1 ID:GM 00001009-0? or GM 00004049-0?
        SnKmode = 2;
      } else if (!strcmp("GM 00001051-00", idLockon) || !strcmp("GM 00001051-01", idLockon) || !strcmp("GM 00001051-02", idLockon)) { // Sonic2 ID:GM 00001051-00 or GM 00001051-01 or GM 00001051-02
        SnKmode = 3;
        // Prepare Sonic2 Banks
        writeSSF2Map(0x509878, 1);  // 0xA130F1
      } else if (!strcmp("GM MK-1079 -00", idLockon)) { // Sonic3 ID:GM MK-1079 -00
        SnKmode = 4;
      } else { // Other game
        SnKmode = 5;
      }

    } else {
      SnKmode = 1;
    }
  }

  // PcConsole EEPROM Check
  for (int i = 0; i < eepcount; i++) {
    int index = i * 2;
    word eepcheck = pgm_read_word(eepid + index);
    if (eepcheck == chksum) {
      eepdata = pgm_read_word(eepid + index + 1);
      eepType = eepdata & 0x7;
      eepSize = eepdata & 0xFFF8;
      saveType = 4;  // SERIAL EEPROM
      break;
    }
  }

  // Greatest Heavyweights of the Ring (J) has blank chksum 0x0000
  // Other non-save carts might have the same blank chksum
  // Check header for PcConsole EEPROM Data
  if (chksum == 0x0000) {
    if (readWord_MD(0xD9) != 0xE840) {  // NOT SERIAL EEPROM
      eepType = 0;
      eepSize = 0;
      saveType = 0;
    }
  }

  // Codemasters EEPROM Check
  // Codemasters used the same incorrect header across multiple carts
  // Carts with checksum 0x165E or 0x168B could be EEPROM or non-EEPROM
  // Check the first DWORD in ROM (0x444E4C44) to identify the EEPROM carts
  if ((chksum == 0x165E) || (chksum == 0x168B)) {
    if (readWord_MD(0x00) != 0x444E) {  // NOT SERIAL EEPROM
      eepType = 0;
      eepSize = 0;
      saveType = 0;
    }
  }

  // CD Backup RAM Cart Check
  // 4 = 128KB (2045 Blocks) Sega CD Backup RAM Cart
  // 6 = 512KB (8189 Blocks) Ultra CD Backup RAM Cart (Aftermarket)
  word bramCheck = readWord_MD(0x00);
  if ((((bramCheck & 0xFF) == 0x04) && ((chksum & 0xFF) == 0x04)) || (((bramCheck & 0xFF) == 0x06) && ((chksum & 0xFF) == 0x06))) {
    unsigned long p = 1 << (bramCheck & 0xFF);
    bramSize = p * 0x2000L;
  }
  if (saveType != 4) {  // NOT SERIAL EEPROM
    // Check if cart has sram
    saveType = 0;
    sramSize = 0;

    // FIXED CODE FOR SRAM/FRAM/PARALLEL EEPROM
    // 0x5241F820 SRAM (ODD BYTES/EVEN BYTES)
    // 0x5241F840 PARALLEL EEPROM - READ AS SRAM
    // 0x5241E020 SRAM (BOTH BYTES)
    if (readWord_MD(0xD8) == 0x5241) {
      word sramType = readWord_MD(0xD9);
      if ((sramType == 0xF820) || (sramType == 0xF840)) {  // SRAM/FRAM ODD/EVEN BYTES
        // Get sram start and end
        sramBase = ((long(readWord_MD(0xDA)) << 16) | readWord_MD(0xDB));
        sramEnd = ((long(readWord_MD(0xDC)) << 16) | readWord_MD(0xDD));
        if (sramBase == 0x20000020 && sramEnd == 0x00010020) {  // Fix for Psy-o-blade
          sramBase = 0x200001;
          sramEnd = 0x203fff;
        }
        // Check alignment of sram
        // 0x300001 for HARDBALL '95 (U)
        // 0x3C0001 for Legend of Wukong (Aftermarket)
        if ((sramBase == 0x200001) || (sramBase == 0x300001) || (sramBase == 0x3C0001)) {
          // low byte
          saveType = 1;  // ODD
          sramSize = (sramEnd - sramBase + 2) / 2;
          // Right shift sram base address so [A21] is set to high 0x200000 = 0b001[0]00000000000000000000
          sramBase = sramBase >> 1;
        } else if (sramBase == 0x200000) {
          // high byte
          saveType = 2;  // EVEN
          sramSize = (sramEnd - sramBase + 1) / 2;
          // Right shift sram base address so [A21] is set to high 0x200000 = 0b001[0]00000000000000000000
          sramBase = sramBase / 2;
        } else {
          showUnknownSramBase_MD(sramType);
        }
      } else if (sramType == 0xE020) {  // SRAM BOTH BYTES
        // Get sram start and end
        sramBase = ((long(readWord_MD(0xDA)) << 16) | readWord_MD(0xDB));
        sramEnd = ((long(readWord_MD(0xDC)) << 16) | readWord_MD(0xDD));

        if (sramBase == 0x200001) {
          saveType = 3;  // BOTH
          sramSize = sramEnd - sramBase + 2;
          sramBase = sramBase >> 1;
        } else if (sramBase == 0x200000) {
          saveType = 3;  // BOTH
          sramSize = sramEnd - sramBase + 1;
          sramBase = sramBase >> 1;
        } else if (sramBase == 0x3FFC00) {
          // Used for some aftermarket carts without sram
          saveType = 0;
        } else {
          showUnknownSramBase_MD(sramType);
        }
      }
    } else {
      // SRAM CARTS WITH BAD/MISSING HEADER SAVE DATA
      struct SramOverride { uint16_t checksum; byte type; byte units; };
      static const SramOverride overrides[] PROGMEM = {
        {0xC2DB, 1, 1},
        {0xD7B6, 1, 4},
        {0xFE3E, 1, 4},
        {0xFDAD, 1, 4},
        {0x632E, 1, 4},
        {0xD2BA, 1, 4},
        {0x44FE, 1, 4},
        {0xDB5E, 3, 8},
        {0x3428, 3, 8},
        {0x43EE, 3, 8},
        {0xBF72, 1, 16},
        {0x72EF, 1, 16},
        {0xD723, 1, 16},
        {0x06C1, 1, 16},
        {0xDB17, 1, 16},
        {0x5B3A, 1, 16},
        {0x2CF2, 1, 16},
        {0xE9B1, 1, 16},
        {0xEEE8, 1, 16}
      };
      for (byte i = 0; i < sizeof(overrides) / sizeof(overrides[0]); ++i) {
        if (chksum == pgm_read_word(&overrides[i].checksum)) {
          saveType = pgm_read_byte(&overrides[i].type);
          sramBase = 0x200001;
          sramEnd = 0x200000UL + (uint32_t)pgm_read_byte(&overrides[i].units) * 4096UL - 1;
          break;
        }
      }
      if (saveType == 1) {
        sramSize = (sramEnd - sramBase + 2) / 2;
        sramBase = sramBase >> 1;
      } else if (saveType == 3) {
        sramSize = sramEnd - sramBase + 2;
        sramBase = sramBase >> 1;
      }
    }
  }

  //Get Lock-on cart name
  if (SnKmode >= 2) {
    char romNameLockon[12];

    //Change romName
    strcpy(romName, "SnK_");

    for (byte c = 0; c < 48; c += 2) {
      // split word
      word myWord = readWord_MD((0x200150 + c) / 2);
      byte loByte = myWord & 0xFF;
      byte hiByte = myWord >> 8;

      // write to buffer
      sdBuffer[c] = hiByte;
      sdBuffer[c + 1] = loByte;
    }
    romNameLockon[copyToRomName_MD(romNameLockon, sdBuffer, sizeof(romNameLockon) - 1)] = 0;

    switch (SnKmode) {
      case 2: strcat(romName, "SONIC1"); break;
      case 3: strcat(romName, "SONIC2"); break;
      case 4: strcat(romName, "SONIC3"); break;
      case 5: strcat(romName, romNameLockon); break;
    }
  }

  // Realtec Mapper Check
  word realtecCheck1 = readWord_MD(0x3F080);  // 0x7E100 "SEGA" (BootROM starts at 0x7E000)
  word realtecCheck2 = readWord_MD(0x3F081);
  if ((realtecCheck1 == 0x5345) && (realtecCheck2 == 0x4741)) {
    realtec = 1;
    strcpy(romName, "Realtec");
    cartSize = 0x80000;
  }

  // Some games are missing the ROM size in the header, in this case calculate ROM size by looking for mirror of the first line of the ROM
  // This does not work for cartridges that have SRAM mapped directly after the maskrom like Striker (Europe)
  if ((cartSize < 0x8000) || (cartSize > 0xEAF400)) {
    for (cartSize = 0x20000 / 2; cartSize < 0x400000 / 2; cartSize += 0x20000 / 2) {
      byte wordIndex = 0;
      for (; wordIndex < 9; ++wordIndex) {
        word firstWord = readWord_MD(wordIndex);
        if (firstWord != readWord_MD(cartSize + wordIndex)) break;
      }
      if (wordIndex == 9) break;
    }
    cartSize = cartSize * 2;
  }

  display_Clear();
  println_Msg(FS(SharedFlashText::textCartInfo));
  println_Msg(FS(FSTRING_SPACE));
  showRomNameLine();
  if (bramCheck != 0x00FF) {
    print_Msg(F("bramCheck: "));
    print_Msg_PaddedHex16(bramCheck);
    printBlankLine();
  }
  if (bramSize > 0) {
    print_Msg(F("bramSize(KB): "));
    println_Msg(bramSize >> 10);
  }
  print_Msg(FS(FSTRING_SIZE));
  print_Msg(cartSize * 8 / 1024 / 1024);
  if (SnKmode >= 2 && SnKmode <= 5) {
    print_Msg(F("+"));
    print_Msg(cartSizeLockon * 8 / 1024 / 1024);
    if (SnKmode == 3) {
      print_Msg(F("+"));
      print_Msg(cartSizeSonic2 * 8 / 1024 / 1024);
    }
  }
  println_Msg(FS(SharedFlashText::textMBit));
  print_Msg(F("ChkS: "));
  print_Msg_PaddedHexByte((chksum >> 8));
  print_Msg_PaddedHexByte((chksum & 0x00ff));
  if (SnKmode >= 2 && SnKmode <= 5) {
    print_Msg(F("+"));
    print_Msg_PaddedHexByte((chksumLockon >> 8));
    print_Msg_PaddedHexByte((chksumLockon & 0x00ff));
    if (SnKmode == 3) {
      print_Msg(F("+"));
      print_Msg_PaddedHexByte((chksumSonic2 >> 8));
      print_Msg_PaddedHexByte((chksumSonic2 & 0x00ff));
    }
  }
  printBlankLine();
  if (saveType == 4) {
    print_Msg(F("PcConsole EEPROM: "));
    print_Msg(eepSize * 8 / 1024);
    println_Msg(FS(SharedFlashText::textKBit));
  } else {
    print_Msg(FS(SharedFlashText::textSram));
    if (sramSize > 0) {
      print_Msg(sramSize * 8 / 1024);
      println_Msg(FS(SharedFlashText::textKBit));
    } else
      println_Msg(FS(SharedFlashText::textNone));
  }
  println_Msg(FS(FSTRING_SPACE));

  // Wait for user input
#if (defined(ENABLE_LCD) || defined(ENABLE_OLED))
  // Prints string out of the common strings array either with or without newline
  promptAndWaitForButton();
#endif
}

void writeSSF2Map(unsigned long myAddress, word myData) {
  dataOut_MD();

  // Set TIME(PJ0) HIGH
  PORTJ |= (1 << 0);

  // 0x50987E * 2 = 0xA130FD  Bank 6 (0x300000-0x37FFFF)
  // 0x50987F * 2 = 0xA130FF  Bank 7 (0x380000-0x3FFFFF)
  PORTL = (myAddress >> 16) & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTF = myAddress & 0xFF;
  PORTC = myData;
  PORTA = (myData >> 8) & 0xFF;

  // Arduino running at 16Mhz -> one nop = 62.5ns
  // Wait till output is stable
  __asm__("nop\n\t"
          "nop\n\t");

  // Strobe TIME(PJ0) LOW to latch the data
  PORTJ &= ~(1 << 0);
  // Switch WR(PH5) to LOW
  PORTH &= ~(1 << 5);

  // Leave WR low for at least 200ns
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
          "nop\n\t");

  // Switch WR(PH5) to HIGH
  PORTH |= (1 << 5);
  // Set TIME(PJ0) HIGH
  PORTJ |= (1 << 0);

  dataIn_MD();
}

// Read rom and save to the SD card
// MD 16-bit reader for the benchmark-gated CRC-checked 2 Mbps PC stream.
static uint32_t md2mWordAddress = 0;
static uint8_t md2mChecksumSlot = 0;
static uint16_t md2mChecksum = 0;
static uint16_t md2mBlockChecksums[16];
static void beginMd2mBlock(uint32_t byteAddress) {
  md2mChecksumSlot = (byteAddress >> 9) & 0x0F;
  // If this 512-byte frame is retried, replace its previous checksum sum.
  md2mChecksum -= md2mBlockChecksums[md2mChecksumSlot];
  md2mBlockChecksums[md2mChecksumSlot] = 0;
  md2mWordAddress = byteAddress >> 1;
}
static void md2mRoundStarted(uint8_t round) {
  // A new 16-frame window starts at round zero. Keep accepted-frame sums
  // during retries so a retransmitted frame replaces only its own sum.
  if (round == 0) memset(md2mBlockChecksums, 0, sizeof(md2mBlockChecksums));
}
static void readMd2mWord(uint8_t* output) {
  const uint32_t address = md2mWordAddress++;
  PORTF = address & 0xFF;
  PORTK = (address >> 8) & 0xFF;
  PORTL = (address >> 16) & 0xFF;
  NOP;
  PORTH &= ~(1 << 3);
  PORTH &= ~(1 << 6);
  PORTJ &= ~(1 << 1);
  PORTG &= ~(1 << 5);
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;
  NOP;
  output[0] = PINA;
  output[1] = PINC;
  PORTH |= (1 << 3);
  PORTH |= (1 << 6);
  PORTJ |= (1 << 1);
  PORTG |= (1 << 5);
  // Legacy MD checksum skips the first 256 words (512 header bytes).
  if (address >= 256UL) {
    const uint16_t value = ((uint16_t)output[0] << 8) | output[1];
    md2mBlockChecksums[md2mChecksumSlot] += value;
    md2mChecksum += value;
  }
}

// Read a 256-word block for ordinary standalone MD ROMs.
// Keep the cartridge control-signal order and access NOPs unchanged.
template <bool AccumulateChecksum>
static inline __attribute__((always_inline)) uint16_t readMdSdBlock_MD(uint32_t address, uint16_t checksum, byte* buffer) {
  for (uint16_t wordIndex = 0; wordIndex < 256; ++wordIndex, ++address) {
    PORTF = address & 0xFF;
    PORTK = (address >> 8) & 0xFF;
    PORTL = (address >> 16) & 0xFF;

    NOP;
    PORTH &= ~(1 << 3);
    PORTH &= ~(1 << 6);
    PORTJ &= ~(1 << 1);
    PORTG &= ~(1 << 5);

    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;

    *buffer++ = PINA;
    *buffer++ = PINC;

    PORTH |= (1 << 3);
    PORTH |= (1 << 6);
    PORTJ |= (1 << 1);
    PORTG |= (1 << 5);

    if (AccumulateChecksum) {
      checksum += ((uint16_t)buffer[-2] << 8) | (uint16_t)buffer[-1];
    }
  }
  return checksum;
}

static void showChecksumMismatch_MD(uint16_t checksum, bool newline) __attribute__((noinline));
static void showChecksumMismatch_MD(uint16_t checksum, bool newline) {
  if (newline) {
    println_Msg(FS(SharedFlashText::textError));
  } else {
    print_Msg(FS(SharedFlashText::textError));
  }
  char calcsumStr[5];
  formatFixedHex(calcsumStr, checksum, 4);
  println_Msg(calcsumStr);
  print_Error(FS(FSTRING_EMPTY));
  display_Update();
}

static word advanceLockonBufferR39_MD(word d) __attribute__((noinline));
static word advanceLockonBufferR39_MD(word d) {
  d += 2;
  if (d == 512) {
    writeSdBufferBlock();
    d = 0;
  }
  return d;
}

void readROM_MD() {
  // Checksum
  uint16_t calcCKS = 0;
  uint16_t calcCKSLockon = 0;
  uint16_t calcCKSSonic2 = 0;

  // Set control
  dataIn_MD();

  // Get name, add extension and convert to char array for sd lib
  createFolderAndOpenFile("MD", "ROM", romName, "BIN");

  // Phantasy Star/Beyond Oasis with 74HC74 and 74HC139 switch ROM/SRAM at address 0x200000
  if (0x200000 < cartSize && cartSize < 0x400000) {
    enableSram_MD(0);
  }

  // Prepare SSF2 Banks
  if (cartSize > 0x400000) {
    writeSSF2Map(0x50987E, 6);  // 0xA130FD
    writeSSF2Map(0x50987F, 7);  // 0xA130FF
  }
  byte offsetSSF2Bank = 0;
  word d = 0;

  //Initialize progress bar
  uint32_t processedProgressBar = 0;
  uint32_t totalProgressBar = (uint32_t)(cartSize);
  if (SnKmode >= 2) totalProgressBar += (uint32_t)cartSizeLockon;
  if (SnKmode == 3) totalProgressBar += (uint32_t)cartSizeSonic2;
  startProgressBar(totalProgressBar);

  bool md2mTransferred = false;

  // Only ordinary MD ROMs use the CRC-checked 2 Mbps retry stream.
  // Mapper/clock-sensitive cartridges retain the original reader path.
  const bool md2mEligible = PcLink::usingPcStorage() && myFile.isPc()
                            && !is32x && !isSVP && SnKmode == 0
                            && cartSize <= 0x400000;
  if (md2mEligible) {
    md2mChecksum = 0;
    memset(md2mBlockChecksums, 0, sizeof(md2mBlockChecksums));
    md2mTransferred = myFile.romRetry2M(cartSize, beginMd2mBlock, readMd2mWord,
                                        PcLink::RETRY_PROFILE_MD, md2mRoundStarted);
    if (md2mTransferred) calcCKS = md2mChecksum;
  }

  const bool useMdStandaloneFastPath = !PcLink::usingPcStorage() && !myFile.isPc()
                                      && !is32x && !isSVP && SnKmode == 0
                                      && cartSize <= 0x400000;

  if (!md2mTransferred && useMdStandaloneFastPath) {
    // Allocate the 1 KiB batching buffer only for this MD standalone SD dump.
    // If allocation fails, retain the original 512-byte writes using sdBuffer.
    byte* mdBatchBuffer = (byte*)malloc(1024);
    if (!mdBatchBuffer) {
      println_Msg(F("[MD SD] 1 KiB batch buffer allocation failed; using 512-byte writes"));
    }

    for (unsigned long currBuffer = 0; currBuffer < cartSize / 2; currBuffer += 512) {
      if (currBuffer % 16384 == 0) blinkLED();

      for (uint8_t half = 0; half < 2; ++half) {
        const uint32_t blockAddress = currBuffer + ((uint32_t)half * 256UL);
        byte* blockBuffer = mdBatchBuffer ? mdBatchBuffer + ((uint16_t)half * 512U) : sdBuffer;
        if (currBuffer == 0 && half == 0) {
          // Preserve the legacy rule: omit the first 256 header words.
          readMdSdBlock_MD<false>(blockAddress, calcCKS, blockBuffer);
        } else {
          calcCKS = readMdSdBlock_MD<true>(blockAddress, calcCKS, blockBuffer);
        }

        if (!mdBatchBuffer) {
          writeSdBufferBlock();
        }
      }

      if (mdBatchBuffer) {
        myFile.write(mdBatchBuffer, 1024);
      }

      processedProgressBar += 1024;
      draw_progressbar(processedProgressBar, totalProgressBar);
    }

    free(mdBatchBuffer);
  } else if (!md2mTransferred) {

  for (unsigned long currBuffer = 0; currBuffer < cartSize / 2; currBuffer += 512) {
    // Blink led
    if (currBuffer % 16384 == 0)
      blinkLED();

    if (currBuffer == 0x200000) {
      writeSSF2Map(0x50987E, 8);  // 0xA130FD
      writeSSF2Map(0x50987F, 9);  // 0xA130FF
      offsetSSF2Bank = 1;
    }

    // Demons of Asteborg Additional Banks
    else if (currBuffer == 0x280000) {
      writeSSF2Map(0x50987E, 10);  // 0xA130FD
      writeSSF2Map(0x50987F, 11);  // 0xA130FF
      offsetSSF2Bank = 2;
    } else if (currBuffer == 0x300000) {
      writeSSF2Map(0x50987E, 12);  // 0xA130FD
      writeSSF2Map(0x50987F, 13);  // 0xA130FF
      offsetSSF2Bank = 3;
    } else if (currBuffer == 0x380000) {
      writeSSF2Map(0x50987E, 14);  // 0xA130FD
      writeSSF2Map(0x50987F, 15);  // 0xA130FF
      offsetSSF2Bank = 4;
    } else if (currBuffer == 0x400000) {
      writeSSF2Map(0x50987E, 16);  // 0xA130FD
      writeSSF2Map(0x50987F, 17);  // 0xA130FF
      offsetSSF2Bank = 5;
    } else if (currBuffer == 0x480000) {
      writeSSF2Map(0x50987E, 18);  // 0xA130FD
      writeSSF2Map(0x50987F, 19);  // 0xA130FF
      offsetSSF2Bank = 6;
    } else if (currBuffer == 0x500000) {
      writeSSF2Map(0x50987E, 20);  // 0xA130FD
      writeSSF2Map(0x50987F, 21);  // 0xA130FF
      offsetSSF2Bank = 7;
    } else if (currBuffer == 0x580000) {
      writeSSF2Map(0x50987E, 22);  // 0xA130FD
      writeSSF2Map(0x50987F, 23);  // 0xA130FF
      offsetSSF2Bank = 8;
    } else if (currBuffer == 0x600000) {
      writeSSF2Map(0x50987E, 24);  // 0xA130FD
      writeSSF2Map(0x50987F, 25);  // 0xA130FF
      offsetSSF2Bank = 9;
    } else if (currBuffer == 0x680000) {
      writeSSF2Map(0x50987E, 26);  // 0xA130FD
      writeSSF2Map(0x50987F, 27);  // 0xA130FF
      offsetSSF2Bank = 10;
    } else if (currBuffer == 0x700000) {
      writeSSF2Map(0x50987E, 28);  // 0xA130FD
      writeSSF2Map(0x50987F, 29);  // 0xA130FF
      offsetSSF2Bank = 11;
    }

    d = 0;

    for (int currWord = 0; currWord < 512; currWord++) {
      unsigned long myAddress = currBuffer + currWord - (offsetSSF2Bank * 0x80000);
      PORTF = myAddress & 0xFF;
      PORTK = (myAddress >> 8) & 0xFF;
      PORTL = (myAddress >> 16) & 0xFF;

      // Arduino running at 16Mhz -> one nop = 62.5ns
      NOP;
      // Setting CS(PH3) LOW
      PORTH &= ~(1 << 3);
      // Setting OE(PH6) LOW
      PORTH &= ~(1 << 6);
      // Setting AS(PJ1) LOW
      PORTJ &= ~(1 << 1);
      // Setting ASEL(PG5) LOW
      PORTG &= ~(1 << 5);
      // Pulse CLK(PH1)
      if (isSVP)
        pulse_clock(10);

      // most MD ROMs are 200ns, comparable to SNES > use similar access delay of 6 x 62.5 = 375ns
      NOP;
      NOP;
      NOP;
      NOP;
      NOP;
      NOP;

      // Read
      sdBuffer[d] = PINA;
      sdBuffer[d + 1] = PINC;

      // Setting CS(PH3) HIGH
      PORTH |= (1 << 3);
      // Setting OE(PH6) HIGH
      PORTH |= (1 << 6);
      // Setting AS(PJ1) HIGH
      PORTJ |= (1 << 1);
      // Setting ASEL(PG5) HIGH
      PORTG |= (1 << 5);
      // Pulse CLK(PH1)
      if (isSVP)
        pulse_clock(10);

      // Skip first 256 words
      if (((currBuffer == 0) && (currWord >= 256)) || (currBuffer > 0)) {
        calcCKS += ((sdBuffer[d] << 8) | sdBuffer[d + 1]);
      }
      d = advanceLockonBufferR39_MD(d);
    }

    // update progress bar
    processedProgressBar += 1024;
    draw_progressbar(processedProgressBar, totalProgressBar);
  }
  if (SnKmode >= 2) {
    for (unsigned long currBuffer = 0; currBuffer < cartSizeLockon / 2; currBuffer += 512) {
      // Blink led
      if (currBuffer % 16384 == 0)
        blinkLED();

      d = 0;

      for (int currWord = 0; currWord < 512; currWord++) {
        unsigned long myAddress = currBuffer + currWord + cartSize / 2;
        PORTF = myAddress & 0xFF;
        PORTK = (myAddress >> 8) & 0xFF;
        PORTL = (myAddress >> 16) & 0xFF;

        // Arduino running at 16Mhz -> one nop = 62.5ns
        NOP;
        // Setting CS(PH3) LOW
        PORTH &= ~(1 << 3);
        // Setting OE(PH6) LOW
        PORTH &= ~(1 << 6);
        // Setting AS(PJ1) LOW
        PORTJ &= ~(1 << 1);
        // Setting ASEL(PG5) LOW
        PORTG &= ~(1 << 5);
        // Pulse CLK(PH1)
        if (isSVP)
          pulse_clock(10);

        // most MD ROMs are 200ns, comparable to SNES > use similar access delay of 6 x 62.5 = 375ns
        NOP;
        NOP;
        NOP;
        NOP;
        NOP;
        NOP;

        // Read
        sdBuffer[d] = PINA;
        sdBuffer[d + 1] = PINC;

        // Setting CS(PH3) HIGH
        PORTH |= (1 << 3);
        // Setting OE(PH6) HIGH
        PORTH |= (1 << 6);
        // Setting AS(PJ1) HIGH
        PORTJ |= (1 << 1);
        // Setting ASEL(PG5) HIGH
        PORTG |= (1 << 5);
        // Pulse CLK(PH1)
        if (isSVP)
          pulse_clock(10);

        // Skip first 256 words
        if (((currBuffer == 0) && (currWord >= 256)) || (currBuffer > 0)) {
          calcCKSLockon += ((sdBuffer[d] << 8) | sdBuffer[d + 1]);
        }
        d = advanceLockonBufferR39_MD(d);
      }

      // update progress bar
      processedProgressBar += 1024;
      draw_progressbar(processedProgressBar, totalProgressBar);
    }
  }
  if (SnKmode == 3) {
    for (unsigned long currBuffer = 0; currBuffer < cartSizeSonic2 / 2; currBuffer += 512) {
      // Blink led
      if (currBuffer % 16384 == 0)
        blinkLED();

      d = 0;

      for (int currWord = 0; currWord < 512; currWord++) {
        unsigned long myAddress = currBuffer + currWord + (cartSize + cartSizeLockon) / 2;
        PORTF = myAddress & 0xFF;
        PORTK = (myAddress >> 8) & 0xFF;
        PORTL = (myAddress >> 16) & 0xFF;

        // Arduino running at 16Mhz -> one nop = 62.5ns
        NOP;
        // Setting CS(PH3) LOW
        PORTH &= ~(1 << 3);
        // Setting OE(PH6) LOW
        PORTH &= ~(1 << 6);
        // Setting AS(PJ1) LOW
        PORTJ &= ~(1 << 1);
        // Setting ASEL(PG5) LOW
        PORTG &= ~(1 << 5);
        // Pulse CLK(PH1)
        if (isSVP)
          PORTH ^= (1 << 1);

        // most MD ROMs are 200ns, comparable to SNES > use similar access delay of 6 x 62.5 = 375ns
        NOP;
        NOP;
        NOP;
        NOP;
        NOP;
        NOP;

        // Read
        sdBuffer[d] = PINA;
        sdBuffer[d + 1] = PINC;

        // Setting CS(PH3) HIGH
        PORTH |= (1 << 3);
        // Setting OE(PH6) HIGH
        PORTH |= (1 << 6);
        // Setting AS(PJ1) HIGH
        PORTJ |= (1 << 1);
        // Setting ASEL(PG5) HIGH
        PORTG |= (1 << 5);
        // Pulse CLK(PH1)
        if (isSVP)
          PORTH ^= (1 << 1);

        calcCKSSonic2 += ((sdBuffer[d] << 8) | sdBuffer[d + 1]);
        d = advanceLockonBufferR39_MD(d);
      }

      // update progress bar
      processedProgressBar += 1024;
      draw_progressbar(processedProgressBar, totalProgressBar);
    }
  }
  } // End of the original reader path when the MD 2 Mbps profile is unavailable.
  if (md2mTransferred) {
    processedProgressBar = totalProgressBar;
    draw_progressbar(processedProgressBar, totalProgressBar);
  }

  closeCurrentFile();
  // Reset SSF2 Banks
  if (cartSize > 0x400000) {
    writeSSF2Map(0x50987E, 6);  // 0xA130FD
    writeSSF2Map(0x50987F, 7);  // 0xA130FF
  }

  // Calculate internal checksum
  print_Msg(F("Internal checksum..."));
  display_Update();
  if (chksum == calcCKS) {
    showOkAndUpdate();
  } else {
    showChecksumMismatch_MD(calcCKS, true);
  }

  // More checksums
  if (SnKmode >= 2) {
    print_Msg(F("Lock-on checksum..."));
    if (chksumLockon == calcCKSLockon) {
      showOkAndUpdate();
    } else {
      showChecksumMismatch_MD(calcCKSLockon, false);
    }
  }
  if (SnKmode == 3) {
    print_Msg(F("Adittional checksum..."));
    if (chksumSonic2 == calcCKSSonic2) {
      showOkAndUpdate();
    } else {
      showChecksumMismatch_MD(calcCKSSonic2, false);
    }
  }
}

/******************************************
  SRAM functions
*****************************************/
// Sonic 3 sram enable
void enableSram_MD(boolean enableSram) {
  dataOut_MD();

  // Set D0 to either 1(enable SRAM) or 0(enable ROM)
  PORTC = enableSram;

  // Strobe TIME(PJ0) LOW to latch the data
  PORTJ &= ~(1 << 0);
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");
  // Set TIME(PJ0) HIGH
  PORTJ |= (1 << 0);
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");

  dataIn_MD();
}

// Write sram to cartridge
void writeSram_MD() {
  dataOut_MD();

  // Create filepath
  appendPathAndShowWritingProgress();

  // Open file on sd card
  if (openSelectedFileForRead()) {
    // Write to the lower byte
    if (saveType == 1) {
      for (unsigned long currByte = sramBase; currByte < sramBase + sramSize; currByte++) {
        if (segaSram16bit > 0) {
          // skip high byte
          myFile.read();
        }
        word data = myFile.read() & 0xFF;
        writeWord_MD(currByte, data);
      }
    }
    // Write to the upper byte
    else if (saveType == 2) {
      for (unsigned long currByte = sramBase; currByte < sramBase + sramSize; currByte++) {
        word data = (myFile.read() << 8) & 0xFF00;
        writeWord_MD(currByte, data);
        if (segaSram16bit > 0) {
          // skip low byte
          myFile.read();
        }
      }
    }
    // Write to both bytes
    else if (saveType == 3) {
      for (unsigned long currByte = sramBase; currByte < sramBase + sramSize; currByte++) {
        word data = (myFile.read() << 8) & 0xFF00;
        data |= (myFile.read() & 0xFF);
        writeWord_MD(currByte, data);
      }
    } else
      print_Error(FS(SharedFlashText::textUnknownSaveType));

    // Close the file:
    closeAndShowDone();
  } else {
    fatalSdError();
  }
  dataIn_MD();
}

// Read sram and save to the SD card
static void readSramBuffer_MD(unsigned long currBuffer, bool verifying) __attribute__((noinline));
static void readSramBuffer_MD(unsigned long currBuffer, bool verifying) {
  for (int currWord = 0; currWord < 256; currWord++) {
    word myWord = readWord_MD(currBuffer + currWord);
    if (saveType == 3) {
      sdBuffer[currWord * 2] = (myWord >> 8) & 0xFF;
      sdBuffer[currWord * 2 + 1] = myWord & 0xFF;
    } else if (saveType == 1 || saveType == 2) {
      byte value = saveType == 2 ? (myWord >> 8) & 0xFF : myWord & 0xFF;
      if (verifying || segaSram16bit > 0) {
        sdBuffer[currWord * 2] = value;
        if (!verifying)
          sdBuffer[currWord * 2 + 1] = value;
      } else {
        sdBuffer[currWord] = value;
      }
    }
  }
}

void readSram_MD() {
  dataIn_MD();

  // Get name, add extension and convert to char array for sd lib
  createFolder("MD", "SAVE", romName, "srm");

  // write new folder number back to eeprom
  foldern = foldern + 1;
  EEPROM_writeAnything(0, foldern);

  // Open file on sd card
  if (!openNamedOutputFile()) {
    fatalSdError();
  }

  for (unsigned long currBuffer = sramBase; currBuffer < sramBase + sramSize; currBuffer += 256) {
    readSramBuffer_MD(currBuffer, false);
    if (saveType == 3 || segaSram16bit > 0)
      writeSdBufferBlock();
    else
      myFile.write(sdBuffer, 256);
  }
  if (segaSram16bit == 2) {
    // pad to 64KB
    for (int i = 0; i < 512; i++) {
      sdBuffer[i] = 0xFF;
    }
    unsigned long padsize = (1UL << 16) - (sramSize << 1);
    unsigned long padblockcount = padsize >> 9;  // number of 512 byte blocks
    for (unsigned long i = 0; i < padblockcount; i++) {
      writeSdBufferBlock();
    }
  }
  // Close the file:
  closeCurrentFile();
  showSavedToFolder();
  println_Msg(FS(SharedFlashText::pathSeparator));
  display_Update();
}

unsigned long verifySram_MD() {
  dataIn_MD();
  writeErrors = 0;

  // Open file on sd card
  if (openSelectedFileForRead()) {
    for (unsigned long currBuffer = sramBase; currBuffer < sramBase + sramSize; currBuffer += 256) {
      readSramBuffer_MD(currBuffer, true);
      int step = saveType == 3 ? 1 : 2;
      // Check sdBuffer content against file on sd card
      for (int i = 0; i < 512; i += step) {
        if (saveType == 1 && segaSram16bit > 0) {
          // skip high byte
          myFile.read();
        }
        byte b = myFile.read();
        if (saveType == 2 && segaSram16bit > 0) {
          // skip low byte
          myFile.read();
        }
        if (b != sdBuffer[i]) {
          writeErrors++;
        }
      }
    }

    // Close the file:
    closeCurrentFile();
  } else {
    fatalSdError();
  }
  // Return 0 if verified ok, or number of errors
  return writeErrors;
}

#ifdef ENABLE_FLASH
//******************************************
// Flashrom Functions
//******************************************
void resetFlash_MD() {
  // Set data pins to output
  dataOut_MD();

  // Reset command sequence
  writeFlash_MD(0x5555, 0xaa);
  writeFlash_MD(0x2aaa, 0x55);
  writeFlash_MD(0x5555, 0xf0);

  // Set data pins to input again
  dataIn_MD();
}

void write29F1610_MD() {
  // Create filepath
  appendSelectedFilePath();
  showFlashingFileAndUpdate();

  // Open file on sd card
  if (openSelectedFileForRead()) {
    // Get rom size from file
    fileSize = myFile.fileSize();
    if (fileSize > flashSize) {
      print_FatalError(file_too_big_STR);
    }
    // Set data pins to output
    dataOut_MD();

    //Initialize progress bar
    uint32_t processedProgressBar = 0;
    uint32_t totalProgressBar = (uint32_t)fileSize / 2;
    startProgressBar(totalProgressBar);

    // Fill sdBuffer with 1 page at a time then write it repeat until all bytes are written
    int d = 0;
    for (unsigned long currByte = 0; currByte < fileSize / 2; currByte += 64) {
      readSdBuffer128();

      // Blink led
      if (currByte % 4096 == 0) {
        blinkLED();
      }

      // Write command sequence
      writeFlash_MD(0x5555, 0xaa);
      writeFlash_MD(0x2aaa, 0x55);
      writeFlash_MD(0x5555, 0xa0);

      // Write one full page at a time
      for (byte c = 0; c < 64; c++) {
        word currWord = ((sdBuffer[d] & 0xFF) << 8) | (sdBuffer[d + 1] & 0xFF);
        writeFlash_MD(currByte + c, currWord);
        d += 2;
      }
      d = 0;

      // Check if write is complete
      delayMicroseconds(100);
      busyCheck_MD();

      // update progress bar
      processedProgressBar += 64;
      draw_progressbar(processedProgressBar, totalProgressBar);
    }

    // Set data pins to input again
    dataIn_MD();

    // Close the file:
    closeCurrentFile();
  } else {
    showOpenFileErrorAndUpdate();
  }
}

void write29GL_MD() {
  // Create filepath
  appendSelectedFilePath();
  showFlashingFileAndUpdate();

  // Open file on sd card
  if (openSelectedFileForRead()) {
    // Get rom size from file
    fileSize = myFile.fileSize();
    if (fileSize > flashSize) {
      print_FatalError(file_too_big_STR);
    }
    // Set data pins to output
    dataOut_MD();

    //Initialize progress bar
    uint32_t processedProgressBar = 0;
    uint32_t totalProgressBar = (uint32_t)fileSize;
    startProgressBar(totalProgressBar);

    for (unsigned long currSdBuffer = 0; currSdBuffer < fileSize; currSdBuffer += 512) {
      readSdBufferBlock();

      // Blink led
      if (currSdBuffer % 4096 == 0) {
        blinkLED();
      }

      for (int currWriteBuffer = 0; currWriteBuffer < 512; currWriteBuffer += 32) {
        // Two unlock cycles
        writeFlash_MD(0x555, 0xaa);
        writeFlash_MD(0x2aa, 0x55);
        // Write Buffer Load command to Sector Address
        writeFlash_MD((currSdBuffer + currWriteBuffer) / 2, 0x25);
        // Sector Address, Word count
        writeFlash_MD((currSdBuffer + currWriteBuffer) / 2, 16 - 1);

        // Load buffer
        word currWord;
        for (byte currByte = 0; currByte < 32; currByte += 2) {
          currWord = ((sdBuffer[currWriteBuffer + currByte] & 0xFF) << 8) | (sdBuffer[currWriteBuffer + currByte + 1] & 0xFF);
          writeFlash_MD((currSdBuffer + currWriteBuffer + currByte) / 2, currWord);
        }

        // Write buffer
        writeFlash_MD((currSdBuffer + currWriteBuffer + 32 - 2) / 2, 0x29);

        // Check if write is complete
        // Set data pins to input
        dataIn_MD();

        // Read the status register
        word statusReg = readFlash_MD((currSdBuffer + currWriteBuffer + 32 - 2) / 2);

        while ((statusReg | 0xFF7F) != (currWord | 0xFF7F)) {
          statusReg = readFlash_MD((currSdBuffer + currWriteBuffer + 32 - 2) / 2);
        }

        // Set data pins to output
        dataOut_MD();
      }
      // update progress bar
      processedProgressBar += 512;
      draw_progressbar(processedProgressBar, totalProgressBar);
    }

    // Set data pins to input again
    dataIn_MD();

    // Close the file:
    closeCurrentFile();
  } else {
    showOpenFileErrorAndUpdate();
  }
}

void idFlash_MD() {
  // Set data pins to output
  dataOut_MD();

  // ID command sequence
  writeFlash_MD(0x5555, 0xaa);
  writeFlash_MD(0x2aaa, 0x55);
  writeFlash_MD(0x5555, 0x90);

  // Set data pins to input again
  dataIn_MD();

  // Read the two id bytes into a string
  flashid = (readFlash_MD(0) & 0xFF) << 8;
  flashid |= readFlash_MD(1) & 0xFF;
  formatFlashId();
}

byte readStatusReg_MD() {
  // Set data pins to output
  dataOut_MD();

  // Status reg command sequence
  writeFlash_MD(0x5555, 0xaa);
  writeFlash_MD(0x2aaa, 0x55);
  writeFlash_MD(0x5555, 0x70);

  // Set data pins to input again
  dataIn_MD();

  // Read the status register
  byte statusReg = readFlash_MD(0);
  return statusReg;
}

void eraseFlash_MD() {
  // Set data pins to output
  dataOut_MD();

  // Erase command sequence
  writeFlash_MD(0x5555, 0xaa);
  writeFlash_MD(0x2aaa, 0x55);
  writeFlash_MD(0x5555, 0x80);
  writeFlash_MD(0x5555, 0xaa);
  writeFlash_MD(0x2aaa, 0x55);
  writeFlash_MD(0x5555, 0x10);

  // Set data pins to input again
  dataIn_MD();

  busyCheck_MD();
}

void blankcheck_MD() {
  blank = 1;
  for (unsigned long currByte = 0; currByte < flashSize / 2; currByte++) {
    if (readFlash_MD(currByte) != 0xFFFF) {
      currByte = flashSize / 2;
      blank = 0;
    }
    if (currByte % 4096 == 0) {
      blinkLED();
    }
  }
  if (!blank) {
    print_Error(FS(SharedFlashText::textErrorNotBlank));
  }
}

void verifyFlash_MD() {
  // Open file on sd card
  if (openSelectedFileForRead()) {
    // Get rom size from file
    fileSize = myFile.fileSize();
    if (fileSize > flashSize) {
      print_FatalError(file_too_big_STR);
    }

    blank = 0;
    word d = 0;
    for (unsigned long currByte = 0; currByte < fileSize / 2; currByte += 256) {
      if (currByte % 4096 == 0) {
        blinkLED();
      }
      //fill sdBuffer
      readSdBufferBlock();
      for (int c = 0; c < 256; c++) {
        word currWord = ((sdBuffer[d] << 8) | sdBuffer[d + 1]);

        if (readFlash_MD(currByte + c) != currWord) {
          blank++;
        }
        d += 2;
      }
      d = 0;
    }
    if (blank == 0) {
      println_Msg(FS(SharedFlashText::textFlashromVerifiedOK));
      display_Update();
    } else {
      showVerificationErrorCount(blank);
    }
    // Close the file:
    closeCurrentFile();
  } else {
    showOpenFileErrorAndUpdate();
  }
}

// Delay between write operations based on status register
void busyCheck_MD() {
  // Set data pins to input
  dataIn_MD();

  // Read the status register
  word statusReg = readFlash_MD(0);

  while ((statusReg | 0xFF7F) != 0xFFFF) {
    statusReg = readFlash_MD(0);
  }

  // Set data pins to output
  dataOut_MD();
}
#endif

//******************************************
// EEPROM Functions
//******************************************
void EepromInit(byte eepmode) {    // Acclaim Type 2
  PORTF = 0x00;                    // ADDR A0-A7
  PORTK = 0x00;                    // ADDR A8-A15
  PORTL = 0x10;                    // ADDR A16-A23
  PORTA = 0x00;                    // DATA D8-D15
  PORTH |= (1 << 0);               // /RES HIGH
  PORTC = eepmode;                 // EEPROM Switch:  0 = Enable (Read EEPROM), 1 = Disable (Read ROM)
  PORTH &= ~(1 << 3);              // CE LOW
  PORTH &= ~(1 << 4) & ~(1 << 5);  // /UDSW + /LDSW LOW
  PORTH |= (1 << 6);               // OE HIGH
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
          "nop\n\t");
  PORTH |= (1 << 4) | (1 << 5);  // /UDSW + /LDSW HIGH
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
          "nop\n\t");
}

static void writeWord_Acclaim_MD(unsigned long myAddress, word myData, byte activeSwitch, byte inactiveSwitch) __attribute__((noinline));
static void writeWord_Acclaim_MD(unsigned long myAddress, word myData, byte activeSwitch, byte inactiveSwitch) {
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTL = (myAddress >> 16) & 0xFF;
  PORTC = myData;
  PORTH &= ~(1 << 3);  // CE LOW
  PORTH &= ~activeSwitch;
  PORTH |= inactiveSwitch;
  PORTH |= (1 << 6);   // OE HIGH
  if (eepSize > 0x100)
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
            "nop\n\t");
  else
    delayMicroseconds(100);
  PORTH |= activeSwitch;
  if (eepSize > 0x100)
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
            "nop\n\t");
  else
    delayMicroseconds(100);
}

void writeWord_SDA(unsigned long myAddress, word myData) {
  writeWord_Acclaim_MD(myAddress, myData, (1 << 5), (1 << 4));
}

void writeWord_SCL(unsigned long myAddress, word myData) {
  writeWord_Acclaim_MD(myAddress, myData, (1 << 4), (1 << 5));
}

void writeWord_CM(unsigned long myAddress, word myData) {  // Codemasters
  PORTF = myAddress & 0xFF;
  PORTK = (myAddress >> 8) & 0xFF;
  PORTL = (myAddress >> 16) & 0xFF;
  PORTC = myData;
  PORTA = (myData >> 8) & 0xFF;

  // Arduino running at 16Mhz -> one nop = 62.5ns
  // Wait till output is stable
  __asm__("nop\n\t"
          "nop\n\t");

  // Switch WR(PH4) to LOW
  PORTH &= ~(1 << 4);
  // Setting CS(PH3) LOW
  PORTH &= ~(1 << 3);
  // Pulse CLK(PH1)
  PORTH ^= (1 << 1);

  // Leave WR low for at least 200ns
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
          "nop\n\t");

  // Pulse CLK(PH1)
  PORTH ^= (1 << 1);
  // Setting CS(PH3) HIGH
  PORTH |= (1 << 3);
  // Switch WR(PH4) to HIGH
  PORTH |= (1 << 4);

  // Leave WR high for at least 50ns
  __asm__("nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t"
          "nop\n\t");
}

// EEPROM COMMANDS
void EepromStart() {
  if (eepType == 2) {               // Acclaim Type 2
    writeWord_SDA(0x100000, 0x00);  // sda low
    writeWord_SCL(0x100000, 0x00);  // scl low
    writeWord_SDA(0x100000, 0x01);  // sda high
    writeWord_SCL(0x100000, 0x01);  // scl high
    writeWord_SDA(0x100000, 0x00);  // sda low
    writeWord_SCL(0x100000, 0x00);  // scl low
  } else if (eepType == 4) {        // EA
    writeWord_MD(0x100000, 0x00);   // sda low, scl low
    writeWord_MD(0x100000, 0xC0);   // sda, scl high
    writeWord_MD(0x100000, 0x40);   // sda low, scl high
    writeWord_MD(0x100000, 0x00);   // START
  } else if (eepType == 5) {        // Codemasters
    writeWord_CM(0x180000, 0x00);   // sda low, scl low
    writeWord_CM(0x180000, 0x02);   // sda low, scl high
    writeWord_CM(0x180000, 0x03);   // sda, scl high
    writeWord_CM(0x180000, 0x02);   // sda low, scl high
    writeWord_CM(0x180000, 0x00);   // START
  } else {
    writeWord_MD(0x100000, 0x00);  // sda low, scl low
    writeWord_MD(0x100000, 0x03);  // sda, scl high
    writeWord_MD(0x100000, 0x02);  // sda low, scl high
    writeWord_MD(0x100000, 0x00);  // START
  }
}

static void setEepromBit_MD(byte bitValue) __attribute__((noinline));
static void setEepromBit_MD(byte bitValue) {
  if (eepType == 2) {
    writeWord_SDA(0x100000, bitValue);
    writeWord_SCL(0x100000, 0x01);
    writeWord_SDA(0x100000, bitValue);
    writeWord_SCL(0x100000, 0x00);
  } else if (eepType == 4) {
    byte value = bitValue ? 0x80 : 0x00;
    writeWord_MD(0x100000, value);
    writeWord_MD(0x100000, value | 0x40);
    writeWord_MD(0x100000, value);
    if (bitValue)
      writeWord_MD(0x100000, 0x00);
  } else if (eepType == 5) {
    writeWord_CM(0x180000, bitValue);
    writeWord_CM(0x180000, bitValue | 0x02);
    writeWord_CM(0x180000, bitValue);
    if (bitValue)
      writeWord_CM(0x180000, 0x00);
  } else {
    writeWord_MD(0x100000, bitValue);
    writeWord_MD(0x100000, bitValue | 0x02);
    writeWord_MD(0x100000, bitValue);
    if (bitValue)
      writeWord_MD(0x100000, 0x00);
  }
}

void EepromSet0() {
  setEepromBit_MD(0);
}

void EepromSet1() {
  setEepromBit_MD(1);
}

void EepromDevice() {  // 24C02+
  EepromSet1();
  EepromSet0();
  EepromSet1();
  EepromSet0();
}

void EepromSetDeviceAddress(word addrhi) {  // 24C02+
  for (int i = 0; i < 3; i++) {
    if ((addrhi >> 2) & 0x1)  // Bit is HIGH
      EepromSet1();
    else  // Bit is LOW
      EepromSet0();
    addrhi <<= 1;  // rotate to the next bit
  }
}

void EepromStatus() {  // ACK
  byte eepStatus = 1;
  if (eepType == 1 || eepType == 3) {
    const byte ackMask = eepType == 1 ? 0x02 : 0x01;
    writeWord_MD(0x100000, 0x01);  // sda high, scl low
    writeWord_MD(0x100000, 0x03);  // sda high, scl high
    do {
      dataIn_MD();
      eepStatus = (readWord_MD(0x100000) & ackMask) != 0;
      dataOut_MD();
      delayMicroseconds(4);
    } while (eepStatus == 1);
    writeWord_MD(0x100000, 0x01);  // sda high, scl low
  } else if (eepType == 2) {        // Acclaim Type 2
    writeWord_SDA(0x100000, 0x01);  // sda high
    writeWord_SCL(0x100000, 0x01);  // scl high
    do {
      dataIn_MD();
      eepStatus = (readWord_MD(0x100000) & 0x1);
      dataOut_MD();
      delayMicroseconds(4);
    } while (eepStatus == 1);
    writeWord_SCL(0x100000, 0x00);  // scl low
  } else if (eepType == 4) {       // EA
    writeWord_MD(0x100000, 0x80);  // sda high, scl low
    writeWord_MD(0x100000, 0xC0);  // sda high, scl high
    do {
      dataIn_MD();
      eepStatus = ((readWord_MD(0x100000) >> 7) & 0x1);
      dataOut_MD();
      delayMicroseconds(4);
    } while (eepStatus == 1);
    writeWord_MD(0x100000, 0x80);  // sda high, scl low
  } else if (eepType == 5) {       // Codemasters
    writeWord_CM(0x180000, 0x01);  // sda high, scl low
    writeWord_CM(0x180000, 0x03);  // sda high, scl high
    do {
      dataIn_MD();
      eepStatus = ((readWord_MD(0x1C0000) >> 7) & 0x1);
      dataOut_MD();
      delayMicroseconds(4);
    } while (eepStatus == 1);
    writeWord_CM(0x180000, 0x01);  // sda high, scl low
  }
}

void EepromReadMode() {
  EepromSet1();    // READ
  EepromStatus();  // ACK
}

void EepromWriteMode() {
  EepromSet0();    // WRITE
  EepromStatus();  // ACK
}

void EepromReadData() {
  if (eepType == 1 || eepType == 3) {
    const byte bitShift = eepType == 1 ? 1 : 0;
    for (int i = 0; i < 8; i++) {
      writeWord_MD(0x100000, 0x03);  // sda high, scl high
      dataIn_MD();
      eepbit[i] = (readWord_MD(0x100000) >> bitShift) & 0x1;
      dataOut_MD();
      writeWord_MD(0x100000, 0x01);  // sda high, scl low
    }
  } else if (eepType == 2) {  // Acclaim Type 2
    for (int i = 0; i < 8; i++) {
      writeWord_SDA(0x100000, 0x01);  // sda high
      writeWord_SCL(0x100000, 0x01);  // scl high
      dataIn_MD();
      eepbit[i] = (readWord_MD(0x100000) & 0x1);  // Read 0x100000 with Mask 0x1 (bit 0)
      dataOut_MD();
      writeWord_SDA(0x100000, 0x01);  // sda high
      writeWord_SCL(0x100000, 0x00);  // scl low
    }
  } else if (eepType == 4) {  // EA
    for (int i = 0; i < 8; i++) {
      writeWord_MD(0x100000, 0xC0);  // sda high, scl high
      dataIn_MD();
      eepbit[i] = ((readWord_MD(0x100000) >> 7) & 0x1);  // Read 0x100000 with Mask (bit 7)
      dataOut_MD();
      writeWord_MD(0x100000, 0x80);  // sda high, scl low
    }
  } else if (eepType == 5) {  // Codemasters
    for (int i = 0; i < 8; i++) {
      writeWord_CM(0x180000, 0x03);  // sda high, scl high
      dataIn_MD();
      eepbit[i] = ((readWord_MD(0x1C0000) >> 7) & 0x1);  // Read 0x1C0000 with Mask 0x1 (bit 7)
      dataOut_MD();
      writeWord_CM(0x180000, 0x01);  // sda high, scl low
    }
  }
}

void EepromWriteData(byte data) {
  for (int i = 0; i < 8; i++) {
    if ((data >> 7) & 0x1)  // Bit is HIGH
      EepromSet1();
    else  // Bit is LOW
      EepromSet0();
    data <<= 1;  // rotate to the next bit
  }
  EepromStatus();  // ACK
}

static void finishOrStopEeprom_MD(bool stop) __attribute__((noinline));
static void finishOrStopEeprom_MD(bool stop) {
  if (eepType == 2) {
    writeWord_SDA(0x100000, 0x00);
    writeWord_SCL(0x100000, stop ? 0x01 : 0x00);
    writeWord_SDA(0x100000, 0x01);
    writeWord_SCL(0x100000, stop ? 0x01 : 0x00);
    if (!stop) {
      writeWord_SDA(0x100000, 0x01);
      writeWord_SCL(0x100000, 0x01);
    }
    writeWord_SDA(0x100000, 0x01);
    writeWord_SCL(0x100000, 0x00);
    writeWord_SDA(0x100000, 0x00);
    writeWord_SCL(0x100000, 0x00);
  } else if (eepType == 4) {
    writeWord_MD(0x100000, 0x00);
    writeWord_MD(0x100000, stop ? 0x40 : 0x80);
    writeWord_MD(0x100000, 0xC0);
    writeWord_MD(0x100000, 0x80);
    writeWord_MD(0x100000, 0x00);
  } else if (eepType == 5) {
    writeWord_CM(0x180000, 0x00);
    writeWord_CM(0x180000, stop ? 0x02 : 0x01);
    writeWord_CM(0x180000, 0x03);
    writeWord_CM(0x180000, 0x01);
    writeWord_CM(0x180000, 0x00);
  } else {
    writeWord_MD(0x100000, 0x00);
    writeWord_MD(0x100000, stop ? 0x02 : 0x01);
    writeWord_MD(0x100000, 0x03);
    writeWord_MD(0x100000, 0x01);
    writeWord_MD(0x100000, 0x00);
  }
}

void EepromFinish() {
  finishOrStopEeprom_MD(false);
}

void EepromStop() {
  finishOrStopEeprom_MD(true);
}

void EepromSetAddress(word address) {
  if (eepSize > 0x80) {  // 24C02+
    for (int i = 0; i < 8; i++) {
      if ((address >> 7) & 0x1)  // Bit is HIGH
        EepromSet1();
      else  // Bit is LOW
        EepromSet0();
      address <<= 1;  // rotate to the next bit
    }
    EepromStatus();  // ACK
  } else {           // 24C01
    for (int i = 0; i < 7; i++) {
      if ((address >> 6) & 0x1)  // Bit is HIGH
        EepromSet1();
      else  // Bit is LOW
        EepromSet0();
      address <<= 1;  // rotate to the next bit
    }
  }
}

static void addressEepromByte_MD() __attribute__((noinline));
static void addressEepromByte_MD() {
  dataOut_MD();
  if (eepType == 2)
    EepromInit(0);  // Enable EEPROM
  EepromStart();    // START
  if (eepSize > 0x80) {
    EepromDevice();         // DEVICE [1010]
    if (eepSize > 0x800) {  // MODE 3 [24C65]
      EepromSetDeviceAddress(0);
      EepromWriteMode();
      EepromSetAddress(addrhi);        // ADDR [A15..A8]
    } else {                           // MODE 2 [24C02/24C08/24C16]
      EepromSetDeviceAddress(addrhi);  // ADDR [A10..A8]
      EepromWriteMode();
    }
  }
  EepromSetAddress(addrlo);
}

void readEepromByte(word address) {
  addrhi = address >> 8;
  addrlo = address & 0xFF;
  addressEepromByte_MD();
  if (eepSize > 0x80) {
    EepromStart();        // START
    EepromDevice();       // DEVICE [1010]
    if (eepSize > 0x800)  // MODE 3 [24C65]
      EepromSetDeviceAddress(0);
    else                               // MODE 2 [24C02/24C08/24C16]
      EepromSetDeviceAddress(addrhi);  // ADDR [A10..A8]
  }
  EepromReadMode();
  EepromReadData();
  EepromFinish();
  EepromStop();  // STOP
  if (eepType == 2)
    EepromInit(1);  // Disable EEPROM
  // OR 8 bits into byte
  eeptemp = 0;
  for (byte i = 0; i < 8; i++)
    eeptemp = (eeptemp << 1) | eepbit[i];
  sdBuffer[addrlo] = eeptemp;
}

void writeEepromByte(word address) {
  addrhi = address >> 8;
  addrlo = address & 0xFF;
  eeptemp = sdBuffer[addrlo];
  addressEepromByte_MD();
  if (eepSize <= 0x80)
    EepromWriteMode();  // 24C01
  EepromWriteData(eeptemp);
  EepromStop();  // STOP
  if (eepType == 2)
    EepromInit(1);  // Disable EEPROM
}

// Read EEPROM and save to the SD card
static void openMdBackupOutput() __attribute__((noinline));
static void openMdBackupOutput() {
  // write new folder number back to eeprom
  foldern = foldern + 1;
  EEPROM_writeAnything(0, foldern);

  println_Msg(FS(SharedFlashText::textReading));
  display_Update();

  // Open file on sd card
  if (!openNamedOutputFile()) {
    fatalSdError();
  }
}

void readEEP_MD() {
  dataIn_MD();

  // Get name, add extension and convert to char array for sd lib
  createFolder("MD", "SAVE", romName, "eep");

  openMdBackupOutput();
  if (eepSize > 0x100) {  // 24C04+
    for (word currByte = 0; currByte < eepSize; currByte += 256) {
      print_Msg(F("*"));
      display_Update();
      for (int i = 0; i < 256; i++) {
        readEepromByte(currByte + i);
      }
      myFile.write(sdBuffer, 256);
    }
  } else {  // 24C01/24C02
    for (word currByte = 0; currByte < eepSize; currByte++) {
      if ((currByte != 0) && ((currByte + 1) % 16 == 0)) {
        print_Msg(F("*"));
        display_Update();
      }
      readEepromByte(currByte);
    }
    myFile.write(sdBuffer, eepSize);
  }
  // Close the file:
  closeBlankAndClear();
  showSavedToFolder();

  display_Update();
}

void writeEEP_MD() {
  dataOut_MD();

  // Create filepath
  appendPathAndShowWritingProgress();

  // Open file on sd card
  if (openSelectedFileForRead()) {
    if (eepSize > 0x100) {  // 24C04+
      for (word currByte = 0; currByte < eepSize; currByte += 256) {
        myFile.read(sdBuffer, 256);
        for (int i = 0; i < 256; i++) {
          writeEepromByte(currByte + i);
          delay(50);  // DELAY NEEDED
        }
        print_Msg(F("."));
        display_Update();
      }
    } else {  // 24C01/24C02
      myFile.read(sdBuffer, eepSize);
      for (word currByte = 0; currByte < eepSize; currByte++) {
        writeEepromByte(currByte);
        print_Msg(F("."));
        if ((currByte != 0) && ((currByte + 1) % 64 == 0))
          printBlankLine();
        display_Update();  // ON SERIAL = delay(100)
      }
    }
    // Close the file:
    closeBlankAndClear();
    showDoneAndUpdate();
  } else {
    fatalSdError();
  }
  dataIn_MD();
}

//******************************************
// CD Backup RAM Functions
//******************************************
void readBram_MD() {
  dataIn_MD();

  // Get name, add extension and convert to char array for sd lib
  createFolder("MD", "RAM", "Cart", "brm");

  openMdBackupOutput();

  for (unsigned long currByte = 0; currByte < bramSize; currByte += 512) {
    for (int i = 0; i < 512; i++) {
      sdBuffer[i] = readWord_MD(0x300000 + currByte + i);
    }
    writeSdBufferBlock();
  }

  // Close the file:
  closeBlankAndClear();
  showSavedToFolder();

  display_Update();
}

void writeBram_MD() {
  dataOut_MD();

  // Create filepath
  appendPathAndShowWritingProgress();

  // Open file on sd card
  if (openSelectedFileForRead()) {

    // 0x700000-0x7FFFFF: Writes by /LWR latch D0; 1=RAM write enabled, 0=disabled
    writeWord_MD(0x380000, 1);  // Enable BRAM Writes

    for (unsigned long currByte = 0; currByte < bramSize; currByte += 512) {
      readSdBufferBlock();
      for (int i = 0; i < 512; i++) {
        writeWord_MD(0x300000 + currByte + i, sdBuffer[i]);
      }
    }
    writeWord_MD(0x380000, 0);  // Disable BRAM Writes
    // Close the file:
    closeBlankAndClear();
    showDoneAndUpdate();
  } else {
    fatalSdError();
  }
  dataIn_MD();
}

//******************************************
// Realtec Mapper Functions
//******************************************
void writeRealtec(unsigned long address, byte value) {  // Realtec 0x404000 (UPPER)/0x400000 (LOWER)
  dataOut_MD();
  PORTF = address & 0xFF;          // 0x00 ADDR A0-A7
  PORTK = (address >> 8) & 0xFF;   // ADDR A8-A15
  PORTL = (address >> 16) & 0xFF;  //0x20 ADDR A16-A23
  PORTA = 0x00;                    // DATA D8-D15
  PORTH |= (1 << 0);               // /RES HIGH

  PORTH |= (1 << 3);  // CE HIGH
  PORTC = value;
  PORTH &= ~(1 << 4) & ~(1 << 5);  // /UDSW + /LDSW LOW
  PORTH |= (1 << 4) | (1 << 5);    // /UDSW + /LDSW HIGH
  dataIn_MD();
}

void readRealtec_MD() {
  // Set control
  dataIn_MD();

  // Get name, add extension and convert to char array for sd lib
  createFolderAndOpenFile("MD", "ROM", romName, "MD");

  // Realtec Registers
  writeWord_MD(0x201000, 4);  // Number of 128K Blocks 0x402000 (0x201000)
  writeRealtec(0x200000, 1);  // ROM Lower Address 0x400000 (0x200000)
  writeRealtec(0x202000, 0);  // ROM Upper Address 0x404000 (0x202000)

  word d = 0;
  for (unsigned long currBuffer = 0; currBuffer < cartSize / 2; currBuffer += 256) {
    // Blink led
    if (currBuffer % 16384 == 0)
      blinkLED();

    for (int currWord = 0; currWord < 256; currWord++) {
      word myWord = readWord_MD(currBuffer + currWord);
      // Split word into two bytes
      // Left
      sdBuffer[d] = ((myWord >> 8) & 0xFF);
      // Right
      sdBuffer[d + 1] = (myWord & 0xFF);
      d += 2;
    }
    writeSdBufferBlock();
    d = 0;
  }
  // Close the file:
  closeCurrentFile();
}

void printRomSize_MD(int index) {
#ifdef ENABLE_GLOBAL_LOG
  dont_log = true;
#endif
  display_Clear();
  printRomSizeLabel();
  print_Msg(pgm_read_byte(&(MDSize[index])));
  println_Msg(FS(SharedFlashText::textMbit));
#ifdef ENABLE_GLOBAL_LOG
  dont_log = false;
#endif
}

void force_cartSize_MD() {
  cartSize = navigateMenu(0, sizeof(MDSize) - 1, &printRomSize_MD);
  cartSize = pgm_read_byte(&(MDSize[cartSize])) * 131072;
#if (defined(ENABLE_OLED) || defined(ENABLE_LCD))
  display.setCursor(0, 56);  // Display selection at bottom
#endif
  printRomSizeLabel();
  print_Msg(cartSize / 131072);
  println_Msg(FS(SharedFlashText::textMbit));
  display_Update();
  delay(1000);
}

// CFI Support
#ifdef ENABLE_FLASH
void eraseFlashCFI_MD() {
  for (byte currChip = 0; currChip < totalChipsCFI; currChip++) {
    print_Msg(F("Erasing Chip"));
    print_Msg(currChip);
    println_Msg("...");
    display_Update();
    eraseFlashCFIChip_MD(currChip);
  }
  display_Clear();
}

void eraseFlashCFIChip_MD(byte currChip) {
  resetFlashCFIChip_MD(currChip);

  dataOut_MD();
  sendCFICommand_MD(currChip, 0x80);
  sendCFICommand_MD(currChip, 0x10);

  dataIn_MD();
  byte statusReg = readFlashCFI_MD(currChip, 0);
  while ((statusReg & 0x80) != 0x80) {
    blinkLED();
    delay(100);
    statusReg = readFlashCFI_MD(currChip, 0);
  }
}

void resetFlashCFI_MD() {
  for (byte currChip = 0; currChip < totalChipsCFI; currChip++) {
    resetFlashCFIChip_MD(currChip);
  }
}

void resetFlashCFIChip_MD(byte currChip) {
  dataOut_MD();
  writeFlashCFI_MD(currChip, 0x555, 0xf0);
  delay(100);
}

void writeCFI_MD() {
  if (openSelectedFileForRead()) {
    // Get rom size from file
    fileSize = myFile.fileSize();
    if (fileSize > totalFlashSizeCFI) {
      print_FatalError(file_too_big_STR);
      return;
    }

    unsigned long flashed = 0;
    byte currChip = 0;
    while (flashed < fileSize) {
      unsigned long toFlash = min(fileSize - flashed, flashSizeCFI[currChip]);
      writeCFIChip_MD(currChip, toFlash, fileSize);
      flashed += toFlash;
      currChip++;
    }

    closeCurrentFile();
  } else {
    fatalSdError();
  }
}

void writeCFIChip_MD(byte currChip, unsigned long toFlash, unsigned long fileSize) {
  display_Clear();
  print_STR(flashing_file_STR, 0);
  print_Msg(filePath);
  println_Msg(FS(SharedFlashText::ellipsis));
  print_Msg(F("Writing"));
  if (currChip == 0 && toFlash == fileSize)  {
    println_Msg("...");
  } else {
    print_Msg(" Chip");
    print_Msg(currChip);
    println_Msg("...");
  }
  display_Update();

  //Initialize progress bar
  uint32_t processedProgressBar = 0;
  uint32_t totalProgressBar = (uint32_t)toFlash / 2;
  startProgressBar(totalProgressBar);

  resetFlashCFIChip_MD(currChip);
  for (unsigned long a = 0; a < toFlash / 2; a += 256) {
    readSdBufferBlock();

    for (int c = 0; c < 256; c++) {
      dataOut_MD();
      sendCFICommand_MD(currChip, 0xa0);

      word currWord = ((sdBuffer[c*2] & 0xFF) << 8) | (sdBuffer[c*2 + 1] & 0xFF);
      writeFlashCFI_MD(currChip, a + c, currWord);

      dataIn_MD();
      byte statusReg = readFlashCFI_MD(currChip, a + c);
      while ((statusReg & 0x80) != (sdBuffer[c*2+1] & 0x80)) {
        statusReg = readFlashCFI_MD(currChip, a + c);
      }
    }

    // update progress bar
    processedProgressBar += 256;
    draw_progressbar(processedProgressBar, totalProgressBar);
  }

  resetFlashCFIChip_MD(currChip);
}

void verifyFlashCFI_MD() {
  // Open file on sd card
  if (openSelectedFileForRead()) {
    // Get rom size from file
    fileSize = myFile.fileSize();
    if (fileSize > totalFlashSizeCFI) {
      print_FatalError(file_too_big_STR);
    }

    unsigned long verified = 0;
    byte currChip = 0;
    while (verified < fileSize) {
      unsigned long toVerify = min(fileSize - verified, flashSizeCFI[currChip]);
      verifyFlashCFIChip_MD(currChip, toVerify);
      verified += toVerify;
      currChip++;
    }

    closeCurrentFile();
  } else {
    showOpenFileErrorAndUpdate();
  }
}

void verifyFlashCFIChip_MD(byte currChip, unsigned long toVerify) {
  print_Msg(F("Verifying Chip"));
  print_Msg(currChip);
  println_Msg(FS(SharedFlashText::ellipsis));
  display_Update();

  blank = 0;
  word d = 0;
  dataIn_MD();
  for (unsigned long a = 0; a < toVerify / 2; a += 256) {
    readSdBufferBlock();

    for (int c = 0; c < 256; c++) {
      word currWord = ((sdBuffer[c*2] & 0xFF) << 8) | (sdBuffer[c*2 + 1] & 0xFF);
      if (readFlashCFI_MD(currChip, a + c) != currWord) {
        blank++;
      }
    }
  }

  if (blank == 0) {
    println_Msg(FS(SharedFlashText::textFlashromVerifiedOK));
    display_Update();
  } else {
    showVerificationErrorCount(blank);
  }
}

void identifyFlashCFI_MD() {
  totalChipsCFI = 0;
  totalFlashSizeCFI = 0;

  if (identifyFlashCFIChip_MD(0) || identifyCFI_29F800_MD(0)) {
    totalFlashSizeCFI += flashSizeCFI[0];
  } else {
    println_Msg(FS(SharedFlashText::textCFIQueryFailed));
    resetFlashCFIChip_MD(0);
    print_STR(press_button_STR, 0);
    updateDisplayAndWait();
    resetArduino();
    return;
  }

  if (totalFlashSizeCFI < 2097152) {
    // Only supports 2 flash chips if the first one is 16Mbit.
    return;
  }

  if (identifySramCFI_MD(1)) {
    println_Msg(F("Chip1 SRAM"));
    display_Update();
    return;
  }

  if (identifyFlashCFIChip_MD(1)) {
    totalFlashSizeCFI += flashSizeCFI[1];
  }
}

bool identifySramCFI_MD(byte currChip) {
  dataIn_MD();
  word firstWord = readFlashCFI_MD(currChip, 0x0);
  dataOut_MD();
  writeFlashCFI_MD(currChip, 0x0, firstWord + 0x0101);
  dataIn_MD();
  word readBack = readFlashCFI_MD(currChip, 0x0);
  dataOut_MD();
  writeFlashCFI_MD(currChip, 0x0, firstWord);
  dataIn_MD();
  // If we were able to change the value, this is a SRAM Chip and not Flash.
  return firstWord != readBack;
}

bool identifyFlashCFIChip_MD(byte currChip) {
  startCFIMode_MD(currChip);
  dataIn_MD();
  char cfiQRYx16[13];
  sprintf(cfiQRYx16, "%02X%02X%02X",
    readFlashCFI_MD(currChip, 0x10),
    readFlashCFI_MD(currChip, 0x11),
    readFlashCFI_MD(currChip, 0x12));

  char cfiID[17];
  unsigned long chipIdHigh = (long(readFlashCFI_MD(currChip, 0x61)) << 16)
        | readFlashCFI_MD(currChip, 0x62);
  unsigned long chipIdLow = (long(readFlashCFI_MD(currChip, 0x63)) << 16)
        | readFlashCFI_MD(currChip, 0x64);
  sprintf(cfiID, "%08lX%08lX", chipIdHigh, chipIdLow);
  chipIdLowCFI[currChip] = chipIdLow;
  chipIdHighCFI[currChip] = chipIdHigh;

  if (currChip == 1 && chipIdLowCFI[0] == chipIdLow && chipIdHighCFI[0] == chipIdHigh) {
    // If the ID matches then this board has only one flash chip
    resetFlashCFIChip_MD(currChip);
    dataIn_MD();
    return false;
  }

  word sizeReg = readFlashCFI_MD(currChip, 0x27);
  unsigned long size = 1L << sizeReg;
  if (strcmp(cfiQRYx16, "515259") != 0) {  // QRY in x16 mode
    // Did not return "QRY", does not support CFI
    return false;
  }

  totalChipsCFI++;
  flashSizeCFI[currChip] = size;
  print_Msg(FS(SharedFlashText::textChip));
  print_Msg(currChip);
  print_Msg(F(" CFI "));
  print_Msg(size >> 17);
  println_Msg(F("MBit x16"));
  print_Msg(F("SN: "));
  println_Msg(cfiID);
  display_Update();

  // Reset flash
  resetFlashCFIChip_MD(currChip);
  dataIn_MD();

  return true;
}

// The 29F800 is compatible with CFI commands but does not offer
// the ID part of CFI so we have to identify it here.
bool identifyCFI_29F800_MD(byte currChip) {
  resetFlashCFIChip_MD(currChip);
  dataOut_MD();
  sendCFICommand_MD(currChip, 0x90);
  dataIn_MD();
  word deviceId = readFlashCFI_MD(currChip, 0x01);
  if (deviceId == 0x2258) {
    totalChipsCFI++;
    flashSizeCFI[currChip] = 1048576;
    print_Msg(FS(SharedFlashText::textChip));
    print_Msg(currChip);
    println_Msg(F(" 8MBit 29F800"));
    display_Update();
    return true;
  }
  return false;
}

void sendCFICommand_MD(byte currChip, byte cmd) {
  writeFlashCFI_MD(currChip, 0x555, 0xaa);
  writeFlashCFI_MD(currChip, 0x2AA, 0x55);
  writeFlashCFI_MD(currChip, 0x555, cmd);
}

void startCFIMode_MD(byte currChip) {
  dataOut_MD();
  writeFlashCFI_MD(currChip, 0x555, 0xf0);  //x16 mode reset command
  delay(500);
  writeFlashCFI_MD(currChip, 0x555, 0xf0);  //Double reset to get out of possible Autoselect + CFI mode
  delay(500);
  writeFlashCFI_MD(currChip, 0x55, 0x98);  //x16 CFI Query command
}

void writeFlashCFI_MD(byte currChip, unsigned long myAddress, word myData) {
  if (currChip == 1) {
    // Pin A20 switches from low to high ROM
    return writeFlash_MD(myAddress | (1L << 20), myData);
  } else {
    return writeFlash_MD(myAddress, myData);
  }
}

word readFlashCFI_MD(byte currChip, unsigned long myAddress) {
  if (currChip == 1) {
    // Pin A20 switches from low to high ROM
    return readFlash_MD(myAddress | (1L << 20));
  } else {
    return readFlash_MD(myAddress);
  }
}

#endif // ENABLE_FLASH

#endif // ENABLE_MD

//******************************************
// End of File
//******************************************
