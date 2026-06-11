---
name: "relay-image2"
description: "Use when the user asks Codex to generate an image through a configured OpenAI-compatible relay or 中转 API, especially requests containing image2, 生图, 画图, 生成图片, or 中转 API 生图. This skill calls a local relay image2 script, saves bitmap files, and can render them back to the user."
---

# relay image2

Generate images in Codex by calling the user's configured OpenAI-compatible relay / 中转 API for image2-style generation. The default script mode is `images`: it calls `/v1/images/generations` with `gpt-image-2`, while allowing each relay provider to override model names and task polling endpoints through env vars or CLI flags. The script requires explicit confirmation before creating an image task, sends `resolution` separately from `size`, handles async task responses, and downloads the final bitmap.

## Trigger

Use this skill when the user asks to generate an image through:

- `生图`
- `画图`
- `生成图片`
- `中转 API 生图`
- `image2`

Do not use it for built-in OpenAI image generation unless the user explicitly asks for the relay / 中转 API path.

## Required local config

The script reads credentials in this order:

1. Environment variables:
   - `RELAY_IMAGE2_BASE_URL`
   - `RELAY_IMAGE2_KEY`
2. Private env file:
   - `~/.codex/relay-image2.env`

The private env file format is:

```sh
RELAY_IMAGE2_BASE_URL=https://your-relay-host
RELAY_IMAGE2_KEY=your-key
# Optional provider-specific settings:
RELAY_IMAGE2_IMAGE_MODEL=gpt-image-2
RELAY_IMAGE2_TASK_ENDPOINTS=/v1/tasks/{task_id},/v1/images/tasks/{task_id}
```

Backward compatibility: the script also reads `RELAY_IMAGEGEN_*`, `SUB2API_*`, `~/.codex/relay-imagegen.env`, and `~/.codex/sub2api-image2.env` if the new relay-image2 names are not configured yet.

Never print the key. If credentials are missing, ask the user to create the env file or export the variables.

## Workflow

1. Convert the user's request into a clear image prompt. Preserve exact text, brand names, aspect ratio, resolution, and style requirements.
2. Choose an output directory:
   - If the user names one, use it.
   - Otherwise use `./generated-images` under the current workspace.
3. Prepare the generation parameters, but do not create a task yet:
   - `prompt`: the final image prompt that will be sent to the relay.
   - `resolution`: `1k`, `2k`, or `4k`; if the user says `4k`, pass `resolution=4k`.
   - `size`: aspect/size string; if the user does not give a specific size, use `1:1`.
4. Ask the user to confirm `prompt`, `resolution`, and `size` in one short message. Do not run the image generation task before the user confirms.
5. Optional parameter preview: run without `--confirmed`; the script exits without any API request and prints `needs_confirmation` JSON:

```bash
rtk python3 /Users/su/.codex/skills/relay-image2/scripts/generate_image2.py \
  --prompt "<prompt>" \
  --resolution 4k \
  --output-dir "<dir>"
```

6. After the user confirms, run the generation command with `--confirmed`:

```bash
rtk python3 /Users/su/.codex/skills/relay-image2/scripts/generate_image2.py \
  --mode images \
  --image-model gpt-image-2 \
  --prompt "<prompt>" \
  --resolution 4k \
  --size 1:1 \
  --output-dir "<dir>" \
  --confirmed
```

7. If the user explicitly asks to use the hosted Responses image tool, use `--mode responses` with a relay-supported text-capable Responses model. Do not use this path when the relay key only exposes image models:

```bash
rtk python3 /Users/su/.codex/skills/relay-image2/scripts/generate_image2.py \
  --mode responses \
  --responses-model "<available-responses-model>" \
  --prompt "<prompt>" \
  --resolution 4k \
  --size 1:1 \
  --output-dir "<dir>" \
  --confirmed
```

8. Inspect the returned JSON. A successful run prints `{"path": "...", ...}` to stdout. If the file is an image, show it inline with Markdown using the absolute path.
9. Report the saved path, final prompt, `resolution`, and `size` used.

## Options

The script supports:

```bash
--resolution auto
--resolution 1k
--resolution 2k
--resolution 4k
--size 1:1
--output-format png
--mode images
--mode auto
--mode responses
--image-model gpt-image-2
--responses-model <available-responses-model>
--task-endpoint /v1/tasks/{task_id}
--filename custom-name.png
--endpoint /v1/responses
--model <override-main-model>
--timeout 180
--poll-timeout 240
--poll-interval 5
--confirmed
```

Resolution rules:

- If the user says `1k`, `1K`, `一千`, `1024`, or asks for normal/default resolution, pass `--resolution 1k`.
- If the user says `2k`, `2K`, `两千`, `2048`, `高清`, or asks for higher resolution, pass `--resolution 2k`.
- If the user says `4k`, `4K`, `四千`, `4096`, `超清`, `超高清`, or asks for maximum/highest resolution, pass `--resolution 4k`.
- Never convert `4k` into `--size 4096x4096` or `--size 4096:4096`; `4k` is the `resolution` value.
- If the user gives an explicit size/aspect like `1:1`, `16:9`, or `1536x1024`, pass that exact value with `--size`.
- If the user does not mention size, pass `--size 1:1` after confirmation.
- If the user does not mention resolution, keep `--resolution auto`; the script defaults to `1k`.

Model rules:

- Default to `--mode images` and `--image-model gpt-image-2`.
- Do not hard-code provider-specific aliases in the skill. If a relay uses another image model name, set `RELAY_IMAGE2_IMAGE_MODEL` in `~/.codex/relay-image2.env` or pass `--image-model <provider-model>`.
- `--mode auto` is an alias for the default direct images path.
- Do not access `gpt-5.5` for ordinary image generation.
- Use `--mode responses` only when the user explicitly asks for the hosted Responses image tool and provides/has an available text-capable Responses model.
- Do not set the Responses `model` to `gpt-image-2`; in Responses mode the image model is invoked through the hosted image tool.
- If the relay returns model-permission errors or any API/task error, stop and report the problem. Do not keep trying alternate modes unless the user explicitly asks to retry with a specific mode.

Async task handling:

- Some relay `/v1/images/generations` responses return `{"status":"submitted","task_id":"..."}` under `data`.
- The script automatically polls configured task endpoints first, then common compatibility paths, until it sees an image or the task fails/times out.
- For provider-specific task APIs, set `RELAY_IMAGE2_TASK_ENDPOINTS` to comma-separated templates such as `/v1/tasks/{task_id},/task/{task_id}` or pass repeated `--task-endpoint` flags.
- The script recognizes nested results including `image_generation_call.result`, `b64_json`, direct `url`, and `result.images[].url[]`.
- Downloaded URLs are validated as image bytes before saving.

## Failure handling

- If HTTP status is not 2xx, report the status and compact response text without secrets.
- If the relay/API returns an error while creating or polling the image task, stop generation immediately and give the user a concise problem description.
- If the relay uses a nonstandard Responses endpoint, ask the user for the endpoint path.
- If task polling cannot find an image, summarize the compact JSON keys/status and ask for the provider's expected task-result response format.
- If the task is still pending after `--poll-timeout`, rerun with a larger timeout only if the user wants to keep waiting.
