/******************************************
  SUPER FAMICOM SUFAMI TURBO MODULE
******************************************/
#if (defined(ENABLE_ST) && defined(ENABLE_SNES))

/******************************************
  Menu
*****************************************/
// Sufami Turbo menu items
static const char stMenuItem1[] PROGMEM = "Read cart in Slot A";
static const char stMenuItem2[] PROGMEM = "Read cart in Slot B";
static const char* const menuOptionsST[] PROGMEM = { stMenuItem1, stMenuItem2, FSTRING_RESET };

void stMenu() {
  // Create ST menu with title and 3 options to choose from
  unsigned char mainMenu;
  mainMenu = chooseFlashMenuOption(F("Sufami Turbo"), menuOptionsST, 3);

  // Wait for user choice to come back from the question box menu
  switch (mainMenu) {
    // Read cart in ST slot A
    case 0:
      readSlot(0);
      break;

    // Read cart in ST slot B
    case 1:
      readSlot(1);
      break;

    // Reset
    case 2:
      resetArduino();
      break;
  }
}

/******************************************
   Setup
 *****************************************/
void setup_ST() {
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
  // Set expand(PG5) to Input
  DDRG &= ~(1 << 5);
  // Set Data Pins (D0-D7) to Input
  DDRC = 0x00;
  // Unused pins
  // Set wram(PE4) to Output
  DDRE |= (1 << 4);
  // Set pawr(PJ1) to Output
  DDRJ |= (1 << 1);
  // Set pard(PJ0) to Output
  DDRJ |= (1 << 0);

  //Check if Sufami Turbo adapter is inserted
  if (!getHeader(0)) {
    display_Clear();
    println_Msg(F("Sufami Turbo adapter"));
    println_Msg(F("was not found."));
    updateDisplayAndWait();
    resetArduino();
  }
}

/******************************************
  ROM Functions
******************************************/
// Verify if 'BANDAI' header is present in specified bank
bool getHeader(unsigned int bank) {
  byte snesHeader[16];
  PORTL = bank;

  // Read first bytes
  for (uint16_t c = 0, currByte = 0; c < 16; c++, currByte++) {
    PORTF = (currByte & 0xFF);
    PORTK = ((currByte >> 8) & 0xFF);
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    NOP;
    snesHeader[c] = PINC;
  }

  // Format internal name
  buildRomName(romName, &snesHeader[0], 14);

  // Check if 'BANDAI' header is present
  if (strncmp(romName, "BANDAI SFC-ADX", 14) == 0)
    return (1);
  else
    return (0);
}

// Select the slot to use and detect cart size
void readSlot(bool cartSlot) {
  // Set control
  dataIn();
  controlIn_SNES();
  changeToStorageRoot();
  display_Clear();

  if (!cartSlot) {           // Slot A was selected
    if (getHeader(32)) {     // Look for a cart in slot A
      if (getHeader(48))     // Look for mirrored data in slot A
        readRom_ST(32, 48);  // Dump 512KB cart
      else
        readRom_ST(32, 64);  // Dump 1MB cart
    }
    else {
      println_Msg(F("No cart detected in Slot A"));
      updateDisplayAndWait();
    }
  }
  else {                      // Slot B was selected
    if (getHeader(64)) {      // Look for a cart in slot B
      if (getHeader(80))      // Look for mirrored data in slot B
        readRom_ST(64, 80);   // Dump 512KB cart
      else
        readRom_ST(64, 96);   // Dump 1MB cart
    }
    else {
      println_Msg(F("No cart detected in Slot B"));
      updateDisplayAndWait();
    }
  }
}

// Read ST rom to SD card
void readRom_ST(unsigned int bankStart, unsigned int bankEnd) {
  // create a new folder to save rom file
  createFolderAndOpenFile("ST", "ROM", "SUFAMI_TURBO", "st");

  // Read specified banks
  readLoRomBanks(bankStart + 0x80, bankEnd + 0x80, &myFile);

  // Close file:
  closeCurrentFile();

  // Compare dump CRC with db values
  compareCRC("st.txt", 0, 1, 0);

  printBlankLine();
  promptAndWaitForButton();
}
#endif

//******************************************
// End of File
//******************************************
