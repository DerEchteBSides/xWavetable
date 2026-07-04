#!/usr/bin/env python3
"""
xWavetable
==========

Durchsucht einen Inputordner rekursiv nach .wav Dateien (Single Cycle
Waveforms und/oder Wavetables), erkennt automatisch um welchen Typ es sich
handelt, und schreibt zwei wahlweise aktivierbare Export-Varianten in den
Outputordner:

1) .xwt Export (Serum/Xfer-Stil), Ordnerstruktur des Inputs bleibt erhalten:

    <Output>/SingleCycles/<gleiche Ordnerstruktur wie Input>/<name>.xwt
    <Output>/Wavetables/<gleiche Ordnerstruktur wie Input>/<name>.xwt

   .xwt ist technisch ein ganz normales RIFF/WAVE-File (16-bit PCM, mono).
   - Single Cycle: data-Chunk enthaelt genau FRAME_SIZE Samples, kein
     "clm "-Chunk.
   - Wavetable: data-Chunk enthaelt N * FRAME_SIZE Samples (N Frames /
     Cycles hintereinander) plus einen "clm "-Chunk mit dem Inhalt
     "<!>FRAME_SIZE 00000000 wavetable (www.xferrecords.com)", wie es z.B.
     Serum erzeugt.

2) MPC Export (OS 3.9 Wavetable-Oscillator), siehe
   https://dreyandersson.com/blog/load-your-own-wavetables-mpc-3-9/

    <Output>/Oscillators/Wavetables/<Library>/*.wav + format.json
    <Output>/Oscillators/SingleCycles/<Library>/*.wav

   Die MPC verlangt dafuer schlichte mono .wav Dateien (kein clm-Chunk),
   FLACH abgelegt (keine Unterordner!) in einem Bibliotheksordner pro
   urspruenglichem Inputunterordner. Pro Bibliotheksordner muss zudem eine
   einheitliche Geometrie gelten (alle Wavetables darin gleich viele
   Samples/Cycle und gleich viele Cycles) - falls ein Inputordner mehrere
   Geometrien enthaelt, werden automatisch getrennte Bibliotheksordner pro
   Geometrie angelegt. Ein format.json mit
   {"formatInfo": {"numSamplesPerSingleCycle": ..., "numSingleCycles": ...}}
   wird je Bibliotheksordner automatisch erzeugt. Den Inhalt von
   <Output>/Oscillators/ kopierst du danach 1:1 an die Wurzel eines USB-
   Sticks/SD-Karte/SSD, z.B. <Drive>/Oscillators/Wavetables/...

Start:
    python3 xwavetable_app.py
"""

import json
import math
import os
import sys
import struct
import threading
import traceback
from dataclasses import dataclass

import numpy as np

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
except ImportError:
    tk = None

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


# --------------------------------------------------------------------------
# App-Icon (eingebettet als Base64, damit auch in der .exe vorhanden)
# --------------------------------------------------------------------------

import base64 as _base64, tempfile as _tempfile

_ICON_B64 = (
    "AAABAAcAEBAAAAEAIAAoBAAAdgAAABgYAAABACAAKAkAAJ4EAAAgIAAAAQAgAFECAADGDQAAMDAAAAEAIABqAwAAFxAAAEBAAAAB"
    "ACAAqQQAAIETAACAgAAAAQAgAG0JAAAqGAAAAAAAAAEAIAAJFQAAlyEAACgAAAAQAAAA8P///wEAIAAAAAAAAAQAAAAAAAAAAAAA"
    "AAAAAAAAAAAODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O"
    "/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Cwsz/wAAy/8AAMn/CgpE/wEBv/8AAMn/CgpJ"
    "/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8FBYf/AADM/wAAy/8AAMv/CQlR/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/CQlN/wAAzP8AAMz/BQWL/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Cws1/wEBwv8AAMj/AADL/wAAxv8MDCT/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "DAww/wEBv/8AAMv/CQlN/wUFjP8AAMz/BQWH/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/DAwq/wEBu/8AAMz/CAha"
    "/w4ODv8MDC3/AADL/wAAy/8LCzP/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O"
    "/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/KAAAABgAAADo////AQAgAAAA"
    "AAAACQAAAAAAAAAAAAAAAAAAAAAAAA4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O"
    "/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O"
    "/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8KCkH/AADM/wAAzP8AAMv/DAwv/w4ODv8ODg7/"
    "CQlM/wAAy/8AAMz/AADI/woKRP8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/BASV"
    "/wAAzP8AAMz/BASQ/w4ODv8KCj7/AADH/wAAzP8AAMj/CgpI/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/DAwt/wAAyf8AAMz/AADM/wkJWP8BAcL/AADM/wAAyv8JCU3/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/wYGff8AAMz/AADM/wAAzP8AAMz/AADL/wkJUP8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w0NHf8BAcL/AADM"
    "/wAAzP8AAMz/CQlW/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/wgIWf8AAMv/AADM/wAAzP8AAMz/CQlW/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/CQlV/wAAy/8AAMz/AADJ/wAAzP8AAMz/AQG5/w0NFf8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8JCVH/AADL/wAAzP8BAcX/Cws8/wICrf8AAMz/AADM"
    "/wcHbf8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/wkJTf8AAMr/AADM/wAA"
    "yP8KCkL/Dg4O/wkJTf8AAMz/AADM/wEBxf8NDSH/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/CgpK/wAAyf8AAMz/AADK/woKSv8ODg7/Dg4O/w4OD/8DA6f/AADM/wAAzP8FBYX/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O"
    "/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O"
    "/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4O"
    "Dv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8O"
    "Dg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/"
    "Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O/w4ODv8ODg7/Dg4O"
    "/4lQTkcNChoKAAAADUlIRFIAAAAgAAAAIAgGAAAAc3p69AAAAhhJREFUeJztlr1rFEEYh593Z5P9kguRpIhoBNOYJmARrGwFra0E"
    "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"
)


def _get_icon_path():
    """Schreibt das eingebettete .ico temporaer auf Disk - wird von
    tkinter.Tk.iconbitmap() benoetigt (akzeptiert nur Dateipfade)."""
    raw = _base64.b64decode(_ICON_B64)
    tmp = _tempfile.NamedTemporaryFile(suffix='.ico', delete=False)
    tmp.write(raw)
    tmp.close()
    return tmp.name


# --------------------------------------------------------------------------
# Farben & Stil (uebernommen aus der Referenz-GUI)
# --------------------------------------------------------------------------

BG          = "#0e0e0e"
BG2         = "#181818"
BG3         = "#222222"
BG4         = "#2a2a2a"
ACCENT      = "#cc0000"
ACCENT_DIM  = "#880000"
FG          = "#e8e8e8"
FG_DIM      = "#666666"
FG_MID      = "#aaaaaa"
SUCCESS     = "#22cc66"
WARNING     = "#ffcc00"
FONT_MONO   = ("Courier New", 10)
FONT_UI     = ("Helvetica", 11)
FONT_TITLE  = ("Helvetica", 18, "bold")
FONT_SMALL  = ("Helvetica", 9)
FONT_LABEL  = ("Helvetica", 10)


# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

FRAME_SIZE_DEFAULT = 2048          # Samples pro Cycle (Serum-Standard)
SAMPLE_RATE_OUT = 44100            # Ziel-Samplerate fuer .xwt Dateien
MIN_FRAMES_FOR_WAVETABLE = 2       # ab wie vielen Frames gilt es als Wavetable
AUDIO_EXTENSIONS = (".wav", ".xwt")

# MPC OS 3.9 Wavetable-Oscillator Grenzwerte (siehe
# https://dreyandersson.com/blog/load-your-own-wavetables-mpc-3-9/)
MPC_MIN_CYCLE_SAMPLES = 512
MPC_MAX_CYCLE_SAMPLES = 16384
MPC_MIN_CYCLES = 2
MPC_MAX_CYCLES = 2048
MPC_MIN_SAMPLE_RATE = 22050
MPC_MAX_SAMPLE_RATE = 96000
MPC_MAX_FILES_PER_FOLDER = 512


# --------------------------------------------------------------------------
# WAV I/O (nur stdlib, keine externen Audio-Libs noetig)
# --------------------------------------------------------------------------

def read_wav_chunks(path):
    """Liest ein RIFF/WAVE-File manuell ein (toleriert beliebige Chunks wie
    JUNK / clm / LIST etc.) und liefert fmt-Infos + rohe PCM-Daten zurueck."""
    with open(path, "rb") as f:
        data = f.read()

    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path}: keine gueltige RIFF/WAVE Datei")

    pos = 12
    fmt = None
    pcm_data = None
    clm_text = None

    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        chunk_size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body_start = pos + 8
        body_end = body_start + chunk_size

        if chunk_id == b"fmt ":
            fmt = data[body_start:body_end]
        elif chunk_id == b"data":
            pcm_data = data[body_start:body_end]
        elif chunk_id == b"clm ":
            clm_text = data[body_start:body_end].rstrip(b"\x00").decode(
                "latin-1", errors="ignore"
            )

        # Chunks sind auf gerade Groessen gepaddet
        pos = body_end + (chunk_size % 2)

    if fmt is None or pcm_data is None:
        raise ValueError(f"{path}: fmt- oder data-Chunk fehlt")

    (audio_format, channels, sample_rate, byte_rate,
     block_align, bits_per_sample) = struct.unpack("<HHIIHH", fmt[:16])

    # WAVE_FORMAT_EXTENSIBLE (0xFFFE): das eigentliche Format steckt in der
    # Sub-Format-GUID ab Byte 24 des fmt-Chunks. Die ersten beiden Bytes
    # dieser GUID entsprechen dem klassischen Format-Code (1 = PCM,
    # 3 = IEEE float).
    if audio_format == 0xFFFE and len(fmt) >= 26:
        sub_format = struct.unpack("<H", fmt[24:26])[0]
        audio_format = sub_format

    if audio_format not in (1, 3):
        raise ValueError(
            f"{path}: nicht unterstuetztes Audioformat (Code {audio_format}). "
            "Unterstuetzt werden PCM (1) und IEEE Float (3)."
        )

    return {
        "channels": channels,
        "sample_rate": sample_rate,
        "bits_per_sample": bits_per_sample,
        "audio_format": audio_format,
        "pcm_data": pcm_data,
        "clm_text": clm_text,
    }


def pcm_bytes_to_float(pcm_data, bits_per_sample, channels, audio_format=1):
    """Wandelt rohe PCM-Bytes in float32 Samples im Bereich [-1, 1] um.
    Bei Mehrkanal-Material wird auf mono (Mittelwert aller Kanaele)
    heruntergemischt."""
    if audio_format == 3:
        # IEEE Float PCM
        if bits_per_sample == 32:
            arr = np.frombuffer(pcm_data, dtype="<f4").astype(np.float32)
        elif bits_per_sample == 64:
            arr = np.frombuffer(pcm_data, dtype="<f8").astype(np.float32)
        else:
            raise ValueError(f"Nicht unterstuetzte Float-Bittiefe: {bits_per_sample}")
    elif bits_per_sample == 16:
        arr = np.frombuffer(pcm_data, dtype="<i2").astype(np.float32)
        arr /= 32768.0
    elif bits_per_sample == 24:
        raw = np.frombuffer(pcm_data, dtype=np.uint8)
        n = len(raw) // 3
        raw = raw[: n * 3].reshape(-1, 3)
        as_int = (
            raw[:, 0].astype(np.int32)
            | (raw[:, 1].astype(np.int32) << 8)
            | (raw[:, 2].astype(np.int32) << 16)
        )
        # Vorzeichen erweitern (24-bit signed)
        as_int[as_int >= (1 << 23)] -= (1 << 24)
        arr = as_int.astype(np.float32) / float(1 << 23)
    elif bits_per_sample == 32:
        arr = np.frombuffer(pcm_data, dtype="<i4").astype(np.float32)
        arr /= float(1 << 31)
    else:
        raise ValueError(f"Nicht unterstuetzte Bittiefe: {bits_per_sample}")

    if channels > 1:
        usable = (len(arr) // channels) * channels
        arr = arr[:usable].reshape(-1, channels).mean(axis=1)

    return arr


def float_to_pcm16_bytes(samples_float):
    samples_float = np.clip(samples_float, -1.0, 1.0)
    ints = np.round(samples_float * 32767.0).astype(np.int16)
    return ints.tobytes()


def resample_linear(data, target_len):
    """Einfaches, aber robustes Resampling per linearer Interpolation -
    fuer Single-Cycle-Wellenformen voellig ausreichend und ohne externe
    Abhaengigkeiten (kein scipy noetig)."""
    src_len = len(data)
    if src_len == target_len:
        return data.astype(np.float32)
    if src_len == 0:
        return np.zeros(target_len, dtype=np.float32)

    # periodische Interpolation: das letzte Sample schliesst nahtlos an
    # das erste an (wichtig fuer Single-Cycle-Loops)
    src_x = np.linspace(0.0, 1.0, num=src_len, endpoint=False)
    tgt_x = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
    src_x_ext = np.concatenate([src_x, [1.0]])
    data_ext = np.concatenate([data, [data[0]]])
    return np.interp(tgt_x, src_x_ext, data_ext).astype(np.float32)


# --------------------------------------------------------------------------
# .xwt schreiben
# --------------------------------------------------------------------------

def write_xwt(path, pcm16_bytes, sample_rate, frame_size, is_wavetable):
    """Schreibt eine .xwt Datei (RIFF/WAVE, 16-bit mono PCM).
    Bei is_wavetable=True wird zusaetzlich ein 'JUNK'-Chunk (28 Null-Bytes)
    und ein 'clm '-Chunk im Serum/Xfer-Format geschrieben - inklusive
    identischer Chunk-Reihenfolge (JUNK, fmt, clm, data). Manche Hardware-
    Importer (z.B. die MPC) parsen RIFF-Dateien nicht vollstaendig generisch,
    sondern erwarten exakt dieses von Serum erzeugte Byte-Layout, daher wird
    es hier 1:1 nachgebildet statt nur RIFF-konform (aber abweichend) zu
    schreiben."""
    channels = 1
    bits_per_sample = 16
    block_align = channels * bits_per_sample // 8
    byte_rate = sample_rate * block_align

    fmt_body = struct.pack(
        "<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits_per_sample
    )

    chunks = b""

    if is_wavetable:
        junk_body = b"\x00" * 28
        chunks += b"JUNK" + struct.pack("<I", len(junk_body)) + junk_body

    chunks += b"fmt " + struct.pack("<I", len(fmt_body)) + fmt_body

    if is_wavetable:
        clm_text = f"<!>{frame_size} 00000000 wavetable (www.xferrecords.com)".encode("latin-1")
        # auf gerade Laenge auffuellen (RIFF-Konvention), mit Nullbyte padden
        if len(clm_text) % 2 == 1:
            clm_text += b"\x00"
        chunks += b"clm " + struct.pack("<I", len(clm_text)) + clm_text

    data_body = pcm16_bytes
    if len(data_body) % 2 == 1:
        data_body += b"\x00"
    chunks += b"data" + struct.pack("<I", len(pcm16_bytes)) + data_body

    riff_size = 4 + len(chunks)  # "WAVE" + chunks
    header = b"RIFF" + struct.pack("<I", riff_size) + b"WAVE"

    with open(path, "wb") as f:
        f.write(header)
        f.write(chunks)


def write_plain_wav(path, pcm16_bytes, sample_rate):
    """Schreibt eine minimale, 'saubere' RIFF/WAVE-Datei mit ausschliesslich
    fmt- und data-Chunk (keine clm/JUNK/LIST Zusatz-Chunks). Das ist das
    Format, das die MPC fuer ihre Oscillator/Wavetable-Engine erwartet -
    schlicht eine ganz normale mono WAV-Datei, exakt
    (numSamplesPerSingleCycle * numSingleCycles) Samples lang."""
    channels = 1
    bits_per_sample = 16
    block_align = channels * bits_per_sample // 8
    byte_rate = sample_rate * block_align

    fmt_body = struct.pack(
        "<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits_per_sample
    )

    chunks = b"fmt " + struct.pack("<I", len(fmt_body)) + fmt_body

    data_body = pcm16_bytes
    if len(data_body) % 2 == 1:
        data_body += b"\x00"
    chunks += b"data" + struct.pack("<I", len(pcm16_bytes)) + data_body

    riff_size = 4 + len(chunks)
    header = b"RIFF" + struct.pack("<I", riff_size) + b"WAVE"

    with open(path, "wb") as f:
        f.write(header)
        f.write(chunks)


_INVALID_NAME_CHARS = '<>:"/\\|?*'


def sanitize_name(name):
    """Macht einen String zu einem auf allen Plattformen gueltigen
    Datei-/Ordnernamen (entfernt z.B. Windows-verbotene Zeichen)."""
    cleaned = "".join("_" if c in _INVALID_NAME_CHARS else c for c in name)
    cleaned = cleaned.strip(" .")
    return cleaned or "Library"


def flatten_rel_dir(rel_dir, root_label):
    """Wandelt einen relativen Unterordnerpfad (kann mehrere Ebenen tief
    sein) zusammen mit dem Namen seines Input-Root-Ordners in einen
    einzelnen, flachen Bibliotheksnamen um, da die MPC keine verschachtelten
    Unterordner unter Oscillators/Wavetables/... akzeptiert. Beispiel:
    Root-Ordner 'Serum' mit Unterordnern 'Basic' und 'Digital' ergibt
    'Serum Basic' bzw. 'Serum Digital'; Dateien direkt im Root-Ordner
    ergeben einfach 'Serum'."""
    root_label = root_label or "Library"
    if not rel_dir or rel_dir == ".":
        return sanitize_name(root_label)
    parts = [root_label] + [p for p in rel_dir.replace("\\", "/").split("/") if p]
    return sanitize_name(" ".join(parts))

# --------------------------------------------------------------------------
# Verarbeitungslogik: erkennen Single Cycle vs. Wavetable + konvertieren
# --------------------------------------------------------------------------

@dataclass
class ProcessResult:
    kind: str          # "single" oder "wavetable"
    num_frames: int
    frame_size: int
    sample_rate: int


def _parse_clm_frame_size(info):
    """Liest die im clm-Chunk eingebettete Frame-Groesse (Samples/Cycle)
    der Quelldatei aus, falls vorhanden (z.B. weil sie selbst schon ein
    Serum/.xwt-Wavetable ist). Liefert None, wenn kein clm-Chunk vorliegt
    oder er nicht geparst werden kann."""
    clm_text = info.get("clm_text")
    if clm_text:
        try:
            # Format: "<!>2048 00000000 wavetable (...)"
            token = clm_text.split()[0]
            num = token.split(">")[-1]
            fs = int(num)
            if fs > 0:
                return fs
        except (ValueError, IndexError):
            pass
    return None


def nearest_power_of_two(n, min_v, max_v):
    """Rundet n auf die naechstliegende Zweierpotenz (im log2-Raum, also
    'naechstliegend' multiplikativ statt additiv), begrenzt auf [min_v, max_v].
    Wichtig fuer MPC-Kompatibilitaet: die MPC erkennt im Wavetable per
    eingebettetem clm-Chunk (ohne format.json) die Cycle-Anzahl offenbar nur
    zuverlaessig, wenn diese eine Zweierpotenz ist (z.B. 64/128/256/512) -
    krumme Werte wie 249 oder 250 Cycles werden sonst stillschweigend
    abgelehnt."""
    n = max(n, 1)
    p = round(math.log2(n))
    val = 2 ** p
    val = max(min_v, min(val, max_v))
    return val


def process_file(in_path, frame_size_default=FRAME_SIZE_DEFAULT, align_phase=False):
    """Liest eine .wav/.xwt Datei, erkennt ob es eine Single-Cycle-
    Wellenform oder ein Wavetable ist und liefert die fertigen PCM16-Bytes
    plus Metadaten zurueck (schreibt noch nichts). Bei align_phase=True
    werden die Frames eines Wavetables zusaetzlich per Kreuzkorrelation
    aufeinander ausgerichtet (siehe phase_align_frames).

    frame_size_default ist die Ziel-Frame-Groesse (Samples/Cycle):
    - != 0: erzwingt diese Groesse fuer ALLE Dateien (Resampling), auch
      wenn die Quelle selbst schon eine andere Frame-Groesse im clm-Chunk
      eingebettet hat - die ECHTE Cycle-Anzahl der Quelle wird dabei aus
      deren eigener Frame-Groesse ermittelt und beibehalten, nur jeder
      einzelne Cycle wird auf die neue Groesse resampelt.
    - == 0: kein erzwungenes Resampling - die Frame-Groesse der Quelle
      (clm-Chunk) wird uebernommen, falls vorhanden, sonst FRAME_SIZE_DEFAULT."""
    info = read_wav_chunks(in_path)
    clm_frame_size = _parse_clm_frame_size(info)
    target_frame_size = frame_size_default if frame_size_default else (
        clm_frame_size if clm_frame_size else FRAME_SIZE_DEFAULT
    )
    # source_frame_size = die TATSAECHLICHE Cycle-Laenge der Quelle, falls
    # bekannt (clm-Chunk) - bestimmt die echte Anzahl an Original-Cycles.
    # Ist sie unbekannt (kein clm), bleibt nur die Heuristik "total/Ziel".
    source_frame_size = clm_frame_size if clm_frame_size else target_frame_size

    mono = pcm_bytes_to_float(
        info["pcm_data"], info["bits_per_sample"], info["channels"],
        info.get("audio_format", 1),
    )
    total_samples = len(mono)

    if total_samples == 0:
        raise ValueError(f"{in_path}: leere Audiodaten")

    # Anzahl Frames anhand der SOURCE-Frame-Groesse bestimmen (das ist die
    # echte Cycle-Anzahl, falls bekannt - unabhaengig davon, auf welche
    # Groesse spaeter resampelt wird).
    raw_frames = total_samples / source_frame_size

    if raw_frames < MIN_FRAMES_FOR_WAVETABLE:
        # --- Single Cycle Waveform ---
        resampled = resample_linear(mono, target_frame_size)
        pcm16 = float_to_pcm16_bytes(resampled)
        result = ProcessResult("single", 1, target_frame_size, SAMPLE_RATE_OUT)
        return pcm16, result

    # --- Wavetable ---
    # Auf naechstliegende Zweierpotenz runden (siehe nearest_power_of_two
    # Docstring) - notwendig damit die MPC die im clm-Chunk eingebettete
    # Geometrie zuverlaessig erkennt, auch ohne format.json.
    num_frames = nearest_power_of_two(raw_frames, MIN_FRAMES_FOR_WAVETABLE, MPC_MAX_CYCLES)
    target_total = num_frames * source_frame_size

    if target_total == total_samples and source_frame_size == target_frame_size:
        resampled = mono.astype(np.float32)
    else:
        # Jeden Frame einzeln sauber auf target_frame_size resamplen, statt
        # das gesamte Wavetable global zu strecken (vermeidet "Verschmieren"
        # der einzelnen Cycles ineinander).
        src_frame_len = total_samples / num_frames
        frames_out = []
        for i in range(num_frames):
            start = int(round(i * src_frame_len))
            end = int(round((i + 1) * src_frame_len))
            end = max(end, start + 1)
            end = min(end, total_samples)
            chunk = mono[start:end]
            if len(chunk) == 0:
                chunk = mono[-1:]
            frames_out.append(resample_linear(chunk, target_frame_size))
        resampled = np.concatenate(frames_out)

    if align_phase and num_frames > 1:
        frames_2d = resampled.reshape(num_frames, target_frame_size)
        frames_2d = phase_align_frames(frames_2d)
        resampled = frames_2d.reshape(-1)

    pcm16 = float_to_pcm16_bytes(resampled)
    result = ProcessResult("wavetable", num_frames, target_frame_size, SAMPLE_RATE_OUT)
    return pcm16, result


# --------------------------------------------------------------------------
# Verzeichnis-Scan & Batch-Verarbeitung
# --------------------------------------------------------------------------

def find_audio_files(input_dir):
    matches = []
    for root, _dirs, files in os.walk(input_dir):
        for name in files:
            if name.lower().endswith(AUDIO_EXTENSIONS):
                matches.append(os.path.join(root, name))
    matches.sort()
    return matches


def _write_format_json(folder, frame_size, num_frames):
    payload = {
        "formatInfo": {
            "numSamplesPerSingleCycle": frame_size,
            "numSingleCycles": num_frames,
        }
    }
    with open(os.path.join(folder, "format.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)


def extend_wavetable_cycle(pcm16, current_frames, target_frames):
    """Verlaengert ein Wavetable durch zyklisches Wiederholen (Tiling) der
    vorhandenen Frames, bis target_frames erreicht ist. Da alle Frame-
    Anzahlen Zweierpotenzen sind, ist target_frames immer ein ganzzahliges
    Vielfaches von current_frames - daher reicht reines Wiederholen ohne
    Rest, der Inhalt der Cycles bleibt dabei unveraendert (kein erneutes
    Resampling, kein Verschmieren)."""
    if target_frames <= current_frames:
        return pcm16
    repeat = target_frames // current_frames
    arr = np.frombuffer(pcm16, dtype="<i2")
    tiled = np.tile(arr, repeat)
    return tiled.tobytes()


def extend_wavetable_interpolate(pcm16, frame_size, current_frames, target_frames):
    """Verlaengert ein Wavetable durch Interpolation entlang der Frame-/
    Morph-Achse - genau so, wie Serum, Massive oder Massive X beim
    Durchfahren der Wavetable-Position (Frame-Index) zwischen zwei
    benachbarten Frames linear ueberblenden. Es werden also zusaetzliche
    Zwischenframes erzeugt, die sanft zwischen den vorhandenen Original-
    Frames morphen, statt sie nur zu wiederholen. Liefert ein deutlich
    weicheres Ergebnis als das zyklische Wiederholen, veraendert aber den
    Charakter der Tabelle etwas (neue, gemittelte Zwischenframes statt
    exakter Wiederholung)."""
    if target_frames <= current_frames:
        return pcm16

    arr = (
        np.frombuffer(pcm16, dtype="<i2").astype(np.float32)
        .reshape(current_frames, frame_size) / 32768.0
    )

    if current_frames == 1:
        # Nichts zum Interpolieren da - einfach wiederholen
        out = np.repeat(arr, target_frames, axis=0)
    else:
        # Morph-Position 0..1 linear auf die vorhandenen Frame-Indizes
        # abbilden (genau wie ein Wavetable-Oszillator beim Scannen durch
        # die Tabelle) und zwischen den beiden naechsten Original-Frames
        # linear interpolieren.
        src_positions = np.linspace(0.0, current_frames - 1, target_frames)
        idx0 = np.floor(src_positions).astype(np.int64)
        idx1 = np.clip(idx0 + 1, 0, current_frames - 1)
        frac = (src_positions - idx0).reshape(-1, 1).astype(np.float32)
        out = arr[idx0] * (1.0 - frac) + arr[idx1] * frac

    return float_to_pcm16_bytes(out.reshape(-1))


def phase_align_frames(frames):
    """Richtet jeden Frame per zirkulaerer Kreuzkorrelation (FFT-basiert) auf
    den jeweils vorherigen Frame aus (zirkulaerer Sample-Shift, kein
    Resampling). Das reduziert Phasenspruenge zwischen benachbarten
    Original-Frames und macht das Morphen spuerbar sauberer - unabhaengig
    davon, ob der abspielende Synth beim Scannen durch die Tabelle linear
    oder spektral interpoliert, denn die Ursache liegt in den Original-
    Frames selbst (z.B. wenn jeder Cycle an einer anderen Phasenlage
    'geschnitten' wurde). frames: float32 Array der Form (num_frames,
    frame_size)."""
    aligned = frames.copy()
    n = frames.shape[1]
    for i in range(1, len(aligned)):
        ref_spec = np.fft.rfft(aligned[i - 1])
        cur_spec = np.fft.rfft(aligned[i])
        corr = np.fft.irfft(ref_spec * np.conj(cur_spec), n=n)
        shift = int(np.argmax(corr))
        aligned[i] = np.roll(aligned[i], shift)
    return aligned



def _spectral_blend_frame(frame_a, frame_b, t):
    """Blendet zwei Frames im Frequenzbereich (Magnitude + Phase) statt im
    Zeitbereich. Magnitude wird linear interpoliert, Phase entlang des
    kuerzesten Winkelpfads (zirkulaer) - das vermeidet die destruktive
    Interferenz/Kammfilter-Artefakte, die bei reiner Sample-fuer-Sample
    Interpolation phasenversetzter Frames entstehen ('abgehacktes' Morphen).
    Das entspricht im Prinzip dem 'Spectrum'-Morph-Modus aus Massive/
    Massive X."""
    spec_a = np.fft.rfft(frame_a)
    spec_b = np.fft.rfft(frame_b)
    mag_a, mag_b = np.abs(spec_a), np.abs(spec_b)
    mag = mag_a * (1.0 - t) + mag_b * t

    phase_a, phase_b = np.angle(spec_a), np.angle(spec_b)
    # Kuerzester Winkelpfad: Differenz auf [-pi, pi] wrappen, dann skaliert
    # auf phase_a aufaddieren statt die Phasen direkt linear zu mischen
    # (was bei Wrap-Around falsch waere).
    delta = np.angle(np.exp(1j * (phase_b - phase_a)))
    phase = phase_a + t * delta

    spec = mag * np.exp(1j * phase)
    return np.fft.irfft(spec, n=len(frame_a)).astype(np.float32)


def extend_wavetable_spectral(pcm16, frame_size, current_frames, target_frames):
    """Verlaengert ein Wavetable durch spektrale Interpolation (Magnitude/
    Phase statt roher Samples) entlang der Frame-/Morph-Achse - siehe
    _spectral_blend_frame(). Liefert deutlich sauberere Uebergaenge als
    extend_wavetable_interpolate() (Zeitbereich), besonders wenn benachbarte
    Original-Frames phasenversetzt sind oder stark unterschiedliche
    Oberton-Strukturen haben (z.B. Sinus -> Rechteck)."""
    if target_frames <= current_frames:
        return pcm16

    arr = (
        np.frombuffer(pcm16, dtype="<i2").astype(np.float32)
        .reshape(current_frames, frame_size) / 32768.0
    )

    if current_frames == 1:
        out = np.repeat(arr, target_frames, axis=0)
    else:
        src_positions = np.linspace(0.0, current_frames - 1, target_frames)
        out = np.empty((target_frames, frame_size), dtype=np.float32)
        for i, pos in enumerate(src_positions):
            idx0 = int(np.floor(pos))
            idx1 = min(idx0 + 1, current_frames - 1)
            frac = float(pos - idx0)
            if frac == 0.0 or idx0 == idx1:
                out[i] = arr[idx0]
            else:
                out[i] = _spectral_blend_frame(arr[idx0], arr[idx1], frac)

    return float_to_pcm16_bytes(out.reshape(-1))


def _extend_entry_to(entry, target_frames, extend_mode, log_callback, tag):
    """Verlaengert einen einzelnen Wavetable-Eintrag (dict mit 'pcm16' und
    'result') in-place auf target_frames Frames, mit der per extend_mode
    gewaehlten Methode, und loggt das Ergebnis mit dem gegebenen tag
    ('EXTEND' fuer Ordner-Angleich, 'MINFRAMES' fuer die globale
    Mindest-Frame-Anzahl)."""
    res = entry["result"]
    if res.num_frames >= target_frames:
        return
    if extend_mode == "spectral":
        entry["pcm16"] = extend_wavetable_spectral(
            entry["pcm16"], res.frame_size, res.num_frames, target_frames
        )
        method_label = "spektral interpoliert"
    elif extend_mode == "interpolate":
        entry["pcm16"] = extend_wavetable_interpolate(
            entry["pcm16"], res.frame_size, res.num_frames, target_frames
        )
        method_label = "interpoliert"
    else:
        entry["pcm16"] = extend_wavetable_cycle(
            entry["pcm16"], res.num_frames, target_frames
        )
        method_label = "zyklisch wiederholt"
    old_frames = res.num_frames
    entry["result"] = ProcessResult("wavetable", target_frames, res.frame_size, res.sample_rate)
    log_callback(
        f"[{tag}] {entry['rel_path']}: {old_frames} -> {target_frames} Frames ({method_label})"
    )


def run_batch(
    input_dirs,
    output_dir,
    frame_size,
    log_callback,
    progress_callback,
    write_xwt_export=True,
    write_mpc_export=True,
    extend_mode="off",  # "off", "cycle", "interpolate" oder "spectral"
    align_phase=False,
    min_frames=0,  # 0/None = aus, sonst Mindest-Frame-Anzahl (wird auf 2er-Potenz gerundet)
):
    if isinstance(input_dirs, str):
        input_dirs = [input_dirs]

    # Pro Input-Root-Ordner alle Dateien einsammeln, dabei den
    # (eindeutig gemachten) Root-Label fuer spaetere Bibliotheksnamen
    # mitfuehren (z.B. 'Serum' fuer Input-Ordner '.../MeineSamples/Serum').
    used_root_labels = set()
    jobs = []  # Liste von (input_dir, root_label)
    for input_dir in input_dirs:
        label = sanitize_name(os.path.basename(os.path.normpath(input_dir)) or "Library")
        final_label = label
        n = 2
        while final_label in used_root_labels:
            final_label = f"{label} {n}"
            n += 1
        used_root_labels.add(final_label)
        jobs.append((input_dir, final_label))

    all_files = []  # Liste von (in_path, input_dir, root_label)
    for input_dir, root_label in jobs:
        found = find_audio_files(input_dir)
        if not found:
            log_callback(f"[{root_label}] Keine .wav/.xwt Dateien gefunden.")
        for f in found:
            all_files.append((f, input_dir, root_label))

    if not all_files:
        log_callback("Keine .wav/.xwt Dateien in den gewaehlten Inputordnern gefunden.")
        return 0, 0

    single_root = os.path.join(output_dir, "SingleCycles")
    wt_root = os.path.join(output_dir, "Wavetables")
    osc_single_root = os.path.join(output_dir, "Oscillators", "SingleCycles")
    osc_wt_root = os.path.join(output_dir, "Oscillators", "Wavetables")

    total = len(all_files)

    # --- Pass 1: alle Dateien einlesen/konvertieren, noch nichts schreiben ---
    single_entries = []   # dicts: rel_path, rel_dir, root_label, base_name, pcm16, result
    wt_entries = []        # dicts: rel_path, rel_dir, root_label, base_name, pcm16, result (result.num_frames veraenderbar)

    for idx, (in_path, input_dir, root_label) in enumerate(all_files, start=1):
        rel_path = os.path.relpath(in_path, input_dir)
        rel_dir = os.path.dirname(rel_path)
        base_name = os.path.splitext(os.path.basename(rel_path))[0]
        log_rel_path = f"[{root_label}] {rel_path}"

        try:
            pcm16, result = process_file(in_path, frame_size, align_phase=align_phase)
        except Exception as exc:  # noqa: BLE001
            log_callback(f"[FEHLER] {log_rel_path}: {exc}")
            progress_callback(idx, total)
            continue

        entry = {
            "rel_path": log_rel_path, "rel_dir": rel_dir, "root_label": root_label,
            "base_name": base_name, "pcm16": pcm16, "result": result,
        }
        if result.kind == "single":
            single_entries.append(entry)
        else:
            wt_entries.append(entry)

        progress_callback(idx, total)

    # --- Optional: Frames innerhalb jedes Inputordners angleichen ---
    if extend_mode in ("cycle", "interpolate", "spectral") and wt_entries:
        by_reldir = {}
        for entry in wt_entries:
            key = (entry["root_label"], entry["rel_dir"])
            by_reldir.setdefault(key, []).append(entry)

        for (root_label, rel_dir), group in by_reldir.items():
            # Nur Eintraege mit identischer Frame-Groesse koennen sinnvoll
            # vereinheitlicht werden (unterschiedliche Samples/Cycle bleiben
            # getrennt, da sich Frame-Inhalte sonst nicht 1:1 angleichen lassen).
            by_fsize = {}
            for entry in group:
                by_fsize.setdefault(entry["result"].frame_size, []).append(entry)

            for fsize, fgroup in by_fsize.items():
                max_frames = max(e["result"].num_frames for e in fgroup)
                if max_frames <= min(e["result"].num_frames for e in fgroup):
                    continue  # schon alle gleich lang
                for entry in fgroup:
                    _extend_entry_to(entry, max_frames, extend_mode, log_callback, "EXTEND")

    # --- Optional: globale Mindest-Frame-Anzahl (z.B. Standard 256) ---
    if extend_mode in ("cycle", "interpolate", "spectral") and min_frames and wt_entries:
        target_min = nearest_power_of_two(min_frames, MIN_FRAMES_FOR_WAVETABLE, MPC_MAX_CYCLES)
        for entry in wt_entries:
            _extend_entry_to(entry, target_min, extend_mode, log_callback, "MINFRAMES")

    # --- Pass 2: schreiben ---
    n_single = len(single_entries)
    n_wt = len(wt_entries)

    mpc_wt_items = []
    mpc_single_items = []

    for entry in single_entries:
        rel_dir, root_label, base_name, pcm16, result = (
            entry["rel_dir"], entry["root_label"], entry["base_name"],
            entry["pcm16"], entry["result"],
        )
        if write_xwt_export:
            out_dir = os.path.join(single_root, root_label, rel_dir)
            os.makedirs(out_dir, exist_ok=True)
            write_xwt(
                os.path.join(out_dir, base_name + ".xwt"),
                pcm16, result.sample_rate, result.frame_size, is_wavetable=False,
            )
        if write_mpc_export:
            mpc_single_items.append({
                "base_name": base_name, "rel_dir": rel_dir, "root_label": root_label,
                "pcm16": pcm16, "sample_rate": result.sample_rate,
            })
        log_callback(f"[OK] {entry['rel_path']}  ->  Single Cycle")

    for entry in wt_entries:
        rel_dir, root_label, base_name, pcm16, result = (
            entry["rel_dir"], entry["root_label"], entry["base_name"],
            entry["pcm16"], entry["result"],
        )
        if write_xwt_export:
            out_dir = os.path.join(wt_root, root_label, rel_dir)
            os.makedirs(out_dir, exist_ok=True)
            write_xwt(
                os.path.join(out_dir, base_name + ".xwt"),
                pcm16, result.sample_rate, result.frame_size, is_wavetable=True,
            )
        if write_mpc_export:
            mpc_wt_items.append({
                "base_name": base_name, "rel_dir": rel_dir, "root_label": root_label,
                "pcm16": pcm16, "frame_size": result.frame_size,
                "num_frames": result.num_frames, "sample_rate": result.sample_rate,
            })
        log_callback(f"[OK] {entry['rel_path']}  ->  Wavetable ({result.num_frames} Frames)")

    if write_mpc_export:
        _write_mpc_wavetables(osc_wt_root, mpc_wt_items, log_callback)
        _write_mpc_single_cycles(osc_single_root, mpc_single_items, log_callback)

    log_callback("")
    log_callback(f"Fertig: {n_single} Single Cycle(s), {n_wt} Wavetable(s) erzeugt.")
    return n_single, n_wt


def _write_mpc_wavetables(osc_wt_root, items, log_callback):
    """Gruppiert verarbeitete Wavetables nach Input-Root-Ordner +
    urspruenglichem Unterordner und Geometrie (frame_size, num_frames),
    schreibt sie flach (keine Unterordner!) nach Oscillators/Wavetables/
    <Library>/ und legt pro Bibliotheksordner ein passendes format.json an.
    Enthaelt ein Inputordner mehrere unterschiedliche Geometrien, werden
    automatisch getrennte Bibliotheksordner je Geometrie angelegt (die MPC
    erlaubt nur eine Geometrie pro format.json)."""
    if not items:
        return

    # Gruppieren nach (Root-Ordner, rel_dir)
    by_reldir = {}
    for item in items:
        key = (item["root_label"], item["rel_dir"])
        by_reldir.setdefault(key, []).append(item)

    for (root_label, rel_dir), group in by_reldir.items():
        base_library = flatten_rel_dir(rel_dir, root_label)

        # Innerhalb dieses Inputordners nach Geometrie weiter aufteilen
        by_geometry = {}
        for item in group:
            key = (item["frame_size"], item["num_frames"])
            by_geometry.setdefault(key, []).append(item)

        multiple_geometries = len(by_geometry) > 1

        for (fsize, nframes), geo_items in by_geometry.items():
            if fsize < MPC_MIN_CYCLE_SAMPLES or fsize > MPC_MAX_CYCLE_SAMPLES:
                log_callback(
                    f"[WARNUNG] {base_library}: {fsize} Samples/Cycle liegt ausserhalb "
                    f"des von der MPC unterstuetzten Bereichs ({MPC_MIN_CYCLE_SAMPLES}-"
                    f"{MPC_MAX_CYCLE_SAMPLES}). Dateien werden trotzdem geschrieben, "
                    "laden vermutlich aber nicht."
                )
            if nframes < MPC_MIN_CYCLES or nframes > MPC_MAX_CYCLES:
                log_callback(
                    f"[WARNUNG] {base_library}: {nframes} Cycles liegt ausserhalb "
                    f"des von der MPC unterstuetzten Bereichs ({MPC_MIN_CYCLES}-"
                    f"{MPC_MAX_CYCLES}). Dateien werden trotzdem geschrieben, "
                    "laden vermutlich aber nicht."
                )

            if multiple_geometries:
                library_name = sanitize_name(f"{base_library} ({fsize}x{nframes})")
            else:
                library_name = base_library

            # In max. MPC_MAX_FILES_PER_FOLDER grosse Chunks aufteilen
            for chunk_idx in range(0, len(geo_items), MPC_MAX_FILES_PER_FOLDER):
                chunk = geo_items[chunk_idx:chunk_idx + MPC_MAX_FILES_PER_FOLDER]
                if len(geo_items) > MPC_MAX_FILES_PER_FOLDER:
                    part_name = f"{library_name} Part{chunk_idx // MPC_MAX_FILES_PER_FOLDER + 1}"
                else:
                    part_name = library_name

                out_dir = os.path.join(osc_wt_root, part_name)
                os.makedirs(out_dir, exist_ok=True)

                used_names = set()
                for item in chunk:
                    name = item["base_name"]
                    final_name = name
                    n = 2
                    while final_name.lower() in used_names:
                        final_name = f"{name}_{n}"
                        n += 1
                    used_names.add(final_name.lower())

                    write_plain_wav(
                        os.path.join(out_dir, final_name + ".wav"),
                        item["pcm16"], item["sample_rate"],
                    )

                _write_format_json(out_dir, fsize, nframes)
                log_callback(
                    f"[MPC] Oscillators/Wavetables/{part_name}/  "
                    f"({len(chunk)} Datei(en), {fsize}x{nframes})"
                )


def _write_mpc_single_cycles(osc_single_root, items, log_callback):
    """Schreibt verarbeitete Single-Cycle-Waveforms flach nach
    Oscillators/SingleCycles/<Library>/ (analog zu Wavetables, ein
    Bibliotheksordner pro Input-Root-Ordner + urspruenglichem Unterordner)."""
    if not items:
        return

    by_reldir = {}
    for item in items:
        key = (item["root_label"], item["rel_dir"])
        by_reldir.setdefault(key, []).append(item)

    for (root_label, rel_dir), group in by_reldir.items():
        library_name = flatten_rel_dir(rel_dir, root_label)

        for chunk_idx in range(0, len(group), MPC_MAX_FILES_PER_FOLDER):
            chunk = group[chunk_idx:chunk_idx + MPC_MAX_FILES_PER_FOLDER]
            if len(group) > MPC_MAX_FILES_PER_FOLDER:
                part_name = f"{library_name} Part{chunk_idx // MPC_MAX_FILES_PER_FOLDER + 1}"
            else:
                part_name = library_name

            out_dir = os.path.join(osc_single_root, part_name)
            os.makedirs(out_dir, exist_ok=True)

            used_names = set()
            for item in chunk:
                name = item["base_name"]
                final_name = name
                n = 2
                while final_name.lower() in used_names:
                    final_name = f"{name}_{n}"
                    n += 1
                used_names.add(final_name.lower())

                write_plain_wav(
                    os.path.join(out_dir, final_name + ".wav"),
                    item["pcm16"], item["sample_rate"],
                )

            log_callback(f"[MPC] Oscillators/SingleCycles/{part_name}/  ({len(chunk)} Datei(en))")


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Einstellungen speichern/laden (letzter Aufruf)
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Mehrsprachigkeit (i18n)
# --------------------------------------------------------------------------

STRINGS = {
    "en": {
        # Header
        "title_suffix":     "Wavetable",
        # Sections
        "sec_input":        "INPUT FOLDERS",
        "sec_output":       "OUTPUT FOLDER",
        "sec_export":       "EXPORT",
        "sec_extend":       "EXTEND FRAMES",
        "sec_fsize":        "FRAME SIZE / RESAMPLING  (Samples per Cycle)",
        # Input list
        "placeholder":      "Drag folders here\nor click '＋ Add'",
        "drop_hint":        "📂  Release to add",
        "btn_add":          "＋ Add",
        "btn_remove":       "✕ Remove",
        "btn_clear":        "Clear all",
        "hint_input":       "Each folder becomes its own library. Subfolders are flattened: Serum/Basic → 'Serum Basic'.",
        # Output
        "choose_output_title": "Choose output folder",
        # Export
        "export_xwt":       ".xwt  (Serum-style, SingleCycles/ + Wavetables/)",
        "export_mpc":       ".wav + format.json  (MPC, Oscillators/...)",
        # Extend
        "ext_off":          "Off (keep geometries separate)",
        "ext_cycle":        "Cyclic repeat (shorter tables loop exactly)",
        "ext_interpolate":  "Linear interpolate (time domain)",
        "ext_spectral":     "Spectral interpolate — like Massive/Massive X 'Spectrum' morph",
        "lbl_min_frames":   "Minimum frame count:",
        "hint_min_frames":  "0 = off  |  256 = Serum default  (rounded to power of 2, requires mode ≠ Off)",
        "chk_phase":        "Align frames by phase  (reduces click / jump artefacts)",
        # Frame size
        "lbl_fsize":        "Samples/Cycle:",
        "hint_fsize":       "Resamples every cycle to this length (even if the source has a different frame size).\n"
                            "0 = off (keep source size)  |  Default: 2048  |  MPC limits: 512–16384",
        # Footer / run
        "status_ready":     "Ready.",
        "status_running":   "Processing…",
        "status_done":      "Done — {s} Single Cycle(s), {w} Wavetable(s).",
        "status_error":     "Error — see log.",
        "btn_run":          "▶  RUN",
        "lbl_log":          "LOG",
        # Dialogs
        "err_title":        "Error",
        "err_no_input":     "Please add at least one valid input folder.",
        "err_no_output":    "Please choose an output folder.",
        "err_no_export":    "Please select at least one export target.",
        "dlg_add_folder":   "Add input folder",
    },
    "de": {
        "title_suffix":     "Wavetable",
        "sec_input":        "INPUTORDNER",
        "sec_output":       "OUTPUTORDNER",
        "sec_export":       "EXPORT",
        "sec_extend":       "FRAMES ANGLEICHEN",
        "sec_fsize":        "FRAME-GRÖSSE / RESAMPLING  (Samples pro Cycle)",
        "placeholder":      "Ordner hierher ziehen\noder '＋ Hinzufügen' klicken",
        "drop_hint":        "📂  Loslassen zum Hinzufügen",
        "btn_add":          "＋ Hinzufügen",
        "btn_remove":       "✕ Entfernen",
        "btn_clear":        "Alle löschen",
        "hint_input":       "Jeder Ordner wird zu einer Bibliothek. Unterordner: Serum/Basic → 'Serum Basic'.",
        "choose_output_title": "Outputordner wählen",
        "export_xwt":       ".xwt  (Serum-Stil, SingleCycles/ + Wavetables/)",
        "export_mpc":       ".wav + format.json  (MPC, Oscillators/...)",
        "ext_off":          "Aus (Geometrien getrennt lassen)",
        "ext_cycle":        "Zyklisch wiederholen (kürzere Tables exakt loopen)",
        "ext_interpolate":  "Linear interpolieren (Zeitbereich)",
        "ext_spectral":     "Spektral interpolieren — wie Massive/Massive X 'Spectrum'-Morph",
        "lbl_min_frames":   "Mindest-Frame-Anzahl:",
        "hint_min_frames":  "0 = aus  |  256 = Serum-Standard  (2er-Potenz, wirkt nur wenn Modus ≠ Aus)",
        "chk_phase":        "Frames aufeinander phasenausrichten  (reduziert Klick-/Sprung-Artefakte)",
        "lbl_fsize":        "Samples/Cycle:",
        "hint_fsize":       "Resampelt jeden Cycle auf diesen Wert (auch wenn die Quelle eine andere Größe hat).\n"
                            "0 = aus (Quell-Größe übernehmen)  |  Standard: 2048  |  MPC-Grenzen: 512–16384",
        "status_ready":     "Bereit.",
        "status_running":   "Verarbeite…",
        "status_done":      "Fertig — {s} Single Cycle(s), {w} Wavetable(s).",
        "status_error":     "Fehler — siehe Log.",
        "btn_run":          "▶  RUN",
        "lbl_log":          "LOG",
        "err_title":        "Fehler",
        "err_no_input":     "Bitte mindestens einen gültigen Inputordner hinzufügen.",
        "err_no_output":    "Bitte einen Outputordner wählen.",
        "err_no_export":    "Bitte mindestens ein Export-Ziel auswählen.",
        "dlg_add_folder":   "Inputordner hinzufügen",
    },
}

LANG_LABELS = {"en": "English", "de": "Deutsch"}


CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".xwavetable_settings.json")



def load_settings():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


class XWavetableApp:
    def __init__(self, root):
        self.root = root
        root.title("xWavetable")
        root.configure(bg=BG)
        root.geometry("980x640")
        root.minsize(820, 480)

        settings = load_settings()

        self.input_dirs = list(settings.get("input_dirs", []))
        self.output_dir = tk.StringVar(value=settings.get("output_dir", ""))
        self.frame_size = tk.IntVar(value=settings.get("frame_size", FRAME_SIZE_DEFAULT))
        self.export_xwt = tk.BooleanVar(value=settings.get("export_xwt", True))
        self.export_mpc = tk.BooleanVar(value=settings.get("export_mpc", True))
        self.extend_mode = tk.StringVar(value=settings.get("extend_mode", "off"))
        self.align_phase = tk.BooleanVar(value=settings.get("align_phase", False))
        self.min_frames = tk.IntVar(value=settings.get("min_frames", 256))
        self.lang = tk.StringVar(value=settings.get("lang", "en"))

        # Widget-Registry fuer Live-Sprachumschaltung: {key: [widget, ...]}
        self._lang_widgets: dict[str, list] = {}

        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        self._bind_dnd()

        for path in self.input_dirs:
            self.listbox.insert("end", f"  {path}")
        self._update_placeholder()

    # -- Layout ---------------------------------------------------------

    def _btn(self, parent, text, cmd):
        return tk.Button(
            parent, text=text, font=FONT_SMALL,
            bg=BG3, fg=FG_MID,
            activebackground=BG2, activeforeground=FG,
            relief="flat", padx=10, pady=5, cursor="hand2",
            command=cmd,
        )

    def _build_ui(self):
        # ---- Fusszeile (zuerst packen, damit sie immer sichtbar bleibt) ----
        footer = tk.Frame(self.root, bg=BG2, pady=12, padx=16)
        footer.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar(value=self.t("status_ready"))
        tk.Label(footer, textvariable=self.status_var,
                 font=FONT_SMALL, fg=FG_DIM, bg=BG2).pack(side="left")

        self.run_button = tk.Button(
            footer, text=self.t("btn_run"),
            font=("Helvetica", 12, "bold"),
            bg=ACCENT, fg="white",
            activebackground=ACCENT_DIM, activeforeground="white",
            relief="flat", padx=24, pady=8, cursor="hand2",
            command=self.start_run,
        )
        self._reg("btn_run", self.run_button)
        self.run_button.pack(side="right")

        prog_frame = tk.Frame(footer, bg=BG2)
        prog_frame.pack(side="left", fill="x", expand=True, padx=(16, 16))
        self._prog_bg = tk.Frame(prog_frame, bg=BG3, height=4)
        self._prog_bg.pack(fill="x", pady=(6, 0))
        self._prog_bar = tk.Frame(self._prog_bg, bg=ACCENT, height=4, width=0)
        self._prog_bar.place(x=0, y=0, relheight=1, relwidth=0)

        # ---- Titelzeile ----
        header = tk.Frame(self.root, bg=BG, pady=14, padx=20)
        header.pack(fill="x")
        tk.Label(header, text="x", font=("Helvetica", 20, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(header, text="Wavetable", font=FONT_TITLE,
                 fg=FG, bg=BG).pack(side="left")

        # Sprachauswahl rechts im Header
        lang_frame = tk.Frame(header, bg=BG)
        lang_frame.pack(side="right")
        tk.Label(lang_frame, text="🌐", font=("Helvetica", 13),
                 fg=FG_DIM, bg=BG).pack(side="left", padx=(0, 4))
        lang_menu = tk.OptionMenu(
            lang_frame, self.lang,
            *LANG_LABELS.keys(),
            command=self._apply_lang,
        )
        lang_menu.configure(
            bg=BG3, fg=FG_MID, activebackground=BG4, activeforeground=FG,
            highlightthickness=0, relief="flat", font=FONT_LABEL,
            indicatoron=True, bd=0,
        )
        lang_menu["menu"].configure(
            bg=BG3, fg=FG_MID, activebackground=ACCENT_DIM,
            activeforeground=FG, relief="flat", bd=0,
        )
        # OptionMenu-Text auf Landesbezeichnung umstellen
        self.lang.trace_add("write", lambda *_: lang_menu.configure(
            text=LANG_LABELS.get(self.lang.get(), self.lang.get())
        ))
        lang_menu.configure(text=LANG_LABELS.get(self.lang.get(), self.lang.get()))
        lang_menu.pack(side="left")

        # ---- Haupt-Container: links scrollbar, rechts Log ----
        main = tk.Frame(self.root, bg=BG, padx=16)
        main.pack(fill="both", expand=True)

        # -- Rechte Spalte: Log (feste Breite) --
        right = tk.Frame(main, bg=BG, width=300)
        right.pack(side="right", fill="both", padx=(8, 0))
        right.pack_propagate(False)

        self._reg("lbl_log",
            tk.Label(right, text=self.t("lbl_log"), font=("Helvetica", 9, "bold"),
                     fg=FG_DIM, bg=BG)
        ).pack(anchor="w", pady=(0, 6))

        self.log_text = scrolledtext.ScrolledText(
            right,
            bg=BG2, fg=FG_MID, font=("Courier New", 9),
            bd=0, highlightthickness=1, highlightbackground=BG3,
            wrap="word", state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

        # -- Linke Spalte: scrollbarer Canvas --
        left_outer = tk.Frame(main, bg=BG)
        left_outer.pack(side="left", fill="both", expand=True)

        self._canvas = tk.Canvas(left_outer, bg=BG, bd=0,
                                  highlightthickness=0, takefocus=False)
        _vsb = tk.Scrollbar(left_outer, orient="vertical",
                             command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=_vsb.set)
        _vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        left = tk.Frame(self._canvas, bg=BG)
        self._left_window = self._canvas.create_window((0, 0), window=left, anchor="nw")

        left.bind("<Configure>",
                  lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(self._left_window, width=e.width))

        def _on_mwheel(e):
            delta = -1 * (e.delta // 120) if e.delta else (-1 if e.num == 4 else 1)
            self._canvas.yview_scroll(delta, "units")

        self._canvas.bind_all("<MouseWheel>", _on_mwheel)
        self._canvas.bind_all("<Button-4>", _on_mwheel)
        self._canvas.bind_all("<Button-5>", _on_mwheel)

        # =========================================================
        # Controls in `left`
        # =========================================================

        PAD = {"padx": 2}

        def section(key):
            lbl = tk.Label(left, text=self.t(key), font=("Helvetica", 9, "bold"),
                           fg=FG_DIM, bg=BG)
            lbl.pack(anchor="w", pady=(14, 5))
            self._reg(key, lbl)

        # ---- Inputordner ----
        section("sec_input")

        list_frame = tk.Frame(left, bg=BG3, highlightthickness=1,
                               highlightbackground=BG4, height=120)
        list_frame.pack(fill="x", **PAD)
        list_frame.pack_propagate(False)

        self.listbox = tk.Listbox(
            list_frame,
            bg=BG3, fg=FG, selectbackground=ACCENT_DIM,
            selectforeground=FG, font=FONT_MONO,
            bd=0, highlightthickness=0,
            activestyle="none", selectmode=tk.EXTENDED,
        )
        sb = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        self.placeholder = tk.Label(
            list_frame, text=self.t("placeholder"),
            font=("Helvetica", 10), fg=FG_DIM, bg=BG3,
        )
        self.drop_label = tk.Label(
            list_frame, text=self.t("drop_hint"),
            font=("Helvetica", 11, "bold"), fg=ACCENT, bg=BG2,
        )

        btn_row = tk.Frame(left, bg=BG, pady=6)
        btn_row.pack(fill="x", **PAD)
        self._reg("btn_add",    self._btn(btn_row, self.t("btn_add"), self._add_folder)).pack(side="left", padx=(0, 6))
        self._reg("btn_remove", self._btn(btn_row, self.t("btn_remove"), self._remove_selected)).pack(side="left", padx=(0, 6))
        self._reg("btn_clear",  self._btn(btn_row, self.t("btn_clear"), self._clear_all)).pack(side="left")

        self._reg("hint_input",
            tk.Label(left, text=self.t("hint_input"),
                     font=FONT_SMALL, fg=FG_DIM, bg=BG, justify="left")
        ).pack(anchor="w", **PAD)

        # ---- Output ----
        section("sec_output")
        out_row = tk.Frame(left, bg=BG)
        out_row.pack(fill="x", pady=(0, 4), **PAD)
        self._out_entry = tk.Entry(
            out_row, textvariable=self.output_dir,
            font=FONT_MONO, bg=BG3, fg=FG_MID,
            insertbackground=FG, relief="flat",
            highlightthickness=1, highlightbackground=BG3,
            highlightcolor=ACCENT,
        )
        self._out_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._btn(out_row, "📂", self.choose_output).pack(side="left")

        # ---- Export ----
        section("sec_export")
        for key, var in [("export_xwt", self.export_xwt), ("export_mpc", self.export_mpc)]:
            self._reg(key,
                tk.Checkbutton(
                    left, text=self.t(key), variable=var,
                    font=FONT_LABEL, fg=FG_MID, bg=BG, selectcolor=BG3,
                    activebackground=BG, activeforeground=FG,
                    relief="flat", cursor="hand2",
                )
            ).pack(anchor="w", **PAD)

        # ---- Frames angleichen ----
        section("sec_extend")
        for value, key in [
            ("off",         "ext_off"),
            ("cycle",       "ext_cycle"),
            ("interpolate", "ext_interpolate"),
            ("spectral",    "ext_spectral"),
        ]:
            self._reg(key,
                tk.Radiobutton(
                    left, text=self.t(key), value=value, variable=self.extend_mode,
                    font=FONT_LABEL, fg=FG_MID, bg=BG, selectcolor=BG3,
                    activebackground=BG, activeforeground=FG,
                    relief="flat", cursor="hand2",
                )
            ).pack(anchor="w", **PAD)

        mf_row = tk.Frame(left, bg=BG)
        mf_row.pack(fill="x", pady=(8, 0), **PAD)
        self._reg("lbl_min_frames",
            tk.Label(mf_row, text=self.t("lbl_min_frames"),
                     font=FONT_LABEL, fg=FG_MID, bg=BG)
        ).pack(side="left")
        tk.Spinbox(
            mf_row, from_=0, to=MPC_MAX_CYCLES, increment=2,
            textvariable=self.min_frames, width=6,
            bg=BG3, fg=FG, insertbackground=FG, relief="flat",
            buttonbackground=BG3, highlightthickness=1, highlightbackground=BG3,
        ).pack(side="left", padx=(8, 0))
        self._reg("hint_min_frames",
            tk.Label(left, text=self.t("hint_min_frames"),
                     font=FONT_SMALL, fg=FG_DIM, bg=BG)
        ).pack(anchor="w", pady=(2, 4), **PAD)

        self._reg("chk_phase",
            tk.Checkbutton(
                left, text=self.t("chk_phase"), variable=self.align_phase,
                font=FONT_LABEL, fg=FG_MID, bg=BG, selectcolor=BG3,
                activebackground=BG, activeforeground=FG,
                relief="flat", cursor="hand2",
            )
        ).pack(anchor="w", pady=(4, 0), **PAD)

        # ---- Frame-Größe / Resampling ----
        section("sec_fsize")
        fs_row = tk.Frame(left, bg=BG)
        fs_row.pack(fill="x", pady=(0, 4), **PAD)
        self._reg("lbl_fsize",
            tk.Label(fs_row, text=self.t("lbl_fsize"),
                     font=FONT_LABEL, fg=FG_MID, bg=BG)
        ).pack(side="left")
        tk.Spinbox(
            fs_row, from_=0, to=MPC_MAX_CYCLE_SAMPLES,
            increment=64, textvariable=self.frame_size, width=8,
            bg=BG3, fg=FG, insertbackground=FG, relief="flat",
            buttonbackground=BG3, highlightthickness=1, highlightbackground=BG3,
        ).pack(side="left", padx=(8, 0))
        self._reg("hint_fsize",
            tk.Label(left, text=self.t("hint_fsize"),
                     font=FONT_SMALL, fg=FG_DIM, bg=BG, justify="left")
        ).pack(anchor="w", pady=(2, 14), **PAD)



    # -- Drag & Drop ------------------------------------------------------

    # -- i18n -----------------------------------------------------------

    def t(self, key):
        """Gibt den uebersetzen String fuer den aktuellen Sprachmodus zurueck."""
        return STRINGS.get(self.lang.get(), STRINGS["en"]).get(key, key)

    def _reg(self, key, widget, attr="text"):
        """Registriert ein Widget fuer Live-Sprachumschaltung.
        Beim naechsten _apply_lang()-Aufruf wird widget.configure(attr=t(key))
        aufgerufen."""
        self._lang_widgets.setdefault(key, []).append((widget, attr))
        return widget

    def _apply_lang(self, *_):
        """Aktualisiert alle registrierten Widgets auf die aktuelle Sprache."""
        for key, entries in self._lang_widgets.items():
            text = self.t(key)
            for widget, attr in entries:
                try:
                    widget.configure(**{attr: text})
                except Exception:
                    pass
        # Platzhalter-Label und Drop-Label direkt updaten
        self.placeholder.configure(text=self.t("placeholder"))
        self.drop_label.configure(text=self.t("drop_hint"))
        self.status_var.set(self.t("status_ready"))

    def _bind_dnd(self):
        if not DND_AVAILABLE:
            return
        try:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            self.listbox.dnd_bind("<<DropLeave>>", self._on_drop_leave)
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

    def _on_drop_enter(self, event):
        self.drop_label.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _on_drop_leave(self, event):
        self.drop_label.place_forget()

    def _on_drop(self, event):
        self.drop_label.place_forget()
        for p in self.root.tk.splitlist(event.data):
            p = p.strip()
            if os.path.isdir(p):
                self._add_path(p)
        self._update_placeholder()

    # -- Ordner-Verwaltung --------------------------------------------------

    def _add_folder(self):
        path = filedialog.askdirectory(title=self.t("dlg_add_folder"))
        if path:
            self._add_path(path)
        self._update_placeholder()

    def _add_path(self, path):
        path = os.path.normpath(path)
        if path not in self.input_dirs:
            self.input_dirs.append(path)
            self.listbox.insert("end", f"  {path}")
        self._update_placeholder()

    def _remove_selected(self):
        for i in reversed(list(self.listbox.curselection())):
            self.input_dirs.pop(i)
            self.listbox.delete(i)
        self._update_placeholder()

    def _clear_all(self):
        self.input_dirs.clear()
        self.listbox.delete(0, "end")
        self._update_placeholder()

    def _update_placeholder(self):
        if self.input_dirs:
            self.placeholder.place_forget()
        else:
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def choose_output(self):
        path = filedialog.askdirectory(title=self.t("choose_output_title"))
        if path:
            self.output_dir.set(path)

    # -- Log / Progress -----------------------------------------------------

    def log(self, msg):
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _append)

    def set_progress(self, current, total):
        def _update():
            frac = (current / total) if total else 0
            self._prog_bar.place(relwidth=max(0.0, min(1.0, frac)))
        self.root.after(0, _update)

    # -- Einstellungen --------------------------------------------------

    def current_settings(self):
        return {
            "input_dirs": list(self.input_dirs),
            "output_dir": self.output_dir.get().strip(),
            "frame_size": self.frame_size.get(),
            "export_xwt": self.export_xwt.get(),
            "export_mpc": self.export_mpc.get(),
            "extend_mode": self.extend_mode.get(),
            "align_phase": self.align_phase.get(),
            "min_frames": self.min_frames.get(),
            "lang": self.lang.get(),
        }

    def on_close(self):
        save_settings(self.current_settings())
        self.root.destroy()

    # -- Run --------------------------------------------------------------

    def start_run(self):
        out_dir = self.output_dir.get().strip()

        valid_dirs = [d for d in self.input_dirs if os.path.isdir(d)]
        if not valid_dirs:
            messagebox.showerror(self.t("err_title"), self.t("err_no_input"))
            return
        if not out_dir:
            messagebox.showerror(self.t("err_title"), self.t("err_no_output"))
            return
        if not self.export_xwt.get() and not self.export_mpc.get():
            messagebox.showerror(self.t("err_title"), self.t("err_no_export"))
            return

        os.makedirs(out_dir, exist_ok=True)
        save_settings(self.current_settings())

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.run_button.configure(state="disabled")
        self.status_var.set(self.t("status_running"))

        frame_size = self.frame_size.get()
        export_xwt = self.export_xwt.get()
        export_mpc = self.export_mpc.get()
        extend_mode = self.extend_mode.get()
        align_phase = self.align_phase.get()
        min_frames = self.min_frames.get()

        def worker():
            try:
                n_single, n_wt = run_batch(
                    valid_dirs, out_dir, frame_size, self.log, self.set_progress,
                    write_xwt_export=export_xwt, write_mpc_export=export_mpc,
                    extend_mode=extend_mode, align_phase=align_phase, min_frames=min_frames,
                )

                def _done():
                    self.status_var.set(
                        self.t("status_done").format(s=n_single, w=n_wt)
                    )
            except Exception:
                self.log("Unexpected error:\n" + traceback.format_exc())

                def _done():
                    self.status_var.set(self.t("status_error"))
            finally:
                pass
            self.root.after(0, lambda: self.run_button.configure(state="normal"))
            self.root.after(0, _done)

        threading.Thread(target=worker, daemon=True).start()


def main():
    if tk is None:
        print("tkinter is not installed. On Linux: sudo apt install python3-tk")
        sys.exit(1)
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()

    # Fenster-Icon setzen (funktioniert sowohl als .py als auch als .exe)
    try:
        icon_path = _get_icon_path()
        root.iconbitmap(icon_path)
    except Exception:
        pass  # Icon ist optional, kein Abbruch bei Fehler

    XWavetableApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
