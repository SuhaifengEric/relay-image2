---
name: "relay-image2"
description: "Use when the user asks Codex to generate an image through a configured OpenAI-compatible relay or 中转 API, especially requests containing image2, 生图, 画图, 生成图片, or 中转 API 生图. This skill calls a local relay image2 script, saves bitmap files, and can render them back to the user."
---

# relay image2

Generate images in Codex by calling the user's configured OpenAI-compatible relay / 中转 API for image2-style generation. The default script mode is `auto`: it first tries `/v1/responses` with the hosted `image_generation` tool, then automatically falls back to the direct `/v1/images/generations` path when the relay key only exposes image models such as `gpt-image-2`. The script also handles async task responses and downloads the final bitmap.

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
```

Backward compatibility: the script also reads `RELAY_IMAGEGEN_*`, `SUB2API_*`, `~/.codex/relay-imagegen.env`, and `~/.codex/sub2api-image2.env` if the new relay-image2 names are not configured yet.

Never print the key. If credentials are missing, ask the user to create the env file or export the variables.

## Workflow

1. Convert the user's request into a clear image prompt. Preserve exact text, brand names, aspect ratio, resolution, and style requirements.
2. Choose an output directory:
   - If the user names one, use it.
   - Otherwise use `./generated-images` under the current workspace.
3. Run without `--size` by default so the script can infer 1k/2k/4k from the prompt. The default `--mode auto` is usually enough:

```bash
rtk python3 /Users/su/.codex/skills/relay-image2/scripts/generate_image2.py \
  --prompt "<prompt>" \
  --output-dir "<dir>"
```

4. If the user explicitly asks to use the direct image2 path, or if you already know Responses models are unavailable, use:

```bash
rtk python3 /Users/su/.codex/skills/relay-image2/scripts/generate_image2.py \
  --mode images \
  --image-model gpt-image-2 \
  --prompt "<prompt>" \
  --output-dir "<dir>"
```

5. Inspect the returned JSON. A successful run prints `{"path": "...", ...}` to stdout. If the file is an image, show it inline with Markdown using the absolute path.
6. Report the saved path and the final prompt used.

## Options

The script supports:

```bash
--resolution auto
--resolution 1k
--resolution 2k
--resolution 4k
--size 1024x1024
--output-format png
--mode auto
--mode responses
--mode images
--responses-model gpt-5.5
--image-model gpt-image-2
--filename custom-name.png
--endpoint /v1/responses
--model <override-main-model>
--timeout 180
--poll-timeout 240
--poll-interval 5
```

Resolution rules:

- If the user says `1k`, `1K`, `一千`, `1024`, or asks for normal/default resolution, use `1024x1024`.
- If the user says `2k`, `2K`, `两千`, `2048`, `高清`, or asks for higher resolution, use `2048x2048`.
- If the user says `4k`, `4K`, `四千`, `4096`, `超清`, `超高清`, or asks for maximum/highest resolution, use `4096x4096`.
- If the user gives an explicit size like `1536x1024`, pass that exact value with `--size`.
- If the user does not mention resolution, keep `--resolution auto`; the script defaults to 1k.

Model rules:

- In `auto` / `responses` mode, keep the Responses model as a text-capable model such as `gpt-5.5` unless the user gives another available mainline model.
- Do not set the Responses `model` to `gpt-image-2`; the image model is invoked through the hosted image tool.
- If the relay returns model-permission errors for the Responses model, `auto` mode falls back to `images` mode.
- In `images` mode, use `--image-model gpt-image-2` or `gpt-image-2-official` depending on what `/v1/models` exposes.

Async task handling:

- Some relay `/v1/images/generations` responses return `{"status":"submitted","task_id":"..."}` under `data`.
- The script automatically polls `/v1/tasks/{task_id}`, plus common compatibility paths, until it sees an image or the task fails/times out.
- The script recognizes nested results including `image_generation_call.result`, `b64_json`, direct `url`, and `result.images[].url[]`.
- Downloaded URLs are validated as image bytes before saving.

## Failure handling

- If HTTP status is not 2xx, report the status and compact response text without secrets.
- If the relay uses a nonstandard Responses endpoint, ask the user for the endpoint path.
- If `auto` falls back to `images` and task polling still cannot find an image, summarize the compact JSON keys/status and ask for the provider's expected task-result response format.
- If the task is still pending after `--poll-timeout`, rerun with a larger timeout only if the user wants to keep waiting.
