from google.genai import types
import re
from multiprocessing import Process, Queue, set_start_method
import numpy as np
import sounddevice as sd
import kokoro
import torch
import threading
from models import constants

class TextToSpeech:
    """Convert text to speech using multiple Kokoro workers."""
    def __init__(self) -> None:
        set_start_method('spawn', force=True)
        self.input_q = Queue()
        self.output_q = Queue()
        self.workers: list[Process] = []
        self.audio_handler_thread: threading.Thread | None = None
        self.processing_chunks = False # flag to indicate if currently processing chunks
        self._start_kokoro_workers() # start multiple Kokoro workers

    @staticmethod
    def _extract_sentences(text: str) -> list[str]:
        """Extract sentences from text using regex."""
        sentence_endings = re.compile(r'(?<=[.!?]) +')
        sentences = sentence_endings.split(text.strip())
        return [s for s in sentences if s]

    @staticmethod
    def _kokoro_worker(input_q: Queue, output_q: Queue, worker_id: int):
        """Continuously process items from input_q and push results to output_q.
        Now expects items of the form (seq, sentence) and will put (seq, audio) on output_q.
        """
        print(f"Worker {worker_id} starting")
        # Initialize pipeline inside the worker (safe for spawn/forkserver start methods)
        pipeline = kokoro.KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
        while True:
            item = input_q.get()  # blocks until an item is available
            
            if item is None: # poison pill → graceful exit
                print(f"Worker {worker_id} shutting down")
                break
            # Expect (seq, sentence)
            seq, sentence = item
            print(f"Worker {worker_id} processing seq={seq}: {sentence[:20]}...")

            # Collect all audio chunks for this sentence and concatenate before sending
            audio_chunks = []
            for _, _, audio in pipeline(sentence, voice='af_bella', speed=1.0):
                if isinstance(audio, torch.Tensor):
                    audio = audio.detach().cpu().numpy()
                else:
                    audio = np.asarray(audio)
                audio_chunks.append(audio)

            if not audio_chunks:
                # put an empty array to preserve ordering if nothing was produced
                output_q.put((seq, np.array([], dtype=np.float32)))
            else:
                # Flatten and concatenate along the time axis
                try:
                    concatenated = np.concatenate([a.flatten() for a in audio_chunks], axis=0)
                except Exception:
                    concatenated = np.concatenate(audio_chunks, axis=0)
                output_q.put((seq, concatenated))

    @staticmethod
    def _audio_handler_worker(output_q: Queue):
        """Continuously read (seq, audio) items from output_q and play them in order."""
        sample_rate = 24000
        buffer: dict[int, np.ndarray] = {}
        current_sequence_number = 0

        while True:
            item = output_q.get()  # blocks until an item is available

            sequence, audio = item # extract sequence number and audio data
            buffer[sequence] = np.asarray(audio) # store in buffer
            
            # play buffered audio in order of sequence numbers
            while current_sequence_number in buffer:
                audio = buffer.pop(current_sequence_number) # get associated audio data

                # Play audio and wait for it to finish before continuing
                sd.play(audio, sample_rate, blocking=True) # play audio and wait for it to finish
                current_sequence_number += 1 # increment expected sequence number
        
    def _start_kokoro_workers(self) -> None:
        """Start multiple Kokoro worker processes."""
        for i in range(constants.n_kokoro_workers):
            p = Process(target=self._kokoro_worker, args=(self.input_q, self.output_q, i))
            p.start()
            self.workers.append(p)

    def _stop_kokoro_workers(self) -> None:
        """Stop all Kokoro worker processes."""
        for _ in self.workers:
            self.input_q.put(None)  # send poison pill to each worker
        for p in self.workers:
            p.join()
        self.workers = []
    
    def _start_audio_handler_worker(self):
        """Start the audio handler thread."""
        self.audio_handler_thread = threading.Thread(target=self._audio_handler_worker, args=(self.output_q,), daemon=True)
        self.audio_handler_thread.start()

    def _stop_audio_handler_worker(self):
        """Stop the audio handler thread."""
        if self.audio_handler_thread is None:
            return
        self.audio_handler_thread.join()

    def on_start_streaming_chunks(self) -> None:
        """Start handling streaming chunks from LLM."""
        assert not self.processing_chunks, "Should only be called when no chunks are being processed"
        self.streaming_buffer = ""
        self.current_seq = 0

        self._start_audio_handler_worker()
        self.processing_chunks = True

    def on_complete_streaming_chunks(self) -> None:
        """Stop handling streaming chunks from LLM."""
        if not self.processing_chunks:
            return
        
        self.streaming_buffer = ""
        self.current_seq = 0
        self._stop_audio_handler_worker()
        self.processing_chunks = False

    def handle_streaming_chunks(self, chunk: types.GenerateContentResponse) -> None:
        """Handle streaming chunks from LLM by enqueuing sentences for TTS processing."""
        if not self.processing_chunks:
            return
        
        # invalid chunk -> skip and pray the fucker terminates
        if chunk is None or chunk.text is None:
            return
        
        # append new text to buffer and extract sentences
        self.streaming_buffer += chunk.text
        sentences = self._extract_sentences(self.streaming_buffer)

        # incomplete sentences -> keep the last one in the buffer
        if sentences and not self.streaming_buffer.endswith(('.', '!', '?')):
            self.streaming_buffer = sentences.pop()
        else:
            self.streaming_buffer = ""
        
        # add each complete sentence to the input queue with its sequence number
        for sentence in sentences:
            self.input_q.put((self.current_seq, sentence))
            self.current_seq += 1