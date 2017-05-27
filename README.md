# musyx-extract
Sample extractor for GameCube MusyX files

## Prerequisites
* Python 3

## Usage
Thanks to an update from *bobjrsenior* on May 21, 2017, the script is also able to pack .dsp files back to .sdir/.samp MusyX files. For this, you must specify `-P` (pack) before the directory path(s).

By default, `-E` (extract) is implied and does not need to be explicitly specified, which allows you to simply drag-and-drop folders if just extracting.

### Extracting (.sdir + .samp -> .dsp)
Supply one or more directories containing .sdi(r) files and their respective .sam(p) files to the script.

### Packing (.dsp -> .sdir + .samp)
Supply one or more directories containing .dsp files with the naming format `ddddd (0xXXXX).dsp` where `ddddd` is a decimal index number and `XXXX` is a hexadecimal SFX ID.
