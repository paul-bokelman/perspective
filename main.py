from models import stt, llm, tts
from agent import persona

persona = persona.load_local_personas()["eric"]

stt.listen(passive=True) # passively listen in the background

# start listening when hotkey is pressed
def on_listen_pressed():
    stt.start()

# stop listening when hotkey is released
def on_listen_released():
    transcription = stt.stop()
    assert isinstance(transcription, str), "Transcription should be a string"
    #todo: llm has to iterate some how
    text_response, tool_chain_proposal = llm.handle(transcription, persona=persona)
    tts.speak(text_response, persona=persona)

    # todo: wait for confirmation
    # todo: execute tool chain proposal
