"""Configuration constants."""
import json
import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────
BASE_DIR = Path(os.environ.get("FLOW_AGENT_DIR", Path(__file__).parent.parent))
# FK-LOCAL: allow an isolated DB (E2E tests) via FLOWKIT_DB_PATH
# Runtime data (database, uploaded idea images, QC frames) lives outside the code: FLOWKIT_DATA_DIR.
DATA_DIR = Path(os.environ.get("FLOWKIT_DATA_DIR") or BASE_DIR)
DB_PATH = Path(os.environ["FLOWKIT_DB_PATH"]) if os.environ.get("FLOWKIT_DB_PATH") else DATA_DIR / "flow_agent.db"

# ─── API Server ──────────────────────────────────────────────
API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "8110"))

# ─── WebSocket Server (extension connects here) ─────────────
WS_HOST = os.environ.get("WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("WS_PORT", "9233"))  # FK-HARDEN: was 9222 (Chrome DevTools default)


# ─── Flow batchexecute ──────────────────────────────────────
# Every call is signed in the page with the session cookie plus a per-page `at`
# token, so the extension runs it inside a signed-in flow.google.com tab. This
# is the only transport; the REST path it replaced was removed once Flow stopped
# minting the bearer it needed.

# The Flow project every RPC is scoped to. Project creation went with the old
# labs.google tRPC endpoint, so a project is made once in the Flow UI and its
# uuid pinned here; POST /api/projects falls back to it when no id is given.
FLOW_PROJECT_ID = os.environ.get("FLOW_PROJECT_ID", "")

# Capabilities whose payloads were never captured off the new UI (4K upscale,
# reference-to-video, start+end-frame chaining) fail loudly by default. With
# this on, the two that have a sane fallback degrade instead: chaining and r2v
# both drop to plain i2v off the start frame. Upscale has no fallback.
FLOW_ALLOW_DEGRADED = os.environ.get("FLOW_ALLOW_DEGRADED", "0") == "1"

# Process-wide guard for every CAPTCHA-bearing generation submit, including
# direct API calls that bypass the background worker's limiter. Submits several
# seconds apart still drew PUBLIC_ERROR_UNUSUAL_ACTIVITY on a burst of 5 images;
# one at a time, ~15s apart, went through.
FLOW_GENERATION_MIN_INTERVAL_S = max(
    0.0, float(os.environ.get("FLOW_GENERATION_MIN_INTERVAL_S", "15"))
)
FLOW_GENERATION_MAX_CONCURRENT = max(
    1, int(os.environ.get("FLOW_GENERATION_MAX_CONCURRENT", "1"))
)
FLOW_UNUSUAL_ACTIVITY_COOLDOWN_S = max(
    0.0, float(os.environ.get("FLOW_UNUSUAL_ACTIVITY_COOLDOWN_S", "120"))
)
# Back-to-back blocks stretch the pause (×1, ×2.5, ×5 → 2, 5, 10 min); a request
# blocked this many times fails for good instead of waiting again.
FLOW_UNUSUAL_ACTIVITY_MAX_ATTEMPTS = 3
FLOW_SESSION_PROJECT_IDLE_S = max(
    300.0, float(os.environ.get("FLOW_SESSION_PROJECT_IDLE_S", "7200"))
)

# The tier no longer picks a model — aspect is its own slot and the model names
# are fixed — so it is only carried for the DB column and the dashboard.
DEFAULT_PAYGATE_TIER = os.environ.get("DEFAULT_PAYGATE_TIER", "PAYGATE_TIER_TWO")

# ─── Media Provider ─────────────────────────────────────────
# "flow" (default): generate via Google Flow through the Chrome extension.
# "assistant": route all generation to the AI assistant instead — each request
# is published as a row in the provider_job table and the worker waits for an
# external worker (the assistant) to claim and complete it via
# /api/provider-jobs. See agent/sdk/services/assistant_provider.py and
# agent/worker/assistant_worker.py for the full protocol.
# Default media provider for requests that don't specify one ("flow" |
# "assistant" | "muse2api" | any registered provider name). MEDIA_PROVIDER is kept as a
# legacy alias — DEFAULT_PROVIDER wins if both are set.
DEFAULT_PROVIDER = os.environ.get(
    "DEFAULT_PROVIDER", os.environ.get("MEDIA_PROVIDER", "flow")
).strip().lower()
MEDIA_PROVIDER = DEFAULT_PROVIDER  # legacy alias
ASSISTANT_PROVIDER_TIMEOUT_S = int(os.environ.get("ASSISTANT_PROVIDER_TIMEOUT_S", "1800"))
ASSISTANT_PROVIDER_POLL_S = int(os.environ.get("ASSISTANT_PROVIDER_POLL_S", "15"))
ASSISTANT_MAX_CONCURRENT = int(os.environ.get("ASSISTANT_MAX_CONCURRENT", "2"))
ASSISTANT_COOLDOWN_S = float(os.environ.get("ASSISTANT_COOLDOWN_S", "0"))

# "muse2api": render through a muse2api gateway (https://github.com/crisng95/muse2api),
# which fronts the muse.ai web app with an OpenAI-compatible API. The provider
# is registered always and becomes available once MUSE2API_URL is set; the key
# is the gateway's own MUSE2API_API_KEY. See agent/sdk/services/muse2api_provider.py.
MUSE2API_URL = os.environ.get("MUSE2API_URL", "").strip().rstrip("/")
MUSE2API_KEY = os.environ.get("MUSE2API_KEY", "")
MUSE2API_IMAGE_MODEL = os.environ.get("MUSE2API_IMAGE_MODEL", "muse-image")
MUSE2API_VIDEO_MODEL = os.environ.get("MUSE2API_VIDEO_MODEL", "muse-video")
MUSE2API_VIDEO_SECONDS = int(os.environ.get("MUSE2API_VIDEO_SECONDS", "8"))
# Covers the gateway's own failover (up to 3 accounts x its 240s/600s timeouts).
MUSE2API_TIMEOUT_S = float(os.environ.get("MUSE2API_TIMEOUT_S", "1800"))
MUSE2API_POLL_S = float(os.environ.get("MUSE2API_POLL_S", "5"))
MUSE2API_MAX_CONCURRENT = int(os.environ.get("MUSE2API_MAX_CONCURRENT", "2"))
MUSE2API_COOLDOWN_S = float(os.environ.get("MUSE2API_COOLDOWN_S", "0"))
# muse.ai takes a first frame only. With this on, chained scenes drop the end
# frame and r2v renders as i2v; off, both fail loudly (same rule as Flow).
MUSE2API_ALLOW_DEGRADED = os.environ.get("MUSE2API_ALLOW_DEGRADED", "0") == "1"

# ─── Worker ──────────────────────────────────────────────────
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
VIDEO_POLL_INTERVAL = int(os.environ.get("VIDEO_POLL_INTERVAL", "10"))  # polling interval for video/upscale status
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
VIDEO_POLL_TIMEOUT = int(os.environ.get("VIDEO_POLL_TIMEOUT", "420"))
# Omni Flash defaults used by the worker when a project's video_model_family
# is "omni_flash". Duration must be 4/6/8/10; resolution 360p or 720p.
OMNI_FLASH_DURATION_S = int(os.environ.get("OMNI_FLASH_DURATION_S", "8"))
OMNI_FLASH_RESOLUTION = os.environ.get("OMNI_FLASH_RESOLUTION", "720p")
# Flow provider pacing. Every generate mints a reCAPTCHA inside the Flow tab;
# firing them back-to-back from a background tab degrades the session score
# until Google answers PUBLIC_ERROR_UNUSUAL_ACTIVITY. Slow down when that hits.
FLOW_MAX_CONCURRENT = int(os.environ.get("FLOW_MAX_CONCURRENT", "3"))
FLOW_COOLDOWN_S = float(os.environ.get("FLOW_COOLDOWN_S", "10"))
API_COOLDOWN = int(os.environ.get("API_COOLDOWN", "10"))  # DEPRECATED: per-provider cooldown_s in provider capabilities is authoritative
MAX_CONCURRENT_REQUESTS = int(os.environ.get("MAX_CONCURRENT_REQUESTS", "5"))  # DEPRECATED: per-provider max_concurrent in provider capabilities is authoritative
STALE_PROCESSING_TIMEOUT = int(os.environ.get("STALE_PROCESSING_TIMEOUT", "600"))  # 10 min

# ─── Model Keys (loaded from models.json for easy updates) ──
_MODELS_FILE = Path(__file__).parent / "models.json"
with open(_MODELS_FILE, encoding="utf-8") as _f:
    _MODELS = json.load(_f)

VIDEO_MODELS = _MODELS["video_models"]
UPSCALE_MODELS = _MODELS["upscale_models"]
IMAGE_MODELS = _MODELS["image_models"]
# Nickname from image_models. Known aliases live in models.json, while the
# batch path also accepts syntactically valid Flow wire model ids directly so
# newly introduced image models do not require a Flow Kit release.
DEFAULT_IMAGE_MODEL = _MODELS.get("default_image_model", "NANO_BANANA_PRO")

# ─── Output Directories ─────────────────────────────────────
# Every project's files (assets, clips, final film) go to OUTPUT_DIR/<project folder>/: FLOWKIT_OUTPUT_DIR.
OUTPUT_DIR = Path(os.environ.get("FLOWKIT_OUTPUT_DIR") or BASE_DIR / "output")
SHARED_OUTPUT_DIR = OUTPUT_DIR / "_shared"
TTS_TEMPLATES_DIR = SHARED_OUTPUT_DIR / "tts_templates"
MUSIC_OUTPUT_DIR = SHARED_OUTPUT_DIR / "music"

# ─── TTS (OmniVoice) ─────────────────────────────────────────
TTS_MODEL = os.environ.get("TTS_MODEL", "k2-fsa/OmniVoice")
TTS_DEVICE = os.environ.get("TTS_DEVICE", "cpu")  # MPS produces gibberish; CPU+fp32 works
TTS_SAMPLE_RATE = int(os.environ.get("TTS_SAMPLE_RATE", "24000"))

# ─── Review / Claude Vision ──────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REVIEW_MODEL = os.environ.get("REVIEW_MODEL", "claude-haiku-4-5-20251001")
REVIEW_FPS_LIGHT = float(os.environ.get("REVIEW_FPS_LIGHT", "4"))
REVIEW_FPS_DEEP = float(os.environ.get("REVIEW_FPS_DEEP", "8"))
REVIEW_MAX_FRAMES = int(os.environ.get("REVIEW_MAX_FRAMES", "64"))
REVIEW_SHEET_COLS = int(os.environ.get("REVIEW_SHEET_COLS", "3"))
REVIEW_SHEET_ROWS = int(os.environ.get("REVIEW_SHEET_ROWS", "3"))

# ─── CLI Providers (video review vision analysis) ────────────
_PROVIDERS_FILE = Path(__file__).parent / "providers.json"
with open(_PROVIDERS_FILE, encoding="utf-8") as _pvf:
    CLI_PROVIDERS = json.load(_pvf)  # mutable dict, hot-reloaded like VIDEO_MODELS
REVIEW_CLI_TIMEOUT_S = float(os.environ.get("REVIEW_CLI_TIMEOUT_S", "120"))

# ─── Suno (Music Generation) — sunoapi.org ──────────────────
def _load_suno_key() -> str:
    """Load Suno API key: env var first, then channel_rules.json fallback."""
    key = os.environ.get("SUNO_API_KEY", "")
    if key:
        return key
    channels_dir = BASE_DIR / "youtube" / "channels"
    if channels_dir.exists():
        for rules_file in channels_dir.glob("*/channel_rules.json"):
            try:
                rules = json.loads(rules_file.read_text(encoding="utf-8"))
                key = rules.get("api_keys", {}).get("suno", "")
                if key:
                    return key
            except (json.JSONDecodeError, OSError):
                continue
    return ""

SUNO_API_KEY = _load_suno_key()
SUNO_BASE_URL = os.environ.get("SUNO_BASE_URL", "https://api.sunoapi.org")
SUNO_MODEL = os.environ.get("SUNO_MODEL", "V4")
SUNO_CALLBACK_URL = os.environ.get("SUNO_CALLBACK_URL", f"http://{API_HOST}:{API_PORT}/api/music/callback")
SUNO_POLL_INTERVAL = int(os.environ.get("SUNO_POLL_INTERVAL", "5"))
SUNO_POLL_TIMEOUT = int(os.environ.get("SUNO_POLL_TIMEOUT", "600"))


# FK-LOCAL: AI director brain (headless `claude -p`) settings
# PROMPTS for a 120s film measured 224–334s per claude call, so 300s was too tight
DIRECTOR_CLAUDE_TIMEOUT_S = int(os.environ.get("DIRECTOR_CLAUDE_TIMEOUT_S", "900"))
# Model + effort per director role (docs/thiet-ke/model-theo-vai-tro.md). Spend Opus where judgement shapes the
# film (story, shot plan, review, sample analysis); Sonnet for template-heavy, machine-checked work; Haiku for
# classification. A role that fails validation or lint escalates to DIRECTOR_ESCALATE_MODEL on its retry.
# Override without code: DIRECTOR_ROLE_MODELS='{"dp": "opus"}', DIRECTOR_ROLE_EFFORT='{"writer": "max"}' in .env.
def _json_env(name: str) -> dict:
    raw = os.environ.get(name, "").strip()
    return json.loads(raw) if raw else {}


DIRECTOR_ROLE_MODELS = {
    "producer": "haiku",   # BRIEF: read the idea, fill a small brief (voice, language, length)
    "writer": "opus",      # STORY: story line, message, characters — the film's quality starts here
    "director": "opus",    # SHOTLIST: coverage, rhythm, physics; most lint failures happen here
    "dp": "sonnet",        # PROMPTS: fills the fixed template per shot; longest output; lint checks every line
    "editor": "opus",      # EDIT_REVIEW: the quality gate — must be at least as strong as the writer
    "reshoot": "sonnet",   # rewrites one failed clip's prompt
    "qc": "sonnet",        # looks at contact sheets of each finished clip
    "reviewer": "opus",    # Agent Review: the whole cut film, script → clips → seams → root causes (user-triggered)
    "coach": "sonnet",     # turns results/feedback into lessons (they feed every later prompt)
    "analyst": "opus",     # learns a sample film: story, shots, techniques
    "assistant": "sonnet", # the canvas "ask AI" bar: edits selected nodes on request (user may pick another model)
} | _json_env("DIRECTOR_ROLE_MODELS")
DIRECTOR_ROLE_EFFORT = {
    "producer": "low", "writer": "high", "director": "high", "dp": "medium", "editor": "high",
    "reshoot": "medium", "qc": "medium", "coach": "low", "analyst": "high", "assistant": "medium", "reviewer": "high",
} | _json_env("DIRECTOR_ROLE_EFFORT")
DIRECTOR_ESCALATE_MODEL = os.environ.get("DIRECTOR_ESCALATE_MODEL", "opus")
DIRECTOR_CREDIT_TABLE = {"image": 1, "video": 15}  # Omni Flash 10s ≈ 15  # editable credit estimate per generation
DIRECTOR_POLL_S = int(os.environ.get("DIRECTOR_POLL_S", "10"))
