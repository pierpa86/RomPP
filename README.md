# RomPP

RomPP is a Tkinter-based ROM utility for inspecting, comparing, preparing, and converting binary ROM files. It uses multiple manual slots with a chip-style graphical memory view, making it quick to compare byte patterns and run common ROM preparation actions.

## Features

- 4, 8, or 12 ROM slots.
- Chip-style graphical memory visualization for each loaded file.
- Automatic file size, CRC32, and SHA1 calculation.
- Double-click on CRC32 or SHA1 to copy the value to the Windows clipboard.
- Small disappearing popup confirms when a checksum is copied.
- Drag and drop a file onto a graphical ROM view to load it into that slot.
- Right-click menu on each ROM view for slot-specific actions.
- Hex viewer for loaded ROM data.
- Help window with descriptions of all tools.

## Tools

- Split a ROM into equal-sized parts.
- Split interleaved data into alternating byte streams.
- Merge selected slots into one file.
- Merge slots 1 and 2 into an interleaved output file.
- Pad a ROM to a selected target size.
- Double or repeat ROM data by a chosen multiplier.
- Split Neo Geo C ROM data into chip-sized parts.
- Split Neo Geo V ROM data into chip-sized parts.
- NeoTool folder analyzer for preparing Neo Geo component files.

## .neoConv

RomPP includes an integrated `.neoConv` window based on `neoconv` by d4NY0H:

https://github.com/d4NY0H/neoconv

`.neoConv` supports:

- Extract TerraOnion `.neo` containers to MAME or Darksoft ROM files.
- Pack MAME ZIP files or folders into `.neo` containers.
- Verify roundtrip conversions.
- Inspect `.neo` metadata and ROM region sizes.

## Build Standalone EXE

```bash
python -m PyInstaller --noconfirm --clean main.spec
```

The standalone executable is generated at:

```text
dist/main.exe
```

## Visualization Notes

- `00` bytes are shown in red.
- `FF` bytes are shown in blue.
- Other bytes are shown in green.
- Empty cells are shown in dark gray.
- `B/P` means bytes per pixel block, computed automatically to fill a 64x32 grid.
