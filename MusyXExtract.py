#
# MusyX sample extraction tool   by Nisto
# Last revision: 2015, July 14
#
# Developed under Python 3 and may or may not work with other Python versions
#

# Changelog

# 2015, July 14
# - Use 0xFFFFFFFF block terminator to determine end of the first sdir meta table instead of determining amount of entries by filesize (Beyblade S.T.B. support)
# - Get offset for second sdir meta table from the first table and seek instead of reading in order (Beyblade S.T.B. support)
# - Extract files to "index (id).dsp" instead of just "id.dsp" (sample IDs might crash)
#
# 2015, May 28
# - Fixed loop end offset calculation (subtract 1 from nibbles rather than samples, which appears to be more accurate, comparing with Nintendo's DSPADPCM encoder)
# - Changed logic of loop and sample count validation
# - Removed exception handling (for now?) since it isn't really helpful in determining where exactly (file) something went wrong with the current code structure
# - Other minor changes
#
# 2015, May 24:
# - Use IDs from Sample Directory files for output names instead of per-directory indexes
# - Case-insensitive detection of file extensions
# - Made sample extraction routine into a separate function
# - Improved (?) handling of loops
# - Code cleanup

# TODO
# - Option for omitting loop values in extracted samples?
# - Option for padding very short samples? (short samples may cause players to crash)

import os
import sys
import struct

if sys.version_info[0] > 2:
    xrange = range

def samples_to_nibbles(samples):
    whole_frames = samples // 14
    remainder = samples % 14
    if remainder > 0:
        return (whole_frames * 16) + remainder + 2
    else:
        return whole_frames * 16

def samples_to_bytes(samples):
    nibbles = samples_to_nibbles(samples)
    return (nibbles // 2) + (nibbles % 2)

def dsp_header(meta):
    if meta["samples"] > 0xDFFFFFFF: # 0xDFFFFFFF samples = 0xFFFFFFFF nibbles
        return ""

    nibbles = samples_to_nibbles(meta["samples"])

    if meta["loop_length"] > 1 and meta["loop_start"] + meta["loop_length"] <= meta["samples"]:
        loop_flag = 1
        loop_start = samples_to_nibbles(meta["loop_start"])
        loop_end = samples_to_nibbles(meta["loop_start"] + meta["loop_length"]) - 1
    else:
        loop_flag = 0
        loop_start = 2 # As per the DSPADPCM docs: "If not looping, specify 2, which is the top sample."
        loop_end = 0

    header  = struct.pack(">I", meta["samples"]) # 0x00 raw samples
    header += struct.pack(">I", nibbles)         # 0x04 nibbles
    header += struct.pack(">I", meta["rate"])    # 0x08 sample rate
    header += struct.pack(">H", loop_flag)       # 0x0C loop flag
    header += struct.pack(">H", 0)               # 0x0E format (always zero - ADPCM)
    header += struct.pack(">I", loop_start)      # 0x10 loop start address (in nibbles)
    header += struct.pack(">I", loop_end)        # 0x14 loop end address (in nibbles)
    header += struct.pack(">I", 2)               # 0x18 initial offset value (in nibbles)
    header += meta["coeffs"]                     # 0x1C coefficients
    header += struct.pack(">H", 0)               # 0x3C gain (always zero for ADPCM)
    header += b"\0" + meta["ps"]                 # 0x3E predictor/scale
    header += struct.pack(">H", 0)               # 0x40 sample history (not specified?)
    header += struct.pack(">H", 0)               # 0x42 sample history (not specified?)
    header += b"\0" + meta["lps"]                # 0x44 predictor/scale for loop context
    header += meta["lyn1"]                       # 0x46 sample history (n-1) for loop context
    header += meta["lyn2"]                       # 0x48 sample history (n-2) for loop context
    header += struct.pack("22x")                 # 0x4A pad (reserved)

    return header

def read_u32_be(f):
    data = f.read(4)
    return struct.unpack(">I", data)[0]

def read_u16_be(f):
    data = f.read(2)
    return struct.unpack(">H", data)[0]

def extract_data(src, dst, size):
    read_max = 4096
    left = size
    while left:
        if read_max > left:
            read_max = left

        data = src.read(read_max)

        if data == b"":
            break # EOF

        dst.write(data)

        left -= read_max

def extract_samples(sound_dir, out_dir):
    print("Directory: %s" % sound_dir)

    musyxfiles = {}

    for filename in os.listdir(sound_dir):

        filepath = os.path.join(sound_dir, filename)

        if os.path.isfile(filepath) is not True:
            continue

        basename = os.path.basename(filename)

        name, ext = os.path.splitext(basename)

        ext = ext.lower()

        if ext == ".sdi" or ext == ".sdir":
            musyxtype = "sdir"
        elif ext == ".sam" or ext == ".samp":
            musyxtype = "samp"
        else:
            continue

        if name not in musyxfiles:
            musyxfiles[name] = {}

        musyxfiles[name][musyxtype] = filepath

    for groupname in musyxfiles:

        group = musyxfiles[groupname]

        if "sdir" not in group:
            print("ERROR: Could not find Sample Directory (.sdir) file for \"%s\"" % groupname)
            continue

        if "samp" not in group:
            print("ERROR: Could not find Sample (.samp) file for \"%s\"" % groupname)
            continue

        samp_name = os.path.basename(group["samp"])

        print("Extracting samples from %s... " % samp_name, end="")

        # sdir_size = os.path.getsize(group["sdir"])

        # 4 = block terminator (0xFFFFFFFF)
        # 72 = table 1 entry size (32) + table 2 entry size (40)
        # num_samples = (sdir_size - 4) // 72

        # if (sdir_size - 4) % num_samples:
        #     print("ERROR: Could not determine number of samples")
        #     continue

        meta = {}

        with open(group["sdir"], "rb") as sdir:

            temp = read_u32_be(sdir)
            i = 0;

            # for i in xrange(num_samples):
            while temp != 0xFFFFFFFF:

                meta[i] = {}

                # meta[i]["id"]            = read_u16_be(sdir)         # sample ID
                # sdir.seek(2, os.SEEK_CUR)                            # reserved?
                meta[i]["id"]              = (temp & 0xFFFF0000) >> 16 # sample ID
                meta[i]["offset"]          = read_u32_be(sdir)         # sample's offset in .samp file
                sdir.seek(6, os.SEEK_CUR)                              # reserved? (4) + base note (1) + reserved? (1)
                meta[i]["rate"]            = read_u16_be(sdir)         # sample rate
                meta[i]["samples"]         = read_u32_be(sdir)         # amount of raw samples
                meta[i]["loop_start"]      = read_u32_be(sdir)         # start address of loop (in raw samples)
                meta[i]["loop_length"]     = read_u32_be(sdir)         # length of loop (in raw samples)
                # sdir.seek(4, os.SEEK_CUR)                            # offset of decoder values (coefficients, etc.)
                meta[i]["meta2_offset"]    = read_u32_be(sdir)         # offset of decoder values (coefficients, etc.)

                temp = read_u32_be(sdir)
                i += 1

            # sdir.seek(4, os.SEEK_CUR) # seek past block terminator (0xFFFFFFFF)

            # for i in xrange(num_samples):
            for i in meta:

                sdir.seek(meta[i]["meta2_offset"])

                sdir.seek(2, os.SEEK_CUR)         # ?
                meta[i]["ps"]     = sdir.read(1)  # predictor/scale
                meta[i]["lps"]    = sdir.read(1)  # loop predictor/scale
                meta[i]["lyn2"]   = sdir.read(2)  # loop sample history n-2
                meta[i]["lyn1"]   = sdir.read(2)  # loop sample history n-1
                meta[i]["coeffs"] = sdir.read(32) # coefficients

        dsp_dir = os.path.join(out_dir, groupname)

        if os.path.isdir(dsp_dir) is not True:
            os.mkdir(dsp_dir)

        with open(group["samp"], "rb") as samp:

            # for i in xrange(num_samples):
            for i in meta:

                samp.seek(meta[i]["offset"])

                # dsp_path = os.path.join(dsp_dir, "%04d.dsp" % i)
                dsp_path = os.path.join(dsp_dir, "%05d (0x%04X).dsp" % (i, meta[i]["id"]))

                sample_size = samples_to_bytes(meta[i]["samples"])

                with open(dsp_path, "wb") as dsp:

                    dsp.write( dsp_header(meta[i]) )

                    extract_data(samp, dsp, sample_size)

        print("Done")

    print()


def pack_samples(sound_dir, out_dir):
    print("Directory: %s" % sound_dir)

    for filename in os.listdir(sound_dir):

        filepath = os.path.join(sound_dir, filename)

        if os.path.isfile(filepath) is not True:
            continue

        basename = os.path.basename(filename)

        name, ext = os.path.splitext(basename)

        ext = ext.lower()

        if ext != ".dsp" and ext != ".DSP":
            continue

        print("Done")

    print()


def main(argc=len(sys.argv), argv=sys.argv):
    if argc < 2:
        print("Usage: %s <sound_dir> [<sound_dir> ...]" % argv[0])
        return 1

    EXTRACT = 0
    PACK    = 1
    mode = EXTRACT

    for i in xrange(1, argc):

        # Set mode
        if argv[i] == "-e" or argv[i] == "-E":
            mode = EXTRACT
            continue
        elif argv[i] == "-p" or argv[i] == "-P":
            mode = PACK
            continue

        sound_dir = os.path.realpath(argv[i])

        if os.path.isdir(sound_dir) is not True:
            print("ERROR: Invalid directory path (arg %d)" % i)
            continue

        if mode == EXTRACT:
            out_dir = os.path.join(sound_dir, "samples")

            if os.path.isdir(out_dir) is not True:
                os.mkdir(out_dir)
            extract_samples(sound_dir, out_dir)
        else:
            out_dir = os.path.join(sound_dir, "sfxProject")

            if os.path.isdir(out_dir) is not True:
                os.mkdir(out_dir)
                pack_samples(sound_dir, out_dir)

    print("No more files to process.")

    return 0

if __name__ == "__main__":
    main()
