# av1clip

A cli script to create .webm clips using mpv, svt-av1 and ffmpeg

## Disclaimer

I just wrote this while playing around with, and testing, SVT-AV1.
There are probably better scripts out there, but it does its job.. kinda.

It will probably not work for some input videos, eg. variable framerate .mkv


## Requirements

`SvtAv1EncApp`, `mpv`, `ffmpeg`, and `ffprobe` in your PATH (or edit the script).

mpv is used to create a temporary clip with burned subtitles. It's
significantly faster for burning subtitles than ffmpegs subtitle filter.
Ffmpegs subtitle filter demuxes the entire subtitle
track in the beginning, which takes a while for large videos.

## Example usage

Clip from 01:20.69 to 01:30.96  
`av1clip -s 01:20.69 -e 01:30.96 coolvideo.mkv`

Clip first 10 seconds and scale video to 480p  
`av1clip -e 10.0 -sh 480 coolvideo.mkv`

## Full help output

```shell
$ av1clip -h
usage: av1clip [-h] [-s START] [-e END] [-vid VID] [-aid AID] [-sid SID] [-sw WIDTH] [-sh HEIGHT] [-ab AUDIO_BITRATE] [-crf CRF] [--preset PRESET] [--tile-rows TILE_ROWS] [--tile-columns TILE_COLUMNS] [-g FILM_GRAIN] [--scd SCD] input_file

positional arguments:
  input_file            input video file

optional arguments:
  -h, --help            show this help message and exit
  -s START, --start START
                        start time
  -e END, --end END     end time

track selection:
  set to 'no' to disable, default 'auto'

  -vid VID              video track id
  -aid AID              audio track id
  -sid SID              subtitle track id

filters:
  -sw WIDTH, --width WIDTH
                        scale to specified width
  -sh HEIGHT, --height HEIGHT
                        scale to specified height

encode settings:
  -ab AUDIO_BITRATE, --audio-bitrate AUDIO_BITRATE
                        Opus audio bitrate [500-512k], default 256k
  -crf CRF, --crf CRF   SVT-AV1 crf [0-63], default 30
  --preset PRESET       SVT-AV1 preset [0-8], default 3
  --tile-rows TILE_ROWS
                        SVT-AV1 log2 of tile rows [0-6], default 2
  --tile-columns TILE_COLUMNS
                        SVT-AV1 log2 of tile columns [0-4], default 2
  -g FILM_GRAIN, --film-grain FILM_GRAIN
                        SVT-AV1 film-grain synthesis [0-50], default 8
  --scd SCD             SVT-AV1 enable scene change detection [0-1], default: 0
```
