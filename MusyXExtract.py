#
# MusyX sample extraction tool   by Nisto
# Last revision: 2017, May 25
#

# Changelog
#
# 2017, May 27
# - Minor fixes and enhancements to the code from bobjrsenior's pull request (thanks)
# - Improved performance (hopefully?) by using pre-compiled structs and less disk I/O
# - Removed pointless Python 2 backward compatibility stuff (xrange fallback)
# - Refactored and cleaned up some code
#
# 2017, May 20
# - Fixed samples_to_bytes by rounding up to the next 8 byte alignment (Checked against Super Monkey Ball 2 audio files)
# - Added support for packing dsp files back into .sdir and .samp files (Checked against Super Monkey Ball 2 audio files)
#
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
import re


DSP_ID_REGEX = re.compile(r"^\d{5} \((0x[\dA-F]{4})\).dsp$", re.IGNORECASE)


u16be_t = struct.Struct(">H")
u32be_t = struct.Struct(">I")


def put_binary(buf, off, data):
    buf[off:off+len(data)] = data

def put_u16_be(buf, off, data):
    buf[off:off+2] = u16be_t.pack(data)

def put_u32_be(buf, off, data):
    buf[off:off+4] = u32be_t.pack(data)


def get_binary(buf, off, size):
    return buf[off:off+size]

def get_u16_be(buf, off):
    return u16be_t.unpack(buf[off:off+2])[0]

def get_u32_be(buf, off):
    return u32be_t.unpack(buf[off:off+4])[0]


def samples_to_nibbles(samples):
    whole_frames = samples // 14
    remainder = samples % 14
    if remainder > 0:
        return (whole_frames * 16) + remainder + 2
    else:
        return whole_frames * 16

def nibbles_to_samples(nibbles):
    whole_frames = nibbles // 16
    remainder = nibbles % 16
    remainder -= 2

    if remainder > 0:
        return (whole_frames * 14) + remainder
    else:
        return whole_frames * 14

def samples_to_bytes(samples):
    nibbles = samples_to_nibbles(samples)
    raw_bytes = (nibbles // 2) + (nibbles % 2)
    if raw_bytes % 8 != 0:
        raw_bytes += 8 - (raw_bytes % 8)
    return raw_bytes


def read_dsp_header(dsp, meta):
    header = dsp.read(96)

    meta["samples"]    = get_u32_be(header, 0x00)      # number of raw samples
    meta["nibbles"]    = get_u32_be(header, 0x04)      # number of nibbles
    meta["rate"]       = get_u32_be(header, 0x08)      # sample rate
    meta["loop_flag"]  = get_u16_be(header, 0x0C)      # loop flag
    meta["loop_start"] = get_u32_be(header, 0x10)      # loop start (in nibbles)
    meta["loop_end"]   = get_u32_be(header, 0x14)      # loop end (in nibbles)
    meta["coeffs"]     = get_binary(header, 0x1C, 32)  # coefficienta
    meta["ps"]         = get_binary(header, 0x3E, 2)   # predictor/scale
    meta["lps"]        = get_binary(header, 0x44, 2)   # predictor/scale for loop context
    meta["lyn1"]       = get_binary(header, 0x46, 2)   # sample history (n-1) for loop context
    meta["lyn2"]       = get_binary(header, 0x48, 2)   # sample history (n-2) for loop context


def write_dsp_header(dsp, meta):
    if meta["loop_length"] > 1 and meta["loop_start"] + meta["loop_length"] <= meta["samples"]:
        loop_flag = 1
        loop_start = samples_to_nibbles(meta["loop_start"])
        loop_end = samples_to_nibbles(meta["loop_start"] + meta["loop_length"]) - 1
    else:
        loop_flag = 0
        loop_start = 2 # As per the DSPADPCM docs: "If not looping, specify 2, which is the top sample."
        loop_end = 0

    header = bytearray(96)

    nibbles = samples_to_nibbles(meta["samples"]) & 0xFFFFFFFF

    put_u32_be(header, 0x00, meta["samples"])   # raw samples
    put_u32_be(header, 0x04, nibbles)           # nibbles
    put_u32_be(header, 0x08, meta["rate"])      # sample rate
    put_u16_be(header, 0x0C, loop_flag)         # loop flag
    put_u16_be(header, 0x0E, 0)                 # format (always zero - ADPCM)
    put_u32_be(header, 0x10, loop_start)        # loop start address (in nibbles)
    put_u32_be(header, 0x14, loop_end)          # loop end address (in nibbles)
    put_u32_be(header, 0x18, 2)                 # initial offset value (in nibbles)
    put_binary(header, 0x1C, meta["coeffs"])    # coefficients
    put_u16_be(header, 0x3C, 0)                 # gain (always zero for ADPCM)
    put_u16_be(header, 0x3E, meta["ps"][0])     # predictor/scale
    put_u16_be(header, 0x40, 0)                 # sample history (not specified?)
    put_u16_be(header, 0x42, 0)                 # sample history (not specified?)
    put_u16_be(header, 0x44, meta["lps"][0])    # predictor/scale for loop context
    put_binary(header, 0x46, meta["lyn1"])      # sample history (n-1) for loop context
    put_binary(header, 0x48, meta["lyn2"])      # sample history (n-2) for loop context

    dsp.write(header)


def read_sdir(sdir, meta):
    # references:
    # http://www.metroid2002.com/retromodding/wiki/AGSC_(File_Format)
    # https://github.com/AxioDL/amuse

    sdirbuf = sdir.read()

    i = 0

    tbl1_offset = 0

    while sdirbuf[tbl1_offset:tbl1_offset+4] != b"\xFF\xFF\xFF\xFF":

        meta[i] = {}

        record = get_binary(sdirbuf, tbl1_offset, 0x20)
        meta[i]["id"]          = get_u16_be(record, 0x00)
        meta[i]["offset"]      = get_u32_be(record, 0x04)
        meta[i]["rate"]        = get_u16_be(record, 0x0E)
        meta[i]["samples"]     = get_u32_be(record, 0x10)
        meta[i]["loop_start"]  = get_u32_be(record, 0x14)
        meta[i]["loop_length"] = get_u32_be(record, 0x18)

        tbl1_offset += 0x20

        tbl2_offset = get_u32_be(record, 0x1C)

        record = get_binary(sdirbuf, tbl2_offset, 0x28)
        meta[i]["ps"]     = record[0x02:0x03]
        meta[i]["lps"]    = record[0x03:0x04]
        meta[i]["lyn2"]   = record[0x04:0x06]
        meta[i]["lyn1"]   = record[0x06:0x08]
        meta[i]["coeffs"] = record[0x08:0x28]

        i += 1

    del sdirbuf


def write_sdir(sdir, meta):
    sdirbuf = bytearray(72 * len(meta) + 4)

    tbl1_offset = 0
    tbl2_offset = 32 * len(meta) + 4

    for i in meta:
        loop_start = nibbles_to_samples(meta[i]["loop_start"])
        loop_end = nibbles_to_samples(meta[i]["loop_end"])
        loop_length = loop_end - loop_start

        if loop_length != 0:
            loop_length += 1

        put_u16_be(sdirbuf, tbl1_offset+0x00, meta[i]["id"])
        put_u32_be(sdirbuf, tbl1_offset+0x04, meta[i]["offset"])
        put_binary(sdirbuf, tbl1_offset+0x0C, b"\x3C")
        put_u16_be(sdirbuf, tbl1_offset+0x0E, meta[i]["rate"])
        put_u32_be(sdirbuf, tbl1_offset+0x10, meta[i]["samples"])
        put_u32_be(sdirbuf, tbl1_offset+0x14, loop_start)
        put_u32_be(sdirbuf, tbl1_offset+0x18, loop_length)
        put_u32_be(sdirbuf, tbl1_offset+0x1C, tbl2_offset)

        put_binary(sdirbuf, tbl2_offset+0x00, b"\x00\x08")
        put_binary(sdirbuf, tbl2_offset+0x02, meta[i]["ps"][1:2])
        put_binary(sdirbuf, tbl2_offset+0x03, meta[i]["lps"][1:2])
        put_binary(sdirbuf, tbl2_offset+0x04, meta[i]["lyn2"])
        put_binary(sdirbuf, tbl2_offset+0x06, meta[i]["lyn1"])
        put_binary(sdirbuf, tbl2_offset+0x08, meta[i]["coeffs"])

        tbl1_offset += 0x20

        tbl2_offset += 0x28

    put_binary(sdirbuf, tbl1_offset, b"\xFF\xFF\xFF\xFF")

    sdir.write(sdirbuf)

    del sdirbuf


def extract_data(src, dst, todo_size):
    while todo_size > 0:
        read_size = min(4096, todo_size)
        dst.write( src.read(read_size) )
        todo_size -= read_size


def extract_samples(sound_dir, out_dir):
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

        meta = {}

        with open(group["sdir"], "rb") as sdir:
            read_sdir(sdir, meta)

        with open(group["samp"], "rb") as samp:

            dsp_dir = os.path.join(out_dir, groupname)

            if os.path.isdir(dsp_dir) is not True:
                os.mkdir(dsp_dir)

            for i in meta:

                samp.seek(meta[i]["offset"])

                dsp_path = os.path.join(dsp_dir, "%05d (0x%04X).dsp" % (i, meta[i]["id"]))

                with open(dsp_path, "wb") as dsp:
                    write_dsp_header(dsp, meta[i])
                    sample_size = samples_to_bytes(meta[i]["samples"])
                    extract_data(samp, dsp, sample_size)

        print("Done")

    print()


def pack_samples(sound_dir, out_dir):
    project_name = os.path.basename(sound_dir)

    samp_out_name = os.path.join(out_dir, "%s.samp" % project_name)
    sdir_out_name = os.path.join(out_dir, "%s.sdir" % project_name)

    meta = {}
    i = 0

    with open(samp_out_name, "wb") as samp:

        for filename in os.listdir(sound_dir):

            filepath = os.path.join(sound_dir, filename)

            if os.path.isfile(filepath) is not True:
                continue

            basename = os.path.basename(filename)

            ext = os.path.splitext(basename)[1]

            if ext.lower() != ".dsp":
                continue

            regex_match = DSP_ID_REGEX.match(basename)

            if regex_match is None:
                print("No Match for: %s" % basename)
                continue

            meta[i] = {
                "id": int(regex_match.group(1), 16),
                "offset": samp.tell()
            }

            cur_position = samp.tell()
            if cur_position % 32 != 0:
                remainder = 32 - (cur_position % 32)
                padding = struct.pack("%dx" % remainder)
                samp.write(padding)

            with open(filepath, "rb") as dsp:
                read_dsp_header(dsp, meta[i])
                sample_size = samples_to_bytes(meta[i]["samples"])
                extract_data(dsp, samp, sample_size)

            print("Done reading : %s" % filename)

            i += 1

    with open(sdir_out_name, "wb") as sdir:
        write_sdir(sdir, meta)

    print("Done")

    print()


def main(argc=len(sys.argv), argv=sys.argv):
    if argc < 2:
        print("Usage: %s [-(E|P)] <sound_dir> [[-(E|P)] <sound_dir> ...]" % argv[0])
        print("By default '-E' (extract) is set.")
        print("Changing modes takes effect for every parameter after it or until another mode is reached")
        return 1

    func_todo = extract_samples
    out_dirname = "samples"

    for arg in argv[1:]:

        if arg == "-e" or arg == "-E":
            func_todo = extract_samples
            out_dirname = "samples"
            continue
        elif arg == "-p" or arg == "-P":
            func_todo = pack_samples
            out_dirname = "sfxProject"
            continue

        sound_dir = os.path.realpath(arg)

        if os.path.isdir(sound_dir) is not True:
            print("ERROR: Invalid directory path: %s" % arg)
            continue

        out_dir = os.path.join(sound_dir, out_dirname)

        if os.path.isdir(out_dir) is not True:
            os.mkdir(out_dir)

        print("Directory: %s" % sound_dir)

        func_todo(sound_dir, out_dir)

    print("No more files to process.")

    return 0

if __name__ == "__main__":
    main()
