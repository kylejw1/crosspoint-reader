#!python3
import freetype
import sys
import math
import argparse
from collections import namedtuple
import flatbuffers

import epd.EpdFontData as EpdFontData
import epd.EpdGlyph as EpdGlyph
import epd.EpdUnicodeInterval as EpdUnicodeInterval


# Originally from https://github.com/vroland/epdiy

parser = argparse.ArgumentParser(description="Generate a FlatBuffers binary file from a font.")
parser.add_argument("name", action="store", help="name of the font (used for output filename).")
parser.add_argument("size", type=int, help="font size to use.")
parser.add_argument("fontstack", action="store", nargs='+', help="list of font files, ordered by descending priority.")
parser.add_argument("--output", "-o", action="store", help="output file path (default: <name>.epd_fb)")
parser.add_argument("--2bit", dest="is2Bit", action="store_true", help="generate 2-bit greyscale bitmap instead of 1-bit black and white.")
parser.add_argument("--additional-intervals", dest="additional_intervals", action="append", help="Additional code point intervals to export as min,max. This argument can be repeated.")
args = parser.parse_args()

GlyphProps = namedtuple("GlyphProps", ["width", "height", "advance_x", "left", "top", "data_length", "data_offset", "code_point"])

font_stack = [freetype.Face(f) for f in args.fontstack]
is2Bit = args.is2Bit
size = args.size
font_name = args.name

# inclusive unicode code point intervals
# must not overlap and be in ascending order
intervals = [
    ### Basic Latin ###
    # ASCII letters, digits, punctuation, control characters
    (0x0000, 0x007F),
    ### Latin-1 Supplement ###
    # Accented characters for Western European languages
    # (0x0080, 0x00FF),
    # ### Latin Extended-A ###
    # # Eastern European and Baltic languages
    # (0x0100, 0x017F),
    # ### General Punctuation (core subset) ###
    # # Smart quotes, en dash, em dash, ellipsis, NO-BREAK SPACE
    # (0x2000, 0x206F),
    # ### Basic Symbols From "Latin-1 + Misc" ###
    # # dashes, quotes, prime marks
    # (0x2010, 0x203A),
    # # misc punctuation
    # (0x2040, 0x205F),
    # # common currency symbols
    # (0x20A0, 0x20CF),
    # ### Combining Diacritical Marks (minimal subset) ###
    # # Needed for proper rendering of many extended Latin languages
    # (0x0300, 0x036F),
    # ### Greek & Coptic ###
    # # Used in science, maths, philosophy, some academic texts
    # # (0x0370, 0x03FF),
    # ### Cyrillic ###
    # # Russian, Ukrainian, Bulgarian, etc.
    # (0x0400, 0x04FF),
    # ### Math Symbols (common subset) ###
    # # General math operators
    # (0x2200, 0x22FF),
    # # Arrows
    # (0x2190, 0x21FF),
    # ### CJK ###
    # # Core Unified Ideographs
    # # (0x4E00, 0x9FFF),
    # # # Extension A
    # # (0x3400, 0x4DBF),
    # # # Extension B
    # # (0x20000, 0x2A6DF),
    # # # Extension C–F
    # # (0x2A700, 0x2EBEF),
    # # # Extension G
    # # (0x30000, 0x3134F),
    # # # Hiragana
    # # (0x3040, 0x309F),
    # # # Katakana
    # # (0x30A0, 0x30FF),
    # # # Katakana Phonetic Extensions
    # # (0x31F0, 0x31FF),
    # # # Halfwidth Katakana
    # # (0xFF60, 0xFF9F),
    # # # Hangul Syllables
    # # (0xAC00, 0xD7AF),
    # # # Hangul Jamo
    # # (0x1100, 0x11FF),
    # # # Hangul Compatibility Jamo
    # # (0x3130, 0x318F),
    # # # Hangul Jamo Extended-A
    # # (0xA960, 0xA97F),
    # # # Hangul Jamo Extended-B
    # # (0xD7B0, 0xD7FF),
    # # # CJK Radicals Supplement
    # # (0x2E80, 0x2EFF),
    # # # Kangxi Radicals
    # # (0x2F00, 0x2FDF),
    # # # CJK Symbols and Punctuation
    # # (0x3000, 0x303F),
    # # # CJK Compatibility Forms
    # # (0xFE30, 0xFE4F),
    # # # CJK Compatibility Ideographs
    # # (0xF900, 0xFAFF),
]
print(f"Intervals: {len(intervals)}")
add_ints = []
if args.additional_intervals:
    add_ints = [tuple([int(n, base=0) for n in i.split(",")]) for i in args.additional_intervals]

def norm_floor(val):
    return int(math.floor(val / (1 << 6)))

def norm_ceil(val):
    return int(math.ceil(val / (1 << 6)))

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]

def load_glyph(code_point):
    face_index = 0
    while face_index < len(font_stack):
        face = font_stack[face_index]
        glyph_index = face.get_char_index(code_point)
        if glyph_index > 0:
            face.load_glyph(glyph_index, freetype.FT_LOAD_RENDER)
            return face
        face_index += 1
    print(f"code point {code_point} ({hex(code_point)}) not found in font stack!", file=sys.stderr)
    return None

unmerged_intervals = sorted(intervals + add_ints)
intervals = []
unvalidated_intervals = []
for i_start, i_end in unmerged_intervals:
    if len(unvalidated_intervals) > 0 and i_start + 1 <= unvalidated_intervals[-1][1]:
        unvalidated_intervals[-1] = (unvalidated_intervals[-1][0], max(unvalidated_intervals[-1][1], i_end))
        continue
    unvalidated_intervals.append((i_start, i_end))

for i_start, i_end in unvalidated_intervals:
    start = i_start
    for code_point in range(i_start, i_end + 1):
        face = load_glyph(code_point)
        if face is None:
            if start < code_point:
                intervals.append((start, code_point - 1))
            start = code_point + 1
    if start != i_end + 1:
        intervals.append((start, i_end))

for face in font_stack:
    face.set_char_size(size << 6, size << 6, 150, 150)

total_size = 0
all_glyphs = []

for i_start, i_end in intervals:
    for code_point in range(i_start, i_end + 1):
        face = load_glyph(code_point)
        bitmap = face.glyph.bitmap

        # Build out 4-bit greyscale bitmap
        pixels4g = []
        px = 0
        for i, v in enumerate(bitmap.buffer):
            y = i / bitmap.width
            x = i % bitmap.width
            if x % 2 == 0:
                px = (v >> 4)
            else:
                px = px | (v & 0xF0)
                pixels4g.append(px);
                px = 0
            # eol
            if x == bitmap.width - 1 and bitmap.width % 2 > 0:
                pixels4g.append(px)
                px = 0

        if is2Bit:
            # 0-3 white, 4-7 light grey, 8-11 dark grey, 12-15 black
            # Downsample to 2-bit bitmap
            pixels2b = []
            px = 0
            pitch = (bitmap.width // 2) + (bitmap.width % 2)
            for y in range(bitmap.rows):
                for x in range(bitmap.width):
                    px = px << 2
                    bm = pixels4g[y * pitch + (x // 2)]
                    bm = (bm >> ((x % 2) * 4)) & 0xF

                    if bm >= 12:
                        px += 3
                    elif bm >= 8:
                        px += 2
                    elif bm >= 4:
                        px += 1

                    if (y * bitmap.width + x) % 4 == 3:
                        pixels2b.append(px)
                        px = 0
            if (bitmap.width * bitmap.rows) % 4 != 0:
                px = px << (4 - (bitmap.width * bitmap.rows) % 4) * 2
                pixels2b.append(px)

            # for y in range(bitmap.rows):
            #     line = ''
            #     for x in range(bitmap.width):
            #         pixelPosition = y * bitmap.width + x
            #         byte = pixels2b[pixelPosition // 4]
            #         bit_index = (3 - (pixelPosition % 4)) * 2
            #         line += '#' if ((byte >> bit_index) & 3) > 0 else '.'
            #     print(line)
            # print('')
        else:
            # Downsample to 1-bit bitmap - treat any 2+ as black
            pixelsbw = []
            px = 0
            pitch = (bitmap.width // 2) + (bitmap.width % 2)
            for y in range(bitmap.rows):
                for x in range(bitmap.width):
                    px = px << 1
                    bm = pixels4g[y * pitch + (x // 2)]
                    px += 1 if ((x & 1) == 0 and bm & 0xE > 0) or ((x & 1) == 1 and bm & 0xE0 > 0) else 0

                    if (y * bitmap.width + x) % 8 == 7:
                        pixelsbw.append(px)
                        px = 0
            if (bitmap.width * bitmap.rows) % 8 != 0:
                px = px << (8 - (bitmap.width * bitmap.rows) % 8)
                pixelsbw.append(px)

            # for y in range(bitmap.rows):
            #     line = ''
            #     for x in range(bitmap.width):
            #         pixelPosition = y * bitmap.width + x
            #         byte = pixelsbw[pixelPosition // 8]
            #         bit_index = 7 - (pixelPosition % 8)
            #         line += '#' if (byte >> bit_index) & 1 else '.'
            #     print(line)
            # print('')

        pixels = pixels2b if is2Bit else pixelsbw

        # Build output data
        packed = bytes(pixels)
        glyph = GlyphProps(
            width = bitmap.width,
            height = bitmap.rows,
            advance_x = norm_floor(face.glyph.advance.x),
            left = face.glyph.bitmap_left,
            top = face.glyph.bitmap_top,
            data_length = len(packed),
            data_offset = total_size,
            code_point = code_point,
        )
        total_size += len(packed)
        all_glyphs.append((glyph, packed))

# pipe seems to be a good heuristic for the "real" descender
face = load_glyph(ord('|'))

glyph_data = []
glyph_props = []
for index, glyph in enumerate(all_glyphs):
    print(f"Glyph {index}: code point {glyph[0].code_point} ({hex(glyph[0].code_point)}), size {glyph[0].width}x{glyph[0].height}, advance {glyph[0].advance_x}, left {glyph[0].left}, top {glyph[0].top}, data length {glyph[0].data_length}, data offset {glyph[0].data_offset}", file=sys.stderr)
    props, packed = glyph
    glyph_data.extend([b for b in packed])
    glyph_props.append(props)

# Build FlatBuffers binary
builder = flatbuffers.Builder(4096)



# # Create bitmap vector
# bitmap_vector_start = builder.StartVector(1, len(glyph_data), 1)
# for byte_val in reversed(glyph_data):
#     
# bitmap_offset = builder.EndVector()

EpdFontData.StartBitmapVector(builder, len(glyph_data))
for byte_val in bytes(reversed(glyph_data)):
    builder.PrependUint8(byte_val)
bitmap_offset = builder.EndVector()

# Create glyph structs vector
glyph_struct_offsets = []
for g in reversed(glyph_props):
    EpdGlyph.Start(builder)
    EpdGlyph.AddWidth(builder, g.width)
    EpdGlyph.AddHeight(builder, g.height)
    EpdGlyph.AddAdvanceX(builder, g.advance_x)
    EpdGlyph.AddLeft(builder, g.left)
    EpdGlyph.AddTop(builder, g.top)
    EpdGlyph.AddDataLength(builder, g.data_length)
    EpdGlyph.AddDataOffset(builder, g.data_offset)
    glyph_struct_offsets.append(EpdGlyph.End(builder))

# interval_offsets = []
# offset = 0
# print(f"Intervals: {len(intervals)}")
# for i_start, i_end in intervals:
#     print(f"{i_start} {i_end} {offset}")
#     interval = EpdUnicodeInterval.CreateEpdUnicodeInterval(builder, i_start, i_end, offset)
#     interval_offsets.append(interval)
#     offset += i_end - i_start + 1
#     break
# Create vector of glyph structs



# # Create interval structs vector
# interval_struct_offsets = []
# offset = 0
# for i_start, i_end in intervals:
#     builder.StartObject(3)
#     EpdUnicodeInterval.CreateEpdUnicodeInterval(builder, i_start, i_end, offset)
#     offset += i_end - i_start + 1
#     interval_struct_offsets.append(builder.EndObject())





EpdFontData.StartGlyphVector(builder, len(glyph_struct_offsets))
for offset in glyph_struct_offsets:
    builder.PrependUOffsetTRelative(offset)
glyph_offset = builder.EndVector()

EpdFontData.StartIntervalsVector(builder, len(intervals))

offset = 0
intervals_with_offsets = []
for interval in intervals:
    intervals_with_offsets.append((interval[0], interval[1], offset))
    offset += interval[1] - interval[0] + 1

for i_start, i_end, offset in reversed(intervals_with_offsets):
    EpdUnicodeInterval.CreateEpdUnicodeInterval(builder, i_start, i_end, offset)
intervals_offset = builder.EndVector()


EpdFontData.Start(builder)
EpdFontData.AddBitmap(builder, bitmap_offset)
EpdFontData.AddGlyph(builder, glyph_offset)
EpdFontData.AddIntervals(builder, intervals_offset)
EpdFontData.AddAdvanceY(builder, norm_ceil(face.size.height))
EpdFontData.AddAscender(builder, norm_ceil(face.size.ascender))
EpdFontData.AddDescender(builder, norm_floor(face.size.descender))
EpdFontData.AddIs2bit(builder, is2Bit)  # Uncomment if EpdFontData schema includes is2Bit field   

font_root = EpdFontData.End(builder)
builder.Finish(font_root)

buf = bytes(builder.Output())

# Write to file
output_file = args.output if args.output else f"{font_name}.epd_fb"
with open(output_file, 'wb') as f:
    f.write(buf)

print(f"Font file generated: {output_file}", file=sys.stderr)
print(f"  - glyphs: {len(glyph_props)}", file=sys.stderr)
print(f"  - intervals: {len(intervals)}", file=sys.stderr)
print(f"  - bitmap size: {len(glyph_data)} bytes", file=sys.stderr)
print(f"  - total size: {len(buf)} bytes", file=sys.stderr)
print(f"  - advance Y: {norm_ceil(face.size.height)}", file=sys.stderr)
print(f"  - ascender: {norm_ceil(face.size.ascender)}", file=sys.stderr)
print(f"  - descender: {norm_floor(face.size.descender)}", file=sys.stderr)
print(f"  - 2-bit mode: {is2Bit}", file=sys.stderr)


read_font = EpdFontData.EpdFontData.GetRootAsEpdFontData(buf, 0)
print(f"Read back font data:", file=sys.stderr)
print(f"  - advance Y: {read_font.AdvanceY()}", file=sys.stderr)
print(f"  - ascender: {read_font.Ascender()}", file=sys.stderr)
print(f"  - descender: {read_font.Descender()}", file=sys.stderr)
print(f"  - is2bit: {read_font.Is2bit()}", file=sys.stderr)
print(f"  - intervals length: {read_font.IntervalsLength()}", file=sys.stderr)
for i in range(read_font.GlyphLength()):
    glyph = read_font.Glyph(i)
    print(f"  - Glyph {i}: size {glyph.Width()}x{glyph.Height()}, advance {glyph.AdvanceX()}, left {glyph.Left()}, top {glyph.Top()}, data length {glyph.DataLength()}, data offset {glyph.DataOffset()}", file=sys.stderr)
for i in range(read_font.IntervalsLength()):
    interval = read_font.Intervals(i)
    print(f"  - Interval {i}: first {interval.First()} ({hex(interval.First())}), last {interval.Last()} ({hex(interval.Last())}), offset {interval.Offset()}", file=sys.stderr)