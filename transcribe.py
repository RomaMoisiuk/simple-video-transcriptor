#!/usr/bin/env python3
"""
YouTube Transcription Tool
Uses yt-dlp to download audio and Whisper to transcribe it.
"""

import os
import sys
import subprocess
import tempfile

# Common languages supported by Whisper
LANGUAGES = {
    "1": ("English", "en"),
    "2": ("Romanian", "ro"),
    "3": ("Spanish", "es"),
    "4": ("French", "fr"),
    "5": ("German", "de"),
    "6": ("Italian", "it"),
    "7": ("Portuguese", "pt"),
    "8": ("Russian", "ru"),
    "9": ("Japanese", "ja"),
    "10": ("Chinese", "zh"),
    "11": ("Arabic", "ar"),
    "12": ("Other (type manually)", None),
}

OUTPUT_FORMATS = {
    "1": ("Plain text (.txt)", "txt"),
    "2": ("Subtitles with timestamps (.srt)", "srt"),
    "3": ("Both", "both"),
}

WHISPER_MODELS = {
    "1": ("Tiny   - fastest, less accurate", "tiny"),
    "2": ("Base   - good balance", "base"),
    "3": ("Small  - better accuracy", "small"),
    "4": ("Medium - high accuracy, slower", "medium"),
    "5": ("Large  - best accuracy, slowest", "large"),
}


def print_header():
    print("\n" + "="*50)
    print("   YouTube Transcription Tool")
    print("="*50 + "\n")


def ask_youtube_url():
    while True:
        url = input("Paste the YouTube URL: ").strip()
        if url.startswith("http") and ("youtube.com" in url or "youtu.be" in url):
            return url
        print("  That doesn't look like a valid YouTube URL. Please try again.\n")


def ask_language():
    print("\nSelect the video language:")
    for key, (name, _) in LANGUAGES.items():
        print(f"  {key:>2}. {name}")
    while True:
        choice = input("\nEnter number: ").strip()
        if choice in LANGUAGES:
            name, code = LANGUAGES[choice]
            if code is None:
                code = input("  Type the language code (e.g. 'uk' for Ukrainian): ").strip()
                name = code
            print(f"  Language set to: {name}")
            return code
        print("  Invalid choice. Please enter a number from the list.")


def ask_output_format():
    print("\nSelect output format:")
    for key, (label, _) in OUTPUT_FORMATS.items():
        print(f"  {key}. {label}")
    while True:
        choice = input("\nEnter number: ").strip()
        if choice in OUTPUT_FORMATS:
            label, fmt = OUTPUT_FORMATS[choice]
            print(f"  Format set to: {label}")
            return fmt
        print("  Invalid choice.")


def ask_whisper_model():
    print("\nSelect Whisper model:")
    for key, (label, _) in WHISPER_MODELS.items():
        print(f"  {key}. {label}")
    while True:
        choice = input("\nEnter number (default: 2 - base): ").strip() or "2"
        if choice in WHISPER_MODELS:
            label, model = WHISPER_MODELS[choice]
            print(f"  Model set to: {label}")
            return model
        print("  Invalid choice.")


def ask_output_dir():
    default = os.path.expanduser("~/transcripts")
    answer = input(f"\nOutput folder (press Enter for default: {default}): ").strip()
    folder = answer if answer else default
    os.makedirs(folder, exist_ok=True)
    print(f"  Transcripts will be saved to: {folder}")
    return folder


def download_audio(url, tmpdir):
    print("\nDownloading audio from YouTube...")
    audio_path = os.path.join(tmpdir, "audio.mp3")
    result = subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "mp3", "-o", audio_path, url],
        capture_output=False
    )
    if result.returncode != 0:
        print("\nFailed to download audio. Check the URL and try again.")
        sys.exit(1)
    if not os.path.exists(audio_path):
        files = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
        if files:
            audio_path = os.path.join(tmpdir, files[0])
        else:
            print("\nAudio file not found after download.")
            sys.exit(1)
    print("  Audio downloaded successfully.")
    return audio_path


def transcribe(audio_path, language, model, output_format, output_dir):
    print(f"\nTranscribing with Whisper (model: {model}, language: {language})...")
    print("  This may take a few minutes depending on video length...\n")

    formats_to_generate = ["txt", "srt"] if output_format == "both" else [output_format]

    for fmt in formats_to_generate:
        result = subprocess.run(
            [
                "whisper", audio_path,
                "--language", language,
                "--model", model,
                "--output_format", fmt,
                "--output_dir", output_dir,
            ],
            capture_output=False
        )
        if result.returncode != 0:
            print(f"\nWhisper transcription failed for format: {fmt}")
            sys.exit(1)

    print("\nTranscription complete!")
    print(f"Files saved to: {output_dir}")
    base = os.path.splitext(os.path.basename(audio_path))[0]
    for fmt in formats_to_generate:
        print(f"  - {base}.{fmt}")


def main():
    print_header()

    url = ask_youtube_url()
    language = ask_language()
    model = ask_whisper_model()
    output_format = ask_output_format()
    output_dir = ask_output_dir()

    print("\n" + "-"*50)
    print("Starting transcription process...")
    print("-"*50)

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = download_audio(url, tmpdir)
        transcribe(audio_path, language, model, output_format, output_dir)

    print("\nAll done! Enjoy your transcript.\n")


if __name__ == "__main__":
    main()
