# HAL 9000 Voice Satellite

## What this is

This project is a fork of
[campwill/hal-voice-assistant](https://github.com/campwill/hal-voice-assistant), adapted into a
small, hardware-agnostic HAL 9000 voice satellite for Raspberry Pi and other Linux SBCs. The
satellite detects a wake word, records and plays audio, controls simple GPIO lighting, and calls
services on your network. Compute-heavy STT, LLM, TTS, automation, and future
recognition/orchestration workloads stay on Home Assistant or a homelab server.

The primary target is a Raspberry Pi 3B+, but there are no Pi-model, ReSpeaker, Pico W, MQTT,
or fixed audio-index assumptions. A Pi Zero 2 W, Pi 3A+, Pi 4, another Linux SBC, or a Linux
development machine can use the same client. Development machines should use null lighting.

## Fork lineage and direction

This fork builds directly on campwill's original HAL 9000 project and physical build. The
original project established the core interaction flow—Porcupine wake-word detection, local
recording and playback, and network-hosted Vosk, Ollama, and Piper services—and demonstrated it
in a wonderfully convincing HAL enclosure. That work remains the foundation of this project,
and the original repository is the best place to see the build that inspired it.

The purpose of this fork is to preserve that character and working direct-service flow while
making the software easier to adapt and extend. In particular, this fork aims to:

- support generic Linux audio devices instead of requiring a ReSpeaker HAT or fixed indexes;
- support Raspberry Pi models and other Linux SBCs without model-specific assumptions;
- split the original single-file application into small configuration, audio, wake-word,
  lighting, STT, conversation, and TTS modules;
- drive GPIO lighting from explicit assistant states, with a null backend for development;
- add Home Assistant conversation support alongside the original direct Vosk/Ollama/Piper mode;
- provide diagnostic scripts, environment-based configuration, service deployment, and clear
  hardware guidance; and
- leave clean extension points for future Assist pipeline, orchestration, camera, and lighting
  features without moving heavy inference onto the satellite.

This is an evolution of the original idea, not a claim of independent origin. Thanks to
[campwill](https://github.com/campwill) for publishing the project and making this fork possible.

## Architecture

```text
HAL Pi / Linux SBC
  - wake word
  - USB mic / speaker
  - GPIO LEDs
  - local recording/playback
        |
        | HTTP / WebSocket
        v
Home Assistant + homelab services
  - conversation agent
  - automations
  - thermostat/lights/entities
  - Vosk STT
  - Piper TTS
  - Ollama / GPU LLM
```

Two modes are supported:

- `direct`: Vosk STT -> Ollama -> Piper TTS.
- `home_assistant_conversation`: Vosk STT -> Home Assistant conversation API -> Piper TTS.

The Home Assistant Assist audio pipeline WebSocket mode is intentionally left for a later pass.

## Recommended hardware

- Raspberry Pi 3B+ or similar Linux SBC, microSD card, and suitable 5 V power supply
- USB microphone, USB headset, USB speakerphone, webcam mic, or USB audio dongle
- Speaker output over USB, HDMI, Pi analog audio out, or Bluetooth
- One red LED and suitable resistor for HAL's eye
- Optional white LEDs with an appropriate driver circuit
- Optional camera for future server-side recognition

The recommended split setup is a 3.5 mm microphone connected through a USB audio adapter,
with the Pi 3.5 mm output connected to a powered speaker. A USB speakerphone or USB headset is
often easiest because it provides standard ALSA/PyAudio input and output in one device.

## Audio notes

Raspberry Pi boards such as the Pi 3B+ do **not** have a native analog microphone input. A
plain 3.5 mm analog microphone will not work in the Pi headphone jack. Connect it through a
USB audio dongle, or use a USB mic, headset, speakerphone, or webcam mic.

Audio input and output are resolved independently. An explicit device index wins, followed by
a case-insensitive device name hint, then the PyAudio default. Indexes may change after a reboot,
so name hints are usually more durable. Bluetooth can work, but USB or wired output is a better
choice for the first reliable build.

Use `python scripts/list_audio_devices.py` to see indexes, channel counts, sample rates, and
default devices. Use `python scripts/test_mic_level.py` to tune `SILENCE_RMS_THRESHOLD`.

## LED notes

The light controller uses BCM GPIO numbering. Red and white channels are both optional, but at
least one must be configured when `LIGHT_BACKEND=gpio`. PWM provides dimming and pulse effects;
plain digital LEDs approximate pulses with blinking. Every effect follows assistant state and
runs in one replaceable background animation.

Raspberry Pi GPIO pins are 3.3 V logic pins. Use GPIO for signal/control; do not power
high-current LEDs, multiple bright LEDs, or LED strips directly from GPIO.

For one small indicator LED:

```text
GPIO pin -> suitable series resistor -> LED anode
LED cathode -> GND
```

For a brighter load or an external 5 V/12 V supply:

```text
GPIO pin -> resistor -> MOSFET/transistor gate/base
external supply -> LED/resistor/load -> MOSFET/transistor -> GND
Pi GND connected to external supply GND
```

Choose the resistor from supply voltage, LED forward voltage, and desired current. Do not
connect a high-current load directly to a GPIO pin.

## Setup

On Raspberry Pi OS or Debian Linux:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip portaudio19-dev libasound2-dev alsa-utils git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/list_audio_devices.py
python scripts/test_mic_level.py
python scripts/test_audio_record.py
python scripts/test_audio_playback.py
python scripts/test_gpio_lights.py
python app.py
```

Edit `.env` before running the tests. Set input/output indexes or name hints, backend service
URLs, GPIO pins, and a Picovoice access key/model path. The included custom model is an example;
Porcupine models must match the platform/runtime version in use.

Useful diagnostics:

```bash
python scripts/test_audio_record.py --seconds 5 --output /tmp/hal_test.wav
python scripts/test_audio_playback.py /tmp/hal_test.wav
python scripts/test_wakeword.py
python scripts/test_ha_conversation.py "turn on the office light"
```

## Home Assistant setup

Create a Home Assistant Long-Lived Access Token and put it in `.env` as `HA_TOKEN`; never commit
the token. Set `HA_URL` and start with:

```env
HAL_MODE=home_assistant_conversation
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your-token
HA_LANGUAGE=en
HA_CONVERSATION_ID=hal-office
```

Home Assistant can route the text through its chosen conversation agent, Ollama integration,
intents, and automations. Expose only a small, safe set of entities to any LLM/conversation
agent. `HA_CONVERSATION_ID` should remain stable for a given HAL device so conversations can
retain context.

## Direct mode setup

Run Vosk's WebSocket server, Ollama, and a Piper-compatible streaming HTTP server elsewhere,
then configure their reachable addresses:

```env
HAL_MODE=direct
VOSK_URL=ws://server:2700
OLLAMA_URL=http://server:11434/api/generate
OLLAMA_MODEL=llama3:latest
PIPER_URL=http://server:5000
```

The Pi records mono 16-bit PCM, sends the WAV to Vosk, sends the transcript to Ollama, streams
raw mono 16-bit PCM from Piper, and plays it locally at `TTS_SAMPLE_RATE`.

## Development mode

To develop without GPIO or a Picovoice key:

```env
WAKEWORD_DISABLED=true
LIGHT_BACKEND=null
OUTPUT_WAV_PATH=hal_prompt.wav
```

Run `python app.py` and press Enter to simulate a wake word. Network services and an audio input
are still required for a complete interaction. The null backend logs state changes and never
imports GPIO libraries.

## Service installation

The sample unit assumes a production checkout at `/opt/hal-voice-assistant`. Development can
remain anywhere. If you use another production path or Linux user, edit the unit first.

```bash
sudo cp systemd/hal-voice-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hal-voice-assistant
sudo journalctl -u hal-voice-assistant -f
```

## Future hooks

Future work belongs behind small interfaces or on a server: Home Assistant Assist pipeline
WebSocket mode, a Hermes/orchestrator endpoint, camera snapshot capture, server-side face
recognition, and voice-level LED animation. None of those workloads run locally in this pass.
