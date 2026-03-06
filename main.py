from typing import Callable, Any
from types import CoroutineType
import asyncio
import base64
from uuid import uuid4
import numpy as np
import sounddevice as sd
import threading
import queue
from openai import AsyncOpenAI
from openai.resources.realtime.realtime import AsyncRealtimeConnection
from openai.types.realtime import RealtimeSessionCreateRequest
from textual import work
from textual.worker import Worker, WorkerState
from textual.app import App, ComposeResult
from textual.theme import Theme
from textual.widgets import Footer, Static
from textual.containers import Container, Vertical
from ui.signals import ToggleDisplaySignal
from ui.partials import PersonaSelectionPartial, SelectedPersonaSignal, PersonaInfoPartial, ConversationHistoryPartial, HelpPartial
from ui.components import  StateIndicator, BinaryStateProperty, RecordingIndicatorStates, ConnectionIndicatorStates
from utils import secrets
from agent import persona
from realtime import constants, prompts

class DerrickApp(App[None]):
    TITLE = "Derrick"
    CSS_PATH = "ui/ui.tcss"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        ("r", "toggle_recording", "Toggle Recording"),
        ("l", "toggle_listening", "Toggle Listening"),
        ("c", "cancel_response", "Cancel Response"),
        ("s", "switch_persona", "Switch Persona"),
        ("h", "toggle_help", "Toggle Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        # derrick state
        self.personas = persona.load_local_personas()
        self.initial_persona_key = list(self.personas.keys())[0]
        self.selected_persona = self.personas[self.initial_persona_key]

        # real-time state
        self.connection = None
        self.session: RealtimeSessionCreateRequest | None = None
        self.connected = asyncio.Event()
        self.ek, self.ek_expiry = secrets.get_ephemeral_key(persona=self.selected_persona)
        self.client = AsyncOpenAI(api_key=self.ek)
        self.remaining_connection_attempts = constants.max_reconnection_attempts
        self.last_client_message: Callable[..., CoroutineType] | None = None

        # workers
        self.recording = threading.Event()
        self.responding = threading.Event()
        self.response_queue = queue.Queue()
        self.record_worker_state: WorkerState | None = None
        self.playback_worker_state: WorkerState | None = None

        # UI state
        self.conversation_history_partial = ConversationHistoryPartial() # temporary, will be set on mount
        self.recording_indicator = StateIndicator(id="recording-indicator") # temporary, will be set on mount
        self.connection_indicator = StateIndicator(id="connection-indicator") # temporary, will be set on mount
        self.help_partial = HelpPartial(self.BINDINGS) # temporary, will be set on mount

    def on_mount(self) -> None:
        self.register_theme(Theme(name="derrick-theme", primary="#c1c1c1", dark=True, variables={
            "footer-key-foreground": "#FBCB97", "footer-description-foreground": "#c1c1c1",
        }))
        self.theme = "derrick-theme"
        self.conversation_history_partial = self.query_one(ConversationHistoryPartial)
        self.conversation_history_partial.display = False # start hidden (show help dialog first)
        self.recording_indicator = self.query_one("#recording-indicator", StateIndicator)
        self.connection_indicator = self.query_one("#connection-indicator", StateIndicator)
        self.help_partial = self.query_one(HelpPartial)
        self.run_realtime_worker()

    def compose(self) -> ComposeResult:
        with Container(id="main"):
            with Container(id="tl", classes="grid-container"):
                yield Static("PERSONA", classes="grid-container-title")
                yield PersonaInfoPartial(persona=self.selected_persona, id="active-persona-info-partial")
            with Container(id="right", classes="grid-container"):
                yield ConversationHistoryPartial()
                yield HelpPartial(self.BINDINGS)
            with Container(id="bl", classes="grid-container"):
                yield Static("INFO", classes="grid-container-title")
                with Vertical():
                    yield Static(f"Session ID: {str(uuid4())[:8]}", id="info-text")
                    yield Static(f"Memory Chunks: 212", id="memory-chunks-text")
                    yield Static(f"---", classes="grey")
                    yield BinaryStateProperty(id="memory-property", initial_state=0, label="Memory", locked=True)
                    yield BinaryStateProperty(id="shared-memory-property", initial_state=0, label="Shared Memory", locked=True)
                    yield BinaryStateProperty(id="listening-property", initial_state=1, label="Listening")
                    yield Static(f"---", classes="grey")
                    yield StateIndicator(id="recording-indicator", state=0, states=RecordingIndicatorStates, locked=True)
                    yield StateIndicator(id="connection-indicator", state=0, states=ConnectionIndicatorStates)

        yield Footer()

    # --------------------------------- internal --------------------------------- #

    def is_responding(self) -> bool:
        """Check if the app is currently responding"""
        return self.playback_worker_state == WorkerState.PENDING or self.responding.is_set() or not self.response_queue.empty()
    
    def is_recording(self) -> bool:
        """Check if the app is currently recording"""
        return self.record_worker_state == WorkerState.PENDING or self.recording.is_set()

    async def _cancel_response(self) -> bool:
        """Attempts to cancel the current response if on-going. Returns True if a response was cancelled, False otherwise."""
        if not self.is_responding():
            print("Not currently responding, nothing to cancel")
            return False

        connection = await self._get_connection()
        await self.send_rt_message(connection.response.cancel) #todo: ensure there is a response to cancel to avoid errors
        self.response_queue = queue.Queue() # clear the response queue
        self.responding.clear() # clear responding event to signal application (stop playback)
        return True

    # ---------------------------------- actions --------------------------------- #

    def action_toggle_listening(self) -> None:
        """Toggle listening state"""
        listening_property = self.query_one("#listening-property", BinaryStateProperty)
        listening_property.state = listening_property.get_next_state()
        listening_property.refresh()

    async def action_toggle_recording(self) -> None:
        """Toggle recording state"""

        # currently responding or not connected -> locked -> do nothing
        if self.is_responding() or not self.connected.is_set():
            print("Locked while responding or not connected")
            return
        
        connection = await self._get_connection()
        
        # recording event not set (not recording) -> start recording
        if not self.recording.is_set():
            self.run_record_worker()

            # hide the help dialog on first recording
            if self.help_partial.initial:
                self.help_partial.initial = False
                self.conversation_history_partial.display = True
                self.help_partial.display = False

        else: # recording event set -> stop recording
            self.recording.clear() # signal the recording thread to stop
            await self.send_rt_message(connection.input_audio_buffer.commit) # commit the audio buffer
            print('input_audio_buffer.commit')
            await self.send_rt_message(connection.response.create) # prompt a response from system
            print('response.create')
            await self.send_rt_message(connection.input_audio_buffer.clear) # clear the input audio buffer for next recording
            print('input_audio_buffer.clear')

        # update the recording indicator state
        self.recording_indicator.set_state(self.recording_indicator.get_next_state())

    def action_toggle_help(self) -> None:
        """Toggle the help dialog"""
        self.conversation_history_partial.display = not self.conversation_history_partial.display
        self.help_partial.display = not self.help_partial.display

    async def action_cancel_response(self) -> None:
        """Cancel the current response"""
        response_cancelled = await self._cancel_response()
        
        # response actually cancelled -> update the ui
        if response_cancelled:
            self.conversation_history_partial.remove_message_loader() # remove loading message (usually stopped when transcript done)
            self.conversation_history_partial.flag_last_message_cancelled() # flag the last message as cancelled

    def action_switch_persona(self) -> None:
        """Switch between personas"""
        if not self.query("#persona-selection-partial"):
            self.mount(PersonaSelectionPartial(personas=self.personas, id="persona-selection-partial"))

    def action_custom_quit(self) -> None:
        """A custom action that performs cleanup before quitting."""
        self.log("Performing custom cleanup before quitting...")
        self.exit()

    # ---------------------------------- signals --------------------------------- #

    def on_toggle_display_signal(self, message: ToggleDisplaySignal) -> None:
        """Handle toggle display signal to show/hide components."""
        component = self.query_one(message.target_id)
        component.display = not component.display

    async def on_selected_persona_signal(self, message: SelectedPersonaSignal) -> None:
        """Handle selected persona signal to update the active persona."""
        self.query_one("#active-persona-info-partial", PersonaInfoPartial).update_persona(message.persona)
        connection = await self._get_connection()
        await self.send_rt_message(lambda: connection.session.update(session={"type": "realtime", "instructions": prompts.construct(message.persona)}))
        self.selected_persona = message.persona
        self.conversation_history_partial.add_alert("switched persona")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when the worker state changes."""
        if event.worker.name == "record":
            self.record_worker_state = event.state
        elif event.worker.name == "playback":
            self.playback_worker_state = event.state

            # visually lock the recording indicator when playback starts, unlock when done
            match event.state: 
                case WorkerState.PENDING :
                    self.recording_indicator.show_lock()
                case WorkerState.SUCCESS | WorkerState.ERROR | WorkerState.CANCELLED:
                    self.recording_indicator.hide_lock()

        self.log(event)

    # --------------------------------- real-time -------------------------------- #

    async def send_rt_message(self, message: Callable[..., CoroutineType]):
        """Wrapper function to send a message to the real-time connection and store it as the last client message."""
        # todo: message itself is malformed??? 
        self.last_client_message = message
        await message()

    async def _get_connection(self) -> AsyncRealtimeConnection:
        """Get or wait for the real-time connection to be established."""
        await self.connected.wait()
        assert self.connection is not None, "Connection must be established"
        return self.connection

    @work
    async def run_realtime_worker(self) -> None:
        """Handle the real-time connection and events from the realtime API."""
        try:
            async with self.client.realtime.connect(model="gpt-realtime") as connection:
                connection._connection
                self.connection = connection
                self.connected.set()
                self.connection_indicator.set_state(1) # update ui to connected
                self.remaining_connection_attempts = constants.max_reconnection_attempts # reset reconnection attempts
                self.recording_indicator.hide_lock() # unlock the recording indicator
                self.conversation_history_partial.add_alert("connected")

                # listen and handle events from the server connection
                async for event in connection:
                    match event.type:
                        # handle or ignore incoming errors
                        case 'error': 
                            # server receives invalid json -> resend previous message and keep connection alive
                            if event.error.code == 'invalid_json':
                                if self.last_client_message is None: # no last message to resend -> exit
                                    break
                                print('WARNING: Resending last message due to invalid_json error')
                                await self.last_client_message()
                                continue

                            print(event.to_dict())
                            print(f"Realtime error: {getattr(event, 'error', event)}")
                            break

                        # session created (on start) -> store the session and print info
                        case 'session.created':
                            assert event.session.type == 'realtime'
                            assert isinstance(event.session.model, str), "No model name in session"
                            assert event.session.audio is not None
                            assert event.session.audio.output is not None
                            assert isinstance(event.session.audio.output.voice, str), "No voice in session audio output"
                            print("------ Session created ------")
                            print(f"Model: {event.session.model}")
                            print(f"Voice: {event.session.audio.output.voice}")
                            print(f"Ephemeral Key Expiry: {self.ek_expiry}")
                            print("-----------------------------")

                            self.session = event.session # store the session for later use

                            # update the session with the selected persona instructions (for retrying connections)
                            await self.send_rt_message(lambda: connection.session.update(session={
                                "type": "realtime", "instructions": prompts.construct(self.selected_persona)
                            }))

                        # server created a response -> start playback worker
                        case 'response.created':
                            self.conversation_history_partial.add_message_loader() # responding -> trigger loading
                            assert not self.recording.is_set(), "Cannot respond while recording"

                            # block playback worker until recording worker has fully stopped todo: possibly don't need this
                            while self.record_worker_state == WorkerState.RUNNING:
                                await asyncio.sleep(0.1) # wait for recording worker to stop if it's still running

                            self.responding.set() # set responding event to signal application
                            self.run_playback_worker() # start playback worker to stream audio

                        # server responding and sending audio chunks -> queue them for playback
                        case 'response.output_audio.delta':
                            self.response_queue.put_nowait(np.frombuffer(base64.b64decode(event.delta), dtype=np.int16))

                        # server added an output item (text, image, etc)
                        case 'response.output_item.added':
                            pass

                        # server finished the response -> stop the playback worker
                        case 'response.done':
                            self.responding.clear() # signal workers to stop playback (waits for queue to empty)

                        # output (system) transcription deltas
                        case 'response.output_audio_transcript.delta':
                            pass

                        # output (system) transcription done -> remove loading and display the transcript
                        case 'response.output_audio_transcript.done':
                            self.conversation_history_partial.remove_message_loader() # done responding -> stop loading
                            self.conversation_history_partial.add_message("derrick", event.transcript) # add the transcript to the chat

                        case _:
                            continue

        # handle unexpected errors -> update ui and attempt to restart the worker
        except Exception as e:
            print(f"An unexpected error occurred in the connection handler: {e}")
            self.conversation_history_partial.add_alert("error")
            self.conversation_history_partial.add_alert("disconnected")
            self.connection_indicator.set_state(0) # update ui to disconnected
            self.recording_indicator.show_lock() # unlock the recording indicator

            # reconnection attempts left -> clear connection state -> try to reconnect
            if self.remaining_connection_attempts > 0:
                self.remaining_connection_attempts -= 1
                self.connected.clear()
                self.connection = None
                print(f"Attempting to reconnect... ({self.remaining_connection_attempts} attempts left)")
                await asyncio.sleep(constants.reconnection_delay_seconds)
                self.run_realtime_worker() # restart the worker

    @work(name="playback", thread=True)
    def run_playback_worker(self):
        """Plays back audio chunks from the response queue."""
        assert self.responding.is_set(), "Cannot play audio when not responding"
        assert not self.recording.is_set(), "Cannot play audio while recording"

        stream = sd.OutputStream(channels=constants.channels, samplerate=constants.sample_rate, dtype='int16')
        stream.start()

        try:
            # continue playback while streaming response is active or there are queued audio chunks
            while self.responding.is_set() or not self.response_queue.empty():
                try:
                    data = self.response_queue.get_nowait()
                    stream.write(data)
                except queue.Empty:
                    sd.sleep(10)
                    continue
        except Exception as e:
            print(f"Error during playback: {e}")
        finally:
            print(f"Stopping playback...")

            # apply fadeout to avoid audio clicks
            fade_frames = int(constants.sample_rate * (constants.output_audio_fadeout_duration / 1000.0))
            silent_chunk = np.zeros((fade_frames, constants.channels), dtype='int16')
            stream.write(silent_chunk)

            stream.close()

    @work(name="record", thread=True)
    async def run_record_worker(self):
        """Records audio from the microphone and sends it to the server asynchronously."""
        assert not self.recording.is_set(), "Already recording"
        assert not self.responding.is_set(), "Cannot record while responding"
        
        self.recording.set() # signal the recording thread to be live

        stream = sd.InputStream(channels=constants.channels, samplerate=constants.sample_rate, dtype='int16', blocksize=constants.input_chunk_size)
        stream.start()
        
        connection = await self._get_connection()

        try:
            while self.recording.is_set():
                data, _ = stream.read(constants.input_chunk_size)
                await self.send_rt_message(lambda: connection.input_audio_buffer.append(audio=base64.b64encode(data).decode("utf-8")))
                print('input_audio_buffer.append')
        except Exception as e:
            print(f"Error during recording: {e}")
            
        stream.close()

if __name__ == "__main__":
    app = DerrickApp()
    app.run()