#include "EpdFont.h"

#include <Utf8.h>

#include <algorithm>

#include <flatbuffers/flatbuffers.h>
#include "generated/epd_font_generated.h"
#include <fstream>
#include <vector>
#include <HardwareSerial.h>
#include <SDCardManager.h>

void EpdFont::getTextBounds(const char* string, const int startX, const int startY, int* minX, int* minY, int* maxX,
                            int* maxY) const {
  *minX = startX;
  *minY = startY;
  *maxX = startX;
  *maxY = startY;

  if (*string == '\0') {
    return;
  }

  int cursorX = startX;
  const int cursorY = startY;
  uint32_t cp;
  while ((cp = utf8NextCodepoint(reinterpret_cast<const uint8_t**>(&string)))) {
    const EpdGlyph* glyph = getGlyph(cp);

    if (!glyph) {
      // TODO: Replace with fallback glyph property?
      glyph = getGlyph('?');
    }

    if (!glyph) {
      // TODO: Better handle this?
      continue;
    }

    *minX = std::min(*minX, cursorX + glyph->left);
    *maxX = std::max(*maxX, cursorX + glyph->left + glyph->width);
    *minY = std::min(*minY, cursorY + glyph->top - glyph->height);
    *maxY = std::max(*maxY, cursorY + glyph->top);
    cursorX += glyph->advanceX;
  }
}

void EpdFont::getTextDimensions(const char* string, int* w, int* h) const {
  int minX = 0, minY = 0, maxX = 0, maxY = 0;

  getTextBounds(string, 0, 0, &minX, &minY, &maxX, &maxY);

  *w = maxX - minX;
  *h = maxY - minY;
}

bool EpdFont::hasPrintableChars(const char* string) const {
  int w = 0, h = 0;

  getTextDimensions(string, &w, &h);

  return w > 0 || h > 0;
}

const EpdGlyph* EpdFont::getGlyph(const uint32_t cp) const {
  const EpdUnicodeInterval* intervals = data->intervals;
  const int count = data->intervalCount;

  if (count == 0) return nullptr;

  // Binary search for O(log n) lookup instead of O(n)
  // Critical for Korean fonts with many unicode intervals
  int left = 0;
  int right = count - 1;

  while (left <= right) {
    const int mid = left + (right - left) / 2;
    const EpdUnicodeInterval* interval = &intervals[mid];

    if (cp < interval->first) {
      right = mid - 1;
    } else if (cp > interval->last) {
      left = mid + 1;
    } else {
      // Found: cp >= interval->first && cp <= interval->last
      return &data->glyph[interval->offset + (cp - interval->first)];
    }
  }
  
  return nullptr;
}

EpdFont* EpdFont::loadFromFlatbufferFile(const char* path) {
  FsFile file;
  if (!SdMan.openFileForRead("FNT", path, file)) {
    Serial.printf("EpdFont::loadFromFlatbufferFile: Failed to open file: %s\n", path);
    return nullptr;
  }

  // Obtain root
  Serial.printf("Loading font from flatbuffer, size: %zu\n", file.fileSize());
  uint8_t* buffer = new uint8_t[file.fileSize()];
  file.read(buffer, file.fileSize());
  const epd::EpdFont* fb = epd::GetEpdFont(buffer);
  if (!fb) return nullptr;

  // Bitmap
  const flatbuffers::Vector<uint8_t>* bmp = fb->bitmap();
  uint8_t* bitmap = nullptr;
  size_t bitmap_size = 0;
  if (bmp) {
    Serial.printf("Loading bitmap\n");
    bitmap_size = bmp->size();
    bitmap = new uint8_t[bitmap_size];
    memcpy(bitmap, bmp->data(), bitmap_size);
  }

  // Glyphs (struct vector)
  const auto* glyphs_vec = fb->glyph();
  EpdGlyph* glyphs = nullptr;
  size_t glyph_count = 0;
  if (glyphs_vec) {
    Serial.printf("Loading glyphs\n");
    glyph_count = glyphs_vec->size();
    glyphs = new EpdGlyph[glyph_count];
    for (size_t i = 0; i < glyph_count; ++i) {
      const epd::EpdGlyph* g = glyphs_vec->Get(i);
      glyphs[i].width = g->width();
      glyphs[i].height = g->height();
      glyphs[i].advanceX = g->advance_x();
      glyphs[i].left = g->left();
      glyphs[i].top = g->top();
      glyphs[i].dataLength = g->data_length();
      glyphs[i].dataOffset = g->data_offset();
    }
  }

  // Intervals
  const auto* intervals_vec = fb->intervals();
  EpdUnicodeInterval* intervals = nullptr;
  size_t interval_count = 0;
  if (intervals_vec) {
    Serial.printf("Loading intervals\n");
    interval_count = intervals_vec->size();
    intervals = new EpdUnicodeInterval[interval_count];
    for (size_t i = 0; i < interval_count; ++i) {
      Serial.printf("Loading interval %zu\n", i);
      const epd::EpdUnicodeInterval* it = intervals_vec->Get(i);
      intervals[i].first = it->first();
      intervals[i].last = it->last();
      intervals[i].offset = it->offset();
    }
  }

  // Populate EpdFontData
  EpdFontData* d = new EpdFontData();
  Serial.printf("Loading meta\n");
  d->bitmap = bitmap;
  d->glyph = glyphs;
  d->intervals = intervals;
  d->intervalCount = static_cast<uint32_t>(interval_count);
  d->advanceY = static_cast<uint8_t>(fb->advance_y());
  d->ascender = static_cast<int>(fb->ascender());
  d->descender = static_cast<int>(fb->descender());
  d->is2Bit = fb->is_2bit();

  Serial.printf("fin\n");

  return new EpdFont(d);
}
