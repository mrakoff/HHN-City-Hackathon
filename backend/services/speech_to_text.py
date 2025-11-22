import os
import tempfile
import subprocess
from typing import Optional

# Try to use local Whisper model (no API key needed)
# Note: Whisper requires Python 3.10-3.13. Python 3.14 is not yet supported by dependencies (numba, av)
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    try:
        import whisper
        WHISPER_AVAILABLE = True
        USE_FASTER_WHISPER = False
    except ImportError:
        WHISPER_AVAILABLE = False
        USE_FASTER_WHISPER = False
    else:
        USE_FASTER_WHISPER = False
else:
    USE_FASTER_WHISPER = True

# Cache the model to avoid reloading it every time
_whisper_model = None
_whisper_model_name = "base"  # Options: tiny, base, small, medium, large-v2, large-v3


def get_whisper_model(model_name: str = "base"):
    """
    Get or load the Whisper model (cached for performance)

    Args:
        model_name: Model size - "tiny" (fastest), "base", "small", "medium", "large-v2", "large-v3" (most accurate)

    Returns:
        Whisper model instance
    """
    global _whisper_model, _whisper_model_name

    if not WHISPER_AVAILABLE:
        import sys
        python_version = sys.version_info
        if python_version.major == 3 and python_version.minor >= 14:
            raise Exception(
                "Whisper is not available on Python 3.14 yet. "
                "The required dependencies (numba, av) don't support Python 3.14. "
                "Please use Python 3.10-3.13 for speech-to-text, or wait for library updates. "
                "Install with: pip install faster-whisper (on Python 3.10-3.13)"
            )
        else:
            raise Exception("Whisper library not available. Install with: pip install faster-whisper or pip install openai-whisper")

    # Reload model if model name changed
    if _whisper_model is None or _whisper_model_name != model_name:
        print(f"Loading Whisper model: {model_name} (this may take a moment on first use)...")
        if USE_FASTER_WHISPER:
            # Use device="cpu" by default, can be changed to "cuda" if GPU is available
            _whisper_model = WhisperModel(model_name, device="cpu", compute_type="int8")
        else:
            # Standard whisper
            _whisper_model = whisper.load_model(model_name)
        _whisper_model_name = model_name
        print(f"Whisper model {model_name} loaded successfully")

    return _whisper_model


def convert_audio_to_wav(input_path: str, output_path: str) -> str:
    """
    Convert audio file to WAV format using ffmpeg (fallback for corrupted/incompatible files)

    Args:
        input_path: Path to input audio file
        output_path: Path to output WAV file

    Returns:
        Path to converted file
    """
    try:
        # Try multiple approaches to handle corrupted or incomplete files
        # Approach 1: Try with error tolerance flags
        cmd1 = [
            'ffmpeg',
            '-err_detect', 'ignore_err',  # Ignore errors in input
            '-i', input_path,
            '-ar', '16000',  # Sample rate: 16kHz
            '-ac', '1',      # Channels: mono
            '-sample_fmt', 's16',  # Sample format: 16-bit PCM
            '-f', 'wav',     # Force WAV output format
            '-y',            # Overwrite output file
            output_path
        ]

        result1 = subprocess.run(
            cmd1,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result1.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path

        # Approach 2: Try without format specification (let ffmpeg auto-detect)
        print("First conversion attempt failed, trying auto-detect...")
        cmd2 = [
            'ffmpeg',
            '-i', input_path,
            '-ar', '16000',
            '-ac', '1',
            '-sample_fmt', 's16',
            '-f', 'wav',
            '-y',
            output_path
        ]
        result2 = subprocess.run(
            cmd2,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result2.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path

        # Approach 3: Try extracting raw audio and converting
        print("Trying raw audio extraction...")
        cmd3 = [
            'ffmpeg',
            '-f', 'webm',
            '-err_detect', 'ignore_err',
            '-i', input_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM 16-bit little-endian
            '-ar', '16000',
            '-ac', '1',
            '-f', 'wav',
            '-y',
            output_path
        ]
        result3 = subprocess.run(
            cmd3,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result3.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path

        # All approaches failed
        error_details = f"Attempt 1: {result1.stderr[:200] if result1.stderr else 'N/A'}"
        if result2.stderr:
            error_details += f" | Attempt 2: {result2.stderr[:200]}"
        if result3.stderr:
            error_details += f" | Attempt 3: {result3.stderr[:200]}"

        raise Exception(f"FFmpeg conversion failed after multiple attempts. {error_details}")

    except subprocess.TimeoutExpired:
        raise Exception("Audio conversion timed out")
    except FileNotFoundError:
        raise Exception("FFmpeg not found. Please install ffmpeg: brew install ffmpeg")
    except Exception as e:
        raise Exception(f"Error converting audio: {str(e)}")


def transcribe_audio(audio_file_path: str, language: Optional[str] = None, model_name: str = "base") -> str:
    """
    Transcribe audio file using local Whisper model (no API key needed)
    faster-whisper supports WebM, MP3, WAV, and many other formats directly via ffmpeg.

    Args:
        audio_file_path: Path to the audio file
        language: Optional language code (e.g., 'en', 'de'). If None, Whisper will auto-detect
        model_name: Model size - "tiny" (fastest), "base", "small", "medium", "large" (most accurate)

    Returns:
        Transcribed text string
    """
    if not WHISPER_AVAILABLE:
        import sys
        python_version = sys.version_info
        if python_version.major == 3 and python_version.minor >= 14:
            raise Exception(
                "Whisper is not available on Python 3.14 yet. "
                "The required dependencies (numba, av) don't support Python 3.14. "
                "Please use Python 3.10-3.13 for speech-to-text."
            )
        else:
            raise Exception("Whisper library not available. Install with: pip install faster-whisper or pip install openai-whisper")

    # Check if file exists and has content
    if not os.path.exists(audio_file_path):
        raise Exception(f"Audio file not found: {audio_file_path}")

    file_size = os.path.getsize(audio_file_path)
    if file_size == 0:
        raise Exception("Audio file is empty")

    print(f"Transcribing audio file: {audio_file_path}, size: {file_size} bytes")

    # Load or get cached model
    model = get_whisper_model(model_name)

    converted_path = None
    try:
        # Try direct transcription first (faster-whisper supports WebM, MP3, WAV, etc. directly)
        try:
            print("Attempting direct transcription (faster-whisper supports WebM natively)...")
            if USE_FASTER_WHISPER:
                segments, info = model.transcribe(audio_file_path, language=language)
                text_parts = [segment.text for segment in segments]
                result_text = " ".join(text_parts).strip()
            else:
                result = model.transcribe(audio_file_path, language=language)
                result_text = result.get("text", "").strip()

            if result_text:
                return result_text
            return ""  # Empty transcription
        except Exception as direct_error:
            # Fallback: convert to WAV if direct processing fails
            error_str = str(direct_error)
            print(f"Direct processing failed: {error_str}")

            file_ext = os.path.splitext(audio_file_path)[1].lower()
            if file_ext == '.wav':
                # Already WAV, re-raise the original error
                raise Exception(f"Error transcribing WAV file: {error_str}")

            # Try to convert to WAV and retry
            print("Falling back to WAV conversion...")
            try:
                converted_path = tempfile.NamedTemporaryFile(delete=False, suffix='.wav').name
                converted_path = convert_audio_to_wav(audio_file_path, converted_path)
                print(f"Audio converted to WAV: {converted_path}")

                # Retry with converted file
                if USE_FASTER_WHISPER:
                    segments, info = model.transcribe(converted_path, language=language)
                    text_parts = [segment.text for segment in segments]
                    result_text = " ".join(text_parts).strip()
                else:
                    result = model.transcribe(converted_path, language=language)
                    result_text = result.get("text", "").strip()

                return result_text if result_text else ""
            except Exception as conv_error:
                # Both direct and conversion failed - provide user-friendly error
                conv_error_str = str(conv_error)
                if "invalid data" in conv_error_str.lower() or "corrupted" in conv_error_str.lower():
                    raise Exception("The audio recording appears to be corrupted or incomplete. Please try recording again.")
                else:
                    raise Exception("Unable to process the audio file. Please try recording again.")
    except Exception as e:
        raise Exception(f"Error transcribing audio: {str(e)}")
    finally:
        # Clean up converted file if it was created
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except Exception as cleanup_error:
                print(f"Warning: Could not delete converted file {converted_path}: {cleanup_error}")


def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "audio.webm", language: Optional[str] = None, model_name: str = "base") -> str:
    """
    Transcribe audio from bytes using local Whisper model (no API key needed)

    Args:
        audio_bytes: Audio data as bytes
        filename: Filename with extension (used to determine format)
        language: Optional language code (e.g., 'en', 'de'). If None, Whisper will auto-detect
        model_name: Model size - "tiny" (fastest), "base", "small", "medium", "large" (most accurate)

    Returns:
        Transcribed text string
    """
    if not audio_bytes or len(audio_bytes) == 0:
        raise Exception("Empty audio bytes provided")

    print(f"Transcribing audio bytes: {len(audio_bytes)} bytes, filename: {filename}")

    # Validate minimum file size (WebM files should be at least a few KB)
    if len(audio_bytes) < 1024:  # Less than 1KB is suspicious
        raise Exception(f"Audio file too small ({len(audio_bytes)} bytes). May be corrupted or incomplete.")

    # Create a temporary file to save the audio bytes
    file_ext = os.path.splitext(filename)[1] or '.webm'

    # Whisper supports many formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, etc.
    # If extension is not recognized, use .webm as default
    if not file_ext or file_ext == '':
        file_ext = '.webm'

    temp_path = None
    converted_path = None
    try:
        # Save original file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        # Validate WebM file structure (basic check)
        # Note: Complete WebM files from MediaRecorder should have proper headers
        if file_ext == '.webm':
            with open(temp_path, 'rb') as f:
                header = f.read(4)
                # WebM magic bytes: 1A 45 DF A3
                if header != b'\x1a\x45\xdf\xa3':
                    print(f"Warning: WebM file may be incomplete (header: {header.hex()})")
                    print(f"File size: {len(audio_bytes)} bytes")
                    # Check if file is too small to be valid
                    if len(audio_bytes) < 4096:  # Less than 4KB is very suspicious
                        raise Exception(
                            "The audio recording appears to be incomplete or corrupted. "
                            "Please try recording again and make sure to stop the recording completely."
                        )
                    print("Will attempt direct processing - faster-whisper may still handle it")

        # Transcribe directly - faster-whisper supports WebM natively
        # Conversion to WAV will only happen as a fallback if direct processing fails
        result = transcribe_audio(temp_path, language=language, model_name=model_name)
        if not result or not result.strip():
            return ""  # Return empty string if no transcription
        return result
    except Exception as e:
        error_msg = str(e)
        print(f"Error in transcribe_audio_bytes: {error_msg}")
        raise Exception(f"Failed to transcribe audio: {error_msg}")
    finally:
        # Clean up temporary files
        for path in [temp_path, converted_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as cleanup_error:
                    print(f"Warning: Could not delete temp file {path}: {cleanup_error}")
                    pass  # Ignore cleanup errors
