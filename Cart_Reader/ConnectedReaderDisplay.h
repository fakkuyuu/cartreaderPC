// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <avr/pgmspace.h>
namespace PcLink { bool connected(); }
void readerConnectionDisplayRefresh();

// Full-buffer HW3 (R0) and HW5 (R2) displays. Overlay only at the existing
// transfer to the panel; restore the original nine bytes afterwards, so a
// disconnect never leaves the badge in the application's framebuffer.
template<class Base, bool Rotated>
class ConnectedReaderDisplay : public Base {
  void connectedTransfer(bool send) {
    uint8_t* buffer=Base::getBufferPtr();
    const uint16_t width=Base::getBufferTileWidth()*8;
    const uint16_t offset=Rotated ? 0 : (Base::getBufferTileHeight()-1)*width+width-9;
    uint8_t previous[9];
    for(uint8_t i=0;i<9;i++) previous[i]=buffer[offset+i];
    const uint8_t color=Base::getDrawColor();
    Base::setDrawColor(0); Base::drawBox(119,57,9,7);
    Base::setDrawColor(1);
    // Bottom-right: 2 black pixels above/left, flush with right/bottom.
    // Columns of the user's 7x5 PC glyph (not a font or another framebuffer).
    static const uint8_t glyph[7] PROGMEM={0x1f,0x05,0x02,0x00,0x0e,0x11,0x11};
    for(uint8_t x=0;x<7;x++) {
      uint8_t column=pgm_read_byte(glyph+x);
      for(uint8_t y=0;y<5;y++) if(column & (1<<y)) Base::drawPixel(121+x,59+y);
    }
    Base::setDrawColor(color);
    if(send) Base::sendBuffer(); else Base::updateDisplay();
    for(uint8_t i=0;i<9;i++) buffer[offset+i]=previous[i];
  }
 public:
  using Base::Base;
  void updateDisplay() {
    if(PcLink::connected()) connectedTransfer(false); else Base::updateDisplay();
  }
  void sendBuffer() {
    if(PcLink::connected()) connectedTransfer(true); else Base::sendBuffer();
  }
};
