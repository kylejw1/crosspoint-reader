#pragma once
#include "EpdFont.h"

class EpdFontRam final : public EpdFont {
public:
    explicit EpdFontRam(const EpdFontData* data) : data(data) {}

    const EpdGlyph* getGlyph(uint32_t cp) const override;
    const uint8_t* getBitmapData() const override { return data->bitmap; }
    int16_t ascent() const override {
      return static_cast<int16_t>(data->ascender);
    };
    int16_t descent() const override {
      return static_cast<int16_t>(data->descender);
    };
    int16_t lineHeight() const override {
      return static_cast<int16_t>(data->advanceY);
    };
    bool is2Bit() const override {
      return data->is2Bit;
    };

private:
    const EpdFontData* data;
};