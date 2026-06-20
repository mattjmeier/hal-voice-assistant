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
so name hints are usually more durable. The container deployment supports direct ALSA devices
such as USB, HDMI, and Pi analog output. Use the native Pixi deployment for Bluetooth,
PulseAudio, or PipeWire integration.

Use `python scripts/list_audio_devices.py` to see indexes, channel counts, sample rates, and
default devices. Use `python scripts/test_mic_level.py` to tune `SILENCE_RMS_THRESHOLD`.

## Wake-word model

Wake-word detection runs locally with
[openWakeWord](https://github.com/dscripka/openWakeWord) and does not require an account or
access key. HAL expects a 16 kHz openWakeWord ONNX model. Place a model trained for "Hey HAL" at
`models/openwakeword/hey-hal.onnx`, or point `OPENWAKEWORD_MODEL_PATH` at another ONNX model.
The container mounts the checkout's `models` directory read-only so a locally supplied model is
available inside the published image.

The old Porcupine `.ppn` file is not reusable with openWakeWord. Use openWakeWord's upstream
training notebook or workflow to create the replacement model, and keep its source and license
with the artifact. Upstream's bundled pre-trained models are CC BY-NC-SA 4.0, while the runtime
code is Apache 2.0; do not redistribute a downloaded model without checking its own terms.

`OPENWAKEWORD_THRESHOLD` defaults to `0.5`. Raise it to reduce false activations or lower it to
reduce missed activations. Use `python scripts/test_wakeword.py` for room-level testing.

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

## Container setup

The supported appliance target is Raspberry Pi OS Lite 64-bit on a Pi 3B+ or newer. ARMv7 and
32-bit Raspberry Pi OS images are not supported. Install Docker Engine and the Compose plugin
using the [official Debian instructions](https://docs.docker.com/engine/install/debian/), then:

```bash
git clone https://github.com/mattjmeier/hal-voice-assistant.git
cd hal-voice-assistant
cp .env.example .env
# Edit .env before continuing.
docker compose pull
docker compose up -d
docker compose logs -f
```

Compose pulls `ghcr.io/mattjmeier/hal-voice-assistant:${HAL_IMAGE_TAG:-latest}`, uses host
networking, and passes only `/dev/snd` and `/dev/gpiochip0` into the container. It does not use
privileged mode. The root filesystem is read-only; transient recordings live in a `/tmp` tmpfs.
The restart policy brings the existing container back after Docker starts on reboot.

Edit `.env` before starting HAL. Set input/output indexes or name hints, backend service URLs,
GPIO pins, and `OPENWAKEWORD_MODEL_PATH`. Supply a compatible ONNX model as described above, or
set `WAKEWORD_DISABLED=true` for interactive development without wake-word detection.

Stop the main service before running hardware diagnostics so two processes do not claim the
same audio or GPIO device:

```bash
docker compose down
docker compose run --rm --entrypoint python hal scripts/list_audio_devices.py
docker compose run --rm --entrypoint python hal scripts/test_mic_level.py
docker compose run --rm --entrypoint python hal scripts/test_audio_record.py --seconds 5 --output /tmp/hal_test.wav
docker compose run --rm --entrypoint python hal scripts/test_audio_playback.py /tmp/hal_test.wav
docker compose run --rm --entrypoint python hal scripts/test_gpio_lights.py
docker compose run --rm --entrypoint python hal scripts/test_wakeword.py
```

The image is also published for `linux/amd64`. To build a fork locally instead, use:

```bash
docker build -t ghcr.io/mattjmeier/hal-voice-assistant:local .
HAL_IMAGE_TAG=local docker compose up -d
```

## Native Pixi setup

Pixi is the native fallback and uses the same locked environment as the image. On Raspberry Pi
OS or Debian Linux, install `git`, `alsa-utils`, and
[Pixi](https://pixi.sh/latest/installation/), then run:

```bash
git clone https://github.com/mattjmeier/hal-voice-assistant.git
cd hal-voice-assistant
pixi install --locked
cp .env.example .env
# Edit .env before continuing.
pixi run list-audio
pixi run test-mic
pixi run test-audio-record --seconds 5 --output /tmp/hal_test.wav
pixi run test-audio-playback /tmp/hal_test.wav
pixi run test-gpio
pixi run test-wakeword
pixi run start
```

The lock covers `linux-aarch64`, `linux-64`, and `win-64`. Windows development should use
`LIGHT_BACKEND=null`. Run `pixi run --environment dev lint` for static checks.

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

To develop without GPIO or a wake-word model:

```env
WAKEWORD_DISABLED=true
LIGHT_BACKEND=null
OUTPUT_WAV_PATH=hal_prompt.wav
```

Run `pixi run start` and press Enter to simulate a wake word. Network services and an audio
input are still required for a complete interaction. The null backend logs state changes and
never imports GPIO libraries.

## Service installation

The native sample unit assumes a Pixi-installed production checkout at
`/opt/hal-voice-assistant`. Development can remain anywhere. If you use another production path
or Linux user, edit the unit first.

```bash
# Clone or copy the repository to /opt/hal-voice-assistant, create .env, and run
# `pixi install --locked` as user pi before installing the unit.
sudo cp systemd/hal-voice-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hal-voice-assistant
sudo journalctl -u hal-voice-assistant -f
```

## Automation contract

Ansible is not required or maintained in this repository. Any deployment tool only needs to:

1. Provide a 64-bit Linux host with Docker Engine and Compose.
2. Place `compose.yaml` and a mode-`0600` `.env` file on the host.
3. Ensure `/dev/snd` and `/dev/gpiochip0` exist.
4. Select an immutable release tag with `HAL_IMAGE_TAG` for reproducible deployments.
5. Run `docker compose pull` followed by `docker compose up -d`.

Pushes to `main` publish `edge` and `sha-<commit>` tags. Tags matching `vX.Y.Z` publish semantic
version tags and `latest`. Production automation should pin a semantic version or commit tag
rather than `latest`. After the first publish, set the GHCR package visibility to public in its
GitHub package settings so unauthenticated machines can pull it.

## Future hooks

Future work belongs behind small interfaces or on a server: Home Assistant Assist pipeline
WebSocket mode, a Hermes/orchestrator endpoint, camera snapshot capture, server-side face
recognition, and voice-level LED animation. None of those workloads run locally in this pass.
