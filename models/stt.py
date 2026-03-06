import queue
import json
import threading
import sounddevice as sd
import vosk
from models import constants

class SpeechToText:
    def __init__(self):
        model = vosk.Model("models/local/vosk-small")
        self.recognizer = vosk.KaldiRecognizer(model, constants.stt_sample_rate)

        self.data_queue = queue.Queue() # store incoming audio data
        self.transcription_queue = queue.Queue() # store finalized transcriptions

        self.transcription_event = threading.Event() # flag to control transcription thread
        self.transcription_thread: threading.Thread | None = None

        self.stream = None

    def _stream_callback(self, data, frames, time, status):
        """Callback function to move incoming data to the data queue."""
        if status:
            print("Stream status:", status)
        self.data_queue.put(bytes(data))

    def _transcription_worker(self):
        """Background thread: fetch audio chunks and send to recognizer."""
        current_partial = ""
        while self.transcription_event.is_set():
            try:
                data = self.data_queue.get(timeout=0.1) # wait for data with timeout
            except queue.Empty:
                continue # no data -> loop back

            if self.recognizer.AcceptWaveform(data):
                result: dict = json.loads(self.recognizer.Result())
                if result.get("text"):
                    print("Final:", result["text"])
                    self.transcription_queue.put(result["text"])
                    current_partial = "" # reset current partial on final
            else:
                partial: dict = json.loads(self.recognizer.PartialResult())
                if partial.get("partial"): # update current partial every-time
                    print("Partial:", partial["partial"])
                    current_partial = partial["partial"]

        if current_partial: # send any remaining partial as final to avoid loss
            self.transcription_queue.put(f"PARTIAL: {current_partial}")

    def start(self):
        """Start a transcription session."""
        # transcribing -> don't attempt to start again
        if self.transcription_event.is_set():
            print("Already transcribing.")
            return
        
        print("Starting transcription...")
        self.stream = sd.RawInputStream(
            samplerate=constants.stt_sample_rate,
            blocksize=constants.stt_blocksize,
            dtype=constants.stt_dtype,
            channels=constants.stt_channels,
            callback=self._stream_callback,
        )
        self.stream.start()
        self.transcription_thread = threading.Thread(target=self._transcription_worker, daemon=True)
        self.transcription_event.set()
        self.transcription_thread.start()
        print("Transcription session started.")

    def stop(self):
        # not transcribing -> don't attempt to stop
        if not self.transcription_event.is_set():
            print("Not currently transcribing.")
            return
        
        print("Stopping transcription...")
        self.transcription_event.clear() # signal transcription thread to stop

        # stop and close the audio stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # wait for transcription thread to finish before cleaning up
        if self.transcription_thread: 
            self.transcription_thread.join(timeout=1)
            self.transcription_thread = None

        print("Transcription session ended.")

    def terminate(self):
        """Terminate the transcription session and clean up resources."""
        if self.transcription_event.is_set():
            self.stop()
        print("SpeechToText resources cleaned up.")

if __name__ == "__main__":
    import time
    stt = SpeechToText()
    stt.start()
    time.sleep(5)
    stt.stop()