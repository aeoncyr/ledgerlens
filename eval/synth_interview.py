"""Generate a short owner interview in Bahasa Indonesia for a fictional sample business.

A loan officer (Petugas) asks about sales, purchases, payments and the loan; the owner (Pemilik)
answers. Gemini's text-to-speech reads the script with two voices, and the result is saved as a WAV
file in the sample's folder and added to its manifest as interview evidence.

The scripts and the recordings are kept with the team's private material, not in this repository:
each script is a few lines of "Petugas: ..." and "Pemilik: ..." in .docs/interviews/<persona>.txt.

    GEMINI_API_KEY=... python eval/synth_interview.py --sample data/samples/pak-hendra
"""

from __future__ import annotations

import argparse
import json
import os
import wave
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-3.8-flash-tts"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".docs" / "interviews"

# The owner's voice for each sample business; the officer is always Charon.
VOICES = {"bu-sari": "Kore", "pak-joko": "Puck", "pak-hendra": "Fenrir"}


def _lines(script: str) -> list[types.Part]:
    """One text part per line, tagged with who says it, as multi-speaker speech requires."""
    parts = []
    for line in script.splitlines():
        speaker, text = line.split(":", 1)
        parts.append(
            types.Part(
                text=text.strip(), speech_metadata=types.SpeechMetadata(speaker=speaker)
            )
        )
    return parts


def _voice(name: str) -> types.VoiceConfig:
    return types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=name)
    )


def synthesise(client: genai.Client, script: str, owner_voice: str) -> bytes:
    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(role="user", parts=_lines(script))],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                language_code="id-ID",
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker="Petugas", voice_config=_voice("Charon")
                        ),
                        types.SpeakerVoiceConfig(
                            speaker="Pemilik", voice_config=_voice(owner_voice)
                        ),
                    ]
                ),
            ),
        ),
    )
    return response.candidates[0].content.parts[0].inline_data.data


def save_wav(path: Path, pcm: bytes, rate: int = 24_000) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic owner interview")
    parser.add_argument("--sample", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.sample / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    persona = manifest["persona"]
    script = (SCRIPTS_DIR / f"{persona}.txt").read_text().strip()
    client = genai.Client(enterprise=False, api_key=os.environ["GEMINI_API_KEY"])
    save_wav(args.sample / "interview.wav", synthesise(client, script, VOICES[persona]))
    evidence = [e for e in manifest["evidence"] if e["type"] != "interview_audio"]
    last = max(e["capturedAt"] for e in evidence)
    evidence.append(
        {"type": "interview_audio", "path": "interview.wav", "capturedAt": last}
    )
    manifest["evidence"] = evidence
    manifest_path.write_text(json.dumps(manifest, indent=2))
    size = (args.sample / "interview.wav").stat().st_size // 1024
    print(f"{persona}: interview.wav ({size} KB)")


if __name__ == "__main__":
    main()
