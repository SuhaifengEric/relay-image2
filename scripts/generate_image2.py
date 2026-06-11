#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def safe_name(text: str, ext: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff._-]+", "-", text.strip())[:48]
    slug = slug.strip("-._") or "relay-image2"
    return f"{int(time.time())}-{slug}.{ext}"


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def resolve_url(base_url: str, endpoint: str) -> str:
    base = normalize_base_url(base_url)
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    return base + endpoint


def request_json(url: str, key: str, payload: dict | None, timeout: int, method: str = "POST"):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json,image/*",
        "User-Agent": "Codex relay-image2 skill",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            return resp.status, content_type, data
    except urllib.error.HTTPError as exc:
        data = exc.read()
        text = data.decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {text[:2000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc


def ext_from_content_type(content_type: str, fallback: str) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    guessed = mimetypes.guess_extension(media_type)
    if guessed:
        return guessed.lstrip(".").replace("jpeg", "jpg")
    return fallback


def looks_like_image(content_type: str, data: bytes) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return (
        media_type.startswith("image/")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"GIF87a")
        or data.startswith(b"GIF89a")
        or data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    )


def save_bytes(output_dir: Path, filename: str | None, prompt: str, data: bytes, ext: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = filename or safe_name(prompt, ext)
    path = output_dir / name
    path.write_bytes(data)
    return path.resolve()


def find_image_item(obj):
    if isinstance(obj, dict):
        if "data" in obj and isinstance(obj["data"], list) and obj["data"]:
            return obj["data"][0]
        return obj
    return None


def walk_json(obj):
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from walk_json(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_json(value)


def find_image(obj):
    for node in walk_json(obj):
        if isinstance(node, dict):
            if node.get("type") == "image_generation_call" and node.get("result"):
                return {"b64_json": node["result"]}
            for key in ("b64_json", "b64", "image", "result"):
                value = node.get(key)
                if isinstance(value, str) and len(value) > 1000 and not value.startswith("http"):
                    return {"b64_json": value}
            for key in ("url", "image_url", "output_url"):
                value = node.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    return {"url": value}
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.startswith("http"):
                            return {"url": item}
        elif isinstance(node, str):
            if node.startswith("http"):
                return {"url": node}
    return None


def find_task_id(obj):
    for node in walk_json(obj):
        if not isinstance(node, dict):
            continue
        for key in ("task_id", "taskId", "id"):
            value = node.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def find_status(obj):
    for node in walk_json(obj):
        if not isinstance(node, dict):
            continue
        for key in ("status", "state", "task_status"):
            value = node.get(key)
            if value is not None:
                return str(value)
    return None


def task_endpoints(task_id: str, custom_endpoints: list[str] | None = None) -> list[str]:
    encoded = urllib.parse.quote(task_id, safe="")
    defaults = [
        "/v1/tasks/{task_id}",
        "/v1/images/tasks/{task_id}",
        "/v1/images/generations/{task_id}",
    ]
    seen = set()
    endpoints = []
    for template in (custom_endpoints or []) + defaults:
        endpoint = template.strip()
        if not endpoint:
            continue
        if "{task_id}" in endpoint:
            endpoint = endpoint.replace("{task_id}", encoded)
        elif endpoint.endswith("/"):
            endpoint = endpoint + encoded
        elif task_id not in endpoint:
            endpoint = endpoint.rstrip("/") + "/" + encoded
        if endpoint not in seen:
            seen.add(endpoint)
            endpoints.append(endpoint)
    return endpoints


def download_url(url: str, timeout: int) -> tuple[str, bytes]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "image/*,*/*",
            "User-Agent": "Codex relay-image2 skill",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.headers.get("Content-Type", ""), resp.read()


def save_image_item(output_dir: Path, filename: str | None, prompt: str, item: dict, output_format: str, timeout: int, source: str, resolution: str, resolution_source: str, size: str, size_source: str) -> Path:
    if item.get("b64_json"):
        value = item["b64_json"]
        if isinstance(value, str) and value.startswith("data:image"):
            value = value.split(",", 1)[1]
        image_bytes = base64.b64decode(value)
        path = save_bytes(output_dir, filename, prompt, image_bytes, output_format)
        print(json.dumps({"path": str(path), "source": source, "resolution": resolution, "resolution_source": resolution_source, "size": size, "size_source": size_source}, ensure_ascii=False))
        return path

    if item.get("url"):
        img_type, image_bytes = download_url(item["url"], timeout)
        if not looks_like_image(img_type, image_bytes):
            raise RuntimeError(f"Downloaded URL is not an image. Content-Type: {img_type or 'unknown'}")
        ext = ext_from_content_type(img_type, output_format)
        path = save_bytes(output_dir, filename, prompt, image_bytes, ext)
        print(json.dumps({"path": str(path), "source": source, "resolution": resolution, "resolution_source": resolution_source, "size": size, "size_source": size_source}, ensure_ascii=False))
        return path

    raise RuntimeError(f"No image field found. Item keys: {list(item.keys())}")


def poll_task(base_url: str, key: str, task_id: str, output_dir: Path, filename: str | None, prompt: str, output_format: str, timeout: int, poll_timeout: int, poll_interval: float, resolution: str, resolution_source: str, size: str, size_source: str, task_endpoint_templates: list[str] | None = None) -> Path:
    deadline = time.time() + poll_timeout
    endpoints = task_endpoints(task_id, task_endpoint_templates)
    last_status = None
    last_error = None

    while time.time() < deadline:
        for endpoint in endpoints:
            url = resolve_url(base_url, endpoint)
            try:
                _, content_type, data = request_json(url, key, None, timeout, method="GET")
            except Exception as exc:
                last_error = exc
                continue

            if content_type.startswith("image/"):
                ext = ext_from_content_type(content_type, output_format)
                path = save_bytes(output_dir, filename, prompt, data, ext)
                print(json.dumps({"path": str(path), "source": "task-direct-bytes", "task_id": task_id, "resolution": resolution, "resolution_source": resolution_source, "size": size, "size_source": size_source}, ensure_ascii=False))
                return path

            text = data.decode("utf-8", errors="replace")
            obj = json.loads(text)
            item = find_image(obj)
            if item:
                return save_image_item(output_dir, filename, prompt, item, output_format, timeout, "task-result", resolution, resolution_source, size, size_source)

            status = find_status(obj)
            if status and status != last_status:
                print(json.dumps({"task_id": task_id, "status": status}, ensure_ascii=False), file=sys.stderr)
                last_status = status
            if status and status.lower() in {"failed", "error", "cancelled", "canceled"}:
                raise RuntimeError(f"Image task failed: {text[:2000]}")

        time.sleep(poll_interval)

    detail = f"; last error: {last_error}" if last_error else ""
    raise RuntimeError(f"Image task did not finish within {poll_timeout}s: {task_id}{detail}")


def infer_generation_params(prompt: str, resolution: str, size: str | None) -> tuple[str, str, str, str]:
    normalized = prompt.lower()
    compact = re.sub(r"\s+", "", normalized)
    if resolution != "auto":
        resolved_resolution = resolution
        resolution_source = f"explicit-{resolution}"
    elif re.search(r"(^|[^0-9])4\s*k([^a-z0-9]|$)", normalized) or any(token in compact for token in ["4k", "4096", "四千", "超高清", "超清", "最高分辨率", "最大分辨率"]):
        resolved_resolution = "4k"
        resolution_source = "prompt-4k"
    elif re.search(r"(^|[^0-9])2\s*k([^a-z0-9]|$)", normalized) or any(token in compact for token in ["2k", "2048", "两千", "高清", "高分辨率"]):
        resolved_resolution = "2k"
        resolution_source = "prompt-2k"
    elif re.search(r"(^|[^0-9])1\s*k([^a-z0-9]|$)", normalized) or any(token in compact for token in ["1k", "1024", "一千", "默认分辨率", "普通分辨率"]):
        resolved_resolution = "1k"
        resolution_source = "prompt-1k"
    else:
        resolved_resolution = "1k"
        resolution_source = "default-resolution"

    resolved_size = size or "1:1"
    size_source = "explicit-size" if size else "default-size"
    return resolved_resolution, resolution_source, resolved_size, size_source


def build_payload(mode: str, model: str, prompt: str, resolution: str, size: str) -> dict:
    if mode == "responses":
        return {
            "model": model,
            "input": prompt,
            "tools": [{"type": "image_generation", "resolution": resolution, "size": size}],
            "tool_choice": {"type": "image_generation"},
        }
    return {
        "model": model,
        "prompt": prompt,
        "resolution": resolution,
        "size": size,
        "response_format": "b64_json",
    }


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an image through a configured relay image2 API.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-dir", default="generated-images")
    parser.add_argument("--filename")
    parser.add_argument("--resolution", choices=["auto", "1k", "2k", "4k"], default="auto")
    parser.add_argument("--size")
    parser.add_argument("--output-format", default="png")
    parser.add_argument("--model")
    parser.add_argument("--responses-model", default=os.environ.get("RELAY_IMAGE2_RESPONSES_MODEL") or os.environ.get("RELAY_IMAGEGEN_RESPONSES_MODEL") or os.environ.get("SUB2API_RESPONSES_MODEL", ""))
    parser.add_argument("--image-model", default=os.environ.get("RELAY_IMAGE2_IMAGE_MODEL") or os.environ.get("RELAY_IMAGEGEN_IMAGE_MODEL") or os.environ.get("SUB2API_IMAGE_MODEL", "gpt-image-2"))
    parser.add_argument("--endpoint")
    parser.add_argument("--mode", choices=["auto", "responses", "images"], default="images")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--poll-timeout", type=int, default=240)
    parser.add_argument("--poll-interval", type=float, default=5)
    parser.add_argument("--task-endpoint", action="append", default=[], help="Task polling endpoint template. Use {task_id}. Can be repeated.")
    parser.add_argument("--confirmed", action="store_true", help="Required after the user confirms prompt, resolution, and size.")
    args = parser.parse_args()

    resolution, resolution_source, size, size_source = infer_generation_params(args.prompt, args.resolution, args.size)
    output_dir = Path(args.output_dir)

    if not args.confirmed:
        print(json.dumps({
            "needs_confirmation": True,
            "prompt": args.prompt,
            "resolution": resolution,
            "resolution_source": resolution_source,
            "size": size,
            "size_source": size_source,
            "message": "Confirm prompt, resolution, and size before rerunning with --confirmed.",
        }, ensure_ascii=False))
        return 3

    load_env_file(Path.home() / ".codex" / "relay-image2.env")
    load_env_file(Path.home() / ".codex" / "relay-imagegen.env")
    load_env_file(Path.home() / ".codex" / "sub2api-image2.env")
    base_url = os.environ.get("RELAY_IMAGE2_BASE_URL") or os.environ.get("RELAY_IMAGEGEN_BASE_URL") or os.environ.get("SUB2API_BASE_URL")
    key = os.environ.get("RELAY_IMAGE2_KEY") or os.environ.get("RELAY_IMAGEGEN_KEY") or os.environ.get("SUB2API_KEY")
    task_endpoint_templates = args.task_endpoint + split_csv(
        os.environ.get("RELAY_IMAGE2_TASK_ENDPOINTS")
        or os.environ.get("RELAY_IMAGEGEN_TASK_ENDPOINTS")
        or os.environ.get("SUB2API_TASK_ENDPOINTS")
    )
    if not base_url or not key:
        print(
            "Missing credentials. Set RELAY_IMAGE2_BASE_URL and RELAY_IMAGE2_KEY, "
            "or create ~/.codex/relay-image2.env. Legacy RELAY_IMAGEGEN_* and SUB2API_* names are also supported.",
            file=sys.stderr,
        )
        return 2

    def run(mode: str) -> Path:
        endpoint = args.endpoint or ("/v1/responses" if mode == "responses" else "/v1/images/generations")
        url = resolve_url(base_url, endpoint)
        model = args.model or (args.responses_model if mode == "responses" else args.image_model)
        if mode == "responses" and not model:
            raise RuntimeError("Responses mode requires --responses-model or RELAY_IMAGE2_RESPONSES_MODEL.")
        payload = build_payload(mode, model, args.prompt, resolution, size)

        _, content_type, data = request_json(url, key, payload, args.timeout)
        if content_type.startswith("image/"):
            ext = ext_from_content_type(content_type, args.output_format)
            path = save_bytes(output_dir, args.filename, args.prompt, data, ext)
            print(json.dumps({"path": str(path), "source": "direct-bytes", "mode": mode, "model": model, "resolution": resolution, "resolution_source": resolution_source, "size": size, "size_source": size_source}, ensure_ascii=False))
            return path

        text = data.decode("utf-8", errors="replace")
        obj = json.loads(text)
        item = find_image(obj)
        if item:
            return save_image_item(output_dir, args.filename, args.prompt, item, args.output_format, args.timeout, f"{mode}-image", resolution, resolution_source, size, size_source)

        task_id = find_task_id(obj)
        if task_id:
            print(json.dumps({"task_id": task_id, "mode": mode, "model": model}, ensure_ascii=False), file=sys.stderr)
            return poll_task(base_url, key, task_id, output_dir, args.filename, args.prompt, args.output_format, args.timeout, args.poll_timeout, args.poll_interval, resolution, resolution_source, size, size_source, task_endpoint_templates)

        item = find_image_item(obj)
        if isinstance(item, dict):
            raise RuntimeError(f"No image or task_id found. Item keys: {list(item.keys())}")
        raise RuntimeError(f"Unexpected JSON shape. Top-level keys: {list(obj) if isinstance(obj, dict) else type(obj).__name__}")

    try:
        mode = "images" if args.mode == "auto" else args.mode
        run(mode)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
