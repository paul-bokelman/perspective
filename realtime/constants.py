import pyaudio

# ---------------------------------- general --------------------------------- #

max_reconnection_attempts = 5
reconnection_delay_seconds = 1

# ------------------------------ audio constants ----------------------------- #
chunk_length_seconds = 0.05
sample_rate = 24000
format = pyaudio.paInt16
channels = 1
input_chunk_size = int(sample_rate * 0.02)
output_audio_fadeout_duration = 500 # milliseconds fade out to avoid clicks