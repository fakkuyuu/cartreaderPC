// SPDX-License-Identifier: GPL-3.0-or-later

#include <stdint.h>
#include <string.h>
#include <avr/io.h>
#include <avr/pgmspace.h>
class __FlashStringHelper {};
#define F(x) reinterpret_cast<const __FlashStringHelper*>(PSTR(x))
#define FS(x) reinterpret_cast<const __FlashStringHelper*>(x)
#define HIGH 1
#define ENABLE_GBX
#define ENABLE_NES
#define ENABLE_SNES
#define ENABLE_N64
#define ENABLE_MD
#define ENABLE_OLED
#ifndef TEST_ROTARY
#define ENABLE_BUTTON2
#else
#define ENABLE_ROTARY
#endif
#undef PING
#define PING mockPG
static uint8_t mockPG=4;
static uint32_t nowMs=0, releaseAt=0;
static uint32_t millis(){return nowMs;}
static void delay(uint16_t n){nowMs+=n;if(releaseAt && nowMs>=releaseAt)mockPG=4;}
static bool buttonVal2=true,buttonLast2=true,DCwaiting2=false,DConUp2=false,ignoreUp2=false;
static bool buttonState=true,lastButtonState=true;
static bool host=false,errorLvl=false;
static uint8_t saveType=0,ram=0,currPage=1,numPages=2,lastPage=1;
static uint32_t lastByte=0,sramSize=0;
static const uint8_t green_color=3;
static const char FSTRING_SELECT_CART_TYPE[] PROGMEM="Select Cart Type";
struct FakeEEPROM {
 uint8_t b[4]={255,255,255,255};uint16_t writes=0;
 uint8_t read(int i){return b[i-(E2END-3)];}
 void update(int i,uint8_t v){if(b[i-(E2END-3)]!=v){writes++;b[i-(E2END-3)]=v;}}
} EEPROM;
namespace PcLink {static bool connected(){return host;}}
struct FakeOut { template<class T> void print(T){} template<class T> void println(T){} } PcConsole;
struct FakeDisplay:FakeOut {
 void setDrawColor(uint8_t){}void drawBox(int,int,int,int){}void setCursor(int,int){}
 void updateDisplay(){}void drawPixel(int,int){}void drawHLine(int,int,int){}
} display;
static void println_Msg(const __FlashStringHelper*){}
static void display_Update(){}
static void rgbLed(uint8_t){}
#include "../../Cart_Reader/BootDumpCursor.h"
#include "../../Cart_Reader/ZZ_StandaloneAuto.ino"
extern "C" {volatile uint16_t test_result=0;volatile uint16_t failed_at=0;volatile uint16_t test_count=0;}
#define CHECK(x) do {test_count++; if(!(x)){failed_at=test_count;test_result=0xDEAD;while(1){asm volatile("nop");}}}while(0)
static void resetRun(){standaloneRun=0;standaloneStage=0;standaloneFlags=0;host=false;errorLvl=false;standaloneNesCandidate=false;mockPG=4;releaseAt=0;standaloneStartupHeld=false;standaloneResetMarker=0;}
static bool hold(uint8_t t,uint16_t ms,bool& changed,bool allow=true){nowMs=0;mockPG=0;releaseAt=ms;return standaloneHold(t,changed,allow);}
int main(){
 standaloneBootCapture();CHECK(standalonePreset==0);CHECK(EEPROM.writes==0);
 bool changed=false;
 CHECK(hold(2,500,changed));CHECK(!changed && !standaloneStage && !standalonePreset);
 CHECK(hold(2,1500,changed));CHECK(!changed && standaloneRun==2 && standaloneStage==1);
 resetRun();CHECK(!hold(2,3500,changed));CHECK(changed && standalonePreset==2 && !standaloneStage);
 CHECK(!hold(4,3500,changed));CHECK(standalonePreset==4);
 CHECK(!hold(4,3500,changed));CHECK(standalonePreset==0);
 standaloneSetPreset(2);uint16_t writes=EEPROM.writes;standalonePreset=0;standaloneBootCapture();CHECK(standalonePreset==2 && EEPROM.writes==writes);
 standaloneBootReady();CHECK(standaloneRun==2 && standaloneStage==1);
 resetRun();mockPG=0;standaloneBootCapture();releaseAt=nowMs+20;
 uint32_t beforeReady=nowMs;standaloneBootReady();
 CHECK(nowMs==beforeReady && !standaloneStage && standalonePreset==2 && mockPG==0);
 CHECK(standaloneInputBlocked());delay(25);CHECK(standaloneInputBlocked());CHECK(!standaloneInputBlocked());
 CHECK(!standaloneStage && standalonePreset==2);
 resetRun();standaloneBootCapture();host=true;standaloneBootReady();CHECK(!standaloneStage && standalonePreset==2);
 resetRun();CHECK(standaloneTarget(F("OPEN SOURCE CART READER"),"Game Boy",false)==0);
 CHECK(standaloneTarget(F("OPEN SOURCE CART READER"),"Game Boy",true)==2);
 CHECK(!hold(2,1500,changed,false));CHECK(!standaloneStage && standalonePreset==2);
 CHECK(!hold(2,3500,changed,false));CHECK(standalonePreset==0);
 standaloneSetPreset(4);CHECK(standaloneTarget(F("OPEN SOURCE CART READER"),"Game Boy",true)==0);
 CHECK(standaloneTarget(F("Select device"),"HuCARD(swapped)",false)==7);
 CHECK(standaloneTarget(F("Select device"),"HuCARD(not swapped)",false)==8);
 resetRun();standaloneRun=2;standaloneStage=1;
 char root[7][20]={"Game Boy","NES/Famicom"};CHECK(standaloneMenu(F("OPEN SOURCE CART READER"),root,2)==0);
 char gb[7][20]={"Game Boy (Color)","GB Advance (3V)"};CHECK(standaloneMenu(F("Select Game Boy"),gb,2)==1);
 CHECK(standaloneCandidate(2));CHECK(!standaloneCandidate(3));CHECK(standaloneWait());
 char read[7][20]={"Read ROM","Read Save","Write Save","Reset"};CHECK(standaloneMenu(F("GBA Cart Reader"),read,4)==0);CHECK(standaloneStage==2);
 standaloneFileClosed(8388608);standaloneVerified();saveType=3;CHECK(standaloneWait());CHECK(standaloneStage==4);
 CHECK(standaloneMenu(F("GBA Cart Reader"),read,4)==1);CHECK(standaloneStage==3);
 standaloneFileClosed(32768);CHECK(!standaloneWait());CHECK(!standaloneStage);CHECK(!standaloneWait());
 resetRun();standaloneRun=7;standaloneStage=2;standaloneFileClosed(16384);CHECK(!standaloneWait());CHECK(!standaloneStage);
 resetRun();standaloneRun=7;standaloneStage=2;standaloneFileClosed(16384);standaloneVerified();CHECK(!standaloneWait());CHECK(!standaloneStage);
 resetRun();standaloneRun=3;standaloneStage=1;CHECK(!standaloneCandidate(3));standaloneCandidateAllowed(true);CHECK(standaloneCandidate(3));standaloneError();CHECK(!standaloneStage);
 resetRun();standaloneRun=4;standaloneStage=2;standaloneFileClosed(1024);standaloneVerified();standaloneError();CHECK(!standaloneWait());CHECK(!standaloneStage);
 resetRun();standaloneRun=4;standaloneStage=1;char unknown[7][20]={"Write ROM"};CHECK(standaloneMenu(F("Unexpected"),unknown,1)==-1);CHECK(!standaloneStage);
 resetRun();standaloneRun=4;standaloneStage=1;CHECK(standaloneMenu(F("SNES Cart Reader"),unknown,1)==-1);CHECK(!standaloneStage);
 resetRun();standaloneRun=4;standaloneStage=1;currPage=1;numPages=2;CHECK(standaloneMenu(F("OPEN SOURCE CART READER"),root,2)==-2);CHECK(currPage==2);CHECK(standaloneMenu(F("OPEN SOURCE CART READER"),root,2)==-1);CHECK(!standaloneStage);
 resetRun();standaloneRun=4;standaloneStage=1;host=true;CHECK(standaloneMenu(F("SNES Cart Reader"),read,4)==-1);CHECK(!standaloneStage);
 resetRun();standaloneRun=4;standaloneStage=3;standaloneFileClosed(0);CHECK(!standaloneStage);
 resetRun();standalonePreset=0;EEPROM.b[0]=0;standaloneBootCapture();CHECK(!standalonePreset);

 const __FlashStringHelper* titles[8]={F("GB Cart Reader"),F("GBA Cart Reader"),F("NES CART READER"),F("SNES Cart Reader"),F("N64 Cart Reader"),F("MEGA DRIVE Reader"),F("PCE HuCARD menu"),F("PCE HuCARD menu")};
 for(uint8_t t=1;t<=8;t++) {
  resetRun();standaloneRun=t;standaloneStage=1;
  char opts[7][20]={"Read ROM","Read Save"};if(t==3)strcpy(opts[0],"Read iNES Rom");
  CHECK(standaloneMenu(titles[t-1],opts,2)==0);CHECK(standaloneStage==2);
 }
 resetRun();standaloneRun=4;standaloneStage=1;char sns[7][20]={"SNES/SFC cartridge","Reset"};CHECK(standaloneMenu(F("Select Cart Type"),sns,2)==0);
 resetRun();standaloneRun=5;standaloneStage=1;char cart[7][20]={"Game Cartridge","Reset"};CHECK(standaloneMenu(F("Select N64 device"),cart,2)==0);
 resetRun();standaloneRun=6;standaloneStage=1;CHECK(standaloneMenu(F("Select MD device"),cart,2)==0);
 resetRun();standaloneRun=8;standaloneStage=1;char pce[7][20]={"HuCARD(swapped)","HuCARD(not swapped)"};CHECK(standaloneMenu(F("Select device"),pce,2)==1);
 standaloneSetPreset(2);standalonePreset=0;EEPROM.b[2]^=1;standaloneBootCapture();CHECK(!standalonePreset);

 resetRun();standaloneSetPreset(2);writes=EEPROM.writes;
 standaloneSuppressNextBoot();standaloneBootCapture();standaloneBootReady();
 CHECK(standaloneSkip && !standaloneStage && standalonePreset==2);
 CHECK(!standaloneStartupHeld && !standaloneInputBlocked());CHECK(EEPROM.writes==writes);
 standaloneSuppressNextBoot();standaloneBootCapture();standaloneBootReady();CHECK(!standaloneStage && standalonePreset==2);
 resetRun();standaloneBootCapture();standaloneBootReady();CHECK(standaloneStage==1 && standalonePreset==2);
 CHECK(standaloneResetMarker==0);

 resetRun();standalonePreset=0;standaloneSetPreset(2);
 CHECK(standaloneHeaderSelectable(F("OPEN SOURCE CART READER")));
 CHECK(standaloneHeaderSelectable(F("Select Game Boy")));
 CHECK(!standaloneHeaderSelectable(F("GBA Cart Reader")));
 CHECK(bootDumpCursorAction(false,2,0,7,true,false)==BD_HEADER);
 CHECK(bootDumpCursorAction(false,1,6,7,true,true)==BD_HEADER);
 CHECK(bootDumpCursorAction(false,1,6,7,true,false)==BD_NORMAL);
 CHECK(bootDumpCursorAction(false,2,2,7,true,true)==BD_NORMAL);
 CHECK(bootDumpCursorAction(true,1,0,7,true,true)==BD_FIRST);
 CHECK(bootDumpCursorAction(true,2,0,7,true,true)==BD_LAST);
 CHECK(bootDumpCursorAction(true,2,0,7,false,true)==BD_PREVIOUS_PAGE);
 CHECK(bootDumpCursorAction(true,3,0,7,true,true)==BD_DISABLE);
 CHECK(bootDumpCursorAction(true,0,0,7,true,true)==BD_NORMAL);
 CHECK(bootDumpCursorAction(true,4,0,7,true,true)==BD_NORMAL);
 standaloneDisablePreset();CHECK(!standalonePreset);
 CHECK(!standaloneHeaderSelectable(F("OPEN SOURCE CART READER")));
 writes=EEPROM.writes;standaloneDisablePreset();CHECK(EEPROM.writes==writes);
 CHECK(!hold(2,3500,changed));CHECK(standalonePreset==2);
 CHECK(!hold(2,3500,changed));CHECK(!standalonePreset);
 test_result=0x600D;while(1){asm volatile("nop");}
}
