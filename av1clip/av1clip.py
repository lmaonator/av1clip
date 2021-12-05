#!/usr/bin/env python3
import argparse
import subprocess
import json
import os
import hashlib
from datetime import datetime, timezone

# program paths
MPV = "mpv"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
SVTAV1 = "SvtAv1EncApp"

# default encode settings
AUDIO_BITRATE = "256k"
SVTAV1_CRF = "32"
SVTAV1_PRESET = "3"
SVTAV1_TILE_ROWS = "2"
SVTAV1_TILE_COLUMNS = "2"


parser = argparse.ArgumentParser()
parser.add_argument("input_file", help="input video file")
parser.add_argument("-s", "--start", help="start time")
parser.add_argument("-e", "--end", help="end time")

group = parser.add_argument_group("track selection",
                                  "set to 'no' to disable, default 'auto'")
group.add_argument("-vid", default="auto", help="video track id")
group.add_argument("-aid", default="auto", help="audio track id")
group.add_argument("-sid", default="auto", help="subtitle track id")

group = parser.add_argument_group("filters")
group.add_argument("-sw", "--width", help="scale to specified width")
group.add_argument("-sh", "--height", help="scale to specified height")

group = parser.add_argument_group("encode settings")


def check_opus_bitrate(value):
    if value.endswith("k"):
        value = value[:-1] + "000"
    ivalue = int(value)
    if ivalue < 500 or ivalue > 512000:  # libopus min/max
        raise argparse.ArgumentTypeError(
            f"libopus: The bit rate {ivalue} bps is unsupported. Please choose"
            " a value between 500 and 512000.")
    return ivalue


group.add_argument("-ab", "--audio-bitrate", default=AUDIO_BITRATE, type=check_opus_bitrate,
                   help=f"Opus audio bitrate, default {AUDIO_BITRATE}")
group.add_argument("-crf", "--crf", default=SVTAV1_CRF,
                   help=f"SVT-AV1 crf, default {SVTAV1_CRF}")
group.add_argument("--preset", default=SVTAV1_PRESET,
                   help=f"SVT-AV1 preset, default {SVTAV1_PRESET}")
group.add_argument("--tile-rows", default=SVTAV1_TILE_ROWS,
                   help=f"SVT-AV1 log2 of tile rows, default {SVTAV1_TILE_ROWS}")
group.add_argument("--tile-columns", default=SVTAV1_TILE_COLUMNS,
                   help=f"SVT-AV1 log2 of tile columns, default {SVTAV1_TILE_COLUMNS}")

args = parser.parse_args()

if not os.path.isfile(args.input_file):
    print(f"'{args.input_file}' is not a file.")
    exit(2)


def get_output(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE)
    return result.stdout.decode("utf-8")


MPV_VERSION = get_output([MPV, "--version"]).split(maxsplit=2)[1]
FFMPEG_VERSION = get_output([FFMPEG, "-version"]).split(maxsplit=3)[2]
SVTAV1_VERSION = get_output([SVTAV1, "--version"]).split(maxsplit=2)[1]


argstr_md5 = hashlib.md5((f"{args.input_file}.v{args.vid}a{args.aid}s{args.sid}w{args.width}h{args.height}"
                          f"ab{args.audio_bitrate}start{args.start}end{args.end}").encode('utf-8')).hexdigest()
temp_file_base = f"av1clip-{argstr_md5}-"

dest_dir = os.path.dirname(args.input_file)
temp_file_processing = os.path.join(dest_dir, temp_file_base + "processing.mkv")
temp_file = os.path.join(dest_dir, temp_file_base + "temp.mkv")

dest_file = os.path.splitext(args.input_file)[0] + " AV1"
source_range = ""
if args.start:
    source_range = args.start.replace(":", ".")
if args.end:
    if not args.start:
        source_range = "0.0"
    source_range += "-" + args.end.replace(":", ".")
if source_range:
    dest_file += " " + source_range
else:
    source_range = "complete"
dest_file += ".webm"

# skip creating temp_file if it already exists
if not os.path.exists(temp_file):
    print("Creating scaled clip with burned subtitles and opus audio..")
    mpv_cmd = [
        MPV,
        # base arguments
        "--no-config", "--loop=no", "--hr-seek=yes",
        "--hr-seek-demuxer-offset=0", "--sub-auto=exact",
        "--sub-visibility=yes", "--sub-fix-timing=no",
        args.input_file, "--of=matroska", f"--o={temp_file_processing}",
        # track selection
        f"--vid={args.vid}", f"--aid={args.aid}", f"--sid={args.sid}",
        # encode settings for temp file, lossless x264, opus audio
        "--ovc=libx264", "--ovcopts-add=preset=ultrafast",
        "--ovcopts-add=crf=0",
        "--oac=libopus", f"--oacopts-add=b={args.audio_bitrate}",
    ]

    if args.start:
        mpv_cmd.append(f"--start={args.start}")
    if args.end:
        mpv_cmd.append(f"--end={args.end}")

    # scale filter
    if args.width or args.height:
        w = args.width if args.width else "-2"
        h = args.height if args.height else "-2"
        mpv_cmd.append(f"--vf=lavfi-scale=w={w}:h={h}:flags=lanczos:force_original_aspect_ratio=decrease")

    result = subprocess.run(mpv_cmd)
    if result.returncode != 0:
        print("Error creating temp file with mpv")
        exit(1)
    os.rename(temp_file_processing, temp_file)

print("Getting video parameters..")
# ffprobe to get video parameters for SVT-AV1
data = json.loads(get_output([
    FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", temp_file,
]))
video = next(s for s in data["streams"] if s["codec_type"] == "video")
fps_num = video["r_frame_rate"].split("/")[0]
fps_denom = video["r_frame_rate"].split("/")[1]

# ffmpeg temp_file pipe to SVT-AV1
ffmpeg_yuvpipe_cmd = [
    FFMPEG, "-hide_banner", "-v", "error", "-i", temp_file, "-map", "0:v:0", "-strict", "-1",
    "-f", "yuv4mpegpipe", "-",
]
# Encode from ffmpeg temp_file pipe and pipe to ffmpeg for muxing
svtav1_cmd = [
    SVTAV1,
    "--preset", args.preset,
    "--tile-rows", args.tile_rows, "--tile-columns", args.tile_columns,
    "--crf", args.crf,
    "--fps-num", fps_num, "--fps-denom", fps_denom,
    "--input-depth", video["bits_per_raw_sample"],
    "-w", str(video["width"]), "-h", str(video["height"]),
    "-i", "stdin", "-b", "stdout",
]
# mux audio from temp_file with SVT-AV1 encode
ffmpeg_mux_cmd = [
    FFMPEG, "-hide_banner", "-v", "error", "-y", "-i", "-", "-i", temp_file,
    "-map", "0:v:0", "-c:v", "copy", "-map", "1:a:0", "-c:a", "copy",
    "-map_chapters", "-1",
    "-metadata", f"TITLE={os.path.basename(args.input_file)} [{source_range}]",
    "-metadata", "creation_time=" + datetime.now(timezone.utc).isoformat(),
    "-metadata", f"COMMENT=Clipped with av1clip.py using mpv {MPV_VERSION}, SVT-AV1 {SVTAV1_VERSION}, "
                 f"ffmpeg version {FFMPEG_VERSION}",
    "-metadata", f"SOURCE-FILE={os.path.basename(args.input_file)}",
    "-metadata", f"SOURCE-RANGE={source_range}",
    "-metadata", "DATE=" + datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
    "-metadata:s:v:0", f"SVT-AV1_ARGS={' '.join(svtav1_cmd[1:-4])}",
    "-metadata:s:a:0", f"BITRATE={args.audio_bitrate} VBR",
    dest_file,
]

print("Starting encode..")
yuvpipe = subprocess.Popen(
    ffmpeg_yuvpipe_cmd, stdout=subprocess.PIPE)
enc = subprocess.Popen(
    svtav1_cmd, stdin=yuvpipe.stdout, stdout=subprocess.PIPE)
mux = subprocess.Popen(
    ffmpeg_mux_cmd, stdin=enc.stdout)
yuvpipe.stdout.close()
enc.stdout.close()
output = mux.communicate()[0]
yuvpipe.wait(10)
enc.wait(10)

print(yuvpipe.returncode, enc.returncode, mux.returncode)
if yuvpipe.returncode == 0 and enc.returncode == 0 and mux.returncode == 0:
    print("\n*** Encode complete! ***\n")
else:
    print("\nError during encode :(")
    exit(1)

answer = input("Keep temp file? [y/N] ")
if not answer or answer[0].lower() != "y":
    print("Deleting temp file..")
    os.remove(temp_file)
else:
    print("Temp file not deleted.")

print("Bye!")
