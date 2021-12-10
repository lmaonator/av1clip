#!/usr/bin/env python3
"""
    av1clip - A cli script to create .webm clips using mpv, svt-av1 and ffmpeg
    Copyright (C) 2021  lmaonator

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
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
SVTAV1_CRF = "30"
SVTAV1_PRESET = "3"
SVTAV1_TILE_ROWS = "2"
SVTAV1_TILE_COLUMNS = "2"
SVTAV1_FILM_GRAIN = "8"
SVTAV1_SCD = "0"


def get_output(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE).stdout.decode("utf-8")


def ffprobe(filepath):
    return json.loads(get_output([
        FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", filepath,
    ]))


def check_positive_int(value):
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"{value} must be a positive integer")
    return ivalue


def check_opus_bitrate(value):
    if value.endswith("k"):
        value = value[:-1] + "000"
    ivalue = int(value)
    if ivalue < 500 or ivalue > 512000:  # libopus min/max
        raise argparse.ArgumentTypeError(
            f"libopus: The bit rate {ivalue} bps is unsupported. Please choose"
            " a value between 500 and 512000.")
    return value


def main():
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
    group.add_argument("-sw", "--width", help="scale to specified width", type=check_positive_int)
    group.add_argument("-sh", "--height", help="scale to specified height", type=check_positive_int)

    group = parser.add_argument_group("encode settings")
    group.add_argument("-ab", "--audio-bitrate", default=AUDIO_BITRATE, type=check_opus_bitrate,
                       help=f"Opus audio bitrate [500-512k], default {AUDIO_BITRATE}")
    group.add_argument("-crf", "--crf", default=SVTAV1_CRF, type=int, choices=range(0, 64),
                       help=f"SVT-AV1 crf [0-63], default {SVTAV1_CRF}")
    group.add_argument("--preset", default=SVTAV1_PRESET, type=int, choices=range(0, 9),
                       help=f"SVT-AV1 preset [0-8], default {SVTAV1_PRESET}")
    group.add_argument("--tile-rows", default=SVTAV1_TILE_ROWS, type=int, choices=range(0, 7),
                       help=f"SVT-AV1 log2 of tile rows [0-6], default {SVTAV1_TILE_ROWS}")
    group.add_argument("--tile-columns", default=SVTAV1_TILE_COLUMNS, type=int, choices=range(0, 5),
                       help=f"SVT-AV1 log2 of tile columns [0-4], default {SVTAV1_TILE_COLUMNS}")
    group.add_argument("-g", "--film-grain", default=SVTAV1_FILM_GRAIN, type=int, choices=range(0, 51),
                       help=f"SVT-AV1 film-grain synthesis [0-50], default {SVTAV1_FILM_GRAIN}")
    group.add_argument("--scd", default=SVTAV1_SCD, type=int, choices=range(0, 2),
                       help=f"SVT-AV1 enable scene change detection [0-1], default: {SVTAV1_SCD}")

    args = parser.parse_args()

    if not os.path.isfile(args.input_file):
        print(f"'{args.input_file}' is not a file.")
        exit(2)

    MPV_VERSION = get_output([MPV, "--version"]).split(maxsplit=2)[1]
    FFMPEG_VERSION = get_output([FFMPEG, "-version"]).split(maxsplit=3)[2]
    SVTAV1_VERSION = get_output([SVTAV1, "--version"]).split(maxsplit=2)[1]

    argstr_md5 = hashlib.md5((f"{args.input_file}.v{args.vid}a{args.aid}s{args.sid}w{args.width}h{args.height}"
                              f"ab{args.audio_bitrate}start{args.start}end{args.end}").encode('utf-8')).hexdigest()
    temp_file_base = f"av1clip-{argstr_md5}-"

    dest_dir = os.getcwd()
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
        print("Creating temporary clip with burned subtitles and opus audio..")
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

        result = subprocess.run(mpv_cmd)
        if result.returncode != 0:
            print("Error creating temp file with mpv")
            exit(1)
        os.rename(temp_file_processing, temp_file)

    print("Getting video parameters..")
    # ffprobe to get video parameters for SVT-AV1
    data = ffprobe(temp_file)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps_num, fps_denom = video["r_frame_rate"].split("/")

    video_width = video["width"]
    video_height = video["height"]
    sample_width, sample_height = map(int, video["sample_aspect_ratio"].split(":"))
    sample_aspect_ratio = sample_width / sample_height

    scale = False
    # calculate dimensions for 1/1 SAR
    if sample_aspect_ratio != 1:
        scale = True
        if sample_aspect_ratio < 1:
            # upscale height
            video_height = round(video_height / sample_aspect_ratio)
        elif sample_aspect_ratio > 1:
            # upscale width
            video_width = round(video_width * sample_aspect_ratio)
    # apply user scale to dimensions
    if args.width or args.height:
        scale = True
        factor = min((args.width if args.width else video_width) / video_width,
                     (args.height if args.height else video_height) / video_height)
        video_width = round(video_width * factor)
        video_height = round(video_height * factor)

    # ffmpeg temp_file pipe to SVT-AV1
    ffmpeg_yuvpipe_cmd = [FFMPEG, "-hide_banner", "-v", "error", "-i", temp_file, "-map", "0:v:0"]
    if scale:
        ffmpeg_yuvpipe_cmd.extend(["-vf", f"scale=w={video_width}:h={video_height}:flags=lanczos,setsar=1/1"])
    ffmpeg_yuvpipe_cmd.extend(["-strict", "-1", "-f", "yuv4mpegpipe", "-"])
    # Encode from ffmpeg temp_file pipe and pipe to ffmpeg for muxing
    svtav1_cmd = [
        SVTAV1,
        "--preset", str(args.preset),
        "--tile-rows", str(args.tile_rows), "--tile-columns", str(args.tile_columns),
        "--crf", str(args.crf),
        "--fps-num", fps_num, "--fps-denom", fps_denom,
        "--film-grain", str(args.film_grain), "--scd", str(args.scd),
        "--input-depth", video["bits_per_raw_sample"],
        "-w", str(video_width), "-h", str(video_height),
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
    mux.communicate()[0]
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


if __name__ == "__main__":
    exit(main())
