# from models import stt, llm, tts
import threading
from models import stt, llm, tts
from agent import constants
from agent.memory import Memory

class STSPipeline:
    """Full end-to-end speech-to-speech pipeline with continuous listening and memory integration."""
    def __init__(self):
        self.listening = False
        self.recording = False
        self.paused = False
        self.stt = stt.SpeechToText()
        self.tts = tts.TextToSpeech()

        # memory worker
        self.memory = Memory()
        self.memory_thread_enabled = False
        self.memory_thread: threading.Thread | None = None

    def _memory_worker(self):
        """Background thread: process finalized transcriptions and store in memory."""
        current_chunk = "" # store a string of all transcriptions

        # continue processing while thread is enabled and either listening or recording
        while self.memory_thread_enabled and (self.listening or self.recording):
            transcription = self.stt.transcription_queue.get()

            # no transcription -> skip
            if not transcription:
                return
            
            # chunk size reached -> summarize and store in memory
            if len(current_chunk) >= constants.memory_chunk_size:
                cleaned_chunk = llm.summarize_transcriptions(current_chunk)
                self.memory.add(cleaned_chunk)
                current_chunk = transcription
            else: # add to current chunk otherwise
                current_chunk += "\n" + transcription

        # process any remaining transcriptions (may exceed chunk size - optimized for speed)
        while not self.stt.transcription_queue.empty():
            transcription = self.stt.transcription_queue.get()
            if transcription:
                current_chunk += "\n" + transcription

        cleaned_chunk = llm.summarize_transcriptions(current_chunk)
        self.memory.add(cleaned_chunk)

    def _start_memory_thread(self):
        """Start the background memory processing thread."""
        self.memory_thread_enabled = True
        self.memory_thread = threading.Thread(target=self._memory_worker, daemon=True)
        self.memory_thread.start()

    def _stop_memory_thread(self):
        """Stop the background memory processing thread."""
        self.memory_thread_enabled = False
        if self.memory_thread and self.memory_thread.is_alive():
            self.memory_thread.join()

    def start_listening(self):
        """Start continuous audio capture, transcription, and passive processing"""
        if self.listening:
            return
        
        self.listening = True
        self.stt.start() # start capturing audio and transcribing
        self._start_memory_thread() # process and store transcriptions in memory
    
    def stop_listening(self):
        """Stop continuous audio capture"""
        if not self.listening:
            return
        
        self.listening = False
        self.stt.stop()
        self._stop_memory_thread()
    
    def start_recording(self):
        """Start 'recording' audio until stop_recording is called"""
        # start capturing audio if not capturing (listening)
        if self.recording:
            return
        
        # no listening -> start stt session
        if not self.listening:
            self.stt.start()
        else: # already listening -> pause memory thread
            self._stop_memory_thread()

        self.recording = True
    
    def stop_recording(self):
        """Take the recorded audio transcription and relay to llm & tts"""
        if not self.recording:
            return
        
        self.recording = False
        self.paused = True
        self.stt.stop() # stop capturing audio during processing

        # extract all transcriptions from the recording queue
        transcriptions = ""
        while not self.stt.transcription_queue.empty():
            transcription = self.stt.transcription_queue.get()
            if transcription:
                transcriptions += "\n" + transcription

        # stream to tts for playback
        llm.stream_response(
            transcriptions,
            on_start=self.tts.on_start_streaming_chunks,
            on_chunk=self.tts.handle_streaming_chunks,
            on_complete=self.tts.on_complete_streaming_chunks
        )
        
        if self.listening:
            self._start_memory_thread() # resume memory thread if listening
            
        self.paused = False

    def terminate(self):
        """Terminate the entire pipeline, stopping all threads and processes."""
        self.stop_listening()
        self.stop_recording()
        self.stt.stop()
        self.tts._stop_kokoro_workers()
        self.tts._stop_audio_handler_worker()
    
if __name__ == "__main__":
    import time
    pipeline = STSPipeline()
    pipeline.start_recording()
    time.sleep(5)
    pipeline.stop_recording()
    pipeline.terminate()