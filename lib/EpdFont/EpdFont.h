#pragma once
#include "EpdFontData.h"

class EpdFont {
  void getTextBounds(const char* string, int startX, int startY, int* minX, int* minY, int* maxX, int* maxY) const;

 public:
  virtual ~EpdFont() = default;

  virtual int16_t ascent() const = 0;
  virtual int16_t descent() const = 0;
  virtual int16_t lineHeight() const = 0;
  virtual bool is2Bit() const = 0;

  void getTextDimensions(const char* string, int* w, int* h) const;
  bool hasPrintableChars(const char* string) const;

  virtual const EpdGlyph* getGlyph(uint32_t cp) const;
  virtual const uint8_t* getBitmapData() const { return nullptr; }
};
