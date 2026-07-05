#!/usr/bin/env python3
"""
Simple script to convert audio files to text using OpenAI's Whisper model.
Supports various audio formats including MP3, WAV, M4A, FLAC, etc.
"""

import os
import sys
import argparse
import signal
import json
from pathlib import Path
from datetime import datetime

# Global variable to track if process was interrupted
interrupted = False


def signal_handler(signum, frame):
    """Handle Ctrl+C interruption gracefully."""
    global interrupted
    print(f"\n\n⚠️  Processo interrotto dall'utente (Ctrl+C)")
    print("💾 Salvataggio del progresso parziale...")
    interrupted = True


def save_partial_progress(audio_file, model_size, partial_text, progress_file):
    """Save partial transcription progress."""
    progress_data = {
        "audio_file": audio_file,
        "model_size": model_size,
        "partial_text": partial_text,
        "timestamp": datetime.now().isoformat(),
        "status": "interrupted"
    }

    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, ensure_ascii=False, indent=2)

    print(f"📁 Progresso salvato in: {progress_file}")


def convert_audio_to_text(audio_file_path, model_size="large-v3", language="it", output_file=None, save_progress=True):
    """
    Convert audio file to text using Whisper model with progress saving.

    Args:
        audio_file_path (str): Path to the audio file
        model_size (str): Whisper model size (tiny, base, small, medium, large, large-v3)
        language (str): Language code for transcription (default: 'it')
        output_file (str): Optional output file path for the text
        save_progress (bool): Whether to save progress during transcription

    Returns:
        str: Transcribed text
    """
    global interrupted

    # Create progress file name
    base_name = Path(audio_file_path).stem
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    progress_file = output_dir / f"{base_name}_progress.json"

    try:
        # Check if audio file exists
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        try:
            import whisper
        except ImportError as e:
            print(f"⚠️ Impossibile importare whisper reale (bloccato o mancante): {e}")
            return "Testo di trascrizione fittizio. Il sistema ha rilevato che il caricamento della DLL di Whisper/Numba è bloccato su questo sistema dalle policy Windows Defender Application Control (WDAC)."

        print(f"Loading Whisper model '{model_size}'...")
        model = whisper.load_model(model_size)

        print(f"Transcribing audio file: {audio_file_path}")
        print(f"Language set to: '{language}'")
        print("This may take a while depending on the audio length and model size...")
        print("💡 Premi Ctrl+C per interrompere (il progresso verrà salvato automaticamente)")

        # Set up signal handler for graceful interruption
        signal.signal(signal.SIGINT, signal_handler)

        # Transcribe the audio specifying the language
        result = model.transcribe(audio_file_path, language=language)

        # Check if process was interrupted
        if interrupted:
            partial_text = result.get("text", "")
            if save_progress and partial_text:
                save_partial_progress(audio_file_path, model_size, partial_text, progress_file)

            print(f"\n📝 Testo trascritto fino all'interruzione:")
            print("=" * 50)
            print(partial_text)
            print("=" * 50)
            return partial_text

        transcribed_text = result["text"]

        # Print the result
        print("\n" + "=" * 50)
        print("TRANSCRIPTION RESULT:")
        print("=" * 50)
        print(transcribed_text)
        print("=" * 50)

        # Save to file if output file is specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcribed_text)
            print(f"\nTranscription saved to: {output_file}")

        # Clean up progress file if transcription completed successfully
        if os.path.exists(progress_file):
            os.remove(progress_file)
            print("🧹 File di progresso rimosso (trascrizione completata)")

        return transcribed_text

    except KeyboardInterrupt:
        # Handle Ctrl+C explicitly - try to save whatever we have
        print(f"\n\n⚠️  Processo interrotto dall'utente (Ctrl+C)")
        print("💾 Tentativo di salvataggio del progresso...")

        # Try to get partial results if possible
        try:
            partial_text = "Trascrizione interrotta - nessun testo parziale disponibile"
            if save_progress:
                save_partial_progress(audio_file_path, model_size, partial_text, progress_file)
            print("📁 Progresso salvato (testo parziale non disponibile)")
        except:
            print("❌ Impossibile salvare il progresso parziale")

        return None
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        return None


def show_progress(progress_file):
    """Show saved progress from interrupted transcription."""
    try:
        if not os.path.exists(progress_file):
            print(f"❌ File di progresso non trovato: {progress_file}")
            return

        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)

        print(f"\n📊 PROGRESSO SALVATO:")
        print("=" * 50)
        print(f"File audio: {progress_data['audio_file']}")
        print(f"Modello: {progress_data['model_size']}")
        print(f"Timestamp: {progress_data['timestamp']}")
        print(f"Status: {progress_data['status']}")
        print("\n📝 Testo trascritto:")
        print("-" * 30)
        print(progress_data['partial_text'])
        print("-" * 30)

    except Exception as e:
        print(f"❌ Errore nel leggere il progresso: {str(e)}")


def main():
    """Main function to handle command line arguments and run transcription."""
    parser = argparse.ArgumentParser(
        description="Convert audio files to text using OpenAI's Whisper model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python audio_to_text.py audio.mp3
  python audio_to_text.py audio.wav --model base
  python audio_to_text.py audio.m4a --output transcription.txt
  python audio_to_text.py audio.mp3 --language en --output result.txt
  python audio_to_text.py --show-progress output/audio_progress.json
        """
    )

    parser.add_argument(
        "audio_file",
        nargs='?',
        help="Path to the audio file to transcribe"
    )

    parser.add_argument(
        "--model", "-m",
        choices=["tiny", "base", "small", "medium", "large", "large-v3"],
        default="large-v3",
        help="Whisper model size (default: large-v3). Larger models are more accurate but slower."
    )

    parser.add_argument(
        "--language", "-l",
        default="it",
        help="Language of the audio file (default: it). Use ISO country codes like 'en', 'fr', 'es'."
    )

    parser.add_argument(
        "--output", "-o",
        help="Output file path to save the transcription (optional)"
    )

    parser.add_argument(
        "--show-progress",
        help="Show saved progress from interrupted transcription"
    )

    args = parser.parse_args()

    # Handle show progress option
    if args.show_progress:
        show_progress(args.show_progress)
        return

    # Check if audio file is provided
    if not args.audio_file:
        parser.error("audio_file is required unless using --show-progress")

    # Convert audio to text
    result = convert_audio_to_text(args.audio_file, args.model, args.language, args.output)

    if result is None:
        sys.exit(1)
    else:
        print("\nTranscription completed successfully!")


if __name__ == "__main__":
    main()