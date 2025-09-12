import queue
import json
import threading
import sounddevice as sd
import vosk

class SpeechToText:
    def __init__(self, samplerate: int= 16000, blocksize: int= 8000, dtype: str = "int16", channels: int = 1):
        model = vosk.Model("models/local/vosk-small")
        self.recognizer = vosk.KaldiRecognizer(model, 16000)

        self.samplerate = samplerate
        self.blocksize = blocksize
        self.dtype = dtype
        self.channels = channels
        self.data_queue = queue.Queue()
        self.transcription_queue = queue.Queue()
        self.stream = None
        self.running = False
        self.thread = None

    def _callback(self, data, frames, time, status):
        if status:
            print("Stream status:", status)
        self.data_queue.put(bytes(data))

    def _worker(self):
        """Background thread: fetch audio chunks and send to recognizer."""
        while self.running:
            data = self.data_queue.get()
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                if result.get("text"):
                    print("Final:", result["text"])
                    self.transcription_queue.put(result["text"])
            else:
                partial = json.loads(self.recognizer.PartialResult())
                if partial.get("partial"):
                    print("Partial:", partial["partial"])

    def start(self):
        """Start a transcription session."""
        if self.stream is not None:
            print("Already recording!")
            return
        self.stream = sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype=self.dtype,
            channels=self.channels,
            callback=self._callback,
        )
        self.stream.start()
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        print("🎤 Recording + recognition started...")

    def stop(self):
        if self.stream is None:
            print("Not recording!")
            return
        self.running = False
        self.stream.stop()
        self.stream.close()
        self.stream = None
        if self.thread is not None:
            self.thread.join(timeout=1)
            self.thread = None
        print("🛑 Recording stopped.")