#!/usr/bin/env python3
"""Render the narrated project teaser and walkthrough in landscape and portrait."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
SCREENS = ROOT / "source_screens"
OUTPUT = ROOT
WORK = Path(tempfile.gettempdir()) / "diffusion-video-build"
VOICE = "Samantha"
RATE = 160
NAVY = (17, 32, 46)
NAVY_2 = (24, 46, 61)
WHITE = (249, 248, 243)
MUTED = (191, 203, 207)
TEAL = (106, 202, 177)
AMBER = (220, 153, 102)

REGULAR_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


TEASER = [
    {"image": "landing.png", "label": "INDONESIAN MARKET INTELLIGENCE", "title": "An index tells one story.", "body": "Markets move through sectors in different directions.", "stat": "Look beneath the headline."},
    {"image": "sectors.png", "label": "SECTOR LEADERSHIP", "title": "Leadership is relative.", "body": "Compare sector returns with IHSG and follow the change in momentum.", "stat": "60D excess · 20D momentum"},
    {"image": "explorer.png", "label": "11 IDX SECTORS", "title": "Follow the companies.", "body": "Open the contributors behind each group reading.", "stat": "132 stocks · 12 per sector"},
    {"image": "sources.png", "label": "COVERAGE THROUGH 2 OCT 2026", "title": "See what is covered.", "body": "Affected windows stay out. Missing prices remain blank.", "stat": "Dates and sources, in view."},
    {"image": "what_changed.png", "label": "THE DIFFUSION", "title": "Leadership beneath the index.", "body": "A closer look at Indonesian sector performance.", "stat": "Explore the research."},
]

WALKTHROUGH = [
    {"image": "landing.png", "label": "THE DIFFUSION", "title": "Look beneath the headline.", "body": "Move from a sector reading to its dates, constituents, and method.", "stat": "A clearer view of market leadership"},
    {"image": "sectors.png", "label": "RESEARCH COVERAGE", "title": "132 stocks · 11 sectors", "body": "Twelve names per sector, selected by market capitalization on 2 October 2026.", "stat": "Retrospective research coverage"},
    {"image": "sectors.png", "label": "HOW TO READ THE MAP", "title": "Position and momentum.", "body": "60-day excess vs IHSG · 20-day minus 60-day excess. Leadership has a separate test and a five-name floor.", "stat": "Rotation and leadership are distinct"},
    {"image": "sectors.png", "label": "REPLAY", "title": "Move through the dates.", "body": "Twenty-one daily or five weekly dates, from 4 September to 2 October. Price history begins 9 June.", "stat": "Daily · weekly · date by date"},
    {"image": "explorer.png", "label": "SECTOR INSPECTOR", "title": "Open a sector.", "body": "Review excess returns, participation, concentration, and an equal-weight basket against IHSG.", "stat": "Each horizon keeps its own cohort"},
    {"image": "ticker.png", "label": "WINDOW ELIGIBILITY", "title": "Keep each window honest.", "body": "Mechanical corporate actions remove affected periods. Missing observations are left out, not filled.", "stat": "Counts stay beside the reading"},
    {"image": "sectors_long.png", "label": "PARTICIPATION", "title": "Compare the same names.", "body": "Breadth uses matched constituents at both dates, with the paired denominator kept visible.", "stat": "See who joined the move"},
    {"image": "sources.png", "label": "COVERAGE & SOURCES", "title": "Coverage has a clear boundary.", "body": "132 stocks support replay. Year-to-date and company flow remain with the original 66; 23 have an action-free year-to-date return.", "stat": "Company flow · 5 Jul–2 Oct"},
    {"image": "ownership.png", "label": "SOURCES BEHIND IDX CONTEXT", "title": "Keep market lenses distinct.", "body": "Official IDX summaries and statistics · Sectors API company flow · Yahoo Finance via yfinance · IDX and KSEI ownership disclosures.", "stat": "Each source has its own coverage"},
    {"image": "methodology.png", "label": "METHODS & SOURCES", "title": "Know what each figure supports.", "body": "Formulas, source boundaries, thresholds, and exclusions sit beside the research.", "stat": "The Diffusion · 2 Oct 2026"},
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD_FONT if bold else REGULAR_FONT, size)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and draw.textlength(trial, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], font: ImageFont.FreeTypeFont,
                 fill: tuple[int, int, int], width: int, leading: int) -> int:
    x, y = xy
    for line in wrap_text(draw, text, font, width):
        draw.text((x, y), line, font=font, fill=fill)
        y += leading
    return y


def draw_brand(draw: ImageDraw.ImageDraw, portrait: bool) -> None:
    x, y = (64, 58) if portrait else (78, 52)
    draw.rounded_rectangle((x, y + 13, x + 13, y + 37), radius=5, fill=AMBER)
    draw.rounded_rectangle((x + 19, y + 4, x + 32, y + 37), radius=5, fill=TEAL)
    draw.rounded_rectangle((x + 38, y, x + 51, y + 37), radius=5, fill=WHITE)
    title_x = x + 68
    draw.text((title_x, y - 1), "THE DIFFUSION", font=load_font(26 if portrait else 23, True), fill=WHITE)
    draw.text((title_x, y + 29), "INDONESIAN MARKET INTELLIGENCE", font=load_font(12 if portrait else 11), fill=MUTED)


def screenshot_card(canvas: Image.Image, path: Path, box: tuple[int, int, int, int], radius: int) -> None:
    x, y, width, height = box
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((x + 4, y + 10, x + width + 4, y + height + 10), radius=radius, fill=(0, 0, 0, 120))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=(252, 251, 247), outline=(85, 112, 125), width=2)
    inset = 10
    source = Image.open(path).convert("RGB")
    image = ImageOps.contain(source, (width - inset * 2, height - inset * 2), Image.Resampling.LANCZOS)
    px, py = x + (width - image.width) // 2, y + (height - image.height) // 2
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=max(3, radius - 8), fill=255)
    canvas.paste(image, (px, py), mask)


def make_landscape_slide(index: int, scene: dict, output: Path, total: int) -> None:
    canvas = Image.new("RGBA", (1920, 1080), NAVY + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1920, 8), fill=TEAL)
    draw_brand(draw, False)
    draw.text((1570, 62), "DATA THROUGH 2 OCT 2026", font=load_font(14, True), fill=MUTED)
    draw.text((80, 188), scene["label"], font=load_font(15, True), fill=AMBER)
    y = draw_wrapped(draw, scene["title"], (80, 236), load_font(64, True), WHITE, 555, 76)
    y += 16
    y = draw_wrapped(draw, scene["body"], (80, y), load_font(28), MUTED, 555, 42)
    stat_y = max(y + 30, 730)
    draw.rounded_rectangle((80, stat_y, 640, stat_y + 58), radius=16, fill=NAVY_2, outline=(65, 93, 105), width=1)
    draw.text((103, stat_y + 15), scene["stat"], font=load_font(20, True), fill=TEAL)
    screenshot_card(canvas, SCREENS / scene["image"], (710, 175, 1130, 707), 20)
    draw.line((80, 1004, 1840, 1004), fill=(63, 82, 94), width=1)
    draw.text((80, 1021), "THE DIFFUSION  ·  LEADERSHIP BENEATH THE INDEX", font=load_font(12, True), fill=(159, 178, 184))
    draw.text((1740, 1017), f"{index:02d} / {total:02d}", font=load_font(15, True), fill=WHITE)
    canvas.convert("RGB").save(output, quality=94)


def make_portrait_slide(index: int, scene: dict, output: Path, total: int) -> None:
    canvas = Image.new("RGBA", (1080, 1920), NAVY + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1080, 8), fill=TEAL)
    draw_brand(draw, True)
    draw.text((64, 153), scene["label"], font=load_font(15, True), fill=AMBER)
    y = draw_wrapped(draw, scene["title"], (64, 197), load_font(60, True), WHITE, 950, 70)
    draw_wrapped(draw, scene["body"], (64, y + 10), load_font(27), MUTED, 950, 39)
    screenshot_card(canvas, SCREENS / scene["image"], (64, 596, 952, 602), 22)
    draw.rounded_rectangle((64, 1252, 1016, 1322), radius=18, fill=NAVY_2, outline=(65, 93, 105), width=1)
    draw.text((91, 1273), scene["stat"], font=load_font(24, True), fill=TEAL)
    draw.text((64, 1762), "THE DIFFUSION  ·  DATA THROUGH 2 OCT 2026", font=load_font(14, True), fill=MUTED)
    draw.line((64, 1802, 1016, 1802), fill=(63, 82, 94), width=1)
    draw.rounded_rectangle((64, 1830, 64 + int(952 * index / total), 1837), radius=4, fill=TEAL)
    draw.text((948, 1850), f"{index:02d} / {total:02d}", font=load_font(14, True), fill=WHITE)
    canvas.convert("RGB").save(output, quality=94)


def parse_scripts() -> dict[str, list[str]]:
    text = (ROOT / "VIDEO_SCRIPTS.md").read_text(encoding="utf-8")
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = "teaser" if line.startswith("## Teaser") else "walkthrough"
            result[current] = []
        elif current and line.strip() and not line.startswith("#"):
            result[current].append(line.strip())
    return result


def run(args: list[str]) -> None:
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def audio_for(paragraphs: list[str], name: str, rate: int = RATE) -> tuple[Path, list[float]]:
    WORK.mkdir(parents=True, exist_ok=True)
    wavs: list[Path] = []
    durations: list[float] = []
    for index, paragraph in enumerate(paragraphs, 1):
        aiff = WORK / f"{name}-{index:02d}.aiff"
        wav_path = WORK / f"{name}-{index:02d}.wav"
        subprocess.run(["say", "-v", VOICE, "-r", str(rate), "-o", str(aiff), paragraph], check=True)
        run(["ffmpeg", "-y", "-i", str(aiff), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(wav_path)])
        with wave.open(str(wav_path), "rb") as source:
            durations.append(source.getnframes() / source.getframerate())
        wavs.append(wav_path)
    output = WORK / f"{name}.wav"
    with wave.open(str(wavs[0]), "rb") as first:
        params = first.getparams()
        silence = b"\x00" * int(params.framerate * params.nchannels * params.sampwidth * 0.36)
        with wave.open(str(output), "wb") as target:
            target.setparams(params)
            for index, wav_path in enumerate(wavs):
                with wave.open(str(wav_path), "rb") as source:
                    target.writeframes(source.readframes(source.getnframes()))
                if index < len(wavs) - 1:
                    target.writeframes(silence)
    return output, durations


def pad_audio_to(path: Path, duration: float) -> None:
    padded = path.with_name(f"{path.stem}-padded.wav")
    with wave.open(str(path), "rb") as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
    current_duration = len(frames) / (params.framerate * params.nchannels * params.sampwidth)
    if current_duration > duration:
        raise SystemExit(f"Narration audio exceeds its video duration ({current_duration:.2f}s > {duration:.2f}s).")
    remaining_frames = round((duration - current_duration) * params.framerate)
    with wave.open(str(padded), "wb") as target:
        target.setparams(params)
        target.writeframes(frames)
        target.writeframes(b"\x00" * remaining_frames * params.nchannels * params.sampwidth)
    padded.replace(path)


def time_stamp(seconds: float, vtt: bool = True) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def caption_chunks(text: str, max_chars: int = 68) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and len(trial) > max_chars:
            chunks.append(current)
            current = word
        else:
            current = trial
    if current:
        chunks.append(current)
    # Keep captions to at most two balanced lines.
    balanced: list[str] = []
    for chunk in chunks:
        part: list[str] = []
        current = ""
        for word in chunk.split():
            trial = f"{current} {word}".strip()
            if current and len(trial) > max_chars // 2:
                part.append(current)
                current = word
            else:
                current = trial
        if current:
            part.append(current)
        balanced.extend([" ".join(part[i:i+2]) for i in range(0, len(part), 2)])
    return balanced


def write_captions(paragraphs: list[str], durations: list[float], name: str, output_base: Path) -> list[float]:
    cues: list[tuple[float, float, str]] = []
    cursor = 0.0
    scene_durations: list[float] = []
    for paragraph, spoken_duration in zip(paragraphs, durations, strict=True):
        chunks = caption_chunks(paragraph)
        total_words = sum(len(chunk.split()) for chunk in chunks)
        for chunk in chunks:
            share = len(chunk.split()) / total_words
            cue_duration = max(0.75, spoken_duration * share)
            cues.append((cursor, cursor + cue_duration, chunk))
            cursor += cue_duration
        # Use the measured audio duration as the scene boundary even when the
        # cue weighting rounds a few milliseconds differently.
        scene_durations.append(spoken_duration + 0.36)
        cursor = sum(durations[:len(scene_durations)]) + 0.36 * len(scene_durations)
    lines = ["WEBVTT", ""]
    srt_lines: list[str] = []
    for index, (start, end, caption) in enumerate(cues, 1):
        lines.extend([f"{time_stamp(start)} --> {time_stamp(end)}", caption, ""])
        srt_lines.extend([str(index), f"{time_stamp(start, False)} --> {time_stamp(end, False)}", caption, ""])
    (output_base.with_suffix(".vtt")).write_text("\n".join(lines), encoding="utf-8")
    (output_base.with_suffix(".srt")).write_text("\n".join(srt_lines), encoding="utf-8")
    return scene_durations


def make_concat_file(scenes: list[dict], durations: list[float], format_name: str, label: str) -> Path:
    slide_dir = WORK / f"slides-{format_name}-{label}"
    slide_dir.mkdir(parents=True, exist_ok=True)
    maker = make_landscape_slide if format_name == "youtube" else make_portrait_slide
    for index, scene in enumerate(scenes, 1):
        maker(index, scene, slide_dir / f"scene-{index:02d}.png", len(scenes))
    concat_file = slide_dir / "playlist.txt"
    rows: list[str] = []
    for index, duration in enumerate(durations, 1):
        image_path = (slide_dir / f"scene-{index:02d}.png").resolve()
        rows.extend([f"file '{image_path}'", f"duration {duration:.6f}"])
    rows.append(f"file '{(slide_dir / f'scene-{len(scenes):02d}.png').resolve()}'")
    concat_file.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return concat_file


def render_video(concat_file: Path, audio_file: Path, output: Path, size: str, duration: float) -> None:
    width, height = (1920, 1080) if size == "youtube" else (1080, 1920)
    run([
        "ffmpeg", "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(audio_file), "-t", f"{duration:.3f}", "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(output),
    ])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    scripts = parse_scripts()
    if len(scripts["teaser"]) != len(TEASER) or len(scripts["walkthrough"]) != len(WALKTHROUGH):
        raise SystemExit("Narration paragraph count does not match the visual storyboard.")
    for scene in [*TEASER, *WALKTHROUGH]:
        if not (SCREENS / scene["image"]).is_file():
            raise SystemExit(f"Missing screen image: {scene['image']}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    teaser_audio, teaser_speech = audio_for(scripts["teaser"], "teaser")
    walkthrough_audio, walkthrough_speech = audio_for(scripts["walkthrough"], "walkthrough")
    teaser_durations = write_captions(scripts["teaser"], teaser_speech, "teaser", OUTPUT / "teaser")
    walk_durations = write_captions(scripts["walkthrough"], walkthrough_speech, "walkthrough", OUTPUT / "walkthrough")

    teaser_total = sum(teaser_durations) + 1.2
    walk_spoken_with_pauses = sum(walk_durations)
    walk_total = 180.0
    if walk_spoken_with_pauses > walk_total:
        raise SystemExit(f"Walkthrough narration exceeds three minutes ({walk_spoken_with_pauses:.1f}s). Lower the voice rate or shorten the script.")
    walk_durations[-1] += walk_total - walk_spoken_with_pauses
    pad_audio_to(teaser_audio, teaser_total)
    pad_audio_to(walkthrough_audio, walk_total)
    assets = [
        (TEASER, teaser_durations, teaser_audio, "teaser-vertical-2026-10-08.mp4", "reels", teaser_total),
        (WALKTHROUGH, walk_durations, walkthrough_audio, "walkthrough-youtube-2026-10-08.mp4", "youtube", walk_total),
        (WALKTHROUGH, walk_durations, walkthrough_audio, "walkthrough-reels-2026-10-08.mp4", "reels", walk_total),
    ]
    manifest = {"voice": VOICE, "speech_rate": RATE, "narration_source": "VIDEO_SCRIPTS.md", "videos": []}
    for scenes, durations, audio, filename, size, seconds in assets:
        concat_file = make_concat_file(scenes, durations, size, filename.split("-")[0])
        output = OUTPUT / filename
        render_video(concat_file, audio, output, size, seconds)
        manifest["videos"].append({
            "file": filename, "format": size, "duration_seconds": seconds,
            "resolution": "1920x1080" if size == "youtube" else "1080x1920",
            "sha256": sha256(output), "captions_vtt": "walkthrough.vtt" if "walkthrough" in filename else "teaser.vtt",
            "captions_srt": "walkthrough.srt" if "walkthrough" in filename else "teaser.srt",
        })
    (OUTPUT / "video_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(WORK, ignore_errors=True)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
