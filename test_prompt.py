import os
import sys
import base64
import mimetypes
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from openai import OpenAI


SYSTEM_PROMPT = """
You are an OCR-style chat transcript extractor.

Your only task is to extract visible messages from chat screenshots and convert them into a clean dialogue transcript.

Strict operating rules:
1. The screenshots contain a messenger dialogue.
2. Read messages strictly from top to bottom in chronological order.
3. Determine the speaker ONLY from visual evidence:
   - message bubble position,
   - message bubble alignment,
   - message bubble color/style,
   - visible avatar/name if present.
4. Use a deterministic mapping:
   - all bubbles on the RIGHT side are user1
   - all bubbles on the LEFT side are user2
   If a screenshot clearly indicates the opposite by visible names/avatars, still keep the mapping consistent inside the whole output.
5. Extract ONLY message text that is actually visible on the screenshot.
6. Never invent hidden, cropped, or implied text.
7. Never summarize.
8. Never paraphrase.
9. Never translate.
10. Preserve the original language exactly. The dialogue is in Russian.
11. Preserve punctuation, emojis, slang, spelling mistakes, and line breaks inside a message when visible.
12. Ignore all interface elements that are not part of the message text:
    - time labels,
    - battery,
    - signal,
    - input field,
    - "typing..." indicators,
    - check marks,
    - delivery/read status,
    - buttons,
    - stickers without readable text,
    - reactions unless they contain readable text.
13. If part of a message is unreadable, replace only that fragment with [unclear].
14. If a message is fully unreadable, skip it.
15. Treat each visible message bubble as a separate message.
16. Do not merge neighboring bubbles unless they are clearly one single bubble.
17. If multiple screenshots are provided, continue the same speaker mapping across all screenshots.
18. Output only the final transcript and nothing else.

Required output format:
user1: <message>
user2: <message>
user1: <message>

No markdown.
No explanations.
No notes.
No confidence scores.
"""

USER_PROMPT = """
Task: perform strict visual extraction of a Russian messenger conversation.

Important:
- This is NOT an image description task.
- This is NOT a summarization task.
- This is NOT a reasoning task about the conversation.
- This is a transcription task.

You must behave like a screenshot transcript extractor.

Rules:
- Extract only the text visible inside message bubbles.
- Use speaker mapping:
  RIGHT bubble -> user1
  LEFT bubble -> user2
- Keep exact order.
- Keep Russian text exactly as seen.
- Keep emojis and punctuation.
- Do not fix spelling.
- Do not add missing words.
- Do not output anything except transcript lines.

Correct output example:
user1: привет
user2: и тебе привет
user1: как дела?
user2: хорошо, а у тебя?
"""


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"image/png", "image/jpeg"}:
        raise ValueError(
            f"Unsupported image type for {path.name}. "
            f"Use PNG, JPG or JPEG."
        )

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    parts = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "message":
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "output_text":
                    parts.append(content.text)

    return "\n".join(parts).strip()


def parse_proxy_file(proxy_file: str) -> str:
    """
    Supports 2 formats:

    1) Key-value:
        IP=1.2.3.4
        PORT=8080
        LOGIN=user
        PASSWORD=pass

    2) Four plain lines:
        1.2.3.4
        8080
        user
        pass
    """
    path = Path(proxy_file)
    if not path.exists():
        raise FileNotFoundError(f"Proxy file not found: {path}")

    raw_lines = path.read_text(encoding="utf-8").splitlines()
    lines = [line.strip() for line in raw_lines if line.strip() and not line.strip().startswith("#")]

    if not lines:
        raise ValueError("Proxy file is empty")

    if any("=" in line for line in lines):
        data = {}
        for line in lines:
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip().upper()] = value.strip()

        ip = data.get("IP")
        port = data.get("PORT")
        login = data.get("LOGIN")
        password = data.get("PASSWORD")
    else:
        if len(lines) < 4:
            raise ValueError(
                "Proxy file in plain format must contain 4 lines: "
                "IP, PORT, LOGIN, PASSWORD"
            )
        ip, port, login, password = lines[:4]

    if not all([ip, port, login, password]):
        raise ValueError(
            "Proxy config is incomplete. Required: IP, PORT, LOGIN, PASSWORD"
        )

    login_quoted = quote(login, safe="")
    password_quoted = quote(password, safe="")

    # HTTP proxy URL
    return f"http://{login_quoted}:{password_quoted}@{ip}:{port}"


def build_http_client(proxy_url: str | None, timeout_seconds: float) -> httpx.Client:
    if proxy_url:
        return httpx.Client(
            proxy=proxy_url,
            timeout=httpx.Timeout(timeout_seconds),
            trust_env=False,
        )

    return httpx.Client(
        timeout=httpx.Timeout(timeout_seconds),
        trust_env=False,
    )


def main() -> None:
    load_dotenv()

    api_key = require_env("AI_API_KEY")
    base_url = os.getenv("AI_API_BASE_URL", "https://api.x.ai/v1")
    model = os.getenv("AI_VISION_MODEL") or os.getenv("AI_DEFAULT_MODEL")
    if not model:
        raise RuntimeError("Set AI_VISION_MODEL or AI_DEFAULT_MODEL in .env")

    max_output_tokens = int(os.getenv("AI_MAX_TOKENS", "2048"))
    temperature = float(os.getenv("AI_TEMPERATURE", "0.8"))
    timeout_seconds = float(os.getenv("AI_REQUEST_TIMEOUT", "60"))

    proxy_file = os.getenv("PROXY_FILE", "proxy.txt")
    proxy_url = None

    if Path(proxy_file).exists():
        proxy_url = parse_proxy_file(proxy_file)
        print(f"[INFO] Proxy enabled from file: {proxy_file}")
    else:
        print(f"[INFO] Proxy file not found, sending requests directly: {proxy_file}")

    http_client = build_http_client(proxy_url=proxy_url, timeout_seconds=timeout_seconds)

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=http_client,
    )

    image_paths = ["test1.jpg"]
    base_path = "C:\\Users\\McHomak\\Projects\\chat_help_bot\\image"

    user_content = []
    for image_path in image_paths:
        image_path = os.path.join(base_path, image_path)
        print(image_path)
        user_content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(image_path),
                "detail": "high",
            }
        )

    user_content.append(
        {
            "type": "input_text",
            "text": USER_PROMPT,
        }
    )

    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.strip(),
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            store=False,
        )

        result = extract_output_text(response)

        print("\n=== TRANSCRIPT ===\n")
        print(result if result else "[empty response]")

    except Exception as e:
        print(f"Request failed: {e}")
        sys.exit(2)
    finally:
        http_client.close()


if __name__ == "__main__":
    main()