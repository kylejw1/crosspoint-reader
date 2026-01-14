#pragma once
#include "EpdFont.h"

class EpdFontFamily {
 public:
  enum Style : uint8_t { REGULAR = 0, BOLD = 1, ITALIC = 2, BOLD_ITALIC = 3 };

  explicit EpdFontFamily(const EpdFont* regular, const EpdFont* bold = nullptr, const EpdFont* italic = nullptr,
                         const EpdFont* boldItalic = nullptr)
      : regular(regular), bold(bold), italic(italic), boldItalic(boldItalic) {}
  ~EpdFontFamily() = default;
  void getTextDimensions(const char* string, int* w, int* h, Style style = REGULAR) const;
  bool hasPrintableChars(const char* string, Style style = REGULAR) const;
  const int16_t ascent(Style style = REGULAR) const { return getFont(style)->ascent(); }
  const int16_t descent(Style style = REGULAR) const { return getFont(style)->descent(); }
  const int16_t lineHeight(Style style = REGULAR) const { return getFont(style)->lineHeight(); }
  const bool is2Bit(Style style = REGULAR) const { return getFont(style)->is2Bit(); }
  const uint8_t* getBitmapData(Style style = REGULAR) const { return getFont(style)->getBitmapData(); }
  const EpdGlyph* getGlyph(uint32_t cp, Style style = REGULAR) const;

 private:
  const EpdFont* regular;
  const EpdFont* bold;
  const EpdFont* italic;
  const EpdFont* boldItalic;

  const EpdFont* getFont(Style style) const;
};
