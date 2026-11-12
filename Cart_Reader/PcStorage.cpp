#include "ConnectedReaderDisplay.h"
#include "StandaloneAuto.h"
// SPDX-License-Identifier: GPL-3.0-or-later
#include "PcStorage.h"
#undef FsFile
#undef SdFile
#undef SdFs
#include <string.h>
#include <time.h>
#include <avr/wdt.h>
extern "C" {
  extern char __heap_start;
  extern char* __brkval;
}
extern void pcVerificationResult(uint8_t code);
extern HybridSdFs sd;
extern uint8_t sdBuffer[512];
static uint16_t sdCopyReadSize = 256;
static uint16_t sdCopyProgressMs = 0;
static uint32_t sdCopyLastProgress = 0;
static bool sdCopyProgressDue(uint32_t done, uint32_t total) {
  if(done==total) return true;
  if(done & 4095UL) return false;
  uint32_t now=millis();
  if(sdCopyProgressMs && (uint32_t)(now-sdCopyLastProgress)<sdCopyProgressMs) return false;
  sdCopyLastProgress=now;
  return true;
}

namespace PcLink {
static constexpr uint16_t dataCapacity = 528;
static uint8_t* data = nullptr;
static bool started = false;
static bool ramTelemetry = false; // Negotiated; old hosts never receive op 26.
static int16_t ramMinimum = INT16_MAX;
static uint8_t ramMinimumStage = RAM_IDLE;
static uint32_t ramReportedAt = 0;
// Keep this call out of byte loops. No allocation, logging, or shared-buffer use.
int16_t __attribute__((noinline)) sampleRam(uint8_t stage) {
  uint8_t saved = SREG;
  cli();
  uint16_t stack = SP;
  uint16_t heap = (uint16_t)(__brkval ? __brkval : &__heap_start);
  SREG = saved;
  int16_t gap = (int16_t)stack - (int16_t)heap;
  if(gap < ramMinimum) { ramMinimum=gap; ramMinimumStage=stage; }
  return gap;
}
static void periodicRam(uint8_t stage) {
  if(ramTelemetry && (uint32_t)(millis()-ramReportedAt)>=5000UL) reportRam(stage);
}
static bool pcStorage = false;
static uint16_t sequence = 0;
static uint32_t activeBaud = 250000UL;
static uint32_t safeBaud = 250000UL;
static uint32_t dumpBaud = 250000UL;
static bool cancelRequested = false;
static uint8_t checkpointBlocks = 8;
static bool hostSnesLookup = false;
static uint32_t hostEpoch = 0, hostSyncMillis = 0;
uint32_t hostTime() {
  return started && hostEpoch ? hostEpoch + (millis() - hostSyncMillis) / 1000UL : 0;
}
void writeDumpTimestamp(Print& target, const __FlashStringHelper* label, uint32_t stamp) {
  if (!stamp)
    return;
  time_t seconds = stamp;
  struct tm calendar;
  gmtime_r(&seconds, &calendar);
  char value[20];
  snprintf_P(value, sizeof(value), PSTR("%04u-%02u-%02u %02u:%02u:%02u"),
             (unsigned)(calendar.tm_year + 1900), (unsigned)(calendar.tm_mon + 1),
             (unsigned)calendar.tm_mday, (unsigned)calendar.tm_hour,
             (unsigned)calendar.tm_min, (unsigned)calendar.tm_sec);
  target.print(label);
  target.println(value);
}

bool hasHostSnesLookup() { return hostSnesLookup; }
static uint16_t transferBlockSize = 512;
static bool ledActivity = false;
static void (*prefetchReader)(uint8_t*) = nullptr;
static uint16_t prefetchUsed = 0;
void preparePrefetch(void (*readWord)(uint8_t*)) {
  prefetchUsed=0;
  prefetchReader=readWord;
}
bool finishPrefetch(uint8_t* destination) {
  prefetchReader=nullptr;
  if(prefetchUsed!=512) return false;
  memcpy(destination,data+16,512);
  return true;
}
static void prefetchPoll() {
  // Deterministic interleave: PC71's UART-backlog condition never completed
  // a block on the tested hardware. Read one word every two payload bytes.
  if(prefetchUsed<512) {
    prefetchReader(data+16+prefetchUsed);
    prefetchUsed+=2;
  }
}
// Timing telemetry removed after the controlled SD-copy stall comparison.
void profileBegin() {}
uint32_t profileReadStart() { return 0; }
void profileReadEnd(uint32_t) {}
void profileEnd() {}
// Preserve one word across watchdog reset.  A disconnect-triggered restart
// must not reconnect to the host during the few milliseconds before Windows
// finishes closing the COM handle.
static uint32_t skipPcBoot __attribute__((section(".noinit")));
static const uint32_t SKIP_PC_BOOT_MAGIC = 0x50434454UL; // "PCDT"
bool takeCancelRequest() { bool value=cancelRequested; cancelRequested=false; return value; }
// CRC16-CCITT-FALSE. Byte lookup occupies flash only, not SRAM.
static const uint16_t crcByte[256] PROGMEM = {
  0x0000,0x1021,0x2042,0x3063,0x4084,0x50A5,0x60C6,0x70E7,
  0x8108,0x9129,0xA14A,0xB16B,0xC18C,0xD1AD,0xE1CE,0xF1EF,
  0x1231,0x0210,0x3273,0x2252,0x52B5,0x4294,0x72F7,0x62D6,
  0x9339,0x8318,0xB37B,0xA35A,0xD3BD,0xC39C,0xF3FF,0xE3DE,
  0x2462,0x3443,0x0420,0x1401,0x64E6,0x74C7,0x44A4,0x5485,
  0xA56A,0xB54B,0x8528,0x9509,0xE5EE,0xF5CF,0xC5AC,0xD58D,
  0x3653,0x2672,0x1611,0x0630,0x76D7,0x66F6,0x5695,0x46B4,
  0xB75B,0xA77A,0x9719,0x8738,0xF7DF,0xE7FE,0xD79D,0xC7BC,
  0x48C4,0x58E5,0x6886,0x78A7,0x0840,0x1861,0x2802,0x3823,
  0xC9CC,0xD9ED,0xE98E,0xF9AF,0x8948,0x9969,0xA90A,0xB92B,
  0x5AF5,0x4AD4,0x7AB7,0x6A96,0x1A71,0x0A50,0x3A33,0x2A12,
  0xDBFD,0xCBDC,0xFBBF,0xEB9E,0x9B79,0x8B58,0xBB3B,0xAB1A,
  0x6CA6,0x7C87,0x4CE4,0x5CC5,0x2C22,0x3C03,0x0C60,0x1C41,
  0xEDAE,0xFD8F,0xCDEC,0xDDCD,0xAD2A,0xBD0B,0x8D68,0x9D49,
  0x7E97,0x6EB6,0x5ED5,0x4EF4,0x3E13,0x2E32,0x1E51,0x0E70,
  0xFF9F,0xEFBE,0xDFDD,0xCFFC,0xBF1B,0xAF3A,0x9F59,0x8F78,
  0x9188,0x81A9,0xB1CA,0xA1EB,0xD10C,0xC12D,0xF14E,0xE16F,
  0x1080,0x00A1,0x30C2,0x20E3,0x5004,0x4025,0x7046,0x6067,
  0x83B9,0x9398,0xA3FB,0xB3DA,0xC33D,0xD31C,0xE37F,0xF35E,
  0x02B1,0x1290,0x22F3,0x32D2,0x4235,0x5214,0x6277,0x7256,
  0xB5EA,0xA5CB,0x95A8,0x8589,0xF56E,0xE54F,0xD52C,0xC50D,
  0x34E2,0x24C3,0x14A0,0x0481,0x7466,0x6447,0x5424,0x4405,
  0xA7DB,0xB7FA,0x8799,0x97B8,0xE75F,0xF77E,0xC71D,0xD73C,
  0x26D3,0x36F2,0x0691,0x16B0,0x6657,0x7676,0x4615,0x5634,
  0xD94C,0xC96D,0xF90E,0xE92F,0x99C8,0x89E9,0xB98A,0xA9AB,
  0x5844,0x4865,0x7806,0x6827,0x18C0,0x08E1,0x3882,0x28A3,
  0xCB7D,0xDB5C,0xEB3F,0xFB1E,0x8BF9,0x9BD8,0xABBB,0xBB9A,
  0x4A75,0x5A54,0x6A37,0x7A16,0x0AF1,0x1AD0,0x2AB3,0x3A92,
  0xFD2E,0xED0F,0xDD6C,0xCD4D,0xBDAA,0xAD8B,0x9DE8,0x8DC9,
  0x7C26,0x6C07,0x5C64,0x4C45,0x3CA2,0x2C83,0x1CE0,0x0CC1,
  0xEF1F,0xFF3E,0xCF5D,0xDF7C,0xAF9B,0xBFBA,0x8FD9,0x9FF8,
  0x6E17,0x7E36,0x4E55,0x5E74,0x2E93,0x3EB2,0x0ED1,0x1EF0
};
static inline __attribute__((always_inline)) uint16_t crc(uint16_t c, uint8_t b) {
  uint8_t index=(uint8_t)(c >> 8)^b;
  return (uint16_t)(c << 8)^pgm_read_word(crcByte+index);
}
// A failed transport cannot be ignored by upstream dump loops: stop permanently.
void stop() {
  pinMode(LED_BUILTIN, OUTPUT);
  for (;;) { digitalWrite(LED_BUILTIN, HIGH); delay(150); digitalWrite(LED_BUILTIN, LOW); delay(150); }
}
void resetAfterHostLoss() {
  // Returning into an arbitrary filesystem call after the host disappears can
  // leave open handles and menu state inconsistent.  A watchdog restart is
  // the same safe recovery path already used after the baud benchmark.  On
  // the next boot the reader selects physical SD when no PC host answers.
  pcStorage=false;
  started=false;
  skipPcBoot=SKIP_PC_BOOT_MAGIC;
  Serial.flush();
  standaloneSuppressNextBoot();
  wdt_enable(WDTO_15MS);
  for (;;) {}
}
bool detachToPhysical() {
  // Menu/Press-Button state is already safe and has no open ROM file.  Do not
  // reboot here: initialize the physical card in-place, then make PcConsole a
  // non-blocking disconnected stream so the same menu immediately resumes
  // physical-button scanning.  Failure to initialize SD must not trap input;
  // storage operations will report SD Error later if the user selects one.
  pcStorage=false;
  bool ready=sd.selectPhysical(SS);
  started=false;
  Serial.flush();
  Serial.end();
  activeBaud=safeBaud=dumpBaud=250000UL;
  readerConnectionDisplayRefresh();
  return ready;
}
static uint8_t receive() {
  unsigned long t = millis();
  while (!Serial.available()) if (millis()-t > 10000UL) resetAfterHostLoss();
  return Serial.read();
}
void put32(uint8_t* p, uint32_t v) { for(uint8_t i=0;i<4;i++) {p[i]=v; v>>=8;} }
uint32_t get32(const uint8_t* p) {
  uint32_t v=0; for(int8_t i=3;i>=0;i--) v=(v<<8)|p[i]; return v;
}
uint16_t call(uint8_t op, uint16_t n) {
  sampleRam(RAM_PROTOCOL);
  if(n>dataCapacity) stop();
  uint16_t seq=++sequence;
  uint8_t h[]={1,op,(uint8_t)seq,(uint8_t)(seq>>8),(uint8_t)n,(uint8_t)(n>>8)};
  uint16_t c=0xffff;
  Serial.write((const uint8_t*)"CRPC",4);
  for(uint8_t b:h) { Serial.write(b); c=crc(c,b); }
  for(uint16_t i=0;i<n;i++) { Serial.write(data[i]); c=crc(c,data[i]); }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8));
  const char* magic="CRPC";
  for(uint8_t i=0;i<4;i++) if(receive()!=magic[i]) stop();
  c=0xffff;
  uint8_t r[6];
  for(uint8_t i=0;i<6;i++) { r[i]=receive(); c=crc(c,r[i]); }
  if(r[0]!=1 || r[1]!=(op|0x80) || r[2]!=h[2] || r[3]!=h[3]) stop();
  n=r[4]|((uint16_t)r[5]<<8);
  if(n<1 || n>dataCapacity) stop();
  for(uint16_t i=0;i<n;i++) {data[i]=receive(); c=crc(c,data[i]);}
  uint16_t got=receive(); got|=(uint16_t)receive()<<8;
  if(c!=got) stop();
  return n;
}
static void notifyPayload(uint8_t op, const uint8_t* payload, uint16_t n) {
  if(!started) return;
  if(n>dataCapacity) return;
  uint16_t seq=++sequence;
  uint8_t h[]={1,op,(uint8_t)seq,(uint8_t)(seq>>8),(uint8_t)n,(uint8_t)(n>>8)};
  uint16_t c=0xffff;
  Serial.write((const uint8_t*)"CRPC",4);
  for(uint8_t b:h) { Serial.write(b); c=crc(c,b); }
  for(uint16_t i=0;i<n;i++) { Serial.write(payload[i]); c=crc(c,payload[i]); }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8));
  // Stream frames contain no reply. HardwareSerial has already copied every
  // queued byte before write() returns, so cartridge reading may overlap the
  // final UART bytes. Control frames still drain before a baud/reset boundary.
  if(op!=22) Serial.flush();
}
static void notify(uint8_t op, uint16_t n) { notifyPayload(op,data,n); }
void reportRam(uint8_t stage) {
  if(!started || !ramTelemetry) return;
  // Private 10-byte payload: never overwrite PcLink::data, a pending ROM
  // segment, or the GBA prefetch region. Send only BETWEEN complete frames.
  int16_t gap=sampleRam(stage);
  uint16_t fixed=(uint16_t)&__heap_start-RAMSTART;
  const uint16_t total=RAMEND-RAMSTART+1;
  uint8_t payload[]={ (uint8_t)gap,(uint8_t)(gap>>8),
    (uint8_t)ramMinimum,(uint8_t)(ramMinimum>>8),
    (uint8_t)fixed,(uint8_t)(fixed>>8),(uint8_t)total,(uint8_t)(total>>8),
    stage,ramMinimumStage };
  notifyPayload(26,payload,sizeof(payload));
  ramReportedAt=millis();
}
void streamWrite(uint8_t handle, uint32_t offset, const uint8_t* source, uint16_t count) {
  if(count>512) stop();
  // Serialize the caller-owned cache directly. Avoid copying it through the
  // shared request/reply buffer; HardwareSerial owns queued bytes on return.
  streamWritePair(handle,offset,source,count,nullptr,0);
}
void streamWritePair(uint8_t handle, uint32_t offset,
                     const uint8_t* first, uint16_t firstCount,
                     const uint8_t* second, uint16_t secondCount) {
  sampleRam(RAM_TRANSFER);
  if(firstCount>512 || secondCount>512 || firstCount+secondCount>1024) stop();
  uint16_t count=firstCount+secondCount;
  uint16_t payloadLength=count+5;
  uint16_t seq=++sequence;
  uint8_t h[]={1,22,(uint8_t)seq,(uint8_t)(seq>>8),
               (uint8_t)payloadLength,(uint8_t)(payloadLength>>8)};
  uint16_t c=0xffff;
  Serial.write((const uint8_t*)"CRPC",4);
  for(uint8_t b:h) { Serial.write(b); c=crc(c,b); }
  Serial.write(handle); c=crc(c,handle);
  for(uint8_t i=0;i<4;i++) { uint8_t b=(uint8_t)(offset>>(i*8)); Serial.write(b); c=crc(c,b); }
  if(prefetchReader) {
    for(uint16_t i=0;i<firstCount;i++) {
      if(!(i&1) && prefetchUsed<512) prefetchPoll();
      Serial.write(first[i]); c=crc(c,first[i]);
    }
    for(uint16_t i=0;i<secondCount;i++) {
      if(!(i&1) && prefetchUsed<512) prefetchPoll();
      Serial.write(second[i]); c=crc(c,second[i]);
    }
  } else {
    for(uint16_t i=0;i<firstCount;i++) { Serial.write(first[i]); c=crc(c,first[i]); }
    for(uint16_t i=0;i<secondCount;i++) { Serial.write(second[i]); c=crc(c,second[i]); }
  }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8));
  periodicRam(RAM_TRANSFER);
}
bool streamCheckpoint(uint8_t handle, uint32_t expectedEnd, bool& cancelled) {
  data[0]=handle; put32(data+1,expectedEnd);
  uint16_t got=call(25,5);
  if(got!=6 || data[0] || get32(data+1)!=expectedEnd) return false;
  cancelled=data[5]!=0;
  return true;
}
uint8_t streamCheckpointBlocks() { return checkpointBlocks; }
uint16_t streamBlockSize() { return transferBlockSize; }
void menuReady() { reportRam(RAM_MENU); notify(20,0); }
static void activityNotify(const char* state) {
  const char prefix[] = "[LED Activity]\t";
  uint8_t prefixLength = sizeof(prefix) - 1;
  uint8_t stateLength = strlen(state);
  memcpy(data, prefix, prefixLength);
  memcpy(data + prefixLength, state, stateLength);
  data[prefixLength + stateLength] = '\n';
  notify(13, prefixLength + stateLength + 1);
}
void activityBlinking() {
  if(started && !ledActivity) {
    ledActivity=true;
    activityNotify("blinking");
  }
}
void pressButtonReady() {
  if(ledActivity) {
    ledActivity=false;
    activityNotify("idle");
  }
  reportRam(RAM_PRESS_BUTTON);
  notify(23,0);
}
static bool receiveTimed(uint8_t& value, unsigned long deadline) {
  while (!Serial.available()) if ((long)(millis() - deadline) >= 0) return false;
  value = Serial.read();
  return true;
}
static bool pollInput(uint16_t& replyLength) {
  periodicRam(RAM_IDLE);
  static uint8_t consecutiveFailures=0;
  const uint8_t op=14;
  const uint16_t seq=++sequence;
  uint8_t h[]={1,op,(uint8_t)seq,(uint8_t)(seq>>8),0,0};
  uint16_t c=0xffff;
  Serial.write((const uint8_t*)"CRPC",4);
  for(uint8_t b:h) { Serial.write(b); c=crc(c,b); }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8)); Serial.flush();
  unsigned long deadline=millis()+750UL;
  uint8_t b;
  const char* magic="CRPC";
  for(uint8_t i=0;i<4;i++) if(!receiveTimed(b,deadline) || b!=(uint8_t)magic[i]) goto failed;
  c=0xffff; uint8_t r[6];
  for(uint8_t i=0;i<6;i++) { if(!receiveTimed(r[i],deadline)) goto failed; c=crc(c,r[i]); }
  replyLength=r[4]|((uint16_t)r[5]<<8);
  if(r[0]!=1 || r[1]!=(op|0x80) || r[2]!=(uint8_t)seq || r[3]!=(uint8_t)(seq>>8) || replyLength<1 || replyLength>65) goto failed;
  for(uint16_t i=0;i<replyLength;i++) { if(!receiveTimed(data[i],deadline)) goto failed; c=crc(c,data[i]); }
  { uint8_t lo,hi;
    if(!receiveTimed(lo,deadline) || !receiveTimed(hi,deadline)) goto failed;
    if(c!=(uint16_t)(lo|((uint16_t)hi<<8))) goto failed;
  }
  consecutiveFailures=0;
  return true;
failed:
  while(Serial.available()) Serial.read();
  replyLength=0;
  // Menu input is polled with a short timeout rather than receive().  Without
  // this separate liveness check, a vanished host makes every physical-button
  // scan pause for 750 ms forever.  Four consecutive misses are long enough
  // to ignore an isolated scheduling delay but recover in about three seconds.
  if(started && ++consecutiveFailures>=4) detachToPhysical();
  return false;
}
static bool echoTest(uint16_t length, uint8_t pattern) {
  uint16_t seq=++sequence;
  uint8_t h[]={1,18,(uint8_t)seq,(uint8_t)(seq>>8),(uint8_t)length,(uint8_t)(length>>8)};
  uint16_t c=0xffff;
  Serial.write((const uint8_t*)"CRPC",4);
  for(uint8_t b:h) { Serial.write(b); c=crc(c,b); }
  for(uint16_t i=0;i<length;i++) { data[i]=(uint8_t)(i^pattern^0xA5); Serial.write(data[i]); c=crc(c,data[i]); }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8)); Serial.flush();
  unsigned long deadline=millis()+2500UL;
  uint8_t b;
  const char* magic="CRPC";
  for(uint8_t i=0;i<4;i++) if(!receiveTimed(b,deadline) || b!=(uint8_t)magic[i]) return false;
  c=0xffff; uint8_t r[6];
  for(uint8_t i=0;i<6;i++) { if(!receiveTimed(r[i],deadline)) return false; c=crc(c,r[i]); }
  uint16_t n=r[4]|((uint16_t)r[5]<<8);
  if(r[0]!=1 || r[1]!=(18|0x80) || r[2]!=h[2] || r[3]!=h[3] || n!=length+1) return false;
  for(uint16_t i=0;i<n;i++) {
    if(!receiveTimed(b,deadline)) return false;
    c=crc(c,b);
    if((i==0 && b!=0) || (i>0 && b!=(uint8_t)((i-1)^pattern^0xA5))) return false;
  }
  uint8_t lo,hi;
  if(!receiveTimed(lo,deadline) || !receiveTimed(hi,deadline)) return false;
  return c==(uint16_t)(lo|((uint16_t)hi<<8));
}
// Exercise the actual ROM-dump direction: a full 512-byte frame travels from
// the Mega to the PC and only the small status reply travels back.  The older
// echo test returned all 512 bytes to the Mega as well, so a weak PC->Mega
// path could incorrectly reject a baud rate that is usable for dumping.
static bool dumpPathTest(uint8_t pattern) {
  for (uint16_t i=0; i<512; i++) data[i]=(uint8_t)(i^pattern^0x5A);
  uint16_t n=call(24,512);
  return n==1 && data[0]==0;
}
static bool switchRuntimeBaud(uint32_t target) {
  if (target == activeBaud) return true;
  put32(data,target);
  data[4]=1; // Runtime switch: host must not start benchmark recovery logic.
  uint16_t got=call(17,5);
  if(got!=1 || data[0]) return false;
  Serial.flush(); delay(80); Serial.end(); Serial.begin(target); delay(80);
  activeBaud=target;
  return true;
}
// A raw transfer negotiated at the normal CRPC baud. CRPC sequence numbers
// are suspended until the file is complete and both ends restore safe baud.
static uint32_t gbaPayloadUs;
static inline void gbaWriteByte(uint8_t byte) {
  while (!(UCSR0A & _BV(UDRE0))) {}
  UDR0 = byte;
  UCSR0A = _BV(U2X0) | _BV(TXC0);
}

static inline void gbaFlushTx() {
  while (!(UCSR0A & _BV(TXC0))) {}
}
template <uint16_t FrameSize>
static void sendGbaRetryFrame(uint32_t block, uint8_t round, bool end,
                              void (*beginBlock)(uint32_t), void (*readWord)(uint8_t*)) {
  uint8_t header[6];
  put32(header, block);
  header[4] = round;
  header[5] = end;
  uint16_t check = 0xffff;
  gbaWriteByte('G'); gbaWriteByte('B'); gbaWriteByte('2'); gbaWriteByte('M');
  for (uint8_t byte : header) {
    gbaWriteByte(byte);
    check = crc(check, byte);
  }
  if (!end) {
    const uint32_t address = block * FrameSize;
    const uint32_t payloadStart = micros();
    for (uint16_t offset = 0; offset < FrameSize; offset += 512) {
      beginBlock(address + offset);
      for (uint16_t wordIndex = 0; wordIndex < (FrameSize < 512 ? FrameSize : 512) / 2; ++wordIndex) {
        uint8_t word[2];
        readWord(word);
        for (uint8_t byte : word) {
          gbaWriteByte(byte);
          check = crc(check, byte);
        }
      }
    }
    gbaPayloadUs += micros() - payloadStart;
  }
  gbaWriteByte((uint8_t)check);
  gbaWriteByte((uint8_t)(check >> 8));
}

static uint32_t gbaRetryMask(uint8_t round, bool wide) {
  uint8_t reply[8];
  const uint8_t size = wide ? 8 : 6;
  uint8_t received = 0;
  uint32_t started = millis();
  while (received < size && millis() - started < 3000UL) {
    int value = Serial.read();
    if (value >= 0) reply[received++] = (uint8_t)value;
  }
  if (received != size || reply[0] != 0xA7 || reply[1] != round) stop();
  uint16_t check = 0xffff;
  for (uint8_t i = 0; i < size - 2; ++i) check = crc(check, reply[i]);
  if (check != (uint16_t)(reply[size - 2] | ((uint16_t)reply[size - 1] << 8))) stop();
  uint32_t mask = reply[2] | ((uint32_t)reply[3] << 8);
  if (wide) mask |= ((uint32_t)reply[4] << 16) | ((uint32_t)reply[5] << 24);
  return mask;
}

static bool gbaRetryTransfer(uint8_t handle, uint32_t length,
                             void (*beginBlock)(uint32_t), void (*readWord)(uint8_t*),
                             uint8_t mode, uint32_t* measuredUs = nullptr,
                             void (*roundStarted)(uint8_t) = nullptr,
                             bool fallbackBeforePayload = false,
                             void (*progress)(uint32_t) = nullptr) {
  data[0] = handle;
  put32(data + 1, length);
  data[5] = mode;
  if (call(30, 6) != 2 || data[0]) return false;
  const uint8_t frameShift = data[1];
  if (frameShift < 8 || frameShift > 10) stop();
  const auto sendFrame = frameShift == 8 ? sendGbaRetryFrame<256> :
                         frameShift == 9 ? sendGbaRetryFrame<512> : sendGbaRetryFrame<1024>;
  const uint8_t window = 8192U >> frameShift;
  const bool wide = window > 16;

  Serial.flush();
  delay(100);
  Serial.end();
  Serial.begin(2000000UL);
  activeBaud = 2000000UL;
  delay(100);
  // Do not start reading the cartridge until the host has received a
  // CRC-checked marker at the new baud and acknowledged it.
  const uint32_t readyStarted = millis();
  while (!Serial.available()) {
    if (millis() - readyStarted >= 3000UL) {
      if (fallbackBeforePayload) {
        // The host did not see a raw 2M marker, so no ROM payload has begun.
        // Restore the normal link before the caller starts its legacy dump.
        gbaFlushTx();
        delay(50);
        Serial.end();
        Serial.begin(safeBaud);
        activeBaud = safeBaud;
        delay(100);
        PcConsole.println(F("[N64 2M] negotiation timed out before payload; using normal transfer"));
        return false;
      }
      stop();
    }
    sendFrame(0xffffffffUL, 0xff, true, beginBlock, readWord);
    gbaFlushTx();
    const uint32_t sent = millis();
    while (!Serial.available() && millis() - sent < 100UL) {}
  }
  if (gbaRetryMask(0xff, wide) != 0) stop();
  gbaPayloadUs = 0;
  uint32_t replyUs = 0;
  const uint32_t streamStart = micros();
  const uint32_t blocks = length >> frameShift;
  for (uint32_t first = 0; first < blocks; first += window) {
    uint8_t count = min((uint32_t)window, blocks - first);
    const uint32_t validMask = 0xffffffffUL >> (32 - count);
    uint32_t mask = validMask;
    for (uint8_t round = 0; mask; ++round) {
      if (round >= 10) stop();
      if (roundStarted) roundStarted(round);
      for (uint8_t i = 0; i < count; ++i) {
        if (mask & (1UL << i)) sendFrame(first + i, round, false, beginBlock, readWord);
      }
      sendFrame(first, round, true, beginBlock, readWord);
      gbaFlushTx();
      const uint32_t replyStart = micros();
      mask = gbaRetryMask(round, wide);
      replyUs += micros() - replyStart;
      if (mask & ~validMask) stop();
    }
    if (progress) progress((first + count) << frameShift);
  }
  const uint32_t streamUs = micros() - streamStart;
  if (measuredUs) *measuredUs = streamUs;
  delay(150);
  Serial.end();
  Serial.begin(safeBaud);
  activeBaud = safeBaud;
  delay(100);
  PcConsole.print(mode == PcLink::RETRY_PROFILE_N64 ? F("[N64 2M profile] payload_us=") : mode == PcLink::RETRY_PROFILE_MD ? F("[MD 2M profile] payload_us=") : mode == PcLink::RETRY_PROFILE_SNES || mode == PcLink::RETRY_PROFILE_SNES_EXPERIMENTAL ? F("[SNES 2M profile] payload_us=") : mode == PcLink::RETRY_PROFILE_BENCHMARK ? F("[Benchmark 2M profile] payload_us=") : F("[GBA 2M profile] payload_us="));
  PcConsole.print(gbaPayloadUs);
  PcConsole.print(F(" reply_us="));
  PcConsole.print(replyUs);
  PcConsole.print(F(" stream_us="));
  PcConsole.println(streamUs);
  return true;
}

bool enterDumpBaud() { return switchRuntimeBaud(dumpBaud); }
bool leaveDumpBaud() { return switchRuntimeBaud(safeBaud); }
bool connected() { return started; }
bool usingPcStorage() { return pcStorage; }
void setPcStorage(bool enabled) { pcStorage=enabled; }
bool tryStart(uint16_t timeoutMs) {
  if(started) return true;
  if(skipPcBoot==SKIP_PC_BOOT_MAGIC) {
    skipPcBoot=0;
    Serial.end();
    pcStorage=false;
    return false;
  }
  // Avoid an accidental match after a cold power-on with undefined .noinit
  // SRAM, and make every later non-disconnect reset eligible for PC mode.
  skipPcBoot=0;
  Serial.begin(250000);
  delay(100);
  const uint8_t op=1;
  const uint16_t seq=++sequence;
  uint8_t h[]={1,op,(uint8_t)seq,(uint8_t)(seq>>8),0,0};
  uint16_t c=0xffff;
  Serial.write((const uint8_t*)"CRPC",4);
  for(uint8_t b:h) { Serial.write(b); c=crc(c,b); }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8)); Serial.flush();
  // A standalone boot should not pay the full host timeout. Give the host a
  // short window to start the reply; once the first correct magic byte is
  // seen, restore the full timeout for the remainder of the handshake.
  uint16_t firstByteTimeout = timeoutMs < 300 ? timeoutMs : 300;
  unsigned long deadline=millis()+firstByteTimeout;
  uint8_t b;
  const char* magic="CRPC";
  for(uint8_t i=0;i<4;i++) {
    if(!receiveTimed(b,deadline) || b!=(uint8_t)magic[i]) goto no_host;
    if(i==0) deadline=millis()+timeoutMs;
  }
  c=0xffff; uint8_t r[6];
  for(uint8_t i=0;i<6;i++) { if(!receiveTimed(r[i],deadline)) goto no_host; c=crc(c,r[i]); }
  { uint16_t helloLength=r[4]|((uint16_t)r[5]<<8);
    if(r[0]!=1 || r[1]!=(op|0x80) || r[2]!=(uint8_t)seq || r[3]!=(uint8_t)(seq>>8) || helloLength<1 || helloLength>dataCapacity) goto no_host;
    uint8_t hello[17];
    for(uint16_t i=0;i<helloLength;i++) {
      if(!receiveTimed(b,deadline)) goto no_host;
      if(i<sizeof(hello)) hello[i]=b;
      c=crc(c,b);
    }
    uint8_t lo,hi;
    if(!receiveTimed(lo,deadline) || !receiveTimed(hi,deadline) || c!=(uint16_t)(lo|((uint16_t)hi<<8)) || hello[0]) goto no_host;
    // A cold standalone boot needs only the small handshake header.
    if(!data) data=(uint8_t*)malloc(dataCapacity);
    if(!data) goto no_host;
    started=true; pcStorage=true;
    ramTelemetry=helloLength>=13 && (hello[12]&1);
    hostSnesLookup=helloLength>=13 && (hello[12]&2);
    hostEpoch=helloLength>=17 && (hello[12]&4) ? get32(hello+13) : 0;
    hostSyncMillis=millis();
  if(helloLength>=5) {
    uint32_t preferred=get32(hello+1);
    uint32_t preferredDump=helloLength>=9 ? get32(hello+5) : preferred;
    uint8_t negotiatedBlocks=(helloLength>=10 && hello[9]>=8 && hello[9]<=64) ? hello[9] : 8;
    uint16_t negotiatedSize=helloLength>=12 ? (uint16_t)(hello[10]|((uint16_t)hello[11]<<8)) : 512;
    if(negotiatedSize!=1024) negotiatedSize=512;
    if(preferred!=250000UL) {
      put32(data,preferred);
      call(17,4);
      if(!data[0]) {
        Serial.flush(); delay(200); Serial.end(); Serial.begin(preferred); delay(100);
        bool verified=true;
        for(uint8_t round=0;round<4;round++) if(!echoTest(512,round)) { verified=false; break; }
        if(verified) activeBaud=safeBaud=preferred;
        else {
          Serial.flush(); Serial.end(); Serial.begin(250000UL); activeBaud=safeBaud=250000UL;
          delay(3200);
        }
      }
    }
    dumpBaud=preferredDump;
    checkpointBlocks=negotiatedBlocks;
    transferBlockSize=negotiatedSize;
  }
  }
  PcConsole.println(F("[Browser protocol] 1"));
  PcConsole.print(F("[Transfer block active] "));
  PcConsole.print(transferBlockSize);
  PcConsole.println(F(" bytes"));
  PcConsole.print(F("[Checkpoint active] "));
  PcConsole.println((uint16_t)checkpointBlocks*transferBlockSize/1024);
  PcConsole.print(F("[TX buffer] ")); PcConsole.println(SERIAL_TX_BUFFER_SIZE);
  return true;
no_host:
  while(Serial.available()) Serial.read();
  Serial.end();
  started=false;
  pcStorage=false;
  return false;
}
void start() {
  if(!tryStart(1500)) stop();
}
uint32_t benchmark() {
  // Exact or low-error divisors for the Mega2560's 16 MHz UART.
  const uint32_t rates[] = {285714UL,333333UL,400000UL,500000UL,666667UL,1000000UL,2000000UL};
  for (uint8_t r = 0; r < 7; r++) {
    uint32_t candidate = rates[r];
    uint32_t previous = activeBaud;
    PcConsole.print(F("[Benchmark] testing baud="));
    PcConsole.println(candidate);
    put32(data, candidate);
    call(17, 4); // response is sent at the old speed
    if (data[0]) break;
    Serial.flush();
    delay(200);
    Serial.end();
    Serial.begin(candidate);
    delay(100);
    bool passed = true;
    uint16_t rounds = candidate > 500000UL ? 128 : 16;
    for (uint16_t round = 0; round < rounds; round++) {
      if (!dumpPathTest(round)) { passed=false; break; }
    }
    if (passed) {
      activeBaud = candidate;
      PcConsole.print(F("[Benchmark] passed baud="));
      PcConsole.println(candidate);
    } else {
      Serial.flush(); Serial.end(); Serial.begin(previous); activeBaud=previous;
      // The host may still be blocked in a one-second read at the failed
      // speed. Keep silent long enough for its timeout/fallback, then send
      // the recovery status at the restored speed.
      delay(3200);
      PcConsole.print(F("[Benchmark] failed baud="));
      PcConsole.println(candidate);
      // A USB-UART can reject 666667 while supporting standard 1M/2M rates.
      // Treat every candidate as an independent test.
      continue;
    }
  }
  return activeBaud;
}
bool benchmarkOne(uint8_t index, uint32_t& candidate) {
  const uint32_t rates[] = {285714UL,333333UL,400000UL,500000UL,666667UL,1000000UL,2000000UL};
  if (index >= 7) return false;
  candidate = rates[index];
  uint32_t previous = activeBaud;
  PcConsole.print(F("[Benchmark] testing baud="));
  PcConsole.println(candidate);
  put32(data, candidate);
  call(17, 4);
  if (data[0]) return false;
  Serial.flush(); delay(200); Serial.end(); Serial.begin(candidate); delay(100);
  // Stress rates above 500 kbaud for 64 KiB. The former 8 KiB probe could
  // occasionally accept 2 Mbaud even though a real ROM failed immediately.
  uint16_t rounds = candidate > 500000UL ? 128 : 16;
  for (uint16_t round = 0; round < rounds; round++) {
    if (!dumpPathTest(round)) {
      Serial.flush(); Serial.end(); Serial.begin(previous); activeBaud=previous;
      return false;
    }
  }
  activeBaud = candidate;
  return true;
}
static uint8_t benchmarkByte;
static void beginBenchmarkBlock(uint32_t offset) { benchmarkByte = offset; }
static void readBenchmarkWord(uint8_t* word) {
  word[0] = benchmarkByte++;
  word[1] = benchmarkByte++;
}

void transmitTest(bool test2M, bool compareRetry) {
  if(!connected()) return;
  PcSdFs fs;
  strcpy_P((char*)sdBuffer,PSTR("/__diagnostics__"));
  if(!fs.mkdir((char*)sdBuffer)) {
    PcConsole.println(F("[TX test] directory error"));
    return;
  }
  PcFsFile file;
  strcpy_P((char*)sdBuffer,PSTR("/__diagnostics__/tx-test.crpctest"));
  if(!file.open((char*)sdBuffer,O_WRITE|O_CREAT|O_TRUNC)) {
    PcConsole.println(F("[TX test] open error"));
    return;
  }
  // Reuse the cartridge block buffer; no extra SRAM and no cartridge access.
  for(uint16_t i=0;i<512;i++) sdBuffer[i]=(uint8_t)i;
  PcConsole.println(F("[TX test] starting 1048576 bytes"));
  const uint32_t configuredDumpBaud = dumpBaud;
  if(test2M) {
    PcConsole.println(F("[TX test] diagnostic 2M"));
    dumpBaud = 2000000UL;
  }
  if(!enterDumpBaud()) stop();
  uint32_t startedUs=micros();
  for(uint16_t block=0;block<2048;block++) file.write(sdBuffer,512);
  file.flush();
  Serial.flush();
  uint32_t transferUs=micros()-startedUs;
  // Close checks the complete pattern on the host and returns to safe baud.
  file.close();
  dumpBaud = configuredDumpBaud;
  if (compareRetry) {
    strcpy_P((char*)sdBuffer,PSTR("/__diagnostics__/tx-test.crpctest"));
    if (!file.open((char*)sdBuffer,O_WRITE|O_CREAT|O_TRUNC)) return;
    uint32_t retryUs = 0;
    file.benchmarkRetry(beginBenchmarkBlock, readBenchmarkWord, retryUs);
    file.close();
    PcConsole.print(F("[Benchmark] retry comparison "));
    PcConsole.print(transferUs);
    PcConsole.print(' ');
    PcConsole.println(retryUs);
  }
  PcConsole.print(F("[TX test] transfer_us=")); PcConsole.println(transferUs);
  PcConsole.println(F("[TX test] complete"));
}
static bool path(uint8_t op, const char* p) {
  size_t n=strlen(p); if(n>260) stop();
  memcpy(data,p,n); call(op,n); return data[0]==0;
}
}
PcSerial PcConsole;
static uint8_t* sharedFileCache = nullptr;
static PcFsFile* sharedFileOwner = nullptr;
void PcFsFile::claimCache() {
  if(!sharedFileCache) sharedFileCache=(uint8_t*)malloc(512);
  PcLink::sampleRam(PcLink::RAM_CACHE);
  if(!sharedFileCache) {
    PcConsole.println(F("[Memory] PC file cache allocation failed (512 bytes)"));
    PcLink::stop();
  }
  if(sharedFileOwner==this) return;
  if(sharedFileOwner) {
    sharedFileOwner->flush();
    sharedFileOwner->used=0;
  }
  sharedFileOwner=this;
  used=0;
}
PcFsFile::PcFsFile(PcFsFile&& o) { *this=static_cast<PcFsFile&&>(o); }
PcFsFile& PcFsFile::operator=(PcFsFile&& o) {
  if(this==&o) return *this;
  close(); handle=o.handle; kind=o.kind; pos=o.pos; size=o.size;
  base=o.base; used=o.used; pendingBlocks=o.pendingBlocks; dirty=o.dirty; writable=o.writable;
  if(sharedFileOwner==&o) sharedFileOwner=this;
  o.handle=0; o.used=0; o.pendingBlocks=0; o.dirty=false; o.writable=false; return *this;
}
bool PcSdFs::chdir(const char* p) {
  // Treat OSCR's stored directory names as volume-root paths. The firmware
  // commonly reuses the same name after that directory is already current.
  if (!p || !*p) return PcLink::path(6, "/");
  if (*p == '/') return PcLink::path(6, p);
  size_t n = strlen(p);
  if (n > 259) PcLink::stop();
  PcLink::data[0] = '/';
  memcpy(PcLink::data + 1, p, n);
  uint16_t got = PcLink::call(6, n + 1);
  return got == 1 && PcLink::data[0] == 0;
}
bool PcSdFs::mkdir(const char* p,bool) { return PcLink::path(7,p); }
bool PcSdFs::exists(const char* p) { return PcLink::path(8,p); }
bool PcSdFs::remove(const char* p) { return PcLink::path(9,p); }
bool PcFsFile::metadata(uint16_t n) {
  if(PcLink::data[0]) return false;
  if(n!=7) PcLink::stop();
  handle=PcLink::data[1]; kind=PcLink::data[2];
  size=PcLink::get32(PcLink::data+3); pos=0; used=0; dirty=false;
  return handle!=0;
}
bool PcFsFile::open(const char* path,uint8_t flags) {
  close(); size_t n=strlen(path); if(n>260) PcLink::stop();
  // Translate native SdFat flags to the compact PC wire protocol flags.
  // The two layouts differ, so redefining SdFat's O_* macros breaks SD I/O.
  uint8_t wireFlags;
  switch(flags & O_ACCMODE) {
    case O_WRONLY: wireFlags=2; break;
    case O_RDWR: wireFlags=3; break;
    default: wireFlags=1; break;
  }
  if(flags & O_CREAT) wireFlags|=4;
  if(flags & O_TRUNC) wireFlags|=8;
  if(flags & O_APPEND) wireFlags|=16;
  PcLink::data[0]=wireFlags; memcpy(PcLink::data+1,path,n);
  bool ok=metadata(PcLink::call(2,n+1));
  writable=ok && wireFlags!=1;
  if(ok && (flags&O_APPEND)) pos=size;
  return ok;
}
bool PcFsFile::openNext(PcFsFile* dir,uint8_t) {
  close(); PcLink::data[0]=dir->handle;
  return metadata(PcLink::call(10,1));
}
void PcFsFile::flush() {
  if(dirty && used) {
    if(writable && !PcLink::enterDumpBaud()) PcLink::stop();
    // Each 512-byte stream frame retains sequence and CRC16 protection.  A
    // PC58 host negotiates a 16 KiB checkpoint window; older hosts retain the
    // proven 4 KiB window automatically.
    PcLink::streamWrite(handle,base,sharedFileCache,used);
    checkpointFrame(base+used);
  }
  dirty=false; used=0;
}
void PcFsFile::checkpointFrame(uint32_t expectedEnd) {
  pendingBlocks++;
  if(pendingBlocks>=PcLink::streamCheckpointBlocks()) {
    bool cancelled=false;
    if(!PcLink::streamCheckpoint(handle,expectedEnd,cancelled)) PcLink::stop();
    pendingBlocks=0;
    if(cancelled) PcLink::cancelRequested=true;
  }
}
bool PcFsFile::romRetry2M(uint32_t length, void (*beginBlock)(uint32_t), void (*readWord)(uint8_t*), bool snes, bool experimental) {
  if (!writable || !handle || pos || !length || length % 512) return false;
  if (!PcLink::gbaRetryTransfer(handle, length, beginBlock, readWord, experimental ? 13 : snes ? 11 : 0)) return false;
  pos = size = length;
  return true;
}

bool PcFsFile::romRetry2M(uint32_t length, void (*beginBlock)(uint32_t), void (*readWord)(uint8_t*),
                           PcLink::RetryProfile profile, void (*roundStarted)(uint8_t),
                           bool fallbackBeforePayload, void (*progress)(uint32_t)) {
  if (!writable || !handle || pos || !length || length % 512) return false;
  if (!PcLink::gbaRetryTransfer(handle, length, beginBlock, readWord,
                                (uint8_t)profile, nullptr, roundStarted,
                                fallbackBeforePayload, progress)) return false;
  pos = size = length;
  return true;
}

void PcFsFile::benchmarkRetry(void (*beginBlock)(uint32_t), void (*readWord)(uint8_t*), uint32_t& elapsed) {
  const uint32_t length = 1048576UL;
  if (PcLink::gbaRetryTransfer(handle, length, beginBlock, readWord, PcLink::RETRY_PROFILE_BENCHMARK, &elapsed))
    pos = size = length;
}

void PcFsFile::close() {
  if(!handle) return;
  flush();
  if(writable && pendingBlocks) {
    bool cancelled=false;
    if(!PcLink::streamCheckpoint(handle,pos,cancelled)) PcLink::stop();
    pendingBlocks=0;
    if(cancelled) PcLink::cancelRequested=true;
  }
  if(writable && !PcLink::leaveDumpBaud()) PcLink::stop();
  PcLink::data[0]=handle; uint16_t got=PcLink::call(3,1);
  if(PcLink::data[0]) PcLink::stop();
  if(got > 1 && PcLink::data[1]) pcVerificationResult(PcLink::data[1]);
  handle=0; writable=false; pendingBlocks=0;
  if(sharedFileOwner==this) {
    sharedFileOwner=nullptr; used=0; dirty=false;
    free(sharedFileCache);
    sharedFileCache=nullptr;
  }
}
int PcFsFile::read() { uint8_t b; return read(&b,1)==1 ? b : -1; }
int PcFsFile::read(void* dst,size_t n) {
  if(!handle || isDir()) return -1;
  if(!PcLink::leaveDumpBaud()) PcLink::stop();
  claimCache();
  if(dirty) flush();
  size_t done=0; uint8_t* d=(uint8_t*)dst;
  while(done<n && pos<size) {
    if(!used || pos<base || pos>=base+used) {
      PcLink::data[0]=handle; PcLink::put32(PcLink::data+1,pos);
      PcLink::data[5]=0; PcLink::data[6]=2; // request 512 bytes
      uint16_t got=PcLink::call(4,7);
      if(PcLink::data[0] || got<2 || got>513) PcLink::stop();
      used=got-1; base=pos; memcpy(sharedFileCache,PcLink::data+1,used);
    }
    size_t take=min(n-done,(size_t)(base+used-pos));
    memcpy(d+done,sharedFileCache+(pos-base),take); pos+=take; done+=take;
  }
  return done;
}
size_t PcFsFile::write(uint8_t b) { return write(&b,1); }
size_t PcFsFile::write(const uint8_t* src,size_t n) {
  if(!handle || isDir()) PcLink::stop();
  claimCache();
  if(!dirty) used=0;
  size_t done=0;
  while(done<n) {
    if(!dirty) { base=pos; used=0; dirty=true; }
    if(used==512 && PcLink::streamBlockSize()==1024) {
      size_t take=min(n-done,(size_t)512);
      if(writable && !PcLink::enterDumpBaud()) PcLink::stop();
      PcLink::streamWritePair(handle,base,sharedFileCache,512,src+done,take);
      done+=take; pos+=take;
      if(pos>size) size=pos;
      dirty=false; used=0;
      checkpointFrame(pos);
      continue;
    }
    size_t take=min(n-done,(size_t)(512-used));
    memcpy(sharedFileCache+used,src+done,take); used+=take; done+=take; pos+=take;
    if(pos>size) size=pos;
    if(used==512 && PcLink::streamBlockSize()==512) flush();
  }
  return done;
}
bool PcFsFile::seekSet(uint32_t p) { if(dirty) flush(); pos=p; return handle!=0; }
bool PcFsFile::findRecord(uint8_t field,const char* key1,const char* key2,bool* unique) {
  if(!handle || isDir() || !key1) return false;
  if(dirty) flush();
  size_t a=strlen(key1), b=key2?strlen(key2):0;
  if(a+b+4>PcLink::dataCapacity) PcLink::stop();
  const bool checkUnique=unique && PcLink::hasHostSnesLookup();
  PcLink::data[0]=handle; PcLink::data[1]=checkUnique ? 254 : field;
  memcpy(PcLink::data+2,key1,a); PcLink::data[2+a]=0;
  uint16_t n=3+a;
  if(key2) { memcpy(PcLink::data+n,key2,b); PcLink::data[n+b]=0; n+=b+1; }
  uint16_t got=PcLink::call(21,n);
  if(PcLink::data[0] || got!=(checkUnique ? 6 : 5)) PcLink::stop();
  if(checkUnique) *unique=PcLink::data[5]!=0;
  uint32_t found=PcLink::get32(PcLink::data+1);
  used=0;
  pos=(found==0xFFFFFFFFUL)?size:found;
  return found!=0xFFFFFFFFUL;
}
void PcFsFile::rewind() {
  seekSet(0);
  if(isDir()) { PcLink::data[0]=handle; PcLink::call(11,1); if(PcLink::data[0]) PcLink::stop(); }
}
int PcFsFile::fgets(char* dst,int n,const char* delim) {
  int i=0,c; while(i<n-1 && (c=read())>=0) {
    if(c=='\r') continue;
    dst[i++]=c; if(c=='\n' || (delim && strchr(delim,c))) break;
  }
  if(n>0) dst[i]=0; return i;
}
size_t PcFsFile::getName(char* dst,size_t n) {
  PcLink::data[0]=handle; uint16_t got=PcLink::call(15,1);
  if(PcLink::data[0] || !n) return 0;
  size_t take=min(n-1,(size_t)(got-1)); memcpy(dst,PcLink::data+1,take); dst[take]=0; return take;
}
bool PcFsFile::rename(const char* name) {
  flush(); size_t n=strlen(name); if(n>260) PcLink::stop();
  PcLink::data[0]=handle; memcpy(PcLink::data+1,name,n);
  PcLink::call(16,n+1); return PcLink::data[0]==0;
}
void PcSerial::flush() {
  if(!PcLink::connected()) { out=0; return; }
  if(!out) return;
  memcpy(PcLink::data,output,out);
  PcLink::notify(13,out); // console output is one-way; never block on a log ACK
  out=0;
}
size_t PcSerial::write(uint8_t c) {
  if(!PcLink::connected()) return 1;
  output[out++]=c; if(out==64 || c=='\n') flush(); return 1;
}
int PcSerial::available() {
  if(!PcLink::connected()) return 0;
  flush();
  if(at<count) return count-at;
  uint16_t n=0;
  if(!PcLink::pollInput(n)) { delay(20); return 0; }
  if(PcLink::data[0] || n>65) { delay(20); return 0; }
  count=n-1; at=0; memcpy(input,PcLink::data+1,count);
  // Acknowledge the complete poll response once. The old per-character ACK
  // could flood the link and freeze after copying a file with a long path.
  if(count) {
    memcpy(PcLink::data,input,count);
    PcLink::notify(19,count);
  }
  if(!count) delay(10);
  return count;
}
int PcSerial::read() {
  // Do not issue another protocol poll after available() has already filled
  // the local buffer. Menu input must be consumed from that exact response.
  if (at >= count && !available()) return -1;
  uint8_t value=input[at++];
  // EOT was acknowledged with the complete block in available().
  if (value==0x04) PcLink::detachToPhysical();
  return value;
}
int PcSerial::peek() { return available() ? input[at] : -1; }

static ::SdFs* physicalVolume = nullptr;
static char physicalCwd[64] = "/";

static bool physicalPath(char* out, size_t capacity, const char* path) {
  if(!path || !*path || !strcmp(path,"/")) {
    if(capacity<2) return false; strcpy(out,"/"); return true;
  }
  if(path[0]=='/') {
    if(strlen(path)+1>capacity) return false; strcpy(out,path); return true;
  }
  size_t cwdLength=strlen(physicalCwd), pathLength=strlen(path);
  bool root=cwdLength==1 && physicalCwd[0]=='/';
  if(cwdLength + pathLength + (root?1:2) > capacity) return false;
  strcpy(out,physicalCwd);
  if(!root) strcat(out,"/");
  strcat(out,path);
  return true;
}

static bool openPhysicalFile(::FsFile& file, const char* path, uint8_t flags) {
  bool opened = file.open(physicalVolume, path, flags);
  if(!opened && PcLink::connected()) {
    PcConsole.print(F("[SD] open failed path=")); PcConsole.print(path);
    PcConsole.print(F(" flags=")); PcConsole.print(flags);
    PcConsole.print(F(" code=")); PcConsole.print(physicalVolume->sdErrorCode(),HEX);
    PcConsole.print(F(" data=")); PcConsole.println(physicalVolume->sdErrorData(),HEX);
  }
  return opened;
}

// Keep the path buffer out of the absolute-path call frame used by fileBrowser.
static bool __attribute__((noinline)) openPhysicalRelative(::FsFile& file, const char* path, uint8_t flags) {
  char absolute[260];
  return physicalPath(absolute, sizeof(absolute), path) && openPhysicalFile(file, absolute, flags);
}

static bool __attribute__((noinline)) openRemoteDatabase(PcFsFile& file, const char* path, size_t length, uint8_t flags) {
  char absolute[64];
  if(length + 2 > sizeof(absolute)) return false;
  absolute[0] = '/';
  memcpy(absolute + 1, path, length + 1);
  return file.open(absolute, flags);
}

HybridFsFile::HybridFsFile(HybridFsFile&& other) { *this=static_cast<HybridFsFile&&>(other); }
HybridFsFile& HybridFsFile::operator=(HybridFsFile&& other) {
  if(this==&other) return *this;
  close(); pc=other.pc;
  if(pc) remote=static_cast<PcFsFile&&>(other.remote);
  else local.move(&other.local);
  return *this;
}
bool HybridFsFile::open(const char* path,uint8_t flags) {
  close();
  // A connected PC always handles root database reads, independently of
  // whether ROM output is directed to PC or physical SD.
  size_t length = path ? strlen(path) : 0;
  bool database = flags == O_READ && length > 4 && !strchr(path, '/') &&
                  !strcasecmp(path + length - 4, ".txt");
  pc = PcLink::usingPcStorage() || (PcLink::connected() && database);
  if(pc) {
    if(database) return openRemoteDatabase(remote, path, length, flags);
    return remote.open(path,flags);
  }
  if(!physicalVolume) return false;
  if(!path || !*path) path = "/";
  if(path[0] == '/') return length < 260 && openPhysicalFile(local, path, flags);
  return openPhysicalRelative(local, path, flags);
}
bool HybridFsFile::openNext(HybridFsFile* dir,uint8_t flags) {
  close(); pc=PcLink::usingPcStorage();
  return pc ? remote.openNext(&dir->remote,flags) : local.openNext(&dir->local,flags);
}
void HybridFsFile::close() {
  if(pc) remote.close();
  else {
    if(standaloneFileTracking() && local.isOpen() && local.isWritable()) {
      if(!local.sync() || local.getWriteError()) standaloneError();
      else standaloneFileClosed(local.fileSize());
    }
    local.close();
  }
}
void HybridFsFile::flush() { if(pc) remote.flush(); else local.flush(); }
bool HybridFsFile::sync() { return pc ? remote.sync() : local.sync(); }
HybridFsFile::operator bool() const { return pc ? (bool)remote : (bool)local; }
bool HybridFsFile::isOpen() const { return pc ? remote.isOpen() : local.isOpen(); }
bool HybridFsFile::isDir() const { return pc ? remote.isDir() : local.isDir(); }
bool HybridFsFile::isFile() const { return pc ? remote.isFile() : local.isFile(); }
bool HybridFsFile::isHidden() const { return pc ? remote.isHidden() : local.isHidden(); }
uint32_t HybridFsFile::fileSize() const { return pc ? remote.fileSize() : local.fileSize(); }
uint32_t HybridFsFile::curPosition() const { return pc ? remote.curPosition() : local.curPosition(); }
uint32_t HybridFsFile::position() const { return pc ? remote.position() : local.position(); }
int HybridFsFile::available() { return pc ? remote.available() : local.available(); }
int HybridFsFile::read() { return pc ? remote.read() : local.read(); }
int HybridFsFile::peek() { return pc ? remote.peek() : local.peek(); }
int HybridFsFile::read(void* dst,size_t n) { return pc ? remote.read(dst,n) : local.read(dst,n); }
size_t HybridFsFile::write(uint8_t b) { return pc ? remote.write(b) : local.write(b); }
size_t HybridFsFile::write(const uint8_t* src,size_t n) { return pc ? remote.write(src,n) : local.write(src,n); }
bool HybridFsFile::seekSet(uint32_t p) { return pc ? remote.seekSet(p) : local.seekSet(p); }
bool HybridFsFile::seek(uint32_t p) { return seekSet(p); }
bool HybridFsFile::seekCur(int32_t p) { return pc ? remote.seekCur(p) : local.seekCur(p); }
bool HybridFsFile::findRecord(uint8_t field,const char* key1,const char* key2,bool* unique) {
  if(pc) return remote.findRecord(field,key1,key2,unique);
  (void)field; (void)key1; (void)key2; return false;
}
void HybridFsFile::rewind() { if(pc) remote.rewind(); else local.rewind(); }
int HybridFsFile::fgets(char* dst,int n,const char* delimiters) { return pc ? remote.fgets(dst,n,delimiters) : local.fgets(dst,n,delimiters); }
size_t HybridFsFile::getName(char* dst,size_t n) { return pc ? remote.getName(dst,n) : local.getName(dst,n); }
bool HybridFsFile::rename(const char* name) { return pc ? remote.rename(name) : local.rename(name); }

bool HybridSdFs::beginPhysical(uint8_t chipSelect) {
  if(physicalReady) {
    physicalVolume=&local;
    local.chvol();
    local.chdir();
    return true;
  }
  pinMode(chipSelect, OUTPUT);
  digitalWrite(chipSelect, HIGH);
  delay(20);
  // First use SdFat's original OSCR initialization and SPI speed.  Only fall
  // back after a real failure; running a healthy HW3 card at 1 MHz made the
  // 285 KB SNES database scan take far longer than upstream firmware.
  if(local.begin(chipSelect)) {
    physicalReady=true; physicalVolume=&local; local.chvol(); return true;
  }
  const uint32_t fallback[] = {SD_SCK_MHZ(4), SD_SCK_MHZ(1)};
  for(uint8_t i=0; i<2; i++) {
    local.end();
    digitalWrite(chipSelect, HIGH);
    delay(50);
    if(local.begin(chipSelect, fallback[i])) {
      physicalReady=true; physicalVolume=&local; local.chvol(); return true;
    }
  }
  return false;
}
bool HybridSdFs::begin(uint8_t chipSelect) {
  if(PcLink::connected()) { PcLink::setPcStorage(true); return true; }
  PcLink::setPcStorage(false);
  return beginPhysical(chipSelect);
}
bool HybridSdFs::chdir(const char* path) {
  if(PcLink::usingPcStorage()) return remote.chdir(path);
  local.chvol();
  char absolute[sizeof(physicalCwd)];
  // OSCR directory strings are volume-root paths even without a leading '/'.
  if(!path || !*path || !strcmp(path,"/")) strcpy(absolute,"/");
  else {
    size_t n=strlen(path); if(n+2>sizeof(absolute)) return false;
    absolute[0]='/'; memcpy(absolute+1,path,n+1);
  }
  bool ok=local.chdir(absolute);
  if(ok) strcpy(physicalCwd,absolute);
  else if(PcLink::connected()) {
    PcConsole.print(F("[SD] chdir failed path=")); PcConsole.println(absolute);
  }
  return ok;
}
bool HybridSdFs::mkdir(const char* path,bool parents) {
  if(PcLink::usingPcStorage()) return remote.mkdir(path,parents);
  char absolute[260]; size_t n=strlen(path);
  if(n+2>sizeof(absolute)) return false;
  absolute[0]='/'; memcpy(absolute+1,path,n+1);
  bool ok=local.mkdir(absolute,parents);
  if(!ok && PcLink::connected()) { PcConsole.print(F("[SD] mkdir failed path=")); PcConsole.println(absolute); }
  return ok;
}
bool HybridSdFs::exists(const char* path) {
  if(PcLink::usingPcStorage()) return remote.exists(path);
  char absolute[260]; size_t n=strlen(path); if(n+2>sizeof(absolute)) return false;
  absolute[0]='/'; memcpy(absolute+1,path,n+1); return local.exists(absolute);
}
bool HybridSdFs::remove(const char* path) {
  if(PcLink::usingPcStorage()) return remote.remove(path);
  char absolute[260]; size_t n=strlen(path); if(n+2>sizeof(absolute)) return false;
  absolute[0]='/'; memcpy(absolute+1,path,n+1); return local.remove(absolute);
}
bool HybridSdFs::selectPhysical(uint8_t chipSelect) {
  if(!beginPhysical(chipSelect)) return false;
  PcLink::setPcStorage(false); return true;
}
void HybridSdFs::selectPc() { if(PcLink::connected()) PcLink::setPcStorage(true); }
bool HybridSdFs::copyPhysicalToPc(uint8_t) {
  PcConsole.println(F("[SD Browser] use PC browser for directory traversal"));
  return false;
}
bool HybridSdFs::listPhysicalPath(uint8_t,const char*) { return false; }
bool HybridSdFs::copyPhysicalPathToPc(uint8_t,const char*) { return false; }
static const char browserToken[]="/__crpc_browser_file__";
static bool copyOnePhysicalFile(const char* name) {
  PcLink::reportRam(PcLink::RAM_COPY_OPEN);
  ::FsFile source;
  if(!physicalVolume || !source.open(physicalVolume,name,O_READ) || source.isDir()) return false;
  PcSdFs pc;
  if(pc.exists(browserToken)) {
    PcConsole.print(F("[SD Copy] skipped existing ")); PcConsole.println(browserToken);
    source.close(); return true;
  }
  PcFsFile destination;
  if(!destination.open(browserToken,O_WRITE|O_CREAT|O_TRUNC)) { source.close(); return false; }
  PcConsole.print(F("[SD Copy] ")); PcConsole.println(browserToken);
  uint32_t done=0, total=source.fileSize();
  while(source.available()) {
    if(PcLink::takeCancelRequest()) {
      destination.close(); source.close();
      pc.remove(browserToken);
      PcConsole.println(F("[SD Browser] copy cancelled")); return false;
    }
    int count=source.read(sdBuffer,sdCopyReadSize);
    PcLink::sampleRam(PcLink::RAM_SD_READ);
    if(count<=0 || destination.write(sdBuffer,count)!=(size_t)count) {
      destination.close(); source.close(); pc.remove(browserToken); return false;
    }
    done+=count;
    PcLink::sampleRam(PcLink::RAM_PC_WRITE);
    if(sdCopyProgressDue(done,total)) {
      PcConsole.print(F("[SD Progress]\t")); PcConsole.print(done);
      PcConsole.print('\t'); PcConsole.println(total);
    }
  }
  destination.close(); source.close(); return true;
}

// One request, root-based component traversal. No heap path, recursion, or
// open ancestor stack. SdFat's current directory is restored before returning.
bool HybridSdFs::browserRequest(uint8_t chipSelect) {
  struct Restore {
    uint8_t checkpoint;
    bool spi, changed;
    Restore(): checkpoint(PcLink::checkpointBlocks),spi(false),changed(false) {}
    ~Restore() {
      if(physicalVolume) {
        physicalVolume->chdir();
        if(changed) physicalVolume->setDedicatedSpi(spi);
      }
      PcLink::checkpointBlocks=checkpoint;
      sdCopyReadSize=256; sdCopyProgressMs=0;
    }
  } restore;
  PcLink::data[0]=PcLink::data[1]=0;
  uint16_t got=PcLink::call(27,2);
  if(got!=7 || PcLink::data[0]) {
    PcConsole.println(F("[SD Browser] invalid request")); return false;
  }
  uint8_t action=PcLink::data[1];
  uint16_t count=PcLink::data[2]|((uint16_t)PcLink::data[3]<<8);
  uint16_t readSize=PcLink::data[4]|((uint16_t)PcLink::data[5]<<8);
  bool dedicated=PcLink::data[6]!=0;
  if((action!='L' && action!='C') || (action=='C' && !count) ||
      (readSize!=256 && readSize!=512)) return false;
  if(!beginPhysical(chipSelect) || !physicalVolume->chdir()) {
    PcConsole.println(F("[SD Browser] SD init failed")); return false;
  }
  for(uint16_t index=1;index<=count;index++) {
    PcLink::data[0]=index; PcLink::data[1]=index>>8;
    got=PcLink::call(27,2);
    if(got<3 || got>257 || PcLink::data[0] || PcLink::data[got-1]) {
      PcConsole.println(F("[SD Browser] invalid component")); return false;
    }
    char* name=(char*)PcLink::data+1;
    if(!*name || strchr(name,'/') || !strcmp(name,".") || !strcmp(name,"..")) {
      PcConsole.println(F("[SD Browser] invalid component")); return false;
    }
    if(action=='C' && index==count) {
      sdCopyReadSize=readSize; sdCopyProgressMs=1000;
      sdCopyLastProgress=millis();
      PcLink::checkpointBlocks=16384UL/PcLink::transferBlockSize;
      restore.spi=physicalVolume->isDedicatedSpi();
      if(dedicated && !restore.spi) {
        if(!physicalVolume->setDedicatedSpi(true)) {
          PcConsole.println(F("[SD Browser] dedicated SPI unavailable")); return false;
        }
        restore.changed=true;
      }
      memcpy(sdBuffer,name,got-1);
      PcConsole.print(F("[SD Browser] copy begin\t")); PcConsole.println(browserToken);
      bool ok=copyOnePhysicalFile((char*)sdBuffer);
      PcConsole.print(ok ? F("[SD Browser] copy complete\t") : F("[SD Browser] copy failed\t"));
      PcConsole.println(browserToken);
      return ok;
    }
    if(!physicalVolume->chdir(name)) {
      PcConsole.println(F("[SD Browser] directory open failed")); return false;
    }
    PcLink::sampleRam(PcLink::RAM_LIST_OPEN);
  }
  PcLink::reportRam(PcLink::RAM_LIST_OPEN);
  ::FsFile directory;
  physicalVolume->chvol();
  if(!(count ? directory.openCwd() : directory.openRoot(physicalVolume)) || !directory.isDir()) {
    PcConsole.println(F("[SD Browser] directory open failed")); return false;
  }
  PcConsole.println(F("[SD Browser] list begin\t/"));
  ::FsFile entry;
  while(entry.openNext(&directory,O_READ)) {
    PcLink::sampleRam(PcLink::RAM_LIST_ENTRY);
    // Listing owns sdBuffer. Console/protocol frames use their separate buffers.
    if(!entry.isHidden()) {
      if(!entry.getName((char*)sdBuffer,256)) {
        PcConsole.println(F("[SD Browser] filename too long")); return false;
      }
      PcConsole.print(F("[SD Entry]\t")); PcConsole.print(entry.isDir()?'D':'F');
      PcConsole.print('\t'); PcConsole.print((char*)sdBuffer); PcConsole.print('\t');
      PcConsole.println(entry.isDir()?0UL:(unsigned long)entry.fileSize());
    }
    entry.close();
  }
  directory.close();
  PcConsole.println(F("[SD Browser] list complete\t/"));
  PcLink::reportRam(PcLink::RAM_LIST_ENTRY);
  return true;
}
