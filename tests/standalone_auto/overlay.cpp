// SPDX-License-Identifier: GPL-3.0-or-later

#include <stdint.h>
#include "../../Cart_Reader/ConnectedReaderDisplay.h"
static bool connected=false;
namespace PcLink {bool connected(){return ::connected;}}
extern "C" {volatile uint16_t test_result=0,failed_at=0,test_count=0;}
#define CHECK(x) do{test_count++;if(!(x)){failed_at=test_count;test_result=0xDEAD;while(1){asm volatile("nop");}}}while(0)
template<bool R> class Panel {
 public:
 uint8_t buffer[1024],sent[9],color;uint16_t updates=0,draws=0;
 Panel():color(2){for(uint16_t i=0;i<1024;i++)buffer[i]=0x55;}
 uint8_t* getBufferPtr(){return buffer;}
 uint8_t getBufferTileWidth(){return 16;}uint8_t getBufferTileHeight(){return 8;}
 uint8_t getDrawColor(){return color;}void setDrawColor(uint8_t c){color=c;}
 void drawPixel(uint8_t x,uint8_t y){draws++;if(R){x=127-x;y=63-y;}uint16_t a=(y/8)*128+x;uint8_t m=1<<(y%8);if(color)buffer[a]|=m;else buffer[a]&=~m;}
 void drawBox(uint8_t x,uint8_t y,uint8_t w,uint8_t h){for(uint8_t a=0;a<w;a++)for(uint8_t b=0;b<h;b++)drawPixel(x+a,y+b);}
 void updateDisplay(){updates++;uint16_t a=R?896:119;for(uint8_t i=0;i<9;i++)sent[i]=buffer[a+i];}
 void sendBuffer(){updateDisplay();}
};
template<bool R> void run(){
 ConnectedReaderDisplay<Panel<R>,R> p;
 connected=false;p.updateDisplay();CHECK(p.updates==1 && p.draws==0);
 for(uint8_t i=0;i<9;i++)CHECK(p.sent[i]==0x55);
 connected=true;p.updateDisplay();CHECK(p.updates==2 && p.draws>0);CHECK(p.color==2);
 const uint8_t glyph[7]={31,5,2,0,14,17,17};
 for(uint8_t i=0;i<9;i++) {
  uint8_t col=i>=1 && i<=7 ? glyph[i-1] : 0;uint8_t expected=R?1:0;
  for(uint8_t y=0;y<5;y++)if(col&(1<<y))expected|=1<<(R?6-y:y+1);
  CHECK(p.sent[R?8-i:i]==expected);
 }
 for(uint16_t i=0;i<1024;i++)CHECK(p.buffer[i]==0x55);
 p.sendBuffer();CHECK(p.updates==3);
 for(uint16_t i=0;i<1024;i++)CHECK(p.buffer[i]==0x55);
 connected=false;p.updateDisplay();CHECK(p.updates==4);
 for(uint8_t i=0;i<9;i++)CHECK(p.sent[i]==0x55);
}
int main(){run<false>();run<true>();test_result=0x600D;while(1){asm volatile("nop");}}
