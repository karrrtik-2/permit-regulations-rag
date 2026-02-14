"""
Speech synthesis and recognition service for HeavyHaul AI.

Provides text-to-speech using edge-tts with pygame playback,
and speech-to-text using Google Speech Recognition.
"""

import asyncio
import logging
import os
import shutil
import threading
import time
from queue import Queue
from typing import Optional

import edge_tts
import pygame
import speech_recognition as sr

from config.settings import settings

logger = logging.getLogger(__name__)


class SpeechSynthesizer:
    """Text-to-speech engine using edge-tts and pygame.

    Supports asynchronous speech generation with queued playback
    for smooth sentence-by-sentence audio output.
    """

    def __init__(self, voice: Optional[str] = None) -> None:
        """Initialize the speech synthesizer.

        Args:
            voice: TTS voice name. Defaults to config setting.
        """
        self.voice = voice or settings.speech.tts_voice
        self.stream_folder = settings.speech.stream_audio_dir
        self._audio_queue: Queue = Queue()

        os.makedirs(self.stream_folder, exist_ok=True)

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=settings.speech.audio_frequency)
        except pygame.error as e:
            logger.error("Failed to initialize pygame mixer: %s", e)
            raise

        # Start background playback thread
        self._playback_thread = threading.Thread(
            target=self._audio_playback_handler,
            daemon=True,
        )
        self._playback_thread.start()

    async def text_to_speech(self, text: str) -> None:
        """Convert text to speech and play it.

        Args:
            text: The text to speak.
        """
        if not text or not text.strip():
            return

        try:
            temp_file = os.path.join(
                self.stream_folder,
                f"tts_{hash(text + str(time.time()))}.mp3",
            )
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(temp_file)

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=settings.speech.audio_frequency)

            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)

            pygame.mixer.music.unload()

        except Exception as e:
            logger.error("Error in text_to_speech: %s", e)
        finally:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass

    def queue_audio(self, filename: str) -> None:
        """Add an audio file to the playback queue.

        Args:
            filename: Path to the audio file.
        """
        self._audio_queue.put(filename)

    def wait_for_playback_completion(self) -> None:
        """Block until all queued audio has finished playing."""
        self._audio_queue.join()

    def _audio_playback_handler(self) -> None:
        """Background thread handler for queued audio playback."""
        while True:
            filename = self._audio_queue.get()
            if filename is None:
                break

            if not os.path.exists(filename):
                logger.warning("Audio file not found: %s", filename)
                self._audio_queue.task_done()
                continue

            try:
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                pygame.mixer.music.unload()
                time.sleep(0.01)
            except Exception as e:
                logger.error("Playback error for %s: %s", filename, e)
            finally:
                self._audio_queue.task_done()
                try:
                    if os.path.exists(filename):
                        os.remove(filename)
                except Exception:
                    pass

    async def cleanup(self) -> None:
        """Clean up resources and stop playback thread."""
        self.wait_for_playback_completion()
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        delete_stream_audio_files(self.stream_folder)
        self._audio_queue.put(None)
        if self._playback_thread.is_alive():
            self._playback_thread.join(timeout=1)


def create_recognizer() -> sr.Recognizer:
    """Create a configured speech recognizer instance.

    Returns:
        A configured SpeechRecognition Recognizer.
    """
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = settings.speech.recognizer_energy_threshold
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = settings.speech.recognizer_pause_threshold
    recognizer.phrase_threshold = settings.speech.recognizer_phrase_threshold
    recognizer.non_speaking_duration = settings.speech.recognizer_non_speaking_duration
    return recognizer


_recognizer = create_recognizer()


async def take_command() -> str:
    """Listen for voice input and return recognized text.

    Returns:
        Recognized text in lowercase, or 'none' if recognition fails.
    """
    try:
        with sr.Microphone() as source:
            logger.debug("Listening...")
            print("\nListening...")
            audio = _recognizer.listen(
                source,
                timeout=settings.speech.listen_timeout,
                phrase_time_limit=settings.speech.phrase_time_limit,
            )

            logger.debug("Recognizing...")
            print("Recognizing...")
            query = _recognizer.recognize_google(audio, language="en-US")
            print(f"You said: {query}")
            return query.lower()

    except sr.UnknownValueError:
        return "none"
    except sr.RequestError as e:
        logger.error("Speech recognition request error: %s", e)
        return "none"
    except Exception as e:
        logger.error("Error in speech recognition: %s", e)
        return "none"


def delete_stream_audio_files(
    folder_path: Optional[str] = None,
) -> None:
    """Remove all files from the stream audio directory.

    Args:
        folder_path: Directory to clean. Defaults to config setting.
    """
    folder = folder_path or settings.speech.stream_audio_dir
    if not os.path.exists(folder):
        return

    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        try:
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except PermissionError:
                    pygame.mixer.music.unload()
                    time.sleep(0.1)
                    os.remove(filepath)
            elif os.path.isdir(filepath):
                shutil.rmtree(filepath)
        except Exception as e:
            logger.error("Error deleting %s: %s", filepath, e)
