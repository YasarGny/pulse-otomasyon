"""Decode and inspect recordings for long near-silent gaps; never synthesize."""
import re
import subprocess


def silence_gaps(path, minimum=5.0):
    result = subprocess.run(['ffmpeg','-nostdin','-hide_banner','-nostats','-v','info','-xerror',
        '-i',str(path),'-af',f'silencedetect=noise=-50dB:d={minimum}', '-f','null','-'],
        check=True,capture_output=True,text=True)
    starts = []
    gaps = []
    for line in result.stderr.splitlines():
        a = re.search(r'silence_start: ([0-9.]+)',line)
        b = re.search(r'silence_end: ([0-9.]+)',line)
        if a: starts.append(float(a[1]))
        if b and starts: gaps.append((starts.pop(0),float(b[1])))
    return gaps


def assert_no_long_silence(path):
    gaps = silence_gaps(path)
    if gaps:
        start,end = max(gaps,key=lambda pair:pair[1]-pair[0])
        raise ValueError(f'Audio quality: {end-start:.2f}s silence at {start:.2f}s')
