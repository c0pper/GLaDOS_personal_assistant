import os
from openai import OpenAI
import io


class OpenAITranscriber:
    """
    A class to handle audio transcription using the OpenAI Whisper API via the OpenAI Python SDK.
    """

    def __init__(self, api_key: str = None):
        """
        Initializes the transcriber with an OpenAI API key.

        Args:
            api_key (str): The API key for authenticating with OpenAI.
                           If not provided, it will attempt to read from
                           the environment variable 'OPENAI_API_KEY'.
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set. Please provide it or set the 'OPENAI_API_KEY' environment variable.")

        # Initialize the OpenAI client
        self.client = OpenAI(api_key=api_key)

    def transcribe(self, audio_file: bytearray, model: str = "gpt-4o-transcribe", language: str = None) -> str:
        """
        Transcribes an audio file into text using the OpenAI Whisper model.

        Args:
            audio_file (bytearray): Raw audio bytes (e.g. from Telegram download).
            model (str): Whisper model to use (default: "gpt-4o-transcribe").
            language (str): Optional language hint (e.g., "en", "it", "es").

        Returns:
            str: The transcribed text.
        """
        try:
            # Wrap bytearray into a file-like object
            audio_io = io.BytesIO(audio_file)
            audio_io.name = "voice.ogg"  # give it a name so OpenAI knows the format

            transcription = self.client.audio.transcriptions.create(
                model=model,
                file=audio_io,
                language=language
            )
            return transcription.text
        except Exception as err:
            print(f"Error during transcription: {err}")
            return "Error: Could not transcribe audio."


if __name__ == "__main__":
    # Example usage
    transcriber = OpenAITranscriber()
    text = transcriber.transcribe("example_audio.mp3", language="en")
    print("Transcription:", text)
