// SPDX-License-Identifier: GPL-3.0-or-later
#include "PcStorage.h"
#undef FsFile
#undef SdFile
#undef SdFs
#include <string.h>
#include <avr/wdt.h>
extern void pcVerificationResult(uint8_t code);
extern HybridSdFs sd;

namespace PcLink {
uint8_t data[528];
static bool started = false;
static bool pcStorage = false;
static uint16_t sequence = 0;
static uint32_t activeBaud = 250000UL;
static uint32_t safeBaud = 250000UL;
static uint32_t dumpBaud = 250000UL;
static bool cancelRequested = false;
static uint8_t checkpointBlocks = 8;
static uint16_t transferBlockSize = 512;
static bool ledActivity = false;
// Preserve one word across watchdog reset.  A disconnect-triggered restart
// must not reconnect to the host during the few milliseconds before Windows
// finishes closing the COM handle.
static uint32_t skipPcBoot __attribute__((section(".noinit")));
static const uint32_t SKIP_PC_BOOT_MAGIC = 0x50434454UL; // "PCDT"
bool takeCancelRequest() { bool value=cancelRequested; cancelRequested=false; return value; }
static uint16_t crc(uint16_t c, uint8_t b) {
  c ^= (uint16_t)b << 8;
  for (uint8_t i=0;i<8;i++) c = c & 0x8000 ? (c<<1)^0x1021 : c<<1;
  return c;
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
  if(n>sizeof(data)) stop();
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
  if(n<1 || n>sizeof(data)) stop();
  for(uint16_t i=0;i<n;i++) {data[i]=receive(); c=crc(c,data[i]);}
  uint16_t got=receive(); got|=(uint16_t)receive()<<8;
  if(c!=got) stop();
  return n;
}
static void notify(uint8_t op, uint16_t n) {
  if(!started) return;
  if(n>sizeof(data)) return;
  uint16_t seq=++sequence;
  uint8_t h[]={1,op,(uint8_t)seq,(uint8_t)(seq>>8),(uint8_t)n,(uint8_t)(n>>8)};
  uint16_t c=0xffff;
  Serial.write((const uint8_t*)"CRPC",4);
  for(uint8_t b:h) { Serial.write(b); c=crc(c,b); }
  for(uint16_t i=0;i<n;i++) { Serial.write(data[i]); c=crc(c,data[i]); }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8));
  Serial.flush();
}
void streamWrite(uint8_t handle, uint32_t offset, const uint8_t* source, uint16_t count) {
  if(count>512) stop();
  data[0]=handle; put32(data+1,offset);
  memcpy(data+5,source,count);
  notify(22,count+5);
}
void streamWritePair(uint8_t handle, uint32_t offset,
                     const uint8_t* first, uint16_t firstCount,
                     const uint8_t* second, uint16_t secondCount) {
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
  for(uint16_t i=0;i<firstCount;i++) { Serial.write(first[i]); c=crc(c,first[i]); }
  for(uint16_t i=0;i<secondCount;i++) { Serial.write(second[i]); c=crc(c,second[i]); }
  Serial.write((uint8_t)c); Serial.write((uint8_t)(c>>8)); Serial.flush();
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
void menuReady() { notify(20,0); }
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
  notify(23,0);
}
static bool receiveTimed(uint8_t& value, unsigned long deadline) {
  while (!Serial.available()) if ((long)(millis() - deadline) >= 0) return false;
  value = Serial.read();
  return true;
}
static bool pollInput(uint16_t& replyLength) {
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
    if(r[0]!=1 || r[1]!=(op|0x80) || r[2]!=(uint8_t)seq || r[3]!=(uint8_t)(seq>>8) || helloLength<1 || helloLength>sizeof(data)) goto no_host;
    for(uint16_t i=0;i<helloLength;i++) { if(!receiveTimed(data[i],deadline)) goto no_host; c=crc(c,data[i]); }
    uint8_t lo,hi;
    if(!receiveTimed(lo,deadline) || !receiveTimed(hi,deadline) || c!=(uint16_t)(lo|((uint16_t)hi<<8)) || data[0]) goto no_host;
    started=true; pcStorage=true;
  if(helloLength>=5) {
    uint32_t preferred=get32(data+1);
    uint32_t preferredDump=helloLength>=9 ? get32(data+5) : preferred;
    uint8_t negotiatedBlocks=(helloLength>=10 && data[9]>=8 && data[9]<=32) ? data[9] : 8;
    uint16_t negotiatedSize=helloLength>=12 ? (uint16_t)(data[10]|((uint16_t)data[11]<<8)) : 512;
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
static bool path(uint8_t op, const char* p) {
  size_t n=strlen(p); if(n>260) stop();
  memcpy(data,p,n); call(op,n); return data[0]==0;
}
}
PcSerial PcConsole;
static uint8_t* sharedFileCache = nullptr;
static PcFsFile* sharedFileOwner = nullptr;
void PcFsFile::claimCache() {
  if(!sharedFileCache) {
    sharedFileCache=(uint8_t*)malloc(512);
    if(!sharedFileCache) PcLink::stop();
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
  if(sharedFileOwner==this) { sharedFileOwner=nullptr; used=0; dirty=false; }
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
bool PcFsFile::findRecord(uint8_t field,const char* key1,const char* key2) {
  if(!handle || isDir() || !key1) return false;
  if(dirty) flush();
  size_t a=strlen(key1), b=key2?strlen(key2):0;
  if(a+b+4>sizeof(PcLink::data)) PcLink::stop();
  PcLink::data[0]=handle; PcLink::data[1]=field;
  memcpy(PcLink::data+2,key1,a); PcLink::data[2+a]=0;
  uint16_t n=3+a;
  if(key2) { memcpy(PcLink::data+n,key2,b); PcLink::data[n+b]=0; n+=b+1; }
  uint16_t got=PcLink::call(21,n);
  if(PcLink::data[0] || got!=5) PcLink::stop();
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
static bool sdBrowserCancelled();

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
    if(database) {
      char absolute[64];
      if(length + 2 > sizeof(absolute)) return false;
      absolute[0]='/'; memcpy(absolute+1,path,length+1);
      return remote.open(absolute,flags);
    }
    return remote.open(path,flags);
  }
  char absolute[260];
  if(!physicalVolume || !physicalPath(absolute,sizeof(absolute),path)) return false;
  bool opened=local.open(physicalVolume,absolute,flags);
  if(!opened && PcLink::connected()) {
    PcConsole.print(F("[SD] open failed path=")); PcConsole.print(absolute);
    PcConsole.print(F(" flags=")); PcConsole.print(flags);
    PcConsole.print(F(" code=")); PcConsole.print(physicalVolume->sdErrorCode(),HEX);
    PcConsole.print(F(" data=")); PcConsole.println(physicalVolume->sdErrorData(),HEX);
  }
  return opened;
}
bool HybridFsFile::openNext(HybridFsFile* dir,uint8_t flags) {
  close(); pc=PcLink::usingPcStorage();
  return pc ? remote.openNext(&dir->remote,flags) : local.openNext(&dir->local,flags);
}
void HybridFsFile::close() { if(pc) remote.close(); else local.close(); }
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
bool HybridFsFile::findRecord(uint8_t field,const char* key1,const char* key2) {
  if(pc) return remote.findRecord(field,key1,key2);
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
bool HybridSdFs::copyDirectory(char* path,uint16_t length) {
  ::FsFile directory;
  if(!physicalVolume || !directory.open(physicalVolume,path,O_READ) || !directory.isDir()) return false;
  ::FsFile entry;
  while(entry.openNext(&directory,O_READ)) {
    if(entry.isHidden()) { entry.close(); continue; }
    uint16_t nameAt=length;
    if(length>1 && path[length-1]!='/') path[nameAt++]='/';
    if(nameAt>=259 || !entry.getName(path+nameAt,260-nameAt)) {
      path[length]=0; entry.close(); continue;
    }
    uint16_t childLength=strlen(path);
    bool isDirectory=entry.isDir();
    entry.close();
    if(isDirectory) {
      remote.mkdir(path,true);
      if(!copyDirectory(path,childLength)) { directory.close(); return false; }
      path[length]=0;
      continue;
    }
    ::FsFile source;
    if(!source.open(physicalVolume,path,O_READ)) { directory.close(); return false; }
    if(remote.exists(path)) {
      PcConsole.print(F("[SD Copy] skipped existing ")); PcConsole.println(path);
      source.close(); path[length]=0; continue;
    }
    PcFsFile destination;
    if(!destination.open(path,O_WRITE|O_CREAT|O_TRUNC)) { source.close(); directory.close(); return false; }
    PcConsole.print(F("[SD Copy] ")); PcConsole.println(path);
    uint32_t done=0, total=source.fileSize();
    while(source.available()) {
      if(PcLink::takeCancelRequest() || ((done & 4095UL)==0 && sdBrowserCancelled())) {
        destination.close(); source.close(); directory.close();
        remote.remove(path);
        PcConsole.println(F("[SD Browser] copy cancelled")); return false;
      }
      int count=source.read(PcLink::data,256);
      if(count<=0 || destination.write(PcLink::data,count)!=(size_t)count) {
        destination.close(); source.close(); directory.close(); remote.remove(path); return false;
      }
      done+=count;
      if((done & 4095UL)==0 || done==total) {
        PcConsole.print(F("[SD Progress]\t")); PcConsole.print(done);
        PcConsole.print('\t'); PcConsole.println(total);
      }
    }
    destination.close(); source.close();
    copiedFiles++;
    path[length]=0;
  }
  directory.close();
  return true;
}
bool HybridSdFs::copyPhysicalToPc(uint8_t chipSelect) {
  if(!PcLink::connected()) return false;
  PcConsole.println(F("[SD Copy] starting"));
  if(!beginPhysical(chipSelect)) {
    PcConsole.print(F("[SD Copy] SD init failed code="));
    PcConsole.print(local.sdErrorCode(), HEX);
    PcConsole.print(F(" data="));
    PcConsole.println(local.sdErrorData(), HEX);
    return false;
  }
  remote.chdir("/");
  char* copyPath=(char*)malloc(260);
  if(!copyPath) { PcConsole.println(F("[SD Copy] not enough memory")); return false; }
  strcpy(copyPath,"/");
  copiedFiles=0;
  bool ok=copyDirectory(copyPath,1);
  free(copyPath);
  if(!ok) PcConsole.println(F("[SD Copy] failed"));
  else if(!copiedFiles) PcConsole.println(F("[SD Copy] no files found"));
  else {
    PcConsole.print(F("[SD Copy] complete files="));
    PcConsole.println(copiedFiles);
  }
  return ok && copiedFiles;
}

bool HybridSdFs::listPhysicalPath(uint8_t chipSelect,const char* requested) {
  if(!PcLink::connected() || !beginPhysical(chipSelect)) {
    PcConsole.println(F("[SD Browser] SD init failed")); return false;
  }
  char path[260];
  if(!physicalPath(path,sizeof(path),requested)) {
    PcConsole.println(F("[SD Browser] invalid path")); return false;
  }
  ::FsFile directory;
  if(!directory.open(physicalVolume,path,O_READ) || !directory.isDir()) {
    PcConsole.println(F("[SD Browser] directory open failed")); return false;
  }
  PcConsole.print(F("[SD Browser] list begin\t")); PcConsole.println(path);
  ::FsFile entry;
  char name[192];
  while(entry.openNext(&directory,O_READ)) {
    if(!entry.isHidden() && entry.getName(name,sizeof(name))) {
      PcConsole.print(F("[SD Entry]\t"));
      PcConsole.print(entry.isDir() ? 'D' : 'F'); PcConsole.print('\t');
      PcConsole.print(name); PcConsole.print('\t');
      PcConsole.println(entry.isDir() ? 0UL : (unsigned long)entry.fileSize());
    }
    entry.close();
  }
  directory.close();
  PcConsole.print(F("[SD Browser] list complete\t")); PcConsole.println(path);
  return true;
}

static bool sdBrowserCancelled() {
  if(!PcConsole.available()) return false;
  int value=PcConsole.read();
  return value=='X' || value=='x';
}

static bool copyOnePhysicalFile(const char* path) {
  ::FsFile source;
  if(!physicalVolume || !source.open(physicalVolume,path,O_READ) || source.isDir()) return false;
  PcSdFs pc;
  if(pc.exists(path)) {
    PcConsole.print(F("[SD Copy] skipped existing ")); PcConsole.println(path);
    source.close(); return true;
  }
  PcFsFile destination;
  if(!destination.open(path,O_WRITE|O_CREAT|O_TRUNC)) { source.close(); return false; }
  PcConsole.print(F("[SD Copy] ")); PcConsole.println(path);
  uint32_t done=0, total=source.fileSize();
  while(source.available()) {
    if(PcLink::takeCancelRequest() || ((done & 4095UL)==0 && sdBrowserCancelled())) {
      destination.close(); source.close();
      pc.remove(path);
      PcConsole.println(F("[SD Browser] copy cancelled")); return false;
    }
    int count=source.read(PcLink::data,256);
    if(count<=0 || destination.write(PcLink::data,count)!=(size_t)count) {
      destination.close(); source.close(); pc.remove(path); return false;
    }
    done+=count;
    if((done & 4095UL)==0 || done==total) {
      PcConsole.print(F("[SD Progress]\t")); PcConsole.print(done);
      PcConsole.print('\t'); PcConsole.println(total);
    }
  }
  destination.close(); source.close(); return true;
}

bool HybridSdFs::copyPhysicalPathToPc(uint8_t chipSelect,const char* requested) {
  if(!PcLink::connected() || !beginPhysical(chipSelect)) {
    PcConsole.println(F("[SD Browser] SD init failed")); return false;
  }
  char path[260];
  if(!physicalPath(path,sizeof(path),requested) || !strcmp(path,"/")) {
    PcConsole.println(F("[SD Browser] invalid copy path")); return false;
  }
  remote.chdir("/");
  // Reuse path while creating its PC-side parent.  A second 260-byte local
  // array here can collide with SdFat state on the Mega's 8 KB SRAM.
  char* slash=strrchr(path,'/');
  if(slash && slash!=path) {
    *slash=0;
    bool parentOk=remote.mkdir(path,true) || remote.exists(path);
    *slash='/';
    if(!parentOk) {
      PcConsole.println(F("[SD Browser] PC parent create failed")); return false;
    }
  }
  ::FsFile source;
  if(!source.open(physicalVolume,path,O_READ)) {
    PcConsole.println(F("[SD Browser] source open failed")); return false;
  }
  bool isDirectory=source.isDir(); source.close();
  PcConsole.print(F("[SD Browser] copy begin\t")); PcConsole.println(path);
  bool ok;
  if(isDirectory) {
    remote.mkdir(path,true);
    copiedFiles=0;
    uint16_t length=strlen(path);
    ok=copyDirectory(path,length);
  } else ok=copyOnePhysicalFile(path);
  if(ok) PcConsole.print(F("[SD Browser] copy complete\t"));
  else PcConsole.print(F("[SD Browser] copy failed\t"));
  PcConsole.println(path);
  return ok;
}
