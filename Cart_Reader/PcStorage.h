// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <Arduino.h>
#include <SdFat.h>

// Preserve native SdFat types before the OSCR compatibility macros below.
using PhysicalFsFile = ::FsFile;
using PhysicalSdFs = ::SdFs;
namespace PcLink {
extern uint8_t data[528];
uint16_t call(uint8_t op, uint16_t count);
void start();
bool tryStart(uint16_t timeoutMs = 1500);
bool connected();
bool usingPcStorage();
bool takeCancelRequest();
void setPcStorage(bool enabled);
bool enterDumpBaud();
bool leaveDumpBaud();
void streamWrite(uint8_t handle, uint32_t offset, const uint8_t* source, uint16_t count);
void streamWritePair(uint8_t handle, uint32_t offset,
                     const uint8_t* first, uint16_t firstCount,
                     const uint8_t* second, uint16_t secondCount);
bool streamCheckpoint(uint8_t handle, uint32_t expectedEnd, bool& cancelled);
uint8_t streamCheckpointBlocks();
uint16_t streamBlockSize();
void activityBlinking();
void stop();
void resetAfterHostLoss();
bool detachToPhysical();
uint32_t benchmark();
bool benchmarkOne(uint8_t index, uint32_t& baud);
void menuReady();
void pressButtonReady();
void put32(uint8_t* p, uint32_t v);
uint32_t get32(const uint8_t* p);
}

// Positional I/O and a 256-byte cache avoid a USB round trip per ROM byte.
class PcFsFile : public Stream {
  uint8_t handle = 0, kind = 0;
  uint32_t pos = 0, size = 0, base = 0;
  uint16_t used = 0;
  uint8_t pendingBlocks = 0;
  bool dirty = false, writable = false;
  void claimCache();
  void checkpointFrame(uint32_t expectedEnd);
  bool metadata(uint16_t n);
 public:
  PcFsFile() = default;
  PcFsFile(const PcFsFile&) = delete;
  PcFsFile& operator=(const PcFsFile&) = delete;
  PcFsFile(PcFsFile&& other);
  PcFsFile& operator=(PcFsFile&& other);
  ~PcFsFile() { close(); }
  using Print::write;
  bool open(const char* path, uint8_t flags = O_READ);
  bool openNext(PcFsFile* dir, uint8_t flags = O_READ);
  void close();
  void flush();
  bool sync() { flush(); return true; }
  operator bool() const { return handle != 0; }
  bool isOpen() const { return handle != 0; }
  bool isDir() const { return kind & 1; }
  bool isFile() const { return handle && !isDir(); }
  bool isHidden() const { return kind & 2; }
  uint32_t fileSize() const { return size; }
  uint32_t curPosition() const { return pos; }
  uint32_t position() const { return pos; }
  int available() override { return pos < size ? (int)min(size-pos, 32767UL) : 0; }
  int read() override;
  int peek() override { int c=read(); if(c>=0) --pos; return c; }
  int read(void* dst, size_t n);
  size_t write(uint8_t b) override;
  size_t write(const uint8_t* src, size_t n) override;
  bool seekSet(uint32_t p);
  bool seek(uint32_t p) { return seekSet(p); }
  bool seekCur(int32_t p) { return seekSet(pos+p); }
  bool findRecord(uint8_t field, const char* key1, const char* key2 = nullptr);
  void rewind();
  int fgets(char* dst, int n, const char* delimiters = nullptr);
  size_t getName(char* dst, size_t n);
  bool rename(const char* name);
  static void dateTimeCallback(void (*)(uint16_t*,uint16_t*)) {}
};
using PcSdFile = PcFsFile;
class PcSdFs {
 public:
  bool begin(uint8_t) { PcLink::start(); return true; }
  bool chdir(const char* path = "/");
  bool mkdir(const char* path, bool parents = true);
  bool exists(const char* path);
  bool remove(const char* path);
  PcFsFile open(const char* path, uint8_t flags = O_READ) {
    PcFsFile f; f.open(path, flags); return f;
  }
};

class HybridFsFile : public Stream {
  bool pc = false;
  PcFsFile remote;
  PhysicalFsFile local;
 public:
  HybridFsFile() = default;
  HybridFsFile(const HybridFsFile&) = delete;
  HybridFsFile& operator=(const HybridFsFile&) = delete;
  HybridFsFile(HybridFsFile&& other);
  HybridFsFile& operator=(HybridFsFile&& other);
  using Print::write;
  bool open(const char* path, uint8_t flags = O_READ);
  bool openNext(HybridFsFile* dir, uint8_t flags = O_READ);
  void close(); void flush(); bool sync();
  operator bool() const;
  bool isOpen() const; bool isDir() const; bool isFile() const; bool isHidden() const;
  bool isPc() const { return pc; }
  uint32_t fileSize() const; uint32_t curPosition() const; uint32_t position() const;
  int available() override; int read() override; int peek() override; int read(void* dst, size_t n);
  size_t write(uint8_t b) override; size_t write(const uint8_t* src, size_t n) override;
  bool seekSet(uint32_t p); bool seek(uint32_t p); bool seekCur(int32_t p);
  bool findRecord(uint8_t field, const char* key1, const char* key2 = nullptr);
  void rewind(); int fgets(char* dst, int n, const char* delimiters = nullptr);
  size_t getName(char* dst, size_t n); bool rename(const char* name);
  static void dateTimeCallback(void (*callback)(uint16_t*,uint16_t*)) { FsDateTime::setCallback(callback); }
};

class HybridSdFs {
  PcSdFs remote;
  PhysicalSdFs local;
  bool physicalReady = false;
  uint16_t copiedFiles = 0;
  bool beginPhysical(uint8_t chipSelect);
  bool copyDirectory(char* path, uint16_t length);
 public:
  bool begin(uint8_t chipSelect);
  bool chdir(const char* path = "/");
  bool mkdir(const char* path, bool parents = true);
  bool exists(const char* path); bool remove(const char* path);
  bool selectPhysical(uint8_t chipSelect);
  void selectPc();
  bool copyPhysicalToPc(uint8_t chipSelect);
  bool listPhysicalPath(uint8_t chipSelect, const char* path);
  bool copyPhysicalPathToPc(uint8_t chipSelect, const char* path);
  uint8_t physicalErrorCode() { return local.sdErrorCode(); }
  uint8_t physicalErrorData() { return local.sdErrorData(); }
  HybridFsFile open(const char* path, uint8_t flags = O_READ) {
    HybridFsFile file; file.open(path, flags); return file;
  }
};

#define FsFile HybridFsFile
#define SdFile HybridFsFile
#define SdFs HybridSdFs

class PcSerial : public Stream {
  uint8_t output[64], input[64];
  uint8_t out = 0, at = 0, count = 0;
 public:
  using Print::write;
  void begin(unsigned long) { PcLink::tryStart(); }
  void end() { flush(); }
  operator bool() { return true; }
  size_t write(uint8_t c) override;
  int available() override;
  int read() override;
  int peek() override;
  void flush() override;
};
extern PcSerial PcConsole;
