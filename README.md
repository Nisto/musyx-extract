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

## Support ❤️

As of June 2024, my monthly salary has been cut by 50%. This has had a significant impact on my freedom and ability to spend as much time working on my projects, especially due to electricity bills. I don't like asking for favors or owing people anything, but if you do appreciate this work and happen to have some funds to spare, I would greatly appreciate any and all donations. All of your contributions goes towards essential everyday expenses. Every little bit helps! Thank you ❤️

**PayPal:** https://paypal.me/nisto7777  
**Buy Me a Coffee:** https://buymeacoffee.com/nisto  
**Bitcoin:** 18LiBhQzHiwFmTaf2z3zwpLG7ALg7TtYkg
