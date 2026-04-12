"""KokoroTTS: A Text-to-Speech system using the Kokoro ONNX model."""

from __future__ import annotations

from kokoro_onnx import Kokoro
import soundfile as sf
import requests
import os
import io
import re

class KokoroTTS:

    CLEAN_REGEX = re.compile(r"[^\w\s.,!?;:\'\-\"()$]")

    def __init__(self):
        """
        Initializes the Kokoro TTS engine.
        Ensures model weights are present before loading the ONNX session.
        """

        self.model_path = "kokoro-v1.0.onnx"
        self.voices_path = "voices-v1.0.bin"
        
        self._ensure_models_exist()
        self.kokoro = Kokoro(self.model_path, self.voices_path)

    def _ensure_models_exist(self):
        """
        Downloads the modern v1.0 model weights and binary voice configs.
        """

        MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
        VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

        if not os.path.exists(self.model_path):
            print("Downloading Kokoro v1.0 Model (this may take a moment)...")
            response = requests.get(MODEL_URL, stream=True)
            response.raise_for_status()
            
            with open(self.model_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Model Downloaded.")

        if not os.path.exists(self.voices_path):
            print("Downloading Voices Config v1.0...")
            response = requests.get(VOICES_URL)
            response.raise_for_status()
            
            with open(self.voices_path, "wb") as f:
                f.write(response.content)
            print("Voices Config Downloaded.")

    def _check_text(self, text: str) -> tuple[bool, str]:
        if text is None or not isinstance(text, str) or text.strip() == "":
            return False, ""

        # Normalize whitespace
        text = " ".join(text.split())
        text = self.CLEAN_REGEX.sub("", text)

        if len(text.split()) > 250:
            print("Warning: Text exceeds 250 words. Truncating to fit model limits.")
            text = " ".join(text.split()[:250])
            end_space = text.rfind(" ")
            if end_space > 0:
                text = text[:end_space] + "..."

        return True, text

    def generate_audio(self, text: str, voice: str = "af_sarah", speed: float = 1.0):
        """Generates audio bytes from text."""
        check_result, text = self._check_text(text)
        if not check_result:
            print("Warning: Empty or invalid text provided. Returning empty audio.")
            return None

        # Generate audio samples
        samples, sample_rate = self.kokoro.create(
            text, voice=voice, speed=speed, lang="en-us"
        )

        # Convert the samples to WAV format in memory
        byte_io = io.BytesIO()
        sf.write(byte_io, samples, sample_rate, format="WAV")
        byte_io.seek(0)
        return byte_io