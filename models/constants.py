from typing import Literal

# ------------------------------------ stt ----------------------------------- #
stt_sample_rate: int = 16000
stt_blocksize: int = 8000
stt_dtype: str = "int16"
stt_channels: int = 1

# -------------------------------- embeddings -------------------------------- #

embedding_dimension: Literal[768, 512, 256, 128, 64] = 768