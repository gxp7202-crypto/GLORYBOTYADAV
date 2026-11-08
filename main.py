# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════
#  🇮🇳  YADAV LEVEL UP v6.0 — SQUAD + GUILD PREMIUM BOT  🇮🇳
#  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#     👑 Owner      : YADAV
#     🌏 Country    : India 🇮🇳
#     🎮 Mode       : Manual Squad Creation + Guild
#     ⚡ Version    : LEVEL UP EDITION v6.0
#     📅 Build      : 2026
#     🔐 Admin Pass : env ADMIN_PASSWORD (default "yadav1only")
#  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import sys, asyncio, httpx, random, json, socket, struct, time, os, uuid
import itertools, secrets, traceback, base64, ssl, threading, re, hashlib
import urllib.parse, urllib.request, urllib.error
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

try:
    from google_play_scraper import app as play_scraper
except Exception:
    play_scraper = None

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

try:
    from protobuf_decoder.protobuf_decoder import Parser
except Exception:
    Parser = None

try:
    from message_ids import MESSAGE_ID_TO_NAME
except Exception:
    MESSAGE_ID_TO_NAME = {}

try:
    import thunderFF_pb2
except Exception:
    thunderFF_pb2 = None

try:
    import CguFF_pb2
    _HAS_CGU = True
except Exception:
    _HAS_CGU = False

try:
    import requests as _requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    _requests = None

# ═══════════════════════════ CONFIG ═══════════════════════════
WEB_HOST = os.environ.get("HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("PORT", 20333))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "YADAV")
BRAND_WEB_NAME = "YADAV LEVEL UP"
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")

ACCOUNTS_FILE = "accounts.json"
TOKEN_CACHE_FILE = "token_cache.json"
DEVICES_FILE = "devices.json"
TOKEN_CACHE_TTL = 4500

NEW_MATCH_DELAY         = 6.0
MAX_MATCH_DURATION      = 3000
MATCH_IDLE_TIMEOUT      = 90.0
EXP_REFRESH_INTERVAL    = 30.0
EXP_REFRESH_AFTER_MATCH_DELAY = 9.0
NON_MATCH_RECONNECT_DELAY      = 1.0

BR_MODE_ID             = 1
BR_MAP_ID              = 1

ANTI_AFK_MIN_INTERVAL  = 1.8
ANTI_AFK_MAX_INTERVAL  = 3.5

MATCH_SEARCH_TIMEOUT   = 90.0
MATCH_WATCHDOG_CHECK   = 30.0

REGION_ROTATION_LIST   = ["IND", "IND", "IN", "SG", "TH", "MY"]
REGION_ROTATE_EVERY_N  = 2
MAX_SEARCH_ATTEMPTS    = 25
DEFAULT_REGION         = os.environ.get("DEFAULT_REGION", "IND")
DEFAULT_SERVER_CODE    = "BDC3"

SAFE_PLAY_MODE        = True
BYPASS_TIMING_JITTER  = True
BYPASS_PACKET_JITTER  = True
BYPASS_HELLO_DELAY    = True
BYPASS_KA_JITTER      = True

# ═══════════════════════════ ANTI-BAN ENGINE — SMART FAST SAFE ═══════════════════════════
# Speed alone never caused bans — *repeatable patterns* do. This engine keeps a fast
# 10–20s gap but destroys every pattern an anti-cheat could fingerprint:
#   • per-account phase offset   → accounts never march in lockstep
#   • micro-jitter on every gap  → no fixed interval ever repeats
#   • random human pauses        → "sip / scroll / stretch" moments
#   • per-UID persistent personality (device quirk, peak hours, break rhythm)
#   • staggered session rests    → forced off-time before fatigue flags
#   • proxy rotation per request → no single IP carries all accounts
#   • timing / packet / hello / KA jitter on the wire
# Locked to one profile on purpose. There is no faster, unsafe option any more.
ANTI_BAN_PROFILES = {
    "max": {
        "match_gap": (10.0, 20.0),   # fast, human-plausible
        "rest_after": 25,            # matches before a forced rest
        "rest": (90, 240),           # 1.5–4 min cool-down
        "afk_scale": 1.35,           # still moves while "AFK"
        "move_scale": 1.20,          # varied movement rhythm
        "micro_pause_chance": 0.18,  # random human hesitation
        "micro_pause": (1.0, 4.5),
        "stagger": (0.0, 12.0),      # first-match spread between accounts
        "session_cap": 5400,         # 90 min → long break
    },
}
ANTI_BAN_LEVEL = "max"          # locked — always max safety, fast pacing
DEFAULT_ANTI_BAN_LEVEL = "max"

# ═══════════════════════ ANTI-CHEAT LAYER STACK (17 layers) ═══════════════════════
# Every layer below is wired into the live play loop — none of them are decorative.
QUIET_HOURS          = (2, 7)          # local hours treated as "asleep"
QUIET_BREAK          = (1500, 4200)    # 25–70 min offline window
WARMUP_MATCHES       = 3               # first matches of a session are slower
WARMUP_MULTIPLIER    = (1.10, 1.25)
SESSION_JITTER       = (0.75, 1.35)    # each account gets its own session cap
MATCH_VARIETY        = [(1, 1), (1, 3), (2, 1), (1, 2)]  # (mode_id, map_id)
ERROR_BACKOFF_BASE   = 1.6
ERROR_BACKOFF_CAP    = 45.0

def _session_cap_for(uid: str) -> int:
    """Layer: per-account session length jitter — no two sessions end alike."""
    base = int(ANTI_BAN_PROFILES["max"].get("session_cap") or 5400)
    rnd = random.Random(f"cap:{uid}")
    return int(base * rnd.uniform(*SESSION_JITTER))

def warmup_multiplier(uid: str) -> float:
    """Layer: warm-up phase — new sessions ramp up like a real player."""
    runs = _antiban_match_runs.get(str(uid), 0)
    if runs < WARMUP_MATCHES:
        return random.uniform(*WARMUP_MULTIPLIER)
    return 1.0

def is_quiet_hours() -> bool:
    """Layer: human sleep cycle — being online at 4 AM every night is a flag."""
    return QUIET_HOURS[0] <= datetime.now().hour < QUIET_HOURS[1]

async def maybe_quiet_break(uid: str) -> bool:
    """Layer: night offline window. Returns True if a break happened."""
    if not is_quiet_hours():
        return False
    if _antiban_match_runs.get(str(uid), 0) % 4 != 0:
        return False
    rest = random.uniform(*QUIET_BREAK)
    try:
        bot_state.log_sync(uid, f"🌙 Quiet hours — offline {int(rest/60)}min", "info")
    except Exception:
        pass
    await asyncio.sleep(rest)
    return True

def pick_match_variation():
    """Layer: match cadence variety — ready→start timing never repeats.

    Squad packets stay wire-identical (that is what keeps matches working);
    what varies is the *human* pause before pressing ready and before the
    match request. Fixed cadence is a fingerprint; drifting cadence is not.
    """
    return {
        "ready_delay": round(random.uniform(0.35, 1.85), 2),
        "start_delay": round(random.uniform(0.08, 0.92), 2),
        "label": random.choice(MATCH_VARIETY),
    }

def rotate_ip_for_match():
    """Layer: fresh IP per match cycle, not just per request."""
    try:
        return next_proxy()
    except Exception:
        return None

def connection_backoff(attempt: int, base: float = ERROR_BACKOFF_BASE, cap: float = ERROR_BACKOFF_CAP) -> float:
    """Layer: full-jitter exponential backoff — no hammering, no fixed retry rhythm."""
    delay = min(cap, base ** max(1, attempt))
    return random.uniform(delay * 0.25, delay)

def device_fingerprint(uid: str) -> Dict[str, Any]:
    """Layer: stable per-UID device fingerprint (same device every session)."""
    try:
        return get_device_for_account(uid) or {}
    except Exception:
        return {}

ANTI_CHEAT_LAYERS = [
    ("per_account_stagger",  "Per-account stagger",      "Accounts never start in lockstep"),
    ("micro_jitter",         "Micro-jitter",             "No two gaps are ever equal"),
    ("human_pauses",         "Human pauses",             "Random sip / scroll / stretch"),
    ("personality",          "Persistent personality",   "Per-UID quirk, peak hours, rhythm"),
    ("warmup",               "Warm-up ramp",             "First matches of a session are slower"),
    ("staggered_cooldown",   "Staggered cool-down",      "Forced rest before fatigue flags"),
    ("session_jitter",       "Session jitter",           "Every session length differs"),
    ("quiet_hours",          "Sleep cycle",              "Offline during 2–7 AM"),
    ("match_variety",        "Match cadence",            "Ready→start timing drifts"),
    ("region_rotation",      "Region rotation",          "Search region drifts"),
    ("proxy_rotation",       "Proxy IP rotation",        "Fresh IP per request"),
    ("ip_per_match",         "IP per match",             "New IP for every match cycle"),
    ("device_fingerprint",   "Device fingerprint",       "Same device, same account"),
    ("packet_jitter",        "Packet jitter",            "Wire timing entropy"),
    ("hello_delay",          "Hello delay",              "Handshake is never instant"),
    ("ka_jitter",            "Keep-alive jitter",        "Heartbeat never beats in rhythm"),
    ("error_backoff",        "Error backoff",            "Full-jitter exponential retry"),
]

def anti_cheat_snapshot():
    out = []
    for key, label, desc in ANTI_CHEAT_LAYERS:
        out.append({"key": key, "label": label, "desc": desc, "on": True})
    return out


# ═══════════════════════════ NETWORK / PROXY ROTATION ═══════════════════════════
# Every outbound request can rotate through a proxy pool so no single IP carries
# all account traffic. Add proxies via env PROXY_LIST="http://user:pass@ip:port,..."
# or drop them one-per-line into proxies.txt. Supports http(s):// and socks5://.
PROXY_FILE = "proxies.txt"

def _load_proxies():
    import os as _os
    out = [p.strip() for p in _os.environ.get("PROXY_LIST", "").split(",") if p.strip()]
    if not out and _os.path.exists(PROXY_FILE):
        try:
            with open(PROXY_FILE, "r", encoding="utf-8") as f:
                out = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
        except Exception:
            out = []
    return out

PROXY_LIST = _load_proxies()
USE_PROXY = os.environ.get("USE_PROXY", "1" if PROXY_LIST else "0").lower() in ("1", "true", "yes", "on")
_proxy_cycle = itertools.cycle(PROXY_LIST) if (PROXY_LIST and USE_PROXY) else None
_proxy_index = {"i": 0}

# httpx renamed `proxies=` -> `proxy=` in 0.27; support both.
try:
    _HTTPX_MAJOR_MINOR = tuple(int(x) for x in httpx.__version__.split(".")[:2])
except Exception:
    _HTTPX_MAJOR_MINOR = (0, 27)
_HTTPX_PROXY_KW = "proxies" if _HTTPX_MAJOR_MINOR < (0, 26) else "proxy"

# ═══════════════════════════ ADVANCED ANTI-BAN FINGERPRINT ═══════════════════════════
# Each account gets a persistent "personality" that never changes across restarts.
# This makes behavioral analysis see consistent human patterns per UID.
_ACCOUNT_PERSONALITY: Dict[str, Dict[str, Any]] = {}
_personality_lock = asyncio.Lock()

async def get_account_personality(uid: str) -> Dict[str, Any]:
    """Get or create a persistent behavioral fingerprint for an account."""
    async with _personality_lock:
        if uid not in _ACCOUNT_PERSONALITY:
            # Deterministic seed from UID so personality is stable across restarts
            seed = int(hashlib.md5(uid.encode()).hexdigest(), 16) % (2**32)
            rng = random.Random(seed)
            
            # Core personality traits (never change for this UID)
            _ACCOUNT_PERSONALITY[uid] = {
                "seed": seed,
                "preferred_regions": rng.sample(["IND", "IN", "SG", "TH", "MY"], k=3),
                "play_style": rng.choice(["aggressive", "cautious", "balanced", "explorer"]),
                "session_length_pref": rng.uniform(1800, 10800),
                "break_frequency": rng.uniform(0.08, 0.25),
                "break_duration_mult": rng.uniform(0.8, 2.2),
                "movement_radius_base": rng.uniform(140, 220),
                "movement_pattern_bias": rng.choice(["circle", "random", "perimeter", "zigzag"]),
                "afk_timing_offset": rng.uniform(-0.5, 0.5),
                "reconnect_patience": rng.uniform(1.2, 3.5),
                "match_skip_chance": rng.uniform(0.02, 0.12),
                "peak_hours": [rng.randint(18, 23), rng.randint(0, 2)],
                "device_quirk": rng.choice(["smooth", "jittery", "delayed", "precise"]),
                "created": time.time(),
            }
        return _ACCOUNT_PERSONALITY[uid]

def apply_personality_to_profile(uid: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Merge account personality into anti-ban profile for truly unique behavior."""
    pers = _ACCOUNT_PERSONALITY.get(uid)
    if not pers:
        return profile
    p = dict(profile)
    p["match_gap"] = (
        max(5.0, p["match_gap"][0] * (0.7 + pers["break_frequency"])),
        max(10.0, p["match_gap"][1] * (1.0 + pers["break_duration_mult"] * 0.3))
    )
    p["rest_after"] = max(3, int(p["rest_after"] * (0.8 + pers["break_frequency"])))
    p["rest"] = (
        int(p["rest"][0] * pers["break_duration_mult"]),
        int(p["rest"][1] * pers["break_duration_mult"])
    )
    p["afk_scale"] *= (0.9 + pers["afk_timing_offset"] * 0.2)
    p["move_scale"] *= (0.85 + (0.3 if pers["device_quirk"] == "smooth" else 0.15 if pers["device_quirk"] == "jittery" else 0))
    p["personalized"] = True
    return p

def next_proxy():
    if not _proxy_cycle:
        return None
    _proxy_index["i"] += 1
    return next(_proxy_cycle)

def _proxy_kwargs():
    p = next_proxy()
    return {_HTTPX_PROXY_KW: p} if p else {}

def set_proxy_list(proxies, enabled=True, persist=True):
    global PROXY_LIST, USE_PROXY, _proxy_cycle, _proxy_index
    PROXY_LIST = [str(p).strip() for p in proxies if str(p).strip()]
    USE_PROXY = bool(enabled)
    _proxy_cycle = itertools.cycle(PROXY_LIST) if (PROXY_LIST and USE_PROXY) else None
    _proxy_index = {"i": 0}
    if persist:
        try:
            with open(PROXY_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(PROXY_LIST) + ("\n" if PROXY_LIST else ""))
        except Exception:
            pass

def _requests_proxies():
    p = next_proxy()
    return {"http": p, "https": p} if p else None

# Optional API keys for third-party helper services (JWT/guild). Set via env.
JWT_API_KEY = os.environ.get("JWT_API_KEY", "")
GUILD_API_KEY = os.environ.get("GUILD_API_KEY", "")

def network_snapshot():
    masked = []
    for p in PROXY_LIST:
        try:
            if "@" in p:
                scheme, rest = p.split("://", 1)
                creds, host = rest.split("@", 1)
                user = creds.split(":", 1)[0]
                masked.append(f"{scheme}://{user}:***@{host}")
            else:
                masked.append(p)
        except Exception:
            masked.append("***")
    return {
        "use_proxy": USE_PROXY,
        "count": len(PROXY_LIST),
        "proxies": masked,
        "kwarg": _HTTPX_PROXY_KW,
    }

# ═══════════════════════════ FREE PROXY AUTO-FETCH ═══════════════════════════
# Pulls public proxy lists from GitHub, validates TCP reachability, and merges
# the live ones into the rotation pool. Dead proxies never enter the pool.
PROXY_SOURCES = [
    ("socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt"),
    ("http",   "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"),
    ("socks5", "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"),
    ("http",   "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt"),
    ("socks5", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt"),
    ("http",   "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt"),
    ("socks5", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt"),
    ("http",   "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks5.txt"),
    ("http",   "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http.txt"),
    ("http",   "https://raw.githubusercontent.com/MrMarble/proxy-list/main/all.txt"),
    ("http",   "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt"),
]
MAX_AUTO_PROXIES = 800
PROXY_CHECK_TIMEOUT = 5.0
PROXY_CHECK_CONCURRENCY = 400

PROXY_FETCH_STATE: Dict[str, Any] = {
    "running": False, "candidates": 0, "alive": 0,
    "last_run": None, "last_error": None, "sources": len(PROXY_SOURCES),
}

def _split_host_port(url: str):
    try:
        rest = url.split("://", 1)[1]
        if "@" in rest:
            rest = rest.rsplit("@", 1)[1]
        host, port = rest.rsplit(":", 1)
        return host, int(port)
    except Exception:
        return None, None

def _normalise_proxy(line: str, default_scheme: str = "http"):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "://" not in line:
        line = f"{default_scheme}://{line}"
    scheme = line.split("://", 1)[0].lower()
    if scheme not in ("http", "https", "socks4", "socks5"):
        return None
    host, port = _split_host_port(line)
    if not host or not port or not (0 < port < 65536):
        return None
    return line

def _download_source(url: str, timeout: int = 12) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(400_000).decode("utf-8", "ignore")
    except Exception:
        return ""

async def _proxy_alive(url: str) -> bool:
    """Handshake-validated proxy check (TCP only is not enough).

    socks5 → real greeting (0x05 0x00), socks4 → real CONNECT reply (0x5A),
    http   → real CONNECT request, expect an HTTP status line.
    A proxy that cannot handshake would fail on the very first game packet,
    so it never enters the pool.
    """
    host, port = _split_host_port(url)
    if not host or not port:
        return False
    scheme = url.split("://", 1)[0].lower()
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=PROXY_CHECK_TIMEOUT
        )
        if scheme == "socks5":
            writer.write(b"\x05\x01\x00")
            await asyncio.wait_for(writer.drain(), timeout=PROXY_CHECK_TIMEOUT)
            reply = await asyncio.wait_for(reader.read(2), timeout=PROXY_CHECK_TIMEOUT)
            return len(reply) == 2 and reply[0] == 0x05
        if scheme == "socks4":
            writer.write(b"\x04\x01\x00\x50\x01\x01\x01\x01\x00")
            await asyncio.wait_for(writer.drain(), timeout=PROXY_CHECK_TIMEOUT)
            reply = await asyncio.wait_for(reader.read(8), timeout=PROXY_CHECK_TIMEOUT)
            return len(reply) >= 2 and reply[1] == 0x5A
        writer.write(b"CONNECT 1.1.1.1:443 HTTP/1.1\r\nHost: 1.1.1.1:443\r\n\r\n")
        await asyncio.wait_for(writer.drain(), timeout=PROXY_CHECK_TIMEOUT)
        reply = await asyncio.wait_for(reader.read(12), timeout=PROXY_CHECK_TIMEOUT)
        return reply.startswith(b"HTTP/")
    except Exception:
        return False
    finally:
        if writer is not None:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

async def fetch_free_proxies(limit: int = MAX_AUTO_PROXIES, validate: bool = True) -> Dict[str, Any]:
    """Download public proxy lists from GitHub, validate them, merge into pool."""
    if PROXY_FETCH_STATE.get("running"):
        return {"ok": False, "error": "already running", **PROXY_FETCH_STATE}
    PROXY_FETCH_STATE.update({"running": True, "last_error": None, "candidates": 0, "alive": 0})
    try:
        async def _dl(scheme: str, url: str):
            try:
                text = await asyncio.wait_for(
                    asyncio.to_thread(_download_source, url, 8), timeout=20
                )
            except Exception:
                text = ""
            return scheme, text
        raw = await asyncio.gather(*[_dl(s, u) for s, u in PROXY_SOURCES])
        seen = set()
        candidates: List[str] = []
        for scheme, text in raw:
            for line in text.splitlines():
                p = _normalise_proxy(line, scheme)
                if p and p not in seen:
                    seen.add(p)
                    candidates.append(p)
        for p in PROXY_LIST:
            if p not in seen:
                seen.add(p)
                candidates.insert(0, p)
        PROXY_FETCH_STATE["candidates"] = len(candidates)
        random.shuffle(candidates)
        candidates = candidates[: max(limit * 5, 2500)]

        alive: List[str] = []
        if validate:
            sem = asyncio.Semaphore(PROXY_CHECK_CONCURRENCY)
            async def _one(p):
                async with sem:
                    return p if await _proxy_alive(p) else None
            results = await asyncio.gather(*[_one(p) for p in candidates])
            alive = [p for p in results if p]
        else:
            alive = candidates

        alive = alive[:limit]
        PROXY_FETCH_STATE["alive"] = len(alive)
        PROXY_FETCH_STATE["last_run"] = datetime.now().isoformat(timespec="seconds")
        if alive:
            set_proxy_list(alive, enabled=True)
            try:
                bot_state.log_sync("system", f"🌐 Proxy pool refreshed: {len(alive)} live proxies", "info")
            except Exception:
                pass
        return {"ok": True, **PROXY_FETCH_STATE}
    except Exception as e:
        PROXY_FETCH_STATE["last_error"] = f"{type(e).__name__}: {e}"
        return {"ok": False, "error": PROXY_FETCH_STATE["last_error"], **PROXY_FETCH_STATE}
    finally:
        PROXY_FETCH_STATE["running"] = False

ENABLE_SPEED_MOVEMENT       = True
MOVEMENT_SPEED_MIN          = 1.0
MOVEMENT_SPEED_MAX          = 1.4
MOVEMENT_PATTERN            = "circle"
MOVEMENT_TICK_MS            = 240
MOVEMENT_RADIUS             = 180
MOVEMENT_UPDATE_SPEED_EVERY = 4.0
MOVEMENT_STATE_IDLE_CHANCE   = 0.10
MOVEMENT_STATE_WALK_CHANCE   = 0.28
MOVEMENT_STATE_RUN_CHANCE    = 0.32
MOVEMENT_STATE_SPRINT_CHANCE = 0.10
MOVEMENT_STATE_JUMP_CHANCE   = 0.08
MOVEMENT_STATE_CROUCH_CHANCE = 0.06
MOVEMENT_STATE_PRONE_CHANCE  = 0.06

ENABLE_HTTP_PING = True
PING_INTERVAL    = 20.0
PING_TIMEOUT     = 8.0
PING_URL         = "https://loginbp.ppmainecoonghj.com/Ping"
PING_REAL_IP     = "103.109.214.211"

FALLBACK_UID = ""
FALLBACK_PASSWORD = ""

# ═══════════════════════════ SQUAD CONFIG ═══════════════════════════
TEAM_MODE               = True
TEAM_SIZE               = 4
TEAM_PEER_WAIT_TIMEOUT  = 25.0
TEAM_CREATE_WAIT        = 2.0
TEAM_INVITE_CYCLE_WAIT  = 2.0
TEAM_INVITE_MAX_TIME    = 60.0
TEAM_HEARTBEAT_INTERVAL = 2.5
TEAM_IDLE_ITERS_TEAM    = 1800
TEAM_MEMBER_START_DELAY = 12.0
TEAM_FINAL_WAIT         = 4.0
TEAM_READY_DELAY        = 3.0
_accept_friend_request  = True
DEBUG_TEAM_PACKETS      = False

# ═══════════════════════════ GUILD CONFIG ═══════════════════════════
GUILD_BASE = os.environ.get("GUILD_BASE", "https://danger-guild-management-web.vercel.app")
GUILD_JOIN_ENDPOINTS  = [f"{GUILD_BASE}/join"]
GUILD_LEAVE_ENDPOINTS = [
    f"{GUILD_BASE}/leave", f"{GUILD_BASE}/guild/leave",
    f"{GUILD_BASE}/quit", f"{GUILD_BASE}/guild/quit", f"{GUILD_BASE}/exit",
]
GUILD_UA = "Mozilla/5.0 (Linux; Android 10) GREAT_FREXY/4.4"
GUILD_TAG = "GREAT FREXY"

JWT_API_ENDPOINTS = [
    ("AGS COMMUNITY JWT API", "https://ags-community-jwt-api.vercel.app/token"),
]
BD_FRIEND_URLS = [
    "https://clientbp.ggblueshark.com/RequestAddingFriend",
    "https://client.bd.freefiremobile.com/RequestAddingFriend",
    "https://client.ind.freefiremobile.com/RequestAddingFriend",
]
FRIEND_AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
FRIEND_AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
FRIEND_HEADERS = {
    "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "X-GA": "v1 1",
    "ReleaseVersion": "OB54",
    "Content-Type": "application/octet-stream",
    "X-Unity-Version": "2022.3.47f1",
    "Connection": "Keep-Alive"
}

# ═══════════════════════════ BRAND ═══════════════════════════
BRAND_NAME       = "YADAV LEVEL UP"
BRAND_COUNTRY    = "India 🇮🇳"
BRAND_VERSION    = "LEVEL UP v6.0"
BRAND_YEAR       = "2026"
BRAND_TAGLINE    = "🔥 India's #1 Squad Bot 🔥"

# ═══════════════════════════ ANTI-BAN ═══════════════════════════
def bypass_jitter(base, spread=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return base
    return max(0.05, base + random.uniform(-spread, spread))

def bypass_packet_jitter(base, spread_ratio=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_PACKET_JITTER): return base
    return max(0.1, base + random.uniform(-base * spread_ratio, base * spread_ratio))

def bypass_hello_delay():
    if not (SAFE_PLAY_MODE and BYPASS_HELLO_DELAY): return 0.0
    return random.uniform(0.05, 0.45)

def bypass_ka_jitter(base=5.0):
    if not (SAFE_PLAY_MODE and BYPASS_KA_JITTER): return base
    return max(3.0, base + random.uniform(-0.8, 1.2))

def bypass_human_reconnect_delay(attempt):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return min(attempt * 0.5, 2.0)
    # Layer: full-jitter exponential backoff — retries never fire on a fixed beat.
    return max(0.25, min(connection_backoff(attempt, base=1.45, cap=9.0), 9.0))

def antiban_profile():
    return ANTI_BAN_PROFILES.get(ANTI_BAN_LEVEL, ANTI_BAN_PROFILES["max"])

_antiban_match_runs: Dict[str, int] = {}
_antiban_session_start: Dict[str, float] = {}

def _get_personalized_profile(uid: str) -> Dict[str, Any]:
    """Get anti-ban profile personalized for this UID."""
    base = ANTI_BAN_PROFILES.get(ANTI_BAN_LEVEL, ANTI_BAN_PROFILES["max"])
    pers = _ACCOUNT_PERSONALITY.get(str(uid))
    if not pers:
        return base
    p = dict(base)
    p["match_gap"] = (
        max(8.0, p["match_gap"][0] * (0.7 + pers["break_frequency"])),
        max(10.0, p["match_gap"][1] * (1.0 + pers["break_duration_mult"] * 0.3))
    )
    p["match_gap"] = (min(p["match_gap"][0], 16.0), min(p["match_gap"][1], 24.0))
    p["rest_after"] = max(3, int(p["rest_after"] * (0.8 + pers["break_frequency"])))
    p["rest"] = (
        int(p["rest"][0] * pers["break_duration_mult"]),
        int(p["rest"][1] * pers["break_duration_mult"])
    )
    p["afk_scale"] *= (0.9 + pers["afk_timing_offset"] * 0.2)
    p["move_scale"] *= (0.85 + (0.3 if pers["device_quirk"] == "smooth" else 0.15 if pers["device_quirk"] == "jittery" else 0))
    p["personalized"] = True
    return p

async def human_match_gap(uid=""):
    """Fast 10–20s pacing with layered pattern-breaking.

    The gap stays short; what keeps the account invisible is that no two gaps,
    two starts, or two sessions ever look alike.
    """
    uid = str(uid)
    p = _get_personalized_profile(uid)
    pers = _ACCOUNT_PERSONALITY.get(uid) or {}

    # ── session cap: force a real off-time before fatigue flags can form ──
    now = time.time()
    session_start = _antiban_session_start.get(uid, now)
    if uid not in _antiban_session_start:
        _antiban_session_start[uid] = now
        session_start = now
    session_len = now - session_start
    cap = _session_cap_for(uid)
    if session_len > cap:
        rest = random.uniform(1500, 3600)
        try:
            bot_state.log_sync(uid, f"😴 Session cap {int(session_len/60)}min — cool-down {int(rest/60)}min", "info")
        except Exception:
            pass
        await asyncio.sleep(rest)
        _antiban_session_start[uid] = time.time()
        _antiban_match_runs[uid] = 0
        return

    # ── night offline window ──
    if await maybe_quiet_break(uid):
        _antiban_session_start[uid] = time.time()

    # ── fresh IP for this match cycle ──
    rotate_ip_for_match()

    # ── per-account phase offset: accounts never start in lockstep ──
    runs = _antiban_match_runs.get(uid, 0)
    if runs == 0:
        slo, shi = p.get("stagger", (0.0, 12.0))
        await asyncio.sleep(random.uniform(slo, shi))

    # ── base gap + micro-jitter so no interval ever repeats ──
    lo, hi = p["match_gap"]
    gap = random.uniform(lo, hi)
    gap += random.uniform(-1.5, 2.5)

    # ── warm-up ramp for the first matches of a session ──
    gap *= warmup_multiplier(uid)

    # ── random human moment (sip / scroll / stretch) ──
    if random.random() < p.get("micro_pause_chance", 0.18):
        mlo, mhi = p.get("micro_pause", (1.0, 4.5))
        gap += random.uniform(mlo, mhi)

    # ── subtle time-of-day drift (humans are not constant) ──
    hour = datetime.now().hour
    peak = pers.get("peak_hours", [19, 22])
    if not (peak[0] <= hour <= peak[1]):
        gap *= random.uniform(1.02, 1.12)

    gap = max(10.0, min(gap, 20.0))
    await asyncio.sleep(gap)

    # ── staggered forced rest ──
    _antiban_match_runs[uid] = runs + 1
    rest_after = int(p.get("rest_after") or 0)
    if rest_after > 0 and _antiban_match_runs[uid] % rest_after == 0:
        rlo, rhi = p["rest"]
        rest = random.uniform(rlo, rhi)
        try:
            bot_state.log_sync(uid, f"😴 Cool-down {int(rest)}s after {rest_after} matches", "info")
        except Exception:
            pass
        await asyncio.sleep(rest)

def antiban_snapshot():
    base = ANTI_BAN_PROFILES.get(ANTI_BAN_LEVEL, ANTI_BAN_PROFILES["max"])
    return {
        "level": ANTI_BAN_LEVEL,
        "label": "SMART FAST SAFE",
        "locked": True,
        "match_gap": list(base["match_gap"]),
        "rest_after": base["rest_after"],
        "rest": list(base["rest"]),
        "afk_scale": base["afk_scale"],
        "move_scale": base["move_scale"],
        "session_cap": base.get("session_cap"),
        "available": list(ANTI_BAN_PROFILES.keys()),
        "layer_count": len(ANTI_CHEAT_LAYERS),
        "bypass": {
            "timing_jitter": BYPASS_TIMING_JITTER,
            "packet_jitter": BYPASS_PACKET_JITTER,
            "hello_delay": BYPASS_HELLO_DELAY,
            "ka_jitter": BYPASS_KA_JITTER,
            "safe_play_mode": SAFE_PLAY_MODE,
        },
        "layers": anti_cheat_snapshot(),
    }

# ═══════════════════════════ DEVICE ═══════════════════════════
def get_device_for_account(account_identifier):
    devices = {}
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                devices = json.load(f)
        except Exception: pass
    key = str(account_identifier)
    if key in devices: return devices[key]
    dev_list = [
        ("Samsung", "SM-G998B", "Adreno (TM) 660", "Android OS 12 / API-31"),
        ("Xiaomi", "2201122G", "Adreno (TM) 730", "Android OS 13 / API-33"),
        ("Realme", "RMX3700", "Mali-G710", "Android OS 14 / API-34"),
        ("OnePlus", "CPH2451", "Adreno (TM) 740", "Android OS 13 / API-33"),
        ("OPPO", "CPH2611", "Adreno (TM) 720", "Android OS 14 / API-34"),
    ]
    brand, model, gpu, os_ver = random.choice(dev_list)
    dev = {
        "unique_device_id": f"Google|{uuid.uuid4()}",
        "brand": brand, "model": model, "gpu_renderer": gpu, "system_software": os_ver,
        "screen_width": random.choice([1080, 1440, 720]),
        "screen_height": random.choice([2400, 3200, 1600]),
        "screen_dpi": str(random.randint(300, 420)),
        "memory": random.randint(2800, 6500),
        "processor_details": f"ARM64 FP ASIMD AES | {random.randint(2200, 3200)} | {random.randint(6, 12)}",
        "client_ip": f"{random.randint(103, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}",
    }
    devices[key] = dev
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2)
    except Exception: pass
    return dev

# ═══════════════════════════ DNS ═══════════════════════════
_DNS_CACHE: Dict[str, Tuple[str, float]] = {}
_DNS_CACHE_TTL = 300.0

async def resolve_host_cloudflare(hostname):
    if not hostname: return hostname
    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() for p in parts): return hostname
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp: return ip
    try:
        loop = asyncio.get_running_loop()
        info = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
        if info:
            ip = info[0][4][0]
            _DNS_CACHE[hostname] = (ip, now + _DNS_CACHE_TTL)
            return ip
    except Exception: pass
    return hostname

def optimize_tcp_socket(sock):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    except Exception: pass

def optimize_udp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception: pass

# ═══════════════════════════ HTTP CLIENT ═══════════════════════════
client = httpx.AsyncClient(verify=False, timeout=10.0,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50), **_proxy_kwargs())
headers = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Unity-Version': '2018.4.12f1', 'X-GA-SV': '1789535859',
    'X-GA': 'v1 1', 'ReleaseVersion': 'OB55'
}

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

CRC7_TABLE = bytes([
    0,9,18,27,36,45,54,63,72,65,90,83,108,101,126,119,25,16,11,2,61,52,47,38,
    81,88,67,74,117,124,103,110,50,59,32,41,22,31,4,13,122,115,104,97,94,87,76,69,
    43,34,57,48,15,6,29,20,99,106,113,120,71,78,85,92,100,109,118,127,64,73,82,91,
    44,37,62,55,8,1,26,19,125,116,111,102,89,80,75,66,53,60,39,46,17,24,3,10,
    86,95,68,77,114,123,96,105,30,23,12,5,58,51,40,33,79,70,93,84,107,98,121,112,
    7,14,21,28,35,42,49,56,65,72,83,90,101,108,119,126,9,0,27,18,45,36,63,54,
    88,81,74,67,124,117,110,103,16,25,2,11,52,61,38,47,115,122,97,104,87,94,69,76,
    59,50,41,32,31,22,13,4,106,99,120,113,78,71,92,85,34,43,48,57,6,15,20,29,
    37,44,55,62,1,8,19,26,109,100,127,118,73,64,91,82,60,53,46,39,24,17,10,3,
    116,125,102,111,80,89,66,75,23,30,5,12,51,58,33,40,95,86,77,68,123,114,105,96,
    14,7,28,21,42,35,56,49,70,79,84,93,98,107,112,121,
])
_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0:1, 1:2, 2:2, 3:1, 4:2}
_FIELD_NAMES = {0:"sendOption", 1:"cmd", 2:"orderId", 3:"flags", 4:"length"}

# ═══════════════════════════ BOT STATE ═══════════════════════════
class BotState:
    def __init__(self):
        self.accounts: Dict[str, dict] = {}
        self.account_workers: Dict[str, asyncio.Task] = {}
        self.account_credentials: Dict[str, dict] = {}
        self.logs: Dict[str, List[dict]] = {}
        self.squad_logs: Dict[int, List[dict]] = {}
        self._log_lock = asyncio.Lock()
        self.paused: set = set()
        self.removed: set = set()   # UIDs removed from dashboard stay gone
        self.refresh_callbacks: dict = {}
        self.guild_jobs: Dict[int, dict] = {}
        self._guild_job_lock = asyncio.Lock()
        self._guild_job_counter = 0
        self.start_time: float = time.time()

    def get_account_uptime(self, uid):
        acc = self.accounts.get(str(uid))
        if not acc: return 0
        return max(0, int(time.time() - acc.get("added_at", self.start_time)))

    def _fmt_time(self):
        return datetime.now().strftime("%H:%M:%S")

    async def log(self, uid: str, msg: str, level: str = "info"):
        uid = str(uid)
        entry = {"t": self._fmt_time(), "m": msg, "lvl": level}
        async with self._log_lock:
            if uid not in self.logs: self.logs[uid] = []
            self.logs[uid].append(entry)
            if len(self.logs[uid]) > 200:
                self.logs[uid] = self.logs[uid][-200:]

    def log_sync(self, uid: str, msg: str, level: str = "info"):
        uid = str(uid)
        entry = {"t": self._fmt_time(), "m": msg, "lvl": level}
        if uid not in self.logs: self.logs[uid] = []
        self.logs[uid].append(entry)
        if len(self.logs[uid]) > 200:
            self.logs[uid] = self.logs[uid][-200:]

    def squad_log(self, squad_id: int, msg: str, level: str = "info"):
        try:
            sid = int(squad_id)
        except Exception:
            return
        entry = {"t": self._fmt_time(), "m": msg, "lvl": level}
        if sid not in self.squad_logs: self.squad_logs[sid] = []
        self.squad_logs[sid].append(entry)
        if len(self.squad_logs[sid]) > 300:
            self.squad_logs[sid] = self.squad_logs[sid][-300:]

    def register_account(self, uid, nickname, region, level, exp, likes, password="", slot=0):
        uid = str(uid)
        if uid in self.removed:
            return
        cur = self.accounts.get(uid, {})
        self.accounts[uid] = {
            **cur,
            "uid": uid, "nickname": nickname, "region": region,
            "level": level, "exp": exp, "likes": likes,
            "password": password, "slot": slot,
            "status": cur.get("status", "ONLINE"),
            "matches": cur.get("matches", 0),
            "added_at": cur.get("added_at", time.time()),
            "guild_status": cur.get("guild_status", "—"),
            "guild_detail": cur.get("guild_detail", ""),
            "squad_id": cur.get("squad_id", 0),
        }

    def update_status(self, uid, status, matches=None):
        uid = str(uid)
        if uid in self.accounts:
            self.accounts[uid]["status"] = status
            if matches is not None:
                self.accounts[uid]["matches"] = matches

    def update_exp(self, uid, exp, level):
        uid = str(uid)
        if uid in self.accounts:
            self.accounts[uid]["exp"] = exp
            self.accounts[uid]["level"] = level

    def update_guild(self, uid, status, detail=""):
        uid = str(uid)
        if uid in self.accounts:
            self.accounts[uid]["guild_status"] = status
            self.accounts[uid]["guild_detail"] = detail

    def increment_match(self, uid):
        uid = str(uid)
        if uid in self.accounts:
            self.accounts[uid]["matches"] = self.accounts[uid].get("matches", 0) + 1

    def remove_account(self, uid):
        """Hard remove: kill the worker, drop every trace, block re-registration."""
        uid = str(uid)
        t = self.account_workers.pop(uid, None)
        if t and not t.done():
            try:
                t.cancel()
            except Exception:
                pass
        self.accounts.pop(uid, None)
        self.account_credentials.pop(uid, None)
        self.logs.pop(uid, None)
        self.paused.discard(uid)
        self.removed.add(uid)
        return True

    def allow_account(self, uid):
        """Un-block a UID (used when it is deliberately added again)."""
        self.removed.discard(str(uid))

    def is_paused(self, uid):
        return str(uid) in self.paused

    async def new_guild_job(self, guild_id, action, uids):
        async with self._guild_job_lock:
            self._guild_job_counter += 1
            jid = self._guild_job_counter
            self.guild_jobs[jid] = {
                "id": jid, "guild_id": str(guild_id), "action": action,
                "uids": list(uids), "results": {}, "started": time.time(),
                "done": False, "owner_uid": None,
            }
            return jid

    def add_guild_result(self, jid, uid, ok, msg, detail=""):
        if jid in self.guild_jobs:
            self.guild_jobs[jid]["results"][str(uid)] = {
                "ok": bool(ok), "msg": str(msg)[:200], "detail": str(detail)[:200],
                "at": time.time(),
            }

    def finish_guild_job(self, jid):
        if jid in self.guild_jobs:
            self.guild_jobs[jid]["done"] = True

bot_state = BotState()

# ═══════════════════════════ CONSOLE COLORS ═══════════════════════════
class Colors:
    GREEN='\033[92m'; FAIL='\033[91m'; WARNING='\033[93m'
    CYAN='\033[96m'; MAGENTA='\033[95m'; WHITE='\033[97m'; ENDC='\033[0m'
    BRAND   = '\033[38;5;208m'
    BDRED   = '\033[38;5;196m'
    BDGREEN = '\033[38;5;46m'
    GOLD    = '\033[38;5;220m'
    PURPLE  = '\033[38;5;93m'
    PINK    = '\033[38;5;213m'
    SKY     = '\033[38;5;51m'
    DIM     = '\033[2m'
    BOLD    = '\033[1m'

def print_colored(t, c=Colors.WHITE):
    try: print(f"{c}{t}{Colors.ENDC}")
    except Exception: pass

def print_banner():
    art = [
        "██╗   ██╗ █████╗ ██████╗  █████╗ ██╗   ██╗",
        "╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗██║   ██║",
        " ╚████╔╝ ███████║██║  ██║███████║██║   ██║",
        "  ╚██╔╝  ██╔══██║██║  ██║██╔══██║╚██╗ ██╔╝",
        "   ██║   ██║  ██║██████╔╝██║  ██║ ╚████╔╝ ",
        "   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝  ╚═══╝  ",
    ]
    bar = "═" * 64
    lines = [f"{Colors.BDRED}╔{bar}╗{Colors.ENDC}"]
    for row in art:
        lines.append(f"{Colors.BDRED}║{Colors.BDGREEN}  {row.ljust(60)}{Colors.BDRED}  ║{Colors.ENDC}")
    lines.append(f"{Colors.BDRED}╚{bar}╝{Colors.ENDC}")
    lines.append(f"{Colors.GOLD}     ⚡  {Colors.BOLD}{BRAND_NAME} — SQUAD + GUILD PREMIUM BOT{Colors.ENDC} {Colors.GOLD}⚡{Colors.ENDC}")
    lines.append(f"{Colors.BDGREEN}     🇮🇳  Made in {BRAND_COUNTRY}  |  © {BRAND_YEAR} {BRAND_NAME}  🇮🇳{Colors.ENDC}")
    lines.append(f"{Colors.PINK}              {BRAND_TAGLINE}{Colors.ENDC}")
    lines.append(f"{Colors.DIM}      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    try: print("\n" + "\n".join(lines) + "\n")
    except Exception: pass

def print_success(t, uid=""):
    print_colored(f"  {Colors.BDGREEN}✔{Colors.ENDC} {t}", Colors.WHITE)
    if uid: bot_state.log_sync(uid, t, "success")

def print_error(t, uid=""):
    print_colored(f"  {Colors.BDRED}✘{Colors.ENDC} {t}", Colors.WHITE)
    if uid: bot_state.log_sync(uid, t, "error")

def print_warning(t, uid=""):
    print_colored(f"  {Colors.GOLD}⚠{Colors.ENDC} {t}", Colors.WHITE)
    if uid: bot_state.log_sync(uid, t, "warning")

def print_info(t, uid=""):
    print_colored(f"  {Colors.SKY}ℹ{Colors.ENDC} {t}", Colors.WHITE)
    if uid: bot_state.log_sync(uid, t, "info")

def print_section(title, color=None):
    color = color or Colors.PURPLE
    bar = "━" * 62
    print_colored(f"\n{color}┏{bar}┓{Colors.ENDC}", color)
    print_colored(f"{color}┃{Colors.ENDC}  {Colors.BOLD}{Colors.GOLD}{title.center(58)}{Colors.ENDC}  {color}┃{Colors.ENDC}", color)
    print_colored(f"{color}┗{bar}┛{Colors.ENDC}\n", color)

def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict): return default
    if key in d:
        v = d[key].get('data'); return v if v is not None else default
    if str(key) in d:
        v = d[str(key)].get('data'); return v if v is not None else default
    return default

# ═══════════════════════════ MATCH COUNTER ═══════════════════════════
_match_counters: Dict[str, int] = {}
_match_counter_lock = asyncio.Lock()

async def _inc_match(uid):
    async with _match_counter_lock:
        _match_counters[uid] = _match_counters.get(uid, 0) + 1
        return _match_counters[uid]

async def _dec_match(uid):
    async with _match_counter_lock:
        if uid in _match_counters and _match_counters[uid] > 0:
            _match_counters[uid] -= 1
        return _match_counters.get(uid, 0)

async def _get_match_count(uid):
    async with _match_counter_lock:
        return _match_counters.get(uid, 0)

# ═══════════════════════════ SQUAD RUNTIME ═══════════════════════════
class SquadRuntime:
    def __init__(self, squad_id):
        self.squad_id = squad_id
        self.members_uids: List[str] = []
        self.peers: Dict[str, dict] = {}
        self.leader_uid: Optional[str] = None
        self.team_code: Optional[str] = None
        self.pk_code: Optional[str] = None
        self.members_joined: set = set()
        self.lock = asyncio.Lock()
        self.members_lock = asyncio.Lock()
        self.is_running = False
        self.team_active = True
        self.match_count = 0

    async def member_join(self, uid):
        uid = str(uid)
        async with self.members_lock:
            before = len(self.members_joined)
            self.members_joined.add(uid)
            after = len(self.members_joined)
        if after != before:
            print_success(f"👥 [SQUAD-{self.squad_id}] Member Joined ({after}/{TEAM_SIZE}) → {uid}", uid)
            bot_state.squad_log(self.squad_id, f"Member joined ({after}/{TEAM_SIZE}): {uid}", "success")
        return after

    async def member_leave(self, uid):
        async with self.members_lock:
            self.members_joined.discard(str(uid))

    async def member_count(self):
        async with self.members_lock:
            return len(self.members_joined)

    async def reset_members(self, keep_leader=True):
        async with self.members_lock:
            self.members_joined.clear()
            if keep_leader and self.leader_uid:
                self.members_joined.add(self.leader_uid)

# ═══════════════════════════ TOKEN CACHE ═══════════════════════════
_token_cache_memo = {}
_token_cache_memo_time = 0.0
_TOKEN_CACHE_MEMO_TTL = 5.0

def _json_serializer(obj):
    if isinstance(obj, (bytes, bytearray)): return {"__bytes_hex__": bytes(obj).hex()}
    raise TypeError(f"not serializable: {type(obj)}")

def _json_deserializer(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj and len(obj) == 1:
            try: return bytes.fromhex(obj["__bytes_hex__"])
            except Exception: return b""
        return {k: _json_deserializer(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_json_deserializer(x) for x in obj]
    return obj

def _load_token_cache():
    global _token_cache_memo, _token_cache_memo_time
    now = time.time()
    if _token_cache_memo and (now - _token_cache_memo_time) < _TOKEN_CACHE_MEMO_TTL:
        return _token_cache_memo
    if not os.path.exists(TOKEN_CACHE_FILE): return {}
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content: return {}
        data = json.loads(content)
        if not isinstance(data, dict): raise ValueError("root must be dict")
        parsed = _json_deserializer(data)
        _token_cache_memo = parsed; _token_cache_memo_time = now
        return parsed
    except Exception as e:
        print_error(f"Token cache corrupt → delete: {e}")
        try: os.remove(TOKEN_CACHE_FILE)
        except Exception: pass
        return {}

def _save_token_cache(cache):
    global _token_cache_memo, _token_cache_memo_time
    try:
        tmp = TOKEN_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=_json_serializer)
        os.replace(tmp, TOKEN_CACHE_FILE)
        _token_cache_memo = cache; _token_cache_memo_time = time.time()
    except Exception as e: print_error(f"Cache save: {e}")

def cache_get(uid):
    cache = _load_token_cache()
    e = cache.get(str(uid))
    if not e: return None
    if time.time() - e.get("cached_at", 0) > TOKEN_CACHE_TTL:
        cache_invalidate(uid); return None
    if str(e.get("account_id", "")).isdigit(): e["account_id"] = int(e["account_id"])
    if not isinstance(e.get("login_payload_data"), (bytes, bytearray)):
        cache_invalidate(uid); return None
    return e

def cache_set(uid, data):
    cache = _load_token_cache()
    e = dict(data); e["cached_at"] = time.time()
    cache[str(uid)] = e; _save_token_cache(cache)
    print_success(f"💾 [CACHE] Saved UID {uid}")

def cache_invalidate(uid):
    cache = _load_token_cache()
    if str(uid) in cache:
        del cache[str(uid)]; _save_token_cache(cache)

def _update_cache_profile(data, level, exp):
    try:
        keys = []
        if data.get('auth_uid'): keys.append(str(data['auth_uid']))
        if data.get('auth_token'): keys.append(f"tok_{data['auth_token'][:20]}")
        if not keys: return
        cache = _load_token_cache(); ch = False
        for k in keys:
            if k in cache and isinstance(cache[k], dict):
                cache[k]['level'] = level; cache[k]['exp'] = exp; ch = True
        if ch: _save_token_cache(cache)
    except Exception: pass

# ═══════════════════════════ ENCRYPTION ═══════════════════════════
async def aes_encrypt(payload, key, iv):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(payload, AES.block_size))

async def get_playstore_version():
    if play_scraper is None: return "1.132.9"
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, lambda: play_scraper('com.dts.freefireth', lang='hi', country='bd'))
        return res.get("version") or "1.132.9"
    except Exception:
        return "1.132.9"

async def version_config():
    app_version = await get_playstore_version()
    url = ("https://version.ggwhitehawk.com/live/ver.php"
           f"?version={app_version}&lang=hi&device=android&channel=android"
           f"&appstore=googleplay&region={DEFAULT_REGION}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    try:
        r = await client.get(url); r.raise_for_status()
        d = r.json()
        su = d.get("server_url"); rv = d.get("remote_version"); lr = d.get("latest_release_version")
        if not su or not rv or not lr: return None
        return lr, rv, su
    except Exception: return None

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br", "Connection": "close"
    }
    data = {
        "uid": uid, "password": password, "response_type": "token", "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    for attempt in range(5):
        try:
            r = await client.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                d = r.json()
                oid = d.get("open_id"); at = d.get("access_token"); pf = d.get("platform", 4)
                if oid and at: return oid, at, pf
            if r.status_code == 429: await asyncio.sleep(1); continue
        except Exception: pass
        await asyncio.sleep(0.5)
    return None

async def parse_results(parsed):
    out = {}
    for r in parsed:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            fd["data"] = await parse_results(r.data.results)
        out[r.field] = fd
    return out

async def decode_protobuf(data):
    if Parser is None: return "{}"
    parsed = Parser().parse(data)
    return json.dumps(await parse_results(parsed))

def decode_protobuf_dict_safe(data):
    if Parser is None: return {}
    try:
        parsed = Parser().parse(data)
        return _recursive_dict(parsed)
    except Exception: return {}

def _recursive_dict(results):
    out = {}
    for r in results:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            if hasattr(r.data, "results"): fd["data"] = _recursive_dict(r.data.results)
            elif isinstance(r.data, list): fd["data"] = _recursive_dict(r.data)
            else: fd["data"] = str(r.data)
        out[str(r.field)] = fd
    return out

def _decode_proto_manual(data):
    result = {}; offset = 0; data_len = len(data)
    while offset < data_len:
        header = 0; shift = 0
        while offset < data_len:
            b = data[offset]; offset += 1
            header |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
            if shift > 28: break
        if header == 0: break
        fn = header >> 3; wt = header & 0x7
        if fn == 0: break
        if wt == 0:
            v = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 63: break
            result[fn] = v
        elif wt == 2:
            length = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                length |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 28: break
            if length > data_len - offset: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                if s and all(31 < ord(c) < 127 or ord(c) in (9,10,13) for c in s):
                    result[fn] = s
                else:
                    nested = _decode_proto_manual(value)
                    result[fn] = nested if nested else value.hex()
            except UnicodeDecodeError:
                nested = _decode_proto_manual(value)
                result[fn] = nested if nested else value.hex()
        elif wt == 5: offset += 4
        elif wt == 1: offset += 8
        else: break
    return result

# ═══════════════════════════ PROTOBUF ENCODE ═══════════════════════════
def encode_varint(n):
    if n < 0: return b''
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict):
            nested = build_proto(v)
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(nested)) + nested)
        elif isinstance(v, int):
            parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)

def encrypt_api(plain_hex):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(
        pad(bytes.fromhex(plain_hex), AES.block_size)).hex()

def encrypt_api_bytes(plain_bytes):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain_bytes, AES.block_size))

# ═══════════════════════════ SQUAD BUILDERS ═══════════════════════════
def _pb_varint(fn, val): return encode_varint((fn << 3) | 0) + encode_varint(val)
def _pb_length(fn, val):
    enc = val.encode('utf-8') if isinstance(val, str) else val
    return encode_varint((fn << 3) | 2) + encode_varint(len(enc)) + enc

def create_proto(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str): field = int(field)
        if isinstance(value, dict):
            packet.extend(_pb_length(field, bytes(create_proto(value))))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    packet.extend(_pb_length(field, bytes(create_proto(item))))
                elif isinstance(item, str): packet.extend(_pb_length(field, item))
                elif isinstance(item, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(item)))
                elif isinstance(item, bool): packet.extend(_pb_varint(field, 1 if item else 0))
                elif isinstance(item, int): packet.extend(_pb_varint(field, item))
        elif isinstance(value, bool): packet.extend(_pb_varint(field, 1 if value else 0))
        elif isinstance(value, int): packet.extend(_pb_varint(field, value))
        elif isinstance(value, str): packet.extend(_pb_length(field, value))
        elif isinstance(value, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(value)))
    return bytes(packet)

def create_packet(Pk, N, K, V):
    if isinstance(K, str): K = bytes.fromhex(K) if len(K) == 32 else K.encode()
    if isinstance(V, str): V = bytes.fromhex(V) if len(V) == 32 else V.encode()
    PkEnc = AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(Pk), 16)).hex()
    L = len(PkEnc) // 2
    hexlen = hex(L)[2:]
    if len(hexlen) % 2 != 0: hexlen = '0' + hexlen
    pad_len = 12 - len(N) - len(hexlen)
    if pad_len < 0: pad_len = 0
    return bytes.fromhex(N + ('0' * pad_len) + hexlen + PkEnc)

def create_team(key, iv, game_version="1.132.9"):
    fields = {
        1: 1, 2: {2: bytes.fromhex("01"), 3: 1, 4: 3, 5: "en",
            8: {1: "BDC3", 2: 123, 3: "BD"}, 9: 1,
            10: bytes.fromhex("01090a0b1219202729"), 11: 2, 13: 1,
            14: {1: "08FBA33B4BABE2790205390333330000009700050092005F72697EB2134DCBB2467625142201040e38e848dc0e748c3f6aa04d81000000ff1113090dcacfa16d",
                 2: 478, 3: "7e585d55", 4: "y[Z]", 6: 12, 7: "15686677735a7506101c",
                 8: str(game_version), 9: 3, 10: 1, 11: "03626253513637754174"},
            19: 329, 21: bytes.fromhex("374f521955"), 24: {1: 21},
            27: "a_6534489873065906362"}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def team_fresh(account_id, key, iv):
    return create_packet(create_proto({1: 72, 2: {1: int(account_id)}}).hex(), "0515", key, iv)

def invite_player_in_team(target_uid, key, iv, region="BD"):
    return create_packet(create_proto({1: 2, 2: {1: int(target_uid), 2: region, 4: 1}}).hex(),
                         "0515", key, iv)

def accept_team_invite(target_uid, group_id, key, iv):
    fields = {1: 4, 2: {1: int(target_uid), 3: int(target_uid),
        4: bytes.fromhex("0107090a0b120f19202729"), 8: 1,
        9: {1: "08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",
            2: 235, 3: {14: 80, 11: 86}, 4: "{Y\\R", 6: 13, 7: {2: 4},
            8: "1.132.9", 9: 2, 10: 1, 11: "0362625351"},
        10: str(group_id),
        11: {"1": "BDC3", "2": 107, "3": "BD"}, 13: "en", 16: "374f5219",
        20: {1: 21}, 23: "a_6534489873065906362",
        24: "https://dl-sg-production.freefiremobile.com/",
        27: {1: 2, 2: 4}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def start_match_team(account_id, key, iv, region="BD"):
    fields = {1: 9, 2: {1: int(account_id), 7: {1: "BDC3", 2: 410, 3: region}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def ready_for_game(uid, key, iv):
    return create_packet(create_proto({1: 15, 2: {1: uid, 2: 1}}).hex(), "0519", key, iv)

# ═══════════════════════════ MAJORLOGIN ═══════════════════════════
async def build_majorlogin_payload(open_id, access_token, platform, client_version, dev):
    try:
        p = {
            3: str(datetime.now())[:-7], 4: "free fire", 5: "1",
            7: str(client_version) if client_version else "1.132.8",
            8: str(dev.get("system_software", "Android OS 14 / API-34")),
            9: "Handheld", 10: "Grameenphone", 11: "CarrierDataNetwork",
            12: str(dev.get("screen_width", 1639)),
            13: str(dev.get("screen_height", 720)),
            14: str(dev.get("screen_dpi", 320)),
            15: str(dev.get("processor_details", "ARM64 FP ASIMD AES | 2000 | 8")),
            16: str(dev.get("memory", 5653)),
            17: str(dev.get("gpu_renderer", "Mali-G52 MC2")),
            18: "OpenGL ES 3.2 v1.r49p1-03bet0",
            19: str(dev.get("unique_device_id", f"Google|{uuid.uuid4()}")),
            20: str(dev.get("client_ip", "182.5.135.225")),
            21: "en", 22: str(open_id), 23: str(platform), 24: "Handheld",
            25: str(dev.get("model", "Xiaomi")), 26: "BD",
            29: str(access_token), 30: "1", 41: "Grameenphone", 42: "4G",
            57: "7428b253defc164018c604a1ebbfebdf", 60: "109278", 61: "55402",
            62: "868", 64: "55927", 65: "109278", 66: "55927", 67: "109278",
            73: 2,
            74: "/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/lib/arm64",
            76: 1,
            77: "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/base.apk",
            78: 6, 79: 1, 81: "32", 83: "2019121229", 85: 3,
            86: "OpenGLES2", 87: 3071, 88: 4, 89: 14466, 93: "3rd_party",
            94: "KqsHTyb7yHjsAiyNWUUZa0DSOD6U0AhDQ76smAo1WeHHHpSmJ8KMRyRrxb2ttgJqO9YOqO/K6AORAvDMAX/qBS8+JahIkrM7kHfzlfULbgRAoZ9r",
            95: "111207", 96: "{\"cur_rate\":[60,90,120],\"support_etc2\":true}", 97: "1",
            98: "1", 99: str(platform), 100: str(platform),
            103: "1", 104: "52837", 105: "1",
            106: "https://dl.gmc.freefiremobile.com/live/ABHotUpdates/|211c933168f55902c7dfbfd8c4e2957d",
            107: "1.3fb8adbf45f44ce9",
        }
        return encrypt_api_bytes(build_proto(p))
    except Exception as e:
        print_error(f"build_majorlogin_payload: {e}"); return None

async def send_majorlogin(data, release_version, server_url):
    if thunderFF_pb2 is None: return None
    try:
        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        hdrs = headers.copy(); hdrs["ReleaseVersion"] = str(release_version)
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code != 200:
            print_error(f"[MAJORLOGIN] HTTP {r.status_code}"); return None
        c = r.content
        if len(c) < 40: return None
        for off in [0, 64] + list(range(128)):
            try:
                m = thunderFF_pb2.MajorLoginRes(); m.ParseFromString(c[off:])
                if m.region and m.token: return m
            except Exception: continue
        return None
    except Exception as e:
        print_error(f"[MAJORLOGIN] {e}"); return None

async def send_getlogin(data, base_url, token, release_version):
    if thunderFF_pb2 is None: return None
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        hdrs = headers.copy()
        hdrs["ReleaseVersion"] = release_version
        hdrs['Authorization'] = f"Bearer {token}"
        hdrs['Host'] = "clientbp.ppmainecoonghj.com"
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code != 200: return None
        c = r.content
        rp = thunderFF_pb2.GetLoginDataRes()
        ok = False
        try:
            rp.ParseFromString(c)
            if rp.functional_addrs or rp.informational_addrs: ok = True
        except Exception: pass
        if not ok:
            for off in range(min(128, len(c))):
                try:
                    cand = thunderFF_pb2.GetLoginDataRes(); cand.ParseFromString(c[off:])
                    if cand.functional_addrs or cand.informational_addrs:
                        rp = cand; break
                except Exception: continue
        dd = {}
        try:
            if Parser is not None:
                parsed = Parser().parse(c.hex())
                dd = await parse_results(parsed)
        except Exception: pass
        return rp, dd
    except Exception: return None

# ═══════════════════════════ HTTP PING ═══════════════════════════
async def send_ping(account_id, token, release_version):
    try:
        try: acc = int(account_id)
        except Exception: acc = 0
        now_ms = int(time.time() * 1000)
        payload = struct.pack("<Q", acc & 0xFFFFFFFFFFFFFFFF) + struct.pack("<Q", now_ms & 0xFFFFFFFFFFFFFFFF)
        req_id = secrets.token_urlsafe(18)[:22]
        hdrs = {
            'accept': '*/*', 'accept-encoding': 'deflate, gzip',
            'authorization': f'Bearer {token}',
            'content-type': 'application/x-www-form-urlencoded',
            'releaseversion': release_version,
            'user-agent': 'UnityPlayer/2018.4.12f1',
            'x-ga': 'v1 1', 'x-ga-sv': str(int(time.time())),
            'x-railway-edge': 'sin1', 'x-railway-request-id': req_id,
            'x-real-ip': PING_REAL_IP, 'x-request-start': str(now_ms),
            'x-unity-version': '2018.4.12f1',
        }
        r = await client.post(PING_URL, headers=hdrs, content=payload, timeout=PING_TIMEOUT)
        return r.status_code == 200
    except Exception: return False

async def ping_worker(account_id, token, release_version, region="BD"):
    if not ENABLE_HTTP_PING: return
    uid_str = str(account_id); ok_count = 0; fails = 0
    try:
        await asyncio.sleep(5.0 + random.uniform(0, 2.0))
        while True:
            ok = await send_ping(uid_str, token, release_version)
            if ok: ok_count += 1; fails = 0
            else: fails += 1
            await asyncio.sleep(max(5.0, PING_INTERVAL + random.uniform(-3.0, 3.0)))
    except asyncio.CancelledError: pass

# ═══════════════════════════ TCP STARTUP ═══════════════════════════
async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="BD", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = (await aes_encrypt(token.encode(), key, iv)).hex()
    enc_len = f"{len(enc)//2:08x}"
    reg = str(region).upper() if region else "BD"
    if typ == 'OnLine':
        if reg == 'BD':     pfx = '7119'
        elif reg == 'IND':  pfx = '7114'
        else:               pfx = '7115'
        return f"{pfx}{uid_hex}{ts_hex}00000000{enc_len}{enc}"
    if reg == 'BD':     pfx = '9219'
    elif reg == 'IND':  pfx = '9214'
    else:               pfx = '9215'
    return f"{pfx}{uid_hex}{ts_hex}{enc_len}{enc}"

async def send_keep_alive(region="BD"):
    try:
        reg = str(region).upper() if region else "BD"
        if reg == "BD":  return bytes.fromhex("0219")
        if reg == "IND": return bytes.fromhex("0214")
        return bytes.fromhex("0215")
    except Exception:
        return bytes.fromhex("0219")

# ═══════════════════════════ BR SEARCH ═══════════════════════════
BR_HEX = (
    "080112800a0a010110013a110a044944433110aa011a064555524f50453a100a044944433210311a064555524f5045"
    "40014a0801090a0b1219202758016291090a80013038384638324246303241393637363730323031303130303030"
    "30303030303030303030303030303031363030303130303135303030323232463937454545304630303030303034363736323531"
    "34303030303030303030303030303030303030303030303030303030303030303030303030306666303030303030"
    "3030636163666131366410241afb02735d5e571400024a775d45414d1a041b1c001f11010449715f4243481a001e"
    "1d071c1703004b1a4066785c524570735c51486775421b5c5a4c07504042685a63610816054e19025e7519600147"
    "7c015165406370195f5547404e4550640103020f1304064863754268676c755f65576e40467e5f0a417a4701026d"
    "675d6e73670b1108495a4c6a0b78470b740065645e525a057258425f584a447d4e6759440c11044e7c596d7f4b62"
    "5f7d04055a47505c4e1d6b5b4107447d7201057d7f0f14084e430457674f7e517d72015172415d027473577c4d61"
    "5f79535256780911030f4d5e027a797f614165067806505d53777750475e75064257076500460817014e741e7e50"
    "78487e7a7c465e7669767153497064605a7376677773550d160148037e18675966787f4c42607a645f577e7b44"
    "1b460776026b18685d0b110205490060020f70676175654674706671797f41067346677c4e06585e780f15074c57"
    "047b40517075415f6364027259674b5b0166407f7340600407770a22047a5d5c52300b3a0a167305067162727516"
    "134208312e3133302e3232480350015ae90403626253513635686e556f4e36416456324b796f566c636f47777648"
    "4f624e56526c4d727073504b4f43654177616848494176795556497273743752737149734a7a786b324752526837"
    "7a2f637664626d504f6a73552f79626d38547a4c69586d2f474351696d494b53486833447955726f39515152756c"
    "34545350626d6d624b7949565937545671577059455372323646572f59624578507338514f706d317372785455736c"
    "30796a434144444d4f34616a654b615753366361496c554b4963797a494e396d52516f715277687939797257476d"
    "337a644345337a6a61436f492f5a585233656f65365a42647a64677654636b6b665733356e4d4c6a6a56507256"
    "4b6433523172756174394e50514150724a5546627859696c4c5a3859707336654d5447666b6649793574666a526c"
    "314d4648706b51774c6373374439656378566c41636f374e664f6d2b30654756466c443474447870677138553359"
    "5973587645384842502f70666c767a737138316a32524f4d7857437556445442492f684735625462773166456e42"
    "49725162762b636144775147696f74554e316d4c4b77734379456f4766706746614251457645672b736a764c4c78"
    "704743334c304a5344532f74526169504354553344374e6249306547516651622f5a466f4c36455630775a324d6f"
    "583932414c572f5049752f56634663584e70596b356f7966326151416a536971486a2f363276354843644f525551"
    "303578754e6171795251625653704654303137655237675255636b4966366c6f447476342b514e4a4670766d7475"
    "7077707774396a5a5974437a4b56743657726d6e36785837706658456251555434684f3758a201050803108703a2"
    "01050804108103a20105080510c001a20105081d10cc01a2010408161078a20105080e10af01a201020815"
)

async def start_game_battle_royale(region, client_version, writer, key, iv):
    packet = bytes.fromhex(BR_HEX)
    try:
        if _HAS_CGU:
            proto = CguFF_pb2.StartMatch(); proto.ParseFromString(packet)
            if hasattr(proto.main, 'region_list') and len(proto.main.region_list) > 0:
                proto.main.region_list[0].region = region
                if len(proto.main.region_list) > 1: proto.main.region_list[1].region = region
            if hasattr(proto.main, 'client_version'):
                proto.main.client_version.remote_version = client_version
            packet = proto.SerializeToString()
    except Exception: pass
    enc = (await aes_encrypt(packet, key, iv)).hex()
    plen = len(enc) // 2
    hl = hex(plen)[2:]
    hl = hl if len(hl) > 1 else "0" + hl
    reg = str(region).upper() if region else "BD"
    if reg == "BD":    pfx = "031900"
    elif reg == "IND": pfx = "031400"
    else:              pfx = "031500"
    final = pfx + "0" * (6 - len(hl)) + hl + enc
    writer.write(bytes.fromhex(final)); await writer.drain()
    print_success(f"🇮🇳 [BR] Search Sent → {plen}B | Region={reg}")

# ═══════════════════════════ UDP HELPERS ═══════════════════════════
async def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while z >= 0x80: out.append((z & 0x7F) | 0x80); z >>= 7
    out.append(z); return bytes(out)

async def uleb_encode(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

async def zigzag_encode_signed(n):
    try: n = int(n)
    except Exception: n = 0
    zz = (n << 1) ^ (n >> 63)
    if zz < 0: zz = -zz
    out = bytearray()
    while True:
        b = zz & 0x7F; zz >>= 7
        if zz: b |= 0x80
        out.append(b)
        if not zz: break
    return bytes(out)

async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1

async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1

async def tea_cbc_encrypt(padded, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(padded)); pc = bytearray(8); pi = bytearray(8)
    for i in range(0, len(padded), 8):
        x = bytearray(8)
        for j in range(8): x[j] = padded[i+j] ^ pc[j]
        e0,e1 = await tea_enc(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0); struct.pack_into("<I", enc, 4, e1)
        for j in range(8): out[i+j] = enc[j] ^ pi[j]
        pc[:] = out[i:i+8]; pi[:] = x
    return bytes(out)

async def tea_cbc_decrypt(body, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(body)); pi = bytearray(8); pc = bytearray(8)
    x = bytearray(8); dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8): x[j] = body[i+j] ^ pi[j]
        d0,d1 = await tea_dec(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        struct.pack_into("<I", dec, 0, d0); struct.pack_into("<I", dec, 4, d1)
        for j in range(8): out[i+j] = dec[j] ^ pc[j]
        pc[:] = body[i:i+8]; pi[:] = dec
    return bytes(out)

async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7

async def encode_header(layout, so, cmd, oid, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        val = {0:so, 1:cmd, 2:oid, 3:flags, 4:length}[code]
        if _FIELD_SIZES[code] == 1: out.append((val & 0xFF) ^ k)
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF); out.append((v >> 8) & 0xFF)
    return bytes(out)

async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf: c = CRC7_TABLE[((2*(c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F

async def sv_frame(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0]) + await encode_header(layout, so, cmd, oid, flags, len(body), k, v80)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def build_packet(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        val = {0:so, 1:cmd, 2:oid, 3:flags, 4:len(body)}[code]
        if _FIELD_SIZES[code] == 1: hdr.append((val & 0xFF) ^ k)
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF); hdr.append((v >> 8) & 0xFF)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def layouts_from_mask(mask):
    ru = [int(c) for c in str(mask).strip()]
    nr = [c for c in ru if c != 2]
    return ru, nr

async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")
    if len(data) > 25: raise ValueError("too long")
    content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data))
    k = key[0] if key else 10
    v80 = ((k << 8) | k) & 0xFFFF
    layout = [int(c) for c in str(layout).strip()] if isinstance(layout, str) else list(layout)
    padded = await build_padded(content)
    enc_body = await tea_cbc_encrypt(padded, key)
    hdr = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    pkt = bytearray([0x63, 0x00]) + hdr + enc_body
    pkt[1] = await crc7_buff(0, pkt[2:]) & 0x7F
    return bytes(pkt).hex()

async def classify(frame):
    cmd = frame["cmd"]
    name = MESSAGE_ID_TO_NAME.get(cmd, f"UNKNOWN_{cmd}")
    if name == "UDP_HELLO": return "HELLO"
    if name == "UDP_ACK": return "ACK"
    if name == "UDP_PING": return "PING"
    if name == "RUDP_JOIN_MATCH": return "JOIN_MATCH"
    if name.startswith("RUDP_"): return name
    if name.startswith("UDP_"): return name
    return "DATA"

async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B, ack_style="short"):
    _, nr = await layouts_from_mask(mask)
    typ = await classify(frame)
    if typ == "HELLO":
        if ack_style == "echo":
            content = frame["content"] if frame["content"] else b"\x10\x00\x00\x00"
            return typ, await build_packet(hello_key, nr, 1, 1, None, 1, content, key)
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK":
        content = frame["content"] if frame["content"] else b"\x01\x00"
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, content, key)
    if typ == "PING":
        c = frame["content"]
        counter = c[:4] if len(c) >= 4 else c
        return typ, await build_packet(ping_key, nr, 0, 3, None, 0, counter + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None

async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event):
    nr = (await layouts_from_mask(mask))[1]
    ping_keys = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
    loop = asyncio.get_event_loop(); i = 0
    while not stop_event.is_set():
        pk = ping_keys[i % len(ping_keys)]
        counter = int(time.time() * 1000) & 0xFFFFFFFF
        pkt = await build_packet(pk, nr, 0, 3, None, 0, struct.pack("<I", counter) + b"\x00\x00\x00",
                                 key_bytes, encrypted=False)
        try: await loop.sock_sendto(sock, pkt, (ip, port))
        except Exception: pass
        i += 1
        try: await asyncio.wait_for(stop_event.wait(), timeout=bypass_packet_jitter(3.0, 0.4))
        except asyncio.TimeoutError: pass

async def try_header(buf, layout, k, v80):
    off = 2; out = {}
    for code in layout:
        size = _FIELD_SIZES[code]
        if off + size > len(buf): return None
        out[_FIELD_NAMES[code]] = ((buf[off] ^ k) if size == 1
                                    else ((buf[off] | (buf[off+1] << 8)) ^ v80) & 0xFFFF)
        off += size
    out["headerLen"] = off
    return out

async def oicq_unpad(padded):
    if not padded or len(padded) < 8: return None
    if not all(padded[-1-i] == 0 for i in range(7)): return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len; e = len(padded) - 7
    return padded[s:e] if s < e else b""

async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8: return None
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    candidates = []
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0,1,2,3,4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0,1,3,4])]
    for kind, layout in layouts:
        f = await try_header(data, layout, k, v80)
        if not f: continue
        if f["flags"] > 7 or f["sendOption"] > 7: continue
        if f["length"] != len(data) - f["headerLen"]: continue
        body = data[f["headerLen"]:f["headerLen"]+f["length"]]
        content = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0: continue
            padded = await tea_cbc_decrypt(body, key)
            content = await oicq_unpad(padded)
            if content is None: continue
        else: content = body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        candidates.append({"kind":kind, "layout":layout, "headerLen":f["headerLen"],
            "msgKey":data[0], "cmd":f["cmd"], "flags":f["flags"],
            "sendOption":f["sendOption"], "orderId":f.get("orderId"),
            "length":f["length"], "content":content, "crcOk":crc_ok,
            "score":score, "total":len(data)})
    if not candidates: return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]

async def build_match_startup_packets(token, udp_key, match_code, account_id, block_val,
                                      server_ip="", region="BD", client_version="1.132.6",
                                      client_version_code="2019121229", access_token="",
                                      mode_id=BR_MODE_ID, map_id=BR_MAP_ID):
    token = token.strip()
    udp_key = bytes.fromhex(udp_key)
    match_code = [int(ch) for ch in str(match_code).strip()]
    thunder_jwt = token[:660] if len(token) > 660 else token
    sharma_jwt = token[660:] if len(token) > 660 else ""
    eth = thunder_jwt.encode() if isinstance(thunder_jwt, str) else thunder_jwt
    esh = sharma_jwt.encode() if isinstance(sharma_jwt, str) else sharma_jwt
    garena420 = await has_ssan_zig(len(eth)) + eth
    reg = str(region).upper() if region else "BD"
    csoversea_block = bytes.fromhex(
        "ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d"
        "3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e"
        "3137302e3233303b33352e3138352e3138332e35370000000000000100000000000000000000000001"
        "00000800000100000000000100a8a2d7bebd8d8bdf110200")
    mid = bytes.fromhex('0000000001000102030101') + await has_ssan_zig(len(reg)) + reg.encode()
    mid += bytes.fromhex('0001030003000004')
    mid += await has_ssan_zig(len(client_version)) + client_version.encode()
    mid += await has_ssan_zig(len(client_version_code)) + client_version_code.encode()
    mid += csoversea_block
    clean_ip = server_ip.split(':')[0] if server_ip else "0.0.0.0"
    mid += await has_ssan_zig(len(clean_ip)) + clean_ip.encode()
    if access_token:
        clean_acc = access_token.strip()
        mid += await has_ssan_zig(len(clean_acc)) + clean_acc.encode()
    mid += await has_ssan_zig(len(esh)) + esh
    tg = (await uleb_encode(int(account_id)) + await uleb_encode(int(block_val)) +
          await uleb_encode(1) + await uleb_encode(int(mode_id)) +
          await uleb_encode(int(block_val)) + await uleb_encode(int(map_id)) + mid)
    process = await sv_frame(0x5E, match_code, 2, 447, 0, 1, garena420, udp_key)
    loading = await sv_frame(0x5A, match_code, 2, 448, 1, 1, tg, udp_key)
    return process.hex(), loading.hex()

# ═══════════════════════════ MOVEMENT 2001 ═══════════════════════════
async def build_movement_packet_2001(key_bytes, msg_key, player_state, x, y, z,
                                     tick, counter, move_state, account_uid,
                                     room_code, phase="arena"):
    if phase == "game":
        TAIL = (b"\x00"*7 + b"\x93\xca\xd5\xf9\x0b" + b"\x8e\xfe\xfc\xf7\x0b"
                + b"\xf4\xe0\xfe\xf7\x03" + b"\x00\x00")
    else:
        TAIL = (b"\x00"*7 + b"\xbd\xb6\xe1\xf3\x03" + b"\x00"
                + b"\xc4\xb6\xe1\xfb\x0b" + b"\x00\x00")
    body = bytearray()
    body += await uleb_encode(int(account_uid))
    body += await uleb_encode(int(player_state))
    body += await zigzag_encode_signed(int(x))
    body += await zigzag_encode_signed(int(y))
    body += await zigzag_encode_signed(int(z))
    body += b"\x00"
    body += await uleb_encode(int(move_state))
    body += TAIL
    body += await uleb_encode(int(tick))
    body += b"\x00\x00\x00"
    body += await uleb_encode(int(counter))
    body = bytes(body)
    k = key_bytes[0]; v80 = ((k << 8) | k) & 0xFFFF
    h = bytearray()
    h.append(msg_key & 0xFF); h.append(0x00); h.append(0x00 ^ k)
    h += ((2001 ^ v80) & 0xFFFF).to_bytes(2, "little")
    h += ((len(body) ^ v80) & 0xFFFF).to_bytes(2, "little")
    h.append(0x00 ^ k)
    h[1] = (await crc7_buff(0, bytes(h[2:]) + body)) & 0x7F
    return bytes(h) + body

class MovementTracker:
    PLAYER_STATE = {"idle":0, "walk":1, "run":2, "sprint":3, "jump":4, "crouch":5, "prone":6}
    def __init__(self, pattern="circle", radius=180, uid=""):
        pers = _ACCOUNT_PERSONALITY.get(str(uid), {})
        self.pattern = pers.get("movement_pattern_bias", pattern)
        self.radius = int(pers.get("movement_radius_base", radius))
        self.tick = 0; self.counter = 0
        self.angle = random.uniform(0, 6.2832)
        self.speed_multiplier = 1.0; self.dir_flip = 1
        self._next_speed_roll = time.time()
        self.state = "walk"; self.state_start = time.time()
        self.state_duration = random.uniform(2.0, 4.0)
        self.device_quirk = pers.get("device_quirk", "smooth")
        self._roll_new_speed()
    def _roll_new_speed(self):
        try:
            lo, hi = float(MOVEMENT_SPEED_MIN), float(MOVEMENT_SPEED_MAX)
            if hi < lo: lo, hi = hi, lo
            base = round(random.uniform(lo, hi), 2)
            # Apply device quirk
            if self.device_quirk == "jittery": base *= random.uniform(0.7, 1.4)
            elif self.device_quirk == "delayed": base *= random.uniform(0.6, 1.1)
            elif self.device_quirk == "precise": base *= random.uniform(0.95, 1.05)
            self.speed_multiplier = base
        except Exception: self.speed_multiplier = 1.0
        self._next_speed_roll = time.time() + MOVEMENT_UPDATE_SPEED_EVERY
    def _pick_next_state(self):
        pers = _ACCOUNT_PERSONALITY.get(str(self._uid), {}) if hasattr(self, '_uid') else {}
        play_style = pers.get("play_style", "balanced")
        # Adjust chances based on play style
        if play_style == "aggressive":
            ci, cw, cr, cs, cj, cc = 0.05, 0.15, 0.30, 0.30, 0.10, 0.10
        elif play_style == "cautious":
            ci, cw, cr, cs, cj, cc = 0.15, 0.30, 0.25, 0.10, 0.05, 0.15
        elif play_style == "explorer":
            ci, cw, cr, cs, cj, cc = 0.08, 0.25, 0.20, 0.15, 0.12, 0.10
        else:  # balanced
            ci, cw, cr, cs, cj, cc = 0.10, 0.28, 0.32, 0.10, 0.08, 0.12
        r = random.random()
        if r < ci: return "idle", random.uniform(0.6, 1.6)
        elif r < ci+cw: return "walk", random.uniform(1.6, 3.0)
        elif r < ci+cw+cr: return "run", random.uniform(2.0, 4.0)
        elif r < ci+cw+cr+cs: return "sprint", random.uniform(1.2, 2.5)
        elif r < ci+cw+cr+cs+cj: return "jump", random.uniform(0.35, 0.65)
        elif r < ci+cw+cr+cs+cj+cc: return "crouch", random.uniform(1.2, 2.5)
        else: return "prone", random.uniform(1.5, 3.5)
    def _generate_movement(self):
        p = (self.pattern or "circle").lower()
        x = y = z = 0; ms = 0
        if p == "circle":
            self.angle += 0.35 * self.dir_flip
            if self.angle > 6.2832: self.angle -= 6.2832
            elif self.angle < 0: self.angle += 6.2832
            x = int(self.radius * random.uniform(0.9, 1.1) * (1.0 if self.angle % 3.14 < 1.57 else -1.0))
            y = int(self.radius * random.uniform(0.4, 0.6))
            z = int(self.radius * random.uniform(0.9, 1.1) * (1.0 if self.angle % 6.28 < 3.14 else -1.0))
            ms = 0x0F
        elif p == "perimeter":
            # Move along edges of the map
            self.angle += 0.25 * self.dir_flip
            if self.angle > 6.2832: self.angle -= 6.2832
            edge = self.angle < 1.57 or self.angle > 4.71
            x = int(self.radius * (1.0 if edge else random.uniform(0.2, 0.8)) * (1.0 if self.angle < 3.14 else -1.0))
            y = int(self.radius * random.uniform(0.3, 0.5))
            z = int(self.radius * (1.0 if not edge else random.uniform(0.2, 0.8)) * (1.0 if self.angle < 3.14 else -1.0))
            ms = 0x0F
        elif p == "zigzag":
            self.angle += 0.5 * self.dir_flip
            if self.angle > 6.2832: self.angle -= 6.2832
            x = int(self.radius * random.uniform(0.8, 1.0) * (1.0 if self.angle % 1.57 < 0.78 else -1.0))
            y = int(self.radius * random.uniform(0.3, 0.5))
            z = int(self.radius * random.uniform(0.8, 1.0) * (1.0 if self.angle % 1.57 < 0.78 else -1.0))
            ms = 0x0F
        else:  # random
            x = random.randint(-self.radius, self.radius)
            y = random.randint(-40, 40)
            z = random.randint(-self.radius, self.radius)
            ms = random.choice([0x01, 0x02, 0x04, 0x08, 0x0F])
        return x, y, z, ms
    def next(self):
        now = time.time()
        if now >= self._next_speed_roll: self._roll_new_speed()
        if now - self.state_start > self.state_duration:
            self.state, self.state_duration = self._pick_next_state()
            self.state_start = now
        self.tick = (self.tick + 1) & 0xFFFFFFFF
        self.counter = (self.counter + 1) & 0xFFFFFFFF
        ps = self.PLAYER_STATE.get(self.state, 1)
        if self.state in ("idle", "crouch", "prone"): x = y = z = 0; move_state = 0
        else: x, y, z, move_state = self._generate_movement()
        return ps, x, y, z, move_state, self.tick, self.counter, self.speed_multiplier, self.state

async def movement_worker(sock, ip, port, udp_key_bytes, match_code, account_id, stop_event, match_index):
    loop = asyncio.get_event_loop(); addr = (ip, port)
    tracker = MovementTracker(pattern=MOVEMENT_PATTERN, radius=MOVEMENT_RADIUS, uid=account_id)
    sent = 0
    try:
        await asyncio.sleep(bypass_jitter(3.0, 0.5))
        while not stop_event.is_set():
            try:
                ps, x, y, z, ms, tick, cnt, sm, st = tracker.next()
                pkt = await build_movement_packet_2001(udp_key_bytes, 0x6B, ps, x, y, z, tick, cnt, ms,
                                                       account_id, match_code, phase="arena")
                await loop.sock_sendto(sock, pkt, addr); sent += 1
                base = MOVEMENT_TICK_MS / 1000.0
                try: smx = max(0.7, min(float(sm), 1.6))
                except Exception: smx = 1.0
                wait = max(0.10, min(base / smx, 0.40))
                wait = bypass_packet_jitter(wait, 0.20) * _get_personalized_profile(account_id)["move_scale"]
                try: await asyncio.wait_for(stop_event.wait(), timeout=wait); break
                except asyncio.TimeoutError: pass
            except asyncio.CancelledError: break
            except Exception: await asyncio.sleep(0.5)
    except asyncio.CancelledError: pass

async def send_anti_afk_fire(sock, addr, udp_key_bytes, match_code, account_id):
    try:
        _, nr = await layouts_from_mask(match_code)
        try: pid = int(account_id)
        except Exception: pid = 0
        ts = int(time.time() * 1000) & 0xFFFFFFFF
        wid = random.choice([101, 102, 103, 201, 202])
        fire = struct.pack("<IIHB", pid & 0xFFFFFFFF, ts, wid, 1)
        fp = await build_packet(0x68, nr, 0, 104, None, 0, fire, udp_key_bytes, encrypted=False)
        loop = asyncio.get_event_loop()
        await loop.sock_sendto(sock, fp, addr)
        await asyncio.sleep(bypass_jitter(random.uniform(0.15, 0.30), 0.05))
        stop = struct.pack("<IIHB", pid & 0xFFFFFFFF, ts + 200, wid, 0)
        sp = await build_packet(0x68, nr, 0, 105, None, 0, stop, udp_key_bytes, encrypted=False)
        await loop.sock_sendto(sock, sp, addr)
        return True
    except Exception: return False

async def anti_afk_worker(sock, ip, port, udp_key_bytes, match_code, account_id, stop_event, match_index):
    addr = (ip, port); fires = 0
    try:
        await asyncio.sleep(bypass_jitter(2.5, 0.5))
        while not stop_event.is_set():
            try:
                if await send_anti_afk_fire(sock, addr, udp_key_bytes, match_code, account_id): fires += 1
                w = random.uniform(ANTI_AFK_MIN_INTERVAL, ANTI_AFK_MAX_INTERVAL)
                w = bypass_packet_jitter(w, 0.25) * _get_personalized_profile(account_id)["afk_scale"]
                try: await asyncio.wait_for(stop_event.wait(), timeout=w); break
                except asyncio.TimeoutError: pass
            except asyncio.CancelledError: break
            except Exception: await asyncio.sleep(1.0)
    except asyncio.CancelledError: pass

# ═══════════════════════════ PLAY GAME ═══════════════════════════
async def play_game(server_ip_port, thunder, sharma, udp_key, match_code,
                    account_id, player_region, client_version, key, iv,
                    match_index, on_match_complete=None):
    t0 = time.time()
    ping_task = anti_task = move_task = None
    sock = None
    ping_stop = asyncio.Event(); anti_stop = asyncio.Event(); move_stop = asyncio.Event()
    uid_str = str(account_id); completed = False
    # Initialize account personality for this session
    await get_account_personality(uid_str)
    _antiban_session_start[uid_str] = time.time()
    _antiban_match_runs[uid_str] = 0
    try:
        ip, port = server_ip_port.split(":"); port = int(port)
        rip = await resolve_host_cloudflare(ip)
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: sock.bind(('0.0.0.0', 0))
        except Exception: pass
        optimize_udp_socket(sock); sock.setblocking(False)
        udp_key_bytes = bytes.fromhex(udp_key)
        await asyncio.sleep(bypass_hello_delay())
        hello = await build_hello_packet(f"{account_id}_2585", udp_key_bytes, match_code)
        await loop.sock_sendto(sock, bytes.fromhex(hello), (rip, port))
        ack_state = "waiting_for_hello_reply"
        thunder_sent = False; join_match_rcv = False; local_closed = False
        send_lock = asyncio.Lock(); anti_started = False
        ping_task = asyncio.create_task(keepalive_ping(sock, rip, port, udp_key_bytes, match_code, ping_stop))
        last_activity = time.time()

        async def start_workers():
            nonlocal anti_task, move_task, anti_started
            if anti_started: return
            anti_started = True
            anti_task = asyncio.create_task(anti_afk_worker(sock, rip, port, udp_key_bytes, match_code,
                                                            account_id, anti_stop, match_index))
            if ENABLE_SPEED_MOVEMENT:
                move_task = asyncio.create_task(movement_worker(sock, rip, port, udp_key_bytes, match_code,
                                                                account_id, move_stop, match_index))

        async def send_startup():
            nonlocal ack_state, thunder_sent
            if thunder_sent: return
            async with send_lock:
                if thunder_sent: return
                try:
                    await loop.sock_sendto(sock, bytes.fromhex(thunder), (rip, port))
                    thunder_sent = True
                    await asyncio.sleep(bypass_jitter(0.1, 0.05))
                    _, nr = await layouts_from_mask(match_code)
                    ack = await build_packet(0x68, nr, 0, 2, None, 1, b"\x01\x00", udp_key_bytes)
                    await loop.sock_sendto(sock, ack, (rip, port))
                    await asyncio.sleep(bypass_jitter(0.2, 0.05))
                    await loop.sock_sendto(sock, bytes.fromhex(sharma), (rip, port))
                    ack_state = "thunder_sharma_sent"
                    await start_workers()
                except Exception as e: print_error(f"[MATCH #{match_index}] startup: {e}", uid_str)

        while not local_closed:
            if time.time() - t0 > MAX_MATCH_DURATION: break
            try:
                resp, saddr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=1.5)
                if resp:
                    last_activity = time.time()
                    frame = await decode_packet(resp, udp_key_bytes, match_code)
                    if frame:
                        pt = await classify(frame)
                        if frame['cmd'] in [103, 107]:
                            completed = True; local_closed = True; continue
                        if frame['cmd'] == 101:
                            try:
                                _, nr = await layouts_from_mask(match_code)
                                a = await build_packet(0x68, nr, 0, 2, None, 1, b"\x01\x00", udp_key_bytes)
                                await loop.sock_sendto(sock, a, saddr)
                            except Exception: pass
                            continue
                        if pt in ["ACK", "PING", "HELLO", "JOIN_MATCH"]:
                            if pt == "HELLO" and ack_state == "waiting_for_hello_reply":
                                _, r = await reply_for(frame, udp_key_bytes, match_code, ack_style="short")
                                if r: await loop.sock_sendto(sock, r, saddr)
                                ack_state = "ack_sent_waiting"
                            elif pt == "ACK":
                                if ack_state == "waiting_for_hello_reply":
                                    _, r = await reply_for(frame, udp_key_bytes, match_code)
                                    if r: await loop.sock_sendto(sock, r, saddr)
                                    ack_state = "ready_to_send_thunder"
                                elif ack_state == "ack_sent_waiting":
                                    ack_state = "ready_to_send_thunder"
                                else:
                                    _, r = await reply_for(frame, udp_key_bytes, match_code)
                                    if r: await loop.sock_sendto(sock, r, saddr)
                            elif pt == "PING":
                                _, r = await reply_for(frame, udp_key_bytes, match_code)
                                if r: await loop.sock_sendto(sock, r, saddr)
                            elif pt == "JOIN_MATCH" and not join_match_rcv:
                                _, r = await reply_for(frame, udp_key_bytes, match_code)
                                if r: await loop.sock_sendto(sock, r, saddr); join_match_rcv = True
            except asyncio.TimeoutError:
                if ack_state == "ready_to_send_thunder" and not thunder_sent:
                    await send_startup()
                elif ack_state == "waiting_for_hello_reply":
                    if (time.time() - last_activity) > 7.0:
                        try:
                            hp = await build_hello_packet(f"{account_id}_2585", udp_key_bytes, match_code)
                            await loop.sock_sendto(sock, bytes.fromhex(hp), (rip, port))
                        except Exception: pass
                        last_activity = time.time()
                    if (time.time() - t0) > 25.0:
                        break
                elif ack_state == "thunder_sharma_sent":
                    if (time.time() - last_activity) > MATCH_IDLE_TIMEOUT:
                        completed = True; break
                continue
            except BlockingIOError: await asyncio.sleep(0.05)
            except OSError: await asyncio.sleep(0.5); continue
            except Exception: await asyncio.sleep(0.5); continue
            if ack_state == "ready_to_send_thunder" and not thunder_sent:
                try: await send_startup()
                except Exception: pass
        return f"match #{match_index} finished"
    except Exception as e:
        print_error(f"[MATCH #{match_index}] {e}", uid_str); return f"match #{match_index} error"
    finally:
        if completed:
            try: bot_state.increment_match(uid_str)
            except Exception: pass
            if on_match_complete:
                try: asyncio.create_task(on_match_complete())
                except Exception: pass
        anti_stop.set()
        move_stop.set()
        for t in (anti_task, move_task):
            if t:
                try:
                    await asyncio.wait_for(t, timeout=2.0)
                except Exception:
                    t.cancel()
                    try:
                        await t
                    except Exception:
                        pass
        ping_stop.set()
        if ping_task:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass
        if sock:
            try: sock.close()
            except Exception: pass
        rem = await _dec_match(uid_str)
        try: bot_state.update_status(uid_str, "IN_MATCH" if rem > 0 else "ONLINE", rem)
        except Exception: pass

# ═══════════════════════════ FRIEND / TEAM HANDLERS ═══════════════════════════
async def _process_social_packet(raw_bytes, account_data, tag="MAIN"):
    try:
        hex_data = raw_bytes.hex()
        candidates = []
        if len(raw_bytes) >= 6:
            plen = raw_bytes[4]
            if 0 < plen <= (len(raw_bytes) - 5):
                try:
                    inner = bytes(raw_bytes[5:5 + plen])
                    d0 = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
                    if d0: candidates.append((5, d0))
                except Exception: pass
        for off in [5, 6, 10, 8, 12, 4, 0]:
            if off >= len(hex_data): continue
            try: inner = bytes.fromhex(hex_data[off:])
            except Exception: continue
            decoded = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
            if decoded: candidates.append((off, decoded))
        if not candidates: return
        candidates.sort(key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0, reverse=True)
        _, decoded = candidates[0]
        def _v(c, k):
            if not isinstance(c, dict): return None
            v = c.get(k) if k in c else c.get(str(k))
            if isinstance(v, dict) and "data" in v: return v["data"]
            return v
        f5w = decoded.get("5") or decoded.get(5) if isinstance(decoded, dict) else None
        f5 = f5w["data"] if isinstance(f5w, dict) and "data" in f5w else f5w
        target = None
        if isinstance(f5, dict):
            for fk in [1, 2, 3, 4, 6]:
                c = _v(f5, fk)
                if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                    target = str(c); break
        if not target: return
        own = str(account_data.get('account_id', '')) if account_data else ''
        if own and target == own: return
        if not _accept_friend_request or not account_data: return
        jwt = account_data.get('token'); srv = account_data.get('server_url')
        rel = account_data.get('release_version'); own_id = account_data.get('account_id')
        if not (jwt and srv and rel and own_id): return
        url = f"{srv.rstrip('/')}/ConfirmFriendRequest"
        fields = {"1": int(target), "2": int(own_id)}
        try:
            payload = bytes.fromhex(encrypt_api(create_proto(fields).hex()))
            hdrs = {
                "authorization": f"Bearer {jwt}",
                "host": srv.replace("https://", "").replace("http://", "").split("/")[0],
                "x-ga": "v1 1", "content-type": "application/x-www-form-urlencoded",
                "accept-encoding": "deflate, gzip", "releaseversion": f"{rel}",
                "user-agent": "UnityPlayer/2022.3.47f1", "accept": "*/*",
                "x-unity-version": "2022.3.47f1",
            }
            async with httpx.AsyncClient(verify=False, timeout=8.0, **_proxy_kwargs()) as s:
                r = await s.post(url, headers=hdrs, content=payload)
                if r.status_code == 200 and len(r.content) > 0:
                    print_success(f"👥 [FRIEND-{tag}] ✅ {target}", str(own_id))
        except Exception: pass
    except Exception: pass

def _wrap_manual(inner):
    try:
        alt = _decode_proto_manual(inner)
        if alt and len(alt) > 0:
            return {str(k): {"data": v} for k, v in alt.items()}
    except Exception: pass
    return None

async def _handle_team_invite(hex_data, pl, uid_str, current_account_data,
                              current_key, current_iv, writer, runtime=None):
    try:
        candidates = []
        for off in [10, 8, 6, 12, 14, 4, 16, 0, 20, 2]:
            if off >= len(hex_data) or len(hex_data) - off < 4: continue
            try: inner = bytes.fromhex(hex_data[off:])
            except Exception: continue
            dec = decode_protobuf_dict_safe(inner)
            if dec and isinstance(dec, dict) and len(dec) > 0:
                candidates.append((off, "parser", dec)); continue
            alt = _decode_proto_manual(inner)
            if alt and len(alt) > 0:
                candidates.append((off, "manual", {str(k): {"data": v} for k, v in alt.items()}))
        if not candidates: return False
        candidates.sort(key=lambda x: len(x[2]) if isinstance(x[2], dict) else 0, reverse=True)
        _, _, dec = candidates[0]

        def _unwrap(d, keys):
            if not isinstance(d, dict): return None
            for k in keys:
                v = d.get(k) if k in d else d.get(str(k))
                if isinstance(v, dict) and "data" in v: return v["data"]
                if isinstance(v, dict): return v
            return None

        target_dict = None
        for kp in [["5"], ["4"], ["6"], ["2"], ["1"]]:
            u = _unwrap(dec, kp)
            if isinstance(u, dict) and len(u) >= 3:
                target_dict = u; break
        if target_dict is None: target_dict = dec

        def _g(d, k):
            if not isinstance(d, dict): return None
            v = d.get(k) if k in d else d.get(str(k))
            if isinstance(v, dict) and "data" in v: return v["data"]
            if isinstance(v, dict):
                for kk in ["1","2","3","4","5","6","7","8"]:
                    vv = v.get(kk) if kk in v else v.get(int(kk))
                    if isinstance(vv, dict) and "data" in vv: return vv["data"]
            return v

        group_id = None
        for k in list(target_dict.keys()):
            c = _g(target_dict, k)
            if isinstance(c, str) and 20 <= len(c) <= 40:
                group_id = c; break
        if not group_id:
            for k in list(dec.keys()):
                c = _g(dec, k)
                if isinstance(c, str) and 20 <= len(c) <= 40:
                    group_id = c; break

        own_acc = str(current_account_data.get('account_id')) if current_account_data else None
        inviter = None
        all_f = list(target_dict.keys()) + list(dec.keys())
        for k in all_f:
            c = _g(target_dict, k) or _g(dec, k)
            if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                if str(c) != uid_str and str(c) != own_acc:
                    inviter = str(c); break

        if inviter and group_id and runtime:
            is_member = (runtime.leader_uid != uid_str)
            if is_member:
                async with runtime.members_lock:
                    already = uid_str in runtime.members_joined
                if already: return True
                accepted = False
                for attempt in range(3):
                    try:
                        acc = accept_team_invite(int(inviter), group_id, current_key, current_iv)
                        if writer and not writer.is_closing():
                            writer.write(acc); await writer.drain()
                            accepted = True; break
                    except Exception: pass
                    await asyncio.sleep(0.8)
                if accepted:
                    await runtime.member_join(uid_str)
                return True
        return False
    except Exception:
        return False

# ═══════════════════════════ FUNCTIONAL (per-squad main loop) ═══════════════════════════
async def functional_battle_royale(runtime: SquadRuntime, addrs, starter_packet, account_region,
                                    client_version, key, iv, account_id="", account_data=None,
                                    account_level=2, max_reconnects=10):
    sid = runtime.squad_id
    reconnects = 0
    ip, port = addrs.split(":")
    play_matches: List[asyncio.Task] = []
    no_response_count = 0
    search_attempts = 0
    uid_str = str(account_id)
    current_level = int(account_level or 2)
    current_token = starter_packet
    current_key = key; current_iv = iv
    current_account_data = account_data
    reconnect_count_total = 0
    region_index = 0
    current_search_region = REGION_ROTATION_LIST[0]
    _writer_ref = {"w": None}
    _team_active = {"flag": True}

    async def trigger_post_match_refresh():
        await asyncio.sleep(EXP_REFRESH_AFTER_MATCH_DELAY)
        try:
            f = bot_state.account_credentials.get(uid_str)
            if f: await refresh_account_profile(f)
        except Exception: pass

    async def _team_coordinator():
        try:
            deadline = time.time() + TEAM_PEER_WAIT_TIMEOUT
            while time.time() < deadline:
                async with runtime.lock:
                    n = len(runtime.peers)
                if n >= TEAM_SIZE: break
                if not runtime.is_running: return
                await asyncio.sleep(0.5)

            async with runtime.lock:
                n = len(runtime.peers)
                is_leader = (runtime.leader_uid == uid_str)
                peers_snapshot = dict(runtime.peers)

            if not is_leader: return
            if n < TEAM_SIZE:
                bot_state.squad_log(sid, f"Only {n}/{TEAM_SIZE} peers — waiting", "warning")

            await asyncio.sleep(TEAM_READY_DELAY)
            async with runtime.lock:
                runtime.team_code = None
                runtime.pk_code = None

            own_id_num = None
            if current_account_data: own_id_num = current_account_data.get('account_id')
            if not own_id_num:
                try: own_id_num = int(uid_str)
                except Exception: own_id_num = 0

            try:
                pkt = create_team(current_key, current_iv, client_version)
                if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                    _writer_ref["w"].write(pkt); await _writer_ref["w"].drain()
                    await runtime.reset_members(keep_leader=False)
                    await runtime.member_join(uid_str)
            except Exception: pass

            await asyncio.sleep(TEAM_CREATE_WAIT)

            peer_uids = []
            for peer_uid, info in peers_snapshot.items():
                if peer_uid == uid_str: continue
                pa = None
                try: pa = info["data"].get("account_id")
                except Exception: pass
                if not pa: pa = peer_uid
                peer_uids.append(int(pa))

            heartbeat_stop = asyncio.Event()
            async def heartbeat_loop():
                while not heartbeat_stop.is_set():
                    try:
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            pkt = team_fresh(int(own_id_num), current_key, current_iv)
                            _writer_ref["w"].write(pkt); await _writer_ref["w"].drain()
                    except Exception: pass
                    try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_HEARTBEAT_INTERVAL)
                    except asyncio.TimeoutError: pass
            hb_task = asyncio.create_task(heartbeat_loop())

            invite_start = time.time(); cycle = 0
            while time.time() - invite_start < TEAM_INVITE_MAX_TIME:
                if not _team_active["flag"]: break
                if not runtime.is_running: break
                cnt = await runtime.member_count()
                if cnt >= TEAM_SIZE: break
                cycle += 1
                for tuid in peer_uids:
                    async with runtime.members_lock:
                        joined = str(tuid) in runtime.members_joined
                    if joined: continue
                    try:
                        inv = invite_player_in_team(tuid, current_key, current_iv, region=account_region)
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            _writer_ref["w"].write(inv); await _writer_ref["w"].drain()
                    except Exception: pass
                    await asyncio.sleep(0.4)
                try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_INVITE_CYCLE_WAIT)
                except asyncio.TimeoutError: pass

            final_cnt = await runtime.member_count()
            if final_cnt < TEAM_SIZE:
                bot_state.squad_log(sid, f"Team only {final_cnt}/{TEAM_SIZE} — retry", "warning")
                heartbeat_stop.set()
                try: hb_task.cancel(); await hb_task
                except Exception: pass
                return

            bot_state.squad_log(sid, f"✅ Team full {final_cnt}/{TEAM_SIZE} — starting match loop", "success")
            await asyncio.sleep(TEAM_FINAL_WAIT)
            heartbeat_stop.set()
            try: hb_task.cancel(); await hb_task
            except Exception: pass

            while _team_active["flag"] and runtime.is_running:
                try:
                    async with runtime.lock:
                        if runtime.leader_uid != uid_str: break
                    oid = current_account_data.get('account_id', own_id_num) if current_account_data else own_id_num
                    _mv = pick_match_variation()
                    await asyncio.sleep(_mv["ready_delay"])
                    try:
                        rdy = ready_for_game(int(oid), current_key, current_iv)
                        if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                            _writer_ref["w"].write(rdy); await _writer_ref["w"].drain()
                    except Exception: pass
                    await asyncio.sleep(_mv["start_delay"])
                    sm = start_match_team(int(oid), current_key, current_iv, region=account_region)
                    if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                        _writer_ref["w"].write(sm); await _writer_ref["w"].drain()
                except Exception: pass
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
        except Exception as e:
            bot_state.squad_log(sid, f"Coordinator error: {e}", "error")

    async def _member_match_trigger():
        try:
            await asyncio.sleep(TEAM_READY_DELAY + TEAM_MEMBER_START_DELAY)
            async with runtime.lock:
                if runtime.leader_uid == uid_str: return
            my_id = current_account_data.get('account_id', uid_str) if current_account_data else uid_str
            while _team_active["flag"] and runtime.is_running:
                try:
                    if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                        _mv = pick_match_variation()
                        await asyncio.sleep(_mv["ready_delay"])
                        try:
                            rdy = ready_for_game(int(my_id), current_key, current_iv)
                            _writer_ref["w"].write(rdy); await _writer_ref["w"].drain()
                        except Exception: pass
                        await asyncio.sleep(_mv["start_delay"])
                        sm = start_match_team(int(my_id), current_key, current_iv, region=account_region)
                        _writer_ref["w"].write(sm); await _writer_ref["w"].drain()
                except Exception: pass
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
        except Exception: pass

    try:
        while runtime.is_running:
            writer = None; gateway_ping_task = None
            team_coord_task = None; member_trigger_task = None
            try:
                if current_account_data:
                    fresh = None
                    if current_account_data.get('auth_type') == 'guest' and current_account_data.get('auth_uid'):
                        fresh = cache_get(str(current_account_data['auth_uid']))
                    elif current_account_data.get('auth_type') == 'token' and current_account_data.get('auth_token'):
                        fresh = cache_get(f"tok_{current_account_data['auth_token'][:20]}")
                    if fresh:
                        current_account_data = fresh
                        current_key = fresh['aes_ak']; current_iv = fresh['iv_i']
                        current_token = await build_tcp_startup_packet(
                            fresh['account_id'], fresh['token'], fresh['server_time'],
                            current_key, current_iv,
                            region=fresh.get('region', account_region), typ='OnLine')
                        try:
                            lv = int(fresh.get('level', current_level) or current_level)
                            if lv != current_level: current_level = lv
                        except Exception: pass
                    else:
                        try:
                            if current_account_data.get('auth_uid'):
                                cache_invalidate(str(current_account_data['auth_uid']))
                            if current_account_data.get('auth_token'):
                                cache_invalidate(f"tok_{current_account_data['auth_token'][:20]}")
                            new_cred = await relogin_account(uid_str, current_account_data)
                            if new_cred:
                                current_account_data = new_cred
                                current_key = new_cred['aes_ak']; current_iv = new_cred['iv_i']
                                current_token = await build_tcp_startup_packet(
                                    new_cred['account_id'], new_cred['token'], new_cred['server_time'],
                                    current_key, current_iv,
                                    region=new_cred.get('region', account_region), typ='OnLine')
                            else:
                                raise ConnectionError("Re-login returned empty credentials")
                        except Exception:
                            await asyncio.sleep(5)
                            raise ConnectionError("Cache expired")

                try:
                    if uid_str in bot_state.accounts:
                        ll = int(bot_state.accounts[uid_str].get('level', current_level) or current_level)
                        if ll != current_level: current_level = ll
                except Exception: pass

                rip = await resolve_host_cloudflare(ip)
                reader, writer = await asyncio.open_connection(rip, int(port))
                _writer_ref["w"] = writer
                raw_sock = writer.get_extra_info('socket')
                if raw_sock: optimize_tcp_socket(raw_sock)
                await asyncio.sleep(bypass_hello_delay())
                writer.write(bytes.fromhex(current_token)); await writer.drain()
                try:
                    ka = await send_keep_alive(account_region)
                    if ka and not writer.is_closing():
                        writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
                except Exception: pass

                async def func_gateway_keepalive():
                    ka_bytes = await send_keep_alive(account_region)
                    while True:
                        await asyncio.sleep(bypass_ka_jitter(5.0))
                        try:
                            if writer and not writer.is_closing():
                                writer.write(ka_bytes); await writer.drain()
                        except Exception: break
                gateway_ping_task = asyncio.create_task(func_gateway_keepalive())

                connection_start_time = asyncio.get_running_loop().time()
                last_watchdog_check = connection_start_time
                search_attempts = 0
                if reconnect_count_total > 0 and (reconnect_count_total % REGION_ROTATE_EVERY_N == 0):
                    region_index = (region_index + 1) % len(REGION_ROTATION_LIST)
                    current_search_region = REGION_ROTATION_LIST[region_index]
                else:
                    current_search_region = REGION_ROTATION_LIST[region_index]

                bot_state.squad_log(sid, f"🔗 TCP connected {uid_str} Lvl{current_level} R:{current_search_region}", "info")
                reconnects = 0; no_response_count = 0

                async with runtime.lock:
                    runtime.peers[uid_str] = {
                        "writer": writer, "data": current_account_data,
                        "key": current_key, "iv": current_iv}
                    if runtime.leader_uid is None:
                        runtime.leader_uid = uid_str
                        bot_state.squad_log(sid, f"👑 Leader: {uid_str}", "success")

                if TEAM_MODE:
                    team_coord_task = asyncio.create_task(_team_coordinator())
                    member_trigger_task = asyncio.create_task(_member_match_trigger())
                else:
                    await start_game_battle_royale(current_search_region, client_version, writer, current_key, current_iv)

                while runtime.is_running:
                    play_matches[:] = [m for m in play_matches if not m.done()]
                    active = await _get_match_count(uid_str)
                    try: bot_state.update_status(uid_str, "ONLINE" if active == 0 else "IN_MATCH", active)
                    except Exception: pass

                    now = asyncio.get_running_loop().time()
                    if now - last_watchdog_check >= MATCH_WATCHDOG_CHECK:
                        last_watchdog_check = now
                        sd = now - connection_start_time
                        if sd > MATCH_SEARCH_TIMEOUT:
                            raise ConnectionError("Search watchdog")
                    if search_attempts >= MAX_SEARCH_ATTEMPTS:
                        raise ConnectionError("Max attempts")

                    try:
                        data = await asyncio.wait_for(reader.read(8192), timeout=0.5)
                    except asyncio.TimeoutError:
                        no_response_count += 1
                        if TEAM_MODE:
                            if no_response_count > TEAM_IDLE_ITERS_TEAM:
                                raise ConnectionError("Team idle timeout")
                        else:
                            if no_response_count > 80: raise ConnectionError("idle")
                        continue

                    if not data: raise ConnectionError("closed")
                    hex_data = data.hex()
                    pl = len(data)
                    no_response_count = 0

                    if hex_data.startswith("0600") and pl > 20:
                        await _process_social_packet(data, current_account_data, tag="MAIN")
                        continue

                    if hex_data.startswith("05") and pl > 10:
                        await _handle_team_invite(hex_data, pl, uid_str, current_account_data,
                                                  current_key, current_iv, writer, runtime)
                        continue

                    if hex_data.startswith("0300") and 10 < pl < 30:
                        continue

                    if hex_data.startswith("0300") and pl >= 300:
                        for tk in (team_coord_task, member_trigger_task):
                            if tk and not tk.done():
                                tk.cancel()
                                try: await tk
                                except asyncio.CancelledError: pass
                        team_coord_task = None; member_trigger_task = None
                        _team_active["flag"] = False

                        try:
                            res = json.loads(await decode_protobuf(hex_data[10:]))
                            token = udp_key = match_code = server_ip_port = None
                            match_account_id = block_val = None
                            if '42' in res and 'data' in res['42']:
                                match_code = res['42']['data']
                            if '5' in res and 'data' in res['5']:
                                r5 = res['5']['data']
                                server_ip_port = r5.get('2', {}).get('data')
                                udp_key = r5.get('3', {}).get('data')
                                token = r5.get('4', {}).get('data')
                                if '42' in r5: match_code = r5['42']['data']
                            if '1' in res and 'data' in res['1']:
                                match_account_id = res['1']['data']
                            if '5' in res and 'data' in res['5']:
                                block_val = res['5']['data'].get('1', {}).get('data')

                            effective = match_account_id or account_id or "BD_BOT"
                            if token and udp_key and match_code and server_ip_port:
                                try:
                                    async with runtime.lock:
                                        runtime.pk_code = str(match_code)
                                        runtime.team_code = str(match_code)
                                except Exception: pass
                                bot_state.squad_log(sid, f"🎯 Match found | Room: {match_code} | Server: {server_ip_port}", "success")

                                acc_tok = current_account_data.get('access_token', '') if current_account_data else ""
                                thunder, sharma = await build_match_startup_packets(
                                    token, udp_key, match_code, effective, block_val or 0,
                                    server_ip=server_ip_port, region=account_region,
                                    client_version=client_version, access_token=acc_tok,
                                    mode_id=BR_MODE_ID, map_id=BR_MAP_ID)
                                match_index = await _inc_match(uid_str)
                                runtime.match_count += 1
                                bot_state.squad_log(sid, f"🎮 Match #{match_index} starting UDP...", "info")

                                new_match = asyncio.create_task(play_game(
                                    server_ip_port, thunder, sharma, udp_key, match_code,
                                    effective, current_search_region, client_version,
                                    current_key, current_iv,
                                    match_index=match_index, on_match_complete=trigger_post_match_refresh))
                                play_matches.append(new_match)

                                async def drain_gw():
                                    while not new_match.done():
                                        try:
                                            dg = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                                            if not dg: break
                                            gh = dg.hex()
                                            if gh.startswith("0600") and len(dg) > 20:
                                                await _process_social_packet(dg, current_account_data, tag="DRAIN")
                                        except asyncio.TimeoutError: continue
                                        except Exception: break
                                drain_task = asyncio.create_task(drain_gw())
                                try: await new_match
                                except Exception as e: bot_state.squad_log(sid, f"Match error: {e}", "error")
                                finally:
                                    drain_task.cancel()
                                    try: await drain_task
                                    except asyncio.CancelledError: pass
                                play_matches[:] = [m for m in play_matches if not m.done()]

                                async with runtime.lock:
                                    runtime.peers.pop(uid_str, None)
                                    if runtime.leader_uid == uid_str:
                                        runtime.leader_uid = None
                                    runtime.pk_code = None
                                await runtime.member_leave(uid_str)
                                _team_active["flag"] = True
                                try: writer.close(); await writer.wait_closed()
                                except Exception: pass
                                bot_state.squad_log(sid, f"🔁 {uid_str} restarting for new match...", "info")
                                await human_match_gap(uid_str)
                                reconnect_count_total += 1
                                break
                            else:
                                try: writer.close(); await writer.wait_closed()
                                except Exception: pass
                                await asyncio.sleep(NON_MATCH_RECONNECT_DELAY)
                                break
                        except Exception as e:
                            bot_state.squad_log(sid, f"Parse error: {e}", "error")
                            try: writer.close(); await writer.wait_closed()
                            except Exception: pass
                            await asyncio.sleep(NON_MATCH_RECONNECT_DELAY)
                            break

                    if 30 <= pl <= 40: continue

            except asyncio.CancelledError:
                for m in play_matches:
                    if not m.done(): m.cancel()
                if play_matches:
                    await asyncio.gather(*play_matches, return_exceptions=True)
                play_matches.clear()
                if gateway_ping_task: gateway_ping_task.cancel()
                async with runtime.lock:
                    runtime.peers.pop(uid_str, None)
                    if runtime.leader_uid == uid_str:
                        runtime.leader_uid = None
                await runtime.member_leave(uid_str)
                raise
            except Exception as e:
                if gateway_ping_task: gateway_ping_task.cancel()
                play_matches[:] = [m for m in play_matches if not m.done()]
                if writer:
                    try: writer.close(); await writer.wait_closed()
                    except Exception: pass
                if "Cache expired" in str(e):
                    break
                reconnect_count_total += 1
                reconnects += 1
                if reconnects > max_reconnects:
                    reconnects = 0
                    await asyncio.sleep(3)
                    continue
                await asyncio.sleep(bypass_human_reconnect_delay(reconnects))
            finally:
                _team_active["flag"] = False
                for tk in (team_coord_task, member_trigger_task):
                    if tk and not tk.done():
                        tk.cancel()
                        try: await tk
                        except (asyncio.CancelledError, Exception): pass
                if gateway_ping_task: gateway_ping_task.cancel()
                if writer:
                    try: writer.close(); await writer.wait_closed()
                    except Exception: pass
                async with runtime.lock:
                    runtime.peers.pop(uid_str, None)
                    if runtime.leader_uid == uid_str:
                        runtime.leader_uid = None
                await runtime.member_leave(uid_str)
                _team_active["flag"] = True
    except asyncio.CancelledError:
        for m in play_matches:
            if not m.done(): m.cancel()
        if play_matches: await asyncio.gather(*play_matches, return_exceptions=True)
        play_matches.clear()
        raise

# ═══════════════════════════ INFORMATIONAL ═══════════════════════════
async def informational(addrs, starter_packet, key, iv, region="BD", max_reconnects=3):
    reconnects = 0
    ip, port = addrs.split(":")
    while True:
        writer = None; ping_task = None
        try:
            rip = await resolve_host_cloudflare(ip)
            reader, writer = await asyncio.open_connection(rip, int(port))
            rs = writer.get_extra_info('socket')
            if rs: optimize_tcp_socket(rs)
            writer.write(bytes.fromhex(starter_packet)); await writer.drain()
            reconnects = 0
            try:
                ka = await send_keep_alive(region)
                if ka and not writer.is_closing():
                    writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
            except Exception: pass
            async def info_ka():
                ka = await send_keep_alive(region)
                while True:
                    await asyncio.sleep(bypass_ka_jitter(5.0))
                    try:
                        if writer and not writer.is_closing():
                            writer.write(ka); await writer.drain()
                    except Exception: break
            ping_task = asyncio.create_task(info_ka())
            while True:
                data = await reader.read(8192)
                if not data: raise ConnectionError("closed")
        except asyncio.CancelledError:
            if ping_task: ping_task.cancel()
            if writer:
                try: writer.close(); await writer.wait_closed()
                except Exception: pass
            raise
        except Exception:
            if ping_task: ping_task.cancel()
            if writer:
                try: writer.close(); await writer.wait_closed()
                except Exception: pass
            reconnects += 1
            if reconnects > max_reconnects:
                await asyncio.sleep(3); reconnects = 0
            else: await asyncio.sleep(1)

# ═══════════════════════════ GUILD ENGINE ═══════════════════════════
_guild_ssl = ssl.create_default_context()
_guild_ssl.check_hostname = False
_guild_ssl.verify_mode    = ssl.CERT_NONE

def _guild_get(url, timeout=20):
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": GUILD_UA,
        "Accept": "application/json, text/plain, */*",
        "Connection": "close",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_guild_ssl) as r:
            return True, r.status, r.read().decode("utf-8", "replace"), url, None
    except urllib.error.HTTPError as e:
        try:  body = e.read().decode("utf-8", "replace")
        except: body = ""
        return False, e.code, body, url, None
    except Exception as e:
        return False, 0, "", url, str(e)

def _guild_call(endpoints, guild_id, uid, pwd):
    last = (False, 0, "", endpoints[0])
    for ep in endpoints:
        q = urllib.parse.urlencode({"guild_id": guild_id, "uid": uid, "password": pwd})
        ok, code, body, used, err = _guild_get(f"{ep}?{q}")
        if ok: return True, code, body, used
        last = (False, code, body, used)
    return last

def guild_do_join(g, u, p):  return _guild_call(GUILD_JOIN_ENDPOINTS,  g, u, p)
def guild_do_leave(g, u, p): return _guild_call(GUILD_LEAVE_ENDPOINTS, g, u, p)

def guild_call_with_retry(fn, gid, uid, pwd, max_retries=3):
    backoff = 0.6
    last = (False, 0, "", "")
    for attempt in range(max_retries + 1):
        try:
            ok, code, body, ep = fn(gid, uid, pwd)
            last = (ok, code, body, ep)
            if ok: return ok, code, body, ep, attempt
            if code == 429 or (500 <= code < 600):
                time.sleep(backoff + random.uniform(0, 0.3))
                backoff *= 2
                continue
            return ok, code, body, ep, attempt
        except Exception as e:
            last = (False, 0, str(e), "")
            time.sleep(backoff)
            backoff *= 2
    return (*last, max_retries)

def get_guild_owner_uid(guild_id):
    endpoints = [
        f"{GUILD_BASE}/guild/info?guild_id={guild_id}",
        f"{GUILD_BASE}/info?guild_id={guild_id}",
        f"{GUILD_BASE}/guild/details?guild_id={guild_id}",
    ]
    for ep in endpoints:
        ok, code, body, _, _ = _guild_get(ep, timeout=12)
        if ok and body:
            try:
                data = json.loads(body)
                owner = (
                    data.get("owner_id") or data.get("leader_id") or
                    data.get("owner_uid") or data.get("leader_uid") or
                    data.get("data", {}).get("owner_id") or
                    data.get("guild_info", {}).get("owner_id")
                )
                if owner and str(owner).isdigit(): return int(owner)
            except Exception: continue
    return None

def guild_encrypt_data(data: bytes) -> bytes:
    cipher = AES.new(FRIEND_AES_KEY, AES.MODE_CBC, FRIEND_AES_IV)
    return cipher.encrypt(pad(data, AES.block_size))

def guild_encode_varint(n: int) -> bytes:
    result = []
    while True:
        byte = n & 0x7F; n >>= 7
        if n: byte |= 0x80
        result.append(byte)
        if not n: break
    return bytes(result)

def guild_build_friend_request_payload(target_uid: int) -> bytes:
    body  = guild_encode_varint(8) + guild_encode_varint(target_uid)
    body += guild_encode_varint(16) + guild_encode_varint(target_uid)
    body += guild_encode_varint(24) + guild_encode_varint(26)
    return body

def guild_jwt_from_external_api(api_url: str, uid: str, password: str, retries: int = 1):
    if _requests is None: return None, "requests unavailable"
    err_msg = ""
    for attempt in range(retries + 1):
        try:
            url = f"{api_url}?uid={uid}&password={password}"
            if JWT_API_KEY:
                url += f"&key={JWT_API_KEY}"
            resp = _requests.get(url, timeout=12, verify=False, proxies=_requests_proxies())
            if resp.status_code == 200:
                data = resp.json()
                token = (
                    data.get("token") or data.get("jwt") or data.get("access_token") or
                    data.get("data", {}).get("token") or data.get("data", {}).get("jwt")
                )
                if token and len(token) > 50: return token, None
                err_msg = "API json missing Token"
            else:
                err_msg = f"API HTTP {resp.status_code}"
        except Exception as e:
            err_msg = str(e)[:30]
        if attempt < retries: time.sleep(0.3)
    return None, err_msg

def guild_get_jwt(uid: str, password: str, retries: int = 1):
    for mname, url in JWT_API_ENDPOINTS:
        jwt, err = guild_jwt_from_external_api(url, uid, password, retries)
        if jwt: return jwt, mname, None
    return None, None, "JWT failed"

def guild_send_friend_request(jwt: str, target_uid: int, retries: int = 1):
    if _requests is None: return False, 0, "requests unavailable"
    plain = guild_build_friend_request_payload(target_uid)
    encrypted = guild_encrypt_data(plain)
    headers = FRIEND_HEADERS.copy()
    headers["Authorization"] = f"Bearer {jwt}"
    last_err = "Max retries"; last_code = 0
    for target_url in BD_FRIEND_URLS:
        for attempt in range(retries + 1):
            try:
                resp = _requests.post(target_url, headers=headers, data=encrypted, timeout=10, verify=False, proxies=_requests_proxies())
                if resp.status_code == 200: return True, resp.status_code, None
                last_code = resp.status_code
                last_err = f"HTTP_{resp.status_code}"
            except Exception as e:
                last_err = str(e)[:25]
            if attempt < retries: time.sleep(0.2)
        if last_code == 200: break
    return False, last_code, last_err

def guild_record_failed(uid, pwd):
    log_dir = "FREXY"
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "failed_accounts.txt"), "a", encoding="utf-8") as f:
            f.write(f"{uid}:{pwd}\n")
    except Exception: pass

# ═══════════════════════════ GUILD RUNNERS ═══════════════════════════
async def guild_run_join_or_leave(jid, guild_id, action, accounts, delay, workers):
    fn = guild_do_join if action == "JOIN" else guild_do_leave
    sem = asyncio.Semaphore(max(1, workers))

    async def one(uid, pwd):
        async with sem:
            try:
                ok, code, body, ep, retries = await asyncio.to_thread(
                    guild_call_with_retry, fn, guild_id, uid, pwd, 3)
                msg = ""
                try:
                    if body:
                        j = json.loads(body)
                        msg = str(j.get("message") or j.get("msg") or j.get("error") or "")[:120]
                except Exception:
                    msg = (body or "")[:120].replace("\n", " ")
                detail = f"HTTP {code} | ep={ep.split('/')[-1]}"
                if not ok:
                    guild_record_failed(uid, pwd)
                bot_state.add_guild_result(jid, uid, ok, msg, detail)
                bot_state.update_guild(str(uid), "SUCCESS" if ok else "FAILED", detail)
                if ok:
                    print_success(f"🏰 [GUILD-{action}] {uid} OK | {msg}", str(uid))
                else:
                    print_error(f"🏰 [GUILD-{action}] {uid} FAIL | {msg}", str(uid))
            except Exception as e:
                bot_state.add_guild_result(jid, uid, False, str(e), "exception")
            await asyncio.sleep(delay)

    tasks = [asyncio.create_task(one(u, p)) for u, p in accounts]
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    bot_state.finish_guild_job(jid)

async def guild_run_owner_spam(jid, guild_id, owner_uid, accounts, delay, workers):
    sem = asyncio.Semaphore(max(1, workers))

    async def one(uid, pwd):
        async with sem:
            try:
                g_ok, g_code, g_body, ep, retries = await asyncio.to_thread(
                    guild_call_with_retry, guild_do_join, guild_id, uid, pwd, 2)
                f_status = "Skipped"; fail_reason = ""
                jwt, method, jwt_err = await asyncio.to_thread(guild_get_jwt, uid, pwd, 1)
                if jwt:
                    ok_f, scode, f_err = await asyncio.to_thread(guild_send_friend_request, jwt, owner_uid, 1)
                    if ok_f: f_status = f"Sent ({scode})"
                    else: f_status = f"Fail ({scode})"; fail_reason = f"Request: {f_err}"
                else:
                    f_status = "JWT Failed"; fail_reason = f"JWT: {jwt_err}"
                extra = f"Guild:{'OK' if g_ok else 'FAIL'} | FR:{f_status}"
                msg = ""
                try:
                    if g_body:
                        j = json.loads(g_body)
                        msg = str(j.get("message") or j.get("msg") or j.get("error") or "")[:120]
                except Exception:
                    msg = (g_body or "")[:120]
                if not g_ok:
                    guild_record_failed(uid, pwd)
                bot_state.add_guild_result(jid, uid, g_ok, msg, extra + (f" | {fail_reason}" if fail_reason else ""))
                bot_state.update_guild(str(uid), "SUCCESS" if g_ok else "FAILED", extra)
                if g_ok:
                    print_success(f"👑 [OWNER-SPAM] {uid} | {extra}", str(uid))
                else:
                    print_error(f"👑 [OWNER-SPAM] {uid} | {extra}", str(uid))
            except Exception as e:
                bot_state.add_guild_result(jid, uid, False, str(e), "exception")
            await asyncio.sleep(delay)

    tasks = [asyncio.create_task(one(u, p)) for u, p in accounts]
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    bot_state.finish_guild_job(jid)

# ═══════════════════════════ ACCOUNT HELPERS ═══════════════════════════
def _register_credentials(ad):
    try:
        acc_id = str(ad['account_id'])
        bot_state.account_credentials[acc_id] = ad
        if ad.get('auth_uid'): bot_state.account_credentials[str(ad['auth_uid'])] = ad
        if ad.get('auth_token'): bot_state.account_credentials[f"tok_{ad['auth_token'][:20]}"] = ad
    except Exception: pass

async def relogin_account(uid_str, old_account_data):
    if not old_account_data: return None
    if old_account_data.get('auth_type') == 'guest':
        u = old_account_data.get('auth_uid'); p = old_account_data.get('auth_password')
        if u and p: return await process_account_uid_pass(str(u), str(p), _skip_cache=True)
    elif old_account_data.get('auth_type') == 'token':
        t = old_account_data.get('auth_token')
        if t: return await process_account_token(str(t), _skip_cache=True)
    return None

async def refresh_account_profile(ad_or_uid):
    try:
        if isinstance(ad_or_uid, str):
            uid = str(ad_or_uid); ad = bot_state.account_credentials.get(uid)
        else:
            ad = ad_or_uid; uid = str(ad.get('account_id')) if ad else "?"
        if not ad: return
        url = ad.get('server_url'); token = ad.get('token')
        rel = ad.get('release_version'); payload = ad.get('login_payload_data')
        if not (url and token and rel and payload): return
        res = await send_getlogin(payload, url, token, rel)
        if not res: return
        rp, dd = res
        def _si(v, d):
            try:
                if v is None or v == "": return d
                return int(v)
            except Exception: return d
        level = _si(get_proto_field(dd, 6, None), None)
        exp = _si(get_proto_field(dd, 7, None), None)
        likes = _si(get_proto_field(dd, 8, None), None)
        try: nick = rp.nickname or get_proto_field(dd, 4, "") or ""
        except Exception: nick = ""
        if level is None and exp is None: return
        level = level if level is not None else 1
        exp = exp if exp is not None else 0
        likes = likes if likes is not None else 0
        acc_id = str(ad['account_id'])
        try: bot_state.update_exp(acc_id, exp, level)
        except Exception: pass
        if likes > 0 and acc_id in bot_state.accounts:
            bot_state.accounts[acc_id]["likes"] = likes
        if nick and acc_id in bot_state.accounts:
            bot_state.accounts[acc_id]["nickname"] = nick
        _update_cache_profile(ad, level, exp)
        ad['level'] = level; ad['exp'] = exp
        if likes > 0: ad['likes'] = likes
        if nick: ad['nickname'] = nick
    except Exception: pass

async def process_account_uid_pass(uid, password, _skip_cache=False):
    if not _skip_cache:
        cached = cache_get(uid)
        if cached:
            acc_id = str(cached['account_id'])
            bot_state.register_account(uid=acc_id,
                nickname=cached.get('nickname', f"Player_{acc_id}"),
                region=cached.get('region', 'BD'),
                level=cached.get('level', 1), exp=cached.get('exp', 0),
                likes=cached.get('likes', 0), password=password)
            _register_credentials(cached); return cached
    try:
        vc = await version_config()
        if not vc: return None
        rel, cv, su = vc
        tg = await get_access_token(uid, password)
        if not tg: return None
        oid, at, pf = tg
        dev = get_device_for_account(uid)
        lpd = await build_majorlogin_payload(oid, at, pf, cv, dev)
        if not lpd: return None
        mresp = await send_majorlogin(lpd, rel, su)
        if mresp is None: return None
        gl = await send_getlogin(lpd, mresp.url, mresp.token, rel)
        if gl is None: return None
        rp, dd = gl
        acc_id = str(mresp.account_id)
        level = int(get_proto_field(dd, 6, 1) or 1)
        exp = int(get_proto_field(dd, 7, 0) or 0)
        likes = int(get_proto_field(dd, 8, 0) or 0)
        nick = rp.nickname or get_proto_field(dd, 4, f"Player_{acc_id}")
        region = mresp.region or get_proto_field(dd, 3, "BD")
        bot_state.register_account(uid=acc_id, nickname=nick, region=region,
                                    level=level, exp=exp, likes=likes, password=password)
        ad = {
            'account_id': mresp.account_id, 'nickname': nick, 'region': region,
            'level': level, 'exp': exp, 'likes': likes,
            'open_id': oid, 'access_token': at, 'platform': str(pf),
            'token': mresp.token, 'server_time': mresp.server_time,
            'aes_ak': mresp.aes_ak, 'iv_i': mresp.iv_i,
            'functional_addrs': rp.functional_addrs or get_proto_field(dd, 14),
            'informational_addrs': rp.informational_addrs or get_proto_field(dd, 32),
            'release_version': rel, 'client_version': cv, 'server_url': mresp.url,
            'login_payload_data': lpd,
            'auth_type': 'guest', 'auth_uid': uid, 'auth_password': password,
        }
        _register_credentials(ad); cache_set(uid, ad); return ad
    except Exception as e:
        print_error(f"process_account_uid_pass: {e}"); return None

async def process_account_token(access_token, _skip_cache=False):
    cache_key = f"tok_{access_token[:20]}"
    if not _skip_cache:
        cached = cache_get(cache_key)
        if cached:
            acc_id = str(cached['account_id'])
            bot_state.register_account(uid=acc_id,
                nickname=cached.get('nickname', f"Player_{acc_id}"),
                region=cached.get('region', 'BD'),
                level=cached.get('level', 1), exp=cached.get('exp', 0),
                likes=cached.get('likes', 0))
            _register_credentials(cached); return cached
    try:
        vc = await version_config()
        if not vc: return None
        rel, cv, su = vc
        if _requests is None: return None
        url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        hdrs = {"User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"}
        resp = await asyncio.to_thread(_requests.get, url, headers=hdrs, timeout=10, proxies=_requests_proxies())
        d = resp.json()
        if 'error' in d: return None
        oid = d.get('open_id'); pf = d.get('platform', 4)
        if not oid: return None
        dev = get_device_for_account(oid)
        lpd = await build_majorlogin_payload(oid, access_token, str(pf), cv, dev)
        if not lpd: return None
        mresp = await send_majorlogin(lpd, rel, su)
        if mresp is None: return None
        gl = await send_getlogin(lpd, mresp.url, mresp.token, rel)
        if gl is None: return None
        rp, dd = gl
        acc_id = str(mresp.account_id)
        level = int(get_proto_field(dd, 6, 1) or 1)
        exp = int(get_proto_field(dd, 7, 0) or 0)
        likes = int(get_proto_field(dd, 8, 0) or 0)
        nick = rp.nickname or get_proto_field(dd, 4, f"Player_{acc_id}")
        region = mresp.region or get_proto_field(dd, 3, "BD")
        bot_state.register_account(uid=acc_id, nickname=nick, region=region,
                                    level=level, exp=exp, likes=likes)
        ad = {
            'account_id': mresp.account_id, 'nickname': nick, 'region': region,
            'level': level, 'exp': exp, 'likes': likes,
            'open_id': oid, 'access_token': access_token, 'platform': str(pf),
            'token': mresp.token, 'server_time': mresp.server_time,
            'aes_ak': mresp.aes_ak, 'iv_i': mresp.iv_i,
            'functional_addrs': rp.functional_addrs or get_proto_field(dd, 14),
            'informational_addrs': rp.informational_addrs or get_proto_field(dd, 32),
            'release_version': rel, 'client_version': cv, 'server_url': mresp.url,
            'login_payload_data': lpd,
            'auth_type': 'token', 'auth_token': access_token,
        }
        _register_credentials(ad); cache_set(cache_key, ad); return ad
    except Exception as e:
        print_error(f"process_account_token: {e}"); return None

async def run_account_worker(runtime: SquadRuntime, ad, label):
    acc_id = str(ad['account_id'])
    info_task = None; exp_task = None; ping_task = None
    try:
        reg = ad.get('region', 'BD')
        tcp_online = await build_tcp_startup_packet(
            ad['account_id'], ad['token'], ad['server_time'],
            ad['aes_ak'], ad['iv_i'], region=reg, typ='OnLine')
        tcp_chat = await build_tcp_startup_packet(
            ad['account_id'], ad['token'], ad['server_time'],
            ad['aes_ak'], ad['iv_i'], region=reg, typ='ChaT')
        info_task = asyncio.create_task(informational(ad['informational_addrs'], tcp_chat,
                                                      ad['aes_ak'], ad['iv_i'], region=reg))
        if ENABLE_HTTP_PING:
            ping_task = asyncio.create_task(ping_worker(acc_id, ad['token'], ad['release_version'], region=reg))

        async def exp_refresher():
            try:
                f = bot_state.account_credentials.get(acc_id)
                if f: await refresh_account_profile(f)
            except Exception: pass
            while True:
                await asyncio.sleep(EXP_REFRESH_INTERVAL + random.uniform(-3.0, 3.0))
                try:
                    f = bot_state.account_credentials.get(acc_id)
                    if f: await refresh_account_profile(f)
                except Exception: pass
        exp_task = asyncio.create_task(exp_refresher())
        await functional_battle_royale(runtime, ad['functional_addrs'], tcp_online, ad['region'], ad['client_version'],
            ad['aes_ak'], ad['iv_i'], account_id=acc_id, account_data=ad,
            account_level=int(ad.get('level', 2) or 2))
    except asyncio.CancelledError: raise
    except Exception as e:
        bot_state.squad_log(runtime.squad_id, f"Account worker error {label}: {e}", "error")
    finally:
        for t in (info_task, exp_task, ping_task):
            if t and not t.done(): t.cancel()
        for t in (info_task, exp_task, ping_task):
            if t:
                try: await t
                except Exception: pass

async def account_loop_guest(runtime: SquadRuntime, uid, password):
    while runtime.is_running:
        try:
            bot_state.update_status(str(uid), "CONNECTING")
            bot_state.squad_log(runtime.squad_id, f"🔐 Logging in {uid}...", "info")
            ad = await process_account_uid_pass(uid, password)
            if not ad:
                bot_state.update_status(str(uid), "ERROR")
                bot_state.squad_log(runtime.squad_id, f"❌ Login failed {uid}", "error")
                await asyncio.sleep(10); continue
            bot_state.squad_log(runtime.squad_id, f"✅ Logged in {uid} ({ad.get('nickname','?')})", "success")
            await run_account_worker(runtime, ad, uid)
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            bot_state.update_status(str(uid), "OFFLINE")
            break
        except Exception as e:
            bot_state.update_status(str(uid), "ERROR")
            bot_state.squad_log(runtime.squad_id, f"Worker error {uid}: {e}", "error")
            await asyncio.sleep(8)

# ═══════════════════════════ SQUAD MANAGER ═══════════════════════════
class SquadManager:
    def __init__(self):
        self.squads: Dict[int, dict] = {}
        self._lock = asyncio.Lock()
        self._counter = 0

    def _allocate_squad_id(self):
        self._counter += 1
        return self._counter

    async def create_squad(self, members: List[Tuple[str, str]]) -> Tuple[bool, str, int]:
        async with self._lock:
            sid = self._allocate_squad_id()
            runtime = SquadRuntime(sid)
            uids = []
            for uid, pw in members:
                bot_state.allow_account(uid)
                uid = str(uid).strip()
                pw = str(pw).strip()
                if not uid or not pw: continue
                for other_sid, other in self.squads.items():
                    if uid in other["uids"]:
                        return False, f"UID {uid} already in Squad {other_sid}", 0
                uids.append(uid)
                bot_state.register_account(uid=uid, nickname=f"Player_{uid}",
                    region="BD", level=1, exp=0, likes=0, password=pw)
                bot_state.accounts[uid]["squad_id"] = sid
                bot_state.accounts[uid]["slot"] = len(uids)
                bot_state.accounts[uid]["status"] = "STOPPED"
            if not uids:
                return False, "No valid accounts", 0
            self.squads[sid] = {
                "runtime": runtime,
                "uids": uids,
                "task": None,
                "is_started": False,
                "credentials": {u: p for u, p in members},
            }
            bot_state.squad_log(sid, f"🛡️ Squad {sid} created with {len(uids)} accounts", "success")
            return True, f"Squad {sid} created", sid

    async def start_squad(self, sid: int) -> Tuple[bool, str]:
        async with self._lock:
            if sid not in self.squads: return False, "Squad not found"
            squad = self.squads[sid]
            if squad["is_started"]: return False, "Already started"
            squad["is_started"] = True
            runtime = squad["runtime"]
            runtime.is_running = True
            runtime.team_active = True

            async def run_all():
                tasks = []
                for uid in squad["uids"]:
                    pw = squad["credentials"].get(uid, "")
                    if pw:
                        t = asyncio.create_task(account_loop_guest(runtime, uid, pw))
                        bot_state.account_workers[uid] = t
                        tasks.append(t)
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            squad["task"] = asyncio.create_task(run_all())
            bot_state.squad_log(sid, f"▶️ Squad {sid} started", "success")
            return True, f"Squad {sid} started"

    async def restart_squad(self, sid: int) -> Tuple[bool, str]:
        async with self._lock:
            if sid not in self.squads: return False, "Squad not found"
            squad = self.squads[sid]
            runtime = squad["runtime"]
            runtime.is_running = False
            for uid in squad["uids"]:
                t = bot_state.account_workers.pop(uid, None)
                if t:
                    t.cancel()
                    try: await t
                    except Exception: pass
            old_task = squad.get("task")
            if old_task:
                old_task.cancel()
                try: await old_task
                except Exception: pass
            await asyncio.sleep(1.0)
            runtime.is_running = True
            runtime.team_active = True
            runtime.peers.clear()
            runtime.leader_uid = None
            runtime.members_joined.clear()
            squad["is_started"] = True

            async def run_all():
                tasks = []
                for uid in squad["uids"]:
                    pw = squad["credentials"].get(uid, "")
                    if pw:
                        t = asyncio.create_task(account_loop_guest(runtime, uid, pw))
                        bot_state.account_workers[uid] = t
                        tasks.append(t)
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            squad["task"] = asyncio.create_task(run_all())
            bot_state.squad_log(sid, f"🔄 Squad {sid} restarted", "success")
            return True, f"Squad {sid} restarted"

    async def stop_squad(self, sid: int) -> Tuple[bool, str]:
        async with self._lock:
            if sid not in self.squads: return False, "Squad not found"
            squad = self.squads[sid]
            runtime = squad["runtime"]
            runtime.is_running = False
            for uid in squad["uids"]:
                t = bot_state.account_workers.pop(uid, None)
                if t:
                    t.cancel()
                    try: await t
                    except Exception: pass
                bot_state.update_status(uid, "STOPPED")
            old_task = squad.get("task")
            if old_task:
                old_task.cancel()
                try: await old_task
                except Exception: pass
            squad["task"] = None
            squad["is_started"] = False
            bot_state.squad_log(sid, f"⏹ Squad {sid} stopped", "warning")
            return True, f"Squad {sid} stopped"

    async def delete_squad(self, sid: int) -> Tuple[bool, str]:
        await self.stop_squad(sid)
        async with self._lock:
            if sid in self.squads:
                for uid in self.squads[sid]["uids"]:
                    bot_state.accounts.pop(uid, None)
                    bot_state.account_credentials.pop(uid, None)
                del self.squads[sid]
                return True, "Deleted"
            return False, "Not found"

    async def remove_member(self, sid: int, uid: str) -> Tuple[bool, str]:
        async with self._lock:
            if sid not in self.squads: return False, "Squad not found"
            squad = self.squads[sid]
            if uid in squad["uids"]:
                squad["uids"].remove(uid)
                squad["credentials"].pop(uid, None)
                t = bot_state.account_workers.pop(uid, None)
                if t:
                    t.cancel()
                    try: await t
                    except Exception: pass
                bot_state.accounts.pop(uid, None)
                bot_state.account_credentials.pop(uid, None)
                return True, "Removed"
            return False, "Not found"

    def get_squads(self):
        out = []
        for sid, s in self.squads.items():
            members = []
            for uid in s["uids"]:
                acc = bot_state.accounts.get(uid, {})
                members.append({
                    "uid": uid,
                    "nickname": acc.get("nickname", "?"),
                    "level": acc.get("level", 1),
                    "matches": acc.get("matches_played", acc.get("matches", 0)),
                    "status": acc.get("status", "STOPPED"),
                    "guild_status": acc.get("guild_status", "—"),
                    "region": acc.get("region", DEFAULT_REGION),
                    "exp": acc.get("current_exp", 0),
                    "gained_exp": acc.get("gained_exp", 0),
                    "next_level": acc.get("next_level", acc.get("level", 1) + 1),
                    "remaining_exp": acc.get("remaining_exp", 0),
                    "progress_pct": acc.get("progress_pct", 0),
                    "mode": acc.get("mode", "BR"),
                    "mode_label": acc.get("mode_label", "Battle Royale"),
                    "likes": acc.get("likes", 0),
                    "is_paused": bot_state.is_paused(uid),
                    "uptime": bot_state.get_account_uptime(uid),
                })
            out.append({
                "id": sid,
                "is_started": s["is_started"],
                "members": members,
            })
        return out

squad_mgr = SquadManager()

# ═══════════════════════════ WEB SERVER ═══════════════════════════
try:
    from aiohttp import web as aioweb
    _HAS_AIOHTTP = True
except Exception:
    _HAS_AIOHTTP = False

ADMIN_SESSIONS: set = set()

def _check_admin(request):
    token = request.cookies.get("admin_token") or request.headers.get("X-Admin-Token")
    return token in ADMIN_SESSIONS

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YADAV LEVEL UP</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0a0a0f; color:#e0e0e0; font-family:'Segoe UI',sans-serif; min-height:100vh; }
.header { background:linear-gradient(135deg,#1a0033,#0d001a); padding:20px; border-bottom:2px solid #ff6600; box-shadow:0 4px 20px rgba(255,102,0,0.3); }
.header h1 { text-align:center; font-size:2em; background:linear-gradient(90deg,#ff6600,#ffaa00,#00cc44); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:900; letter-spacing:3px; }
.header p { text-align:center; color:#00cc44; margin-top:4px; font-size:0.85em; }
.login-box { max-width:400px; margin:80px auto; padding:30px; background:#141420; border-radius:12px; border:1px solid #ff6600; box-shadow:0 8px 32px rgba(0,0,0,0.6); }
.login-box h2 { text-align:center; color:#ff6600; margin-bottom:20px; }
.login-box input { width:100%; padding:12px; margin:8px 0; background:#0a0a0f; border:1px solid #333; color:#e0e0e0; border-radius:6px; font-size:1em; }
.login-box button { width:100%; padding:12px; margin-top:12px; background:linear-gradient(90deg,#ff6600,#ffaa00); border:none; border-radius:6px; color:#000; font-weight:900; font-size:1em; cursor:pointer; }
.login-box button:hover { transform:scale(1.02); }
.btn { padding:8px 14px; background:#ff6600; border:none; border-radius:6px; color:#000; font-weight:bold; cursor:pointer; font-size:0.85em; }
.btn:hover { background:#ffaa00; }
.btn.danger { background:#cc0000; color:#fff; }
.btn.danger:hover { background:#ff2222; }
.btn.green { background:#00cc44; }
.btn.green:hover { background:#00ff55; }
.btn.blue { background:#0088ff; color:#fff; }
.btn.blue:hover { background:#33aaff; }
.btn.gold { background:#ffaa00; }
.btn.red { background:#cc0000; color:#fff; }
.btn.small { padding:5px 10px; font-size:0.75em; }
.tabs { display:flex; gap:4px; padding:12px 20px; background:#141420; flex-wrap:wrap; border-bottom:1px solid #333; }
.tab { padding:8px 16px; background:#0a0a0f; border:1px solid #333; border-radius:6px 6px 0 0; cursor:pointer; color:#888; font-size:0.9em; }
.tab.active { background:#ff6600; color:#000; border-color:#ff6600; font-weight:bold; }
.content { padding:20px; }
.squad-card { background:#141420; border-radius:10px; padding:16px; margin-bottom:16px; border-left:4px solid #ff6600; }
.squad-card h3 { color:#00cc44; margin-bottom:12px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.squad-slots { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; margin-bottom:12px; }
.slot { background:#0a0a0f; padding:10px; border-radius:6px; border:1px dashed #333; min-height:70px; font-size:0.85em; }
.slot.filled { border-style:solid; border-color:#00cc44; }
.slot .status { font-size:0.75em; color:#ffaa00; margin-top:4px; }
.add-form { display:grid; grid-template-columns:1fr 1fr 1fr auto; gap:8px; margin-bottom:16px; max-width:900px; }
.add-form input { padding:10px; background:#0a0a0f; border:1px solid #333; color:#e0e0e0; border-radius:6px; }
.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:12px; }
.form-grid input { padding:10px; background:#0a0a0f; border:1px solid #333; color:#e0e0e0; border-radius:6px; }
.log-panel { background:#000; border:1px solid #333; border-radius:8px; padding:12px; height:400px; overflow-y:auto; font-family:'Consolas',monospace; font-size:0.8em; margin-top:10px; }
.log-line { padding:2px 0; }
.log-line.success { color:#00ff55; }
.log-line.error { color:#ff2222; }
.log-line.warning { color:#ffaa00; }
.log-line.info { color:#66ccff; }
.badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:0.7em; font-weight:bold; }
.badge.online { background:#00cc44; color:#000; }
.badge.offline { background:#666; color:#fff; }
.badge.stopped { background:#666; color:#fff; }
.badge.error { background:#cc0000; color:#fff; }
.badge.inmatch { background:#ff6600; color:#000; }
.badge.success { background:#00cc44; color:#000; }
.badge.failed { background:#cc0000; color:#fff; }
.badge.pending { background:#666; color:#fff; }
.badge.connecting { background:#ffaa00; color:#000; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:16px; }
.stat { background:#141420; padding:14px; border-radius:8px; text-align:center; border:1px solid #ff6600; }
.stat .num { font-size:1.8em; font-weight:900; color:#ff6600; }
.stat .lbl { font-size:0.75em; color:#888; margin-top:4px; }
.row { display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap; }
.guild-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:8px; margin-top:12px; }
.guild-item { background:#0a0a0f; border:1px solid #333; border-radius:6px; padding:8px; font-size:0.8em; }
.guild-item.ok { border-color:#00cc44; }
.guild-item.fail { border-color:#cc0000; }
.guild-item .u { font-weight:bold; color:#fff; }
.guild-item .m { color:#888; font-size:0.75em; margin-top:4px; word-break:break-word; }
.alert-red { background:#2a0000; border:1px solid #cc0000; border-radius:8px; padding:14px; margin:12px 0; color:#ff6666; }
.alert-green { background:#002a00; border:1px solid #00cc44; border-radius:8px; padding:14px; margin:12px 0; color:#00ff88; }
.alert-info { background:#001a2a; border:1px solid #0088ff; border-radius:8px; padding:14px; margin:12px 0; color:#66ccff; }
select { padding:10px; background:#0a0a0f; border:1px solid #333; color:#e0e0e0; border-radius:6px; }
.squad-create-form { background:#0a0a0f; padding:14px; border-radius:8px; border:1px solid #444; }
.member-input { display:grid; grid-template-columns:60px 1fr 1fr; gap:8px; margin-bottom:8px; align-items:center; }
.member-input label { color:#888; font-size:0.85em; }
.member-input input { padding:8px; background:#141420; border:1px solid #333; color:#e0e0e0; border-radius:5px; font-size:0.85em; }
</style>
</head>
<body>
<div id="app"></div>
<script>
const API = window.location.origin;
let adminToken = localStorage.getItem('fglory_token') || '';
let currentTab = 'dashboard';
let pollTimer = null;
let currentConsoleSquad = null;

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}

async function api(path, opts={}) {
  opts.headers = opts.headers || {};
  if (adminToken) opts.headers['X-Admin-Token'] = adminToken;
  if (opts.body && typeof opts.body !== 'string') { opts.body = JSON.stringify(opts.body); opts.headers['Content-Type']='application/json'; }
  try {
    const r = await fetch(API+path, opts);
    return await r.json();
  } catch(e) { return {ok:false, error:'network error'}; }
}

function renderLogin() {
  document.getElementById('app').innerHTML = `
    <div class="header"><h1>YADAV LEVEL UP</h1><p>🔥 Squad + Guild Premium Bot v6.0 🇮🇳 🔥</p></div>
    <div class="login-box">
      <h2>🔐 Admin Login</h2>
      <input type="password" id="pw" placeholder="Admin Password" onkeydown="if(event.key==='Enter')doLogin()">
      <button onclick="doLogin()">LOGIN</button>
      <p style="text-align:center;color:#666;margin-top:12px;font-size:0.75em;">YADAV LEVEL UP v6.0 © 2026 🇮🇳</p>
    </div>`;
}

async function doLogin() {
  const pw = document.getElementById('pw').value;
  const r = await api('/api/login', {method:'POST', body:{password:pw}});
  if (r.ok) { adminToken = r.token; localStorage.setItem('fglory_token', adminToken); renderMain(); }
  else { alert('Wrong password!'); }
}

function renderMain() {
  document.getElementById('app').innerHTML = `
    <div class="header"><h1>YADAV LEVEL UP</h1><p>🔥 Squad + Guild Premium Bot v6.0 🇮🇳 🔥</p></div>
    <div class="tabs">
      <div class="tab ${currentTab==='dashboard'?'active':''}" onclick="switchTab('dashboard')">📊 Dashboard</div>
      <div class="tab ${currentTab==='create'?'active':''}" onclick="switchTab('create')">➕ Create Squad</div>
      <div class="tab ${currentTab==='guild'?'active':''}" onclick="switchTab('guild')">🏰 Guild</div>
      <div class="tab ${currentTab==='consoles'?'active':''}" onclick="switchTab('consoles')">💻 Consoles</div>
      <div class="tab" onclick="logout()" style="margin-left:auto;background:#cc0000;color:#fff;">🚪 Logout</div>
    </div>
    <div class="content" id="content"></div>`;
  if (pollTimer) clearInterval(pollTimer);
  if (currentTab==='dashboard') { renderDashboard(); pollTimer = setInterval(renderDashboard, 2000); }
  else if (currentTab==='create') { renderCreate(); }
  else if (currentTab==='guild') { renderGuild(); pollTimer = setInterval(refreshGuild, 1500); }
  else if (currentTab==='consoles') { renderConsoles(); pollTimer = setInterval(refreshConsoles, 2000); }
}

function switchTab(t){ currentTab=t; renderMain(); }

async function renderDashboard() {
  const d = await api('/api/status');
  if (!d.ok) return;
  const c = document.getElementById('content');
  if (!c) return;
  const failed = (d.failed_uids || []);
  let html = `
    <div class="stats">
      <div class="stat"><div class="num">${d.total_squads}</div><div class="lbl">Squads</div></div>
      <div class="stat"><div class="num">${d.total_accounts}</div><div class="lbl">Accounts</div></div>
      <div class="stat"><div class="num">${d.total_matches}</div><div class="lbl">Total Matches</div></div>
      <div class="stat"><div class="num">${d.active_workers}</div><div class="lbl">Workers</div></div>
    </div>`;
  if (failed.length > 0) {
    html += `<div class="alert-red">⚠️ <b>${failed.length} account(s) failed guild request:</b> ${failed.map(esc).join(', ')} — নতুন ID দিয়ে আবার চেষ্টা করো।</div>`;
  }
  html += `<div id="squads"></div>`;
  c.innerHTML = html;
  const sq = document.getElementById('squads');
  if (!d.squads || d.squads.length===0) {
    sq.innerHTML = '<div class="squad-card"><p style="color:#888;">No squads yet. Go to "Create Squad" tab to make one.</p></div>';
    return;
  }
  let sHtml = '';
  for (const s of d.squads) {
    let slotsHtml = '';
    for (let i=0;i<4;i++) {
      const m = s.members[i];
      if (m) {
        const st = (m.status||'STOPPED').toUpperCase();
        const badgeCls = st==='ONLINE'?'online':st==='IN_MATCH'?'inmatch':st==='ERROR'?'error':st==='CONNECTING'?'connecting':'stopped';
        const gst = (m.guild_status||'—').toUpperCase();
        const gBadge = gst==='SUCCESS'?'success':gst==='FAILED'?'failed':'pending';
        slotsHtml += `<div class="slot filled">
          <div><b>Slot ${i+1}</b> <span class="badge ${badgeCls}">${esc(st)}</span></div>
          <div style="color:#fff;font-size:1.05em;margin:4px 0;">${esc(m.nickname||'?')}</div>
          <div style="color:#888;">UID: ${esc(m.uid)}</div>
          <div class="status">Lvl ${m.level||1} | Matches: ${m.matches||0}</div>
          <div style="margin-top:4px;"><span class="badge ${gBadge}">🏰 ${esc(gst)}</span></div>
          <div class="row">
            <button class="btn small danger" onclick="removeMember(${s.id}, '${esc(m.uid)}')">🗑️</button>
          </div>
        </div>`;
      } else {
        slotsHtml += `<div class="slot"><div style="color:#444;">Slot ${i+1} — Empty</div></div>`;
      }
    }
    const startBtn = s.is_started
      ? `<button class="btn small gold" onclick="restartSquad(${s.id})">🔄 Restart</button>
         <button class="btn small red" onclick="stopSquad(${s.id})">⏹ Stop</button>`
      : `<button class="btn small green" onclick="startSquad(${s.id})">▶️ Start</button>`;
    sHtml += `<div class="squad-card">
      <h3>🛡️ Squad ${s.id} ${s.is_started?'<span class="badge success">RUNNING</span>':'<span class="badge stopped">STOPPED</span>'} (${s.members.length}/4)
        <div style="margin-left:auto;display:flex;gap:6px;">
          ${startBtn}
          <button class="btn small danger" onclick="deleteSquad(${s.id})">🗑️ Delete Squad</button>
        </div>
      </h3>
      <div class="squad-slots">${slotsHtml}</div>
    </div>`;
  }
  sq.innerHTML = sHtml;
}

function renderCreate() {
  let rowsHtml = '';
  for (let i=1;i<=4;i++) {
    rowsHtml += `<div class="member-input">
      <label>Slot ${i}</label>
      <input id="cuid${i}" placeholder="UID">
      <input id="cpw${i}" type="password" placeholder="Password">
    </div>`;
  }
  document.getElementById('content').innerHTML = `
    <div class="squad-card">
      <h3>➕ Create New Squad</h3>
      <p style="color:#888;font-size:0.85em;margin-bottom:10px;">৪টা UID/Password দাও (অন্তত ১টা)। Create চাপলে squad তৈরি হবে, Start চাপলে match শুরু হবে।</p>
      <div class="squad-create-form">
        ${rowsHtml}
        <button class="btn green" style="margin-top:12px;width:100%;padding:12px;font-size:1em;" onclick="createSquad()">✅ CREATE SQUAD</button>
      </div>
    </div>`;
}

async function createSquad() {
  const members = [];
  for (let i=1;i<=4;i++) {
    const uid = document.getElementById('cuid'+i).value.trim();
    const pw = document.getElementById('cpw'+i).value.trim();
    if (uid && pw) members.push({uid, password:pw});
  }
  if (members.length === 0) return alert('অন্তত ১টা UID + Password দাও');
  const r = await api('/api/squad/create', {method:'POST', body:{members}});
  if (!r.ok) return alert('Error: '+r.error);
  alert('✅ Squad '+r.squad_id+' তৈরি হয়েছে! Start করতে Dashboard এ যাও।');
  switchTab('dashboard');
}

async function startSquad(sid) {
  const r = await api('/api/squad/start', {method:'POST', body:{squad_id:sid}});
  if (!r.ok) alert('Error: '+r.error); else renderDashboard();
}

async function restartSquad(sid) {
  if (!confirm('Restart Squad '+sid+'?')) return;
  const r = await api('/api/squad/restart', {method:'POST', body:{squad_id:sid}});
  if (!r.ok) alert('Error: '+r.error); else renderDashboard();
}

async function stopSquad(sid) {
  if (!confirm('Stop Squad '+sid+'?')) return;
  const r = await api('/api/squad/stop', {method:'POST', body:{squad_id:sid}});
  if (!r.ok) alert('Error: '+r.error); else renderDashboard();
}

async function deleteSquad(sid) {
  if (!confirm('Delete Squad '+sid+'? This will remove all members.')) return;
  const r = await api('/api/squad/delete', {method:'POST', body:{squad_id:sid}});
  if (!r.ok) alert('Error: '+r.error); else renderDashboard();
}

async function removeMember(sid, uid) {
  if (!confirm('Remove '+uid+' from Squad '+sid+'?')) return;
  const r = await api('/api/squad/remove', {method:'POST', body:{squad_id:sid, uid}});
  if (!r.ok) alert('Error: '+r.error); else renderDashboard();
}

async function renderGuild() {
  document.getElementById('content').innerHTML = `
    <div class="squad-card">
      <h3>🏰 Manual Guild Join (Any UID)</h3>
      <p style="color:#888;font-size:0.85em;margin-bottom:10px;">এখানে যেকোনো UID + Password দিয়ে guild-এ join/leave/owner-spam করা যাবে — squad-এর বাইরের ID-ও চলবে।</p>
      <div class="form-grid">
        <input id="gGuildId" placeholder="Guild ID">
        <select id="gAction">
          <option value="JOIN">Join</option>
          <option value="LEAVE">Leave</option>
          <option value="OWNER_SPAM">Owner Spam (Join + FR)</option>
        </select>
      </div>
      <div class="form-grid" style="grid-template-columns:1fr 1fr auto;">
        <input id="gUid" placeholder="UID">
        <input id="gPw" type="password" placeholder="Password">
        <button class="btn blue" onclick="guildOne()">Send For This UID</button>
      </div>
      <hr style="margin:16px 0; border-color:#333;">
      <h4 style="color:#ffaa00;margin-bottom:10px;">Batch Mode (Squad-এর সব ID)</h4>
      <div class="form-grid" style="grid-template-columns:1fr 1fr auto auto;">
        <input id="gBatchGuildId" placeholder="Guild ID">
        <select id="gBatchAction">
          <option value="JOIN">Join</option>
          <option value="LEAVE">Leave</option>
          <option value="OWNER_SPAM">Owner Spam</option>
        </select>
        <input id="gOwnerUid" placeholder="Owner UID (for OWNER_SPAM)">
        <button class="btn gold" onclick="guildBatch()">🚀 Run On All Accounts</button>
      </div>
    </div>
    <div id="guildResult"></div>`;
  await refreshGuild();
}

async function guildOne() {
  const guild_id = document.getElementById('gGuildId').value.trim();
  const action = document.getElementById('gAction').value;
  const uid = document.getElementById('gUid').value.trim();
  const password = document.getElementById('gPw').value.trim();
  if (!guild_id || !uid || !password) return alert('Guild ID + UID + Password required');
  const r = await api('/api/guild/one', {method:'POST', body:{guild_id, action, uid, password}});
  if (!r.ok) alert('Error: '+r.error);
  else refreshGuild();
}

async function guildBatch() {
  const guild_id = document.getElementById('gBatchGuildId').value.trim();
  const action = document.getElementById('gBatchAction').value;
  const owner_uid = document.getElementById('gOwnerUid').value.trim();
  if (!guild_id) return alert('Guild ID required');
  const r = await api('/api/guild/run', {method:'POST', body:{guild_id, action, owner_uid}});
  if (!r.ok) alert('Error: '+r.error);
  else refreshGuild();
}

async function refreshGuild() {
  const hist = await api('/api/guild/jobs');
  const d = await api('/api/status');
  const el = document.getElementById('guildResult');
  if (!el) return;
  let h = '';
  if (d.ok && d.failed_uids && d.failed_uids.length > 0) {
    h += `<div class="alert-red">⚠️ <b>${d.failed_uids.length} account(s) failed:</b> ${d.failed_uids.map(esc).join(', ')}</div>`;
  }
  if (hist && hist.ok && hist.jobs && hist.jobs.length > 0) {
    for (const job of hist.jobs.slice().reverse().slice(0, 5)) {
      const total = job.uids.length;
      const results = Object.entries(job.results || {});
      const ok = results.filter(([_,r]) => r.ok).length;
      const fail = results.filter(([_,r]) => !r.ok).length;
      h += `<div class="squad-card">
        <h3>🎯 Job #${job.id} — ${esc(job.guild_id)} — ${esc(job.action)} ${job.done?'<span class="badge success">DONE</span>':'<span class="badge connecting">RUNNING</span>'}</h3>
        <div class="stats">
          <div class="stat"><div class="num">${total}</div><div class="lbl">Total</div></div>
          <div class="stat"><div class="num" style="color:#00cc44">${ok}</div><div class="lbl">Success</div></div>
          <div class="stat"><div class="num" style="color:#cc0000">${fail}</div><div class="lbl">Failed</div></div>
        </div>
        <div class="guild-grid">`;
      for (const [uid, r] of results) {
        h += `<div class="guild-item ${r.ok?'ok':'fail'}">
          <div class="u">${esc(uid)} <span class="badge ${r.ok?'success':'failed'}">${r.ok?'OK':'FAIL'}</span></div>
          <div class="m">${esc(r.msg || '')}</div>
          <div class="m">${esc(r.detail || '')}</div>
        </div>`;
      }
      h += `</div></div>`;
    }
  } else {
    h += `<div class="squad-card"><p style="color:#888;">No guild job started yet.</p></div>`;
  }
  el.innerHTML = h;
}

async function renderConsoles() {
  const d = await api('/api/status');
  if (!d.ok) return;
  let html = `<div class="alert-info">💻 প্রতিটা squad-এর আলাদা console। Squad select করো।</div>`;
  if (!d.squads || d.squads.length === 0) {
    html += `<div class="squad-card"><p style="color:#888;">No squads yet.</p></div>`;
    document.getElementById('content').innerHTML = html;
    return;
  }
  if (currentConsoleSquad === null) currentConsoleSquad = d.squads[0].id;
  html += `<div class="row" style="margin-bottom:12px;">`;
  for (const s of d.squads) {
    html += `<button class="btn ${currentConsoleSquad===s.id?'blue':''}" onclick="selectConsole(${s.id})">💻 Squad ${s.id}</button>`;
  }
  html += `</div>`;
  html += `<div id="consoleBox"></div>`;
  document.getElementById('content').innerHTML = html;
  await loadConsole(currentConsoleSquad);
}

async function selectConsole(sid) {
  currentConsoleSquad = sid;
  await renderConsoles();
}

async function loadConsole(sid) {
  if (!sid) return;
  const d = await api('/api/squad/logs?squad_id='+sid);
  const box = document.getElementById('consoleBox');
  if (!box) return;
  if (!d.ok) { box.innerHTML = '<p style="color:#f66;">Error loading logs</p>'; return; }
  let html = `<div class="squad-card">
    <h3>💻 Console — Squad ${sid}</h3>
    <div class="log-panel">`;
  const logs = d.logs || [];
  if (logs.length === 0) {
    html += `<div style="color:#666;">No logs yet for this squad.</div>`;
  } else {
    for (const l of logs) {
      html += `<div class="log-line ${l.lvl}">[${l.t}] ${esc(l.m)}</div>`;
    }
  }
  html += `</div></div>`;
  box.innerHTML = html;
  const panel = box.querySelector('.log-panel');
  if (panel) panel.scrollTop = panel.scrollHeight;
}

async function refreshConsoles() {
  if (currentConsoleSquad) await loadConsole(currentConsoleSquad);
}

function logout() {
  localStorage.removeItem('fglory_token');
  adminToken='';
  if (pollTimer) clearInterval(pollTimer);
  renderLogin();
}

if (adminToken) {
  api('/api/status').then(d => { if (d.ok) renderMain(); else renderLogin(); }).catch(()=>renderLogin());
} else {
  renderLogin();
}
</script>
</body>
</html>
"""

async def web_index(request):
    index_path = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                return aioweb.Response(text=f.read(), content_type="text/html")
        except Exception:
            pass
    return aioweb.Response(text=HTML_PAGE, content_type="text/html")

async def web_health(request):
    return aioweb.json_response({
        "ok": True, "brand": BRAND_NAME, "status": "healthy",
        "guild_api": "danger-guild-management-web.vercel.app",
        "version": "7.0.0"
    })

async def web_create_guest(request):
    """Create a Free Fire guest account — user creates it in Free Fire app, then pastes UID + password here."""
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        uid = str(body.get("uid", "")).strip()
        password = str(body.get("password", "")).strip()
        if not uid or not password:
            return aioweb.json_response({
                "ok": False,
                "error": "UID + Password required. Create a guest account in Free Fire app first (Login → Guest), then paste credentials here.",
            })

        # Validate by running the full login flow
        ad = await process_account_uid_pass(uid, password, _skip_cache=True)
        if not ad:
            return aioweb.json_response({
                "ok": False,
                "error": "Invalid UID/Password or Garena rejected. Create a fresh guest account in Free Fire app and try again.",
                "uid": uid,
            })

        # Step 3: Register in dashboard
        bot_state.register_account(
            uid=str(ad['account_id']),
            nickname=f"Guest_{str(ad['account_id'])[:6]}",
            region=DEFAULT_REGION,
            level=ad.get('level', 1),
            exp=ad.get('exp', 0),
            likes=ad.get('likes', 0),
            password=password,
            slot=0
        )
        bot_state.accounts[str(ad['account_id'])]['auth_type'] = 'guest'
        bot_state.accounts[str(ad['account_id'])]['auth_uid'] = uid
        bot_state.accounts[str(ad['account_id'])]['auth_password'] = password
        bot_state.log_sync(str(ad['account_id']), "Guest account registered via Free Fire app credentials", "success")

        return aioweb.json_response({
            "ok": True,
            "uid": str(ad['account_id']),
            "nickname": f"Guest_{str(ad['account_id'])[:6]}",
            "password": password,
            "level": ad.get('level', 1),
            "region": ad.get('region', DEFAULT_REGION),
            "message": "Guest account registered. Add to squad and hit Start to play matches and earn glory.",
        })
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_login(request):
    try:
        body = await request.json()
        pw = str(body.get("password", "")).strip()
        print_info(f"[LOGIN] attempt from {request.remote} password={'set' if pw else 'empty'}")
        if pw == ADMIN_PASSWORD:
            tok = secrets.token_hex(24)
            ADMIN_SESSIONS.add(tok)
            print_success(f"[LOGIN] success token={tok[:12]}...")
            return _add_cors_headers(aioweb.json_response({"ok": True, "token": tok}))
        print_error(f"[LOGIN] wrong password from {request.remote}")
        return _add_cors_headers(aioweb.json_response({"ok": False, "error": "Wrong password — check ADMIN_PASSWORD"}))
    except Exception as e:
        print_error(f"[LOGIN] error: {e}\n{traceback.format_exc()}")
        return _add_cors_headers(aioweb.json_response({"ok": False, "error": f"{type(e).__name__}: {e}"}))

def _require_admin(request):
    if not _check_admin(request):
        return aioweb.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    return None

async def web_status(request):
    chk = _require_admin(request)
    if chk: return chk
    squads = squad_mgr.get_squads()
    failed_uids = [uid for uid, a in bot_state.accounts.items() if a.get("guild_status") == "FAILED"]
    total_gained = sum(a.get("gained_exp", 0) for a in bot_state.accounts.values())
    uptime = max(1, int(time.time() - bot_state.start_time))
    return aioweb.json_response({
        "ok": True,
        "total_squads": len(squad_mgr.squads),
        "total_accounts": len(bot_state.accounts),
        "total_matches": sum(a.get("matches_played", a.get("matches", 0)) for a in bot_state.accounts.values()),
        "active_workers": sum(1 for t in bot_state.account_workers.values() if not t.done()),
        "total_gained_exp": total_gained,
        "exp_per_hour": int((total_gained / uptime) * 3600),
        "uptime": uptime,
        "squads": squads,
        "failed_uids": failed_uids,
    })

async def web_glory(request):
    """Match Play / Glory — full per-account progression for the glory leaderboard."""
    chk = _require_admin(request)
    if chk: return chk
    accounts = []
    for uid, a in bot_state.accounts.items():
        accounts.append({
            "uid": uid,
            "nickname": a.get("nickname", f"Player_{str(uid)[:6]}"),
            "region": a.get("region", DEFAULT_REGION),
            "level": a.get("level", 1),
            "next_level": a.get("next_level", a.get("level", 1) + 1),
            "exp": a.get("current_exp", 0),
            "gained_exp": a.get("gained_exp", 0),
            "remaining_exp": a.get("remaining_exp", 0),
            "target_exp": a.get("target_exp", 0),
            "needed_for_level": a.get("needed_for_level", 1),
            "earned_in_level": a.get("earned_in_level", 0),
            "progress_pct": a.get("progress_pct", 0),
            "likes": a.get("likes", 0),
            "matches": a.get("matches_played", a.get("matches", 0)),
            "status": a.get("status", "STOPPED"),
            "mode": a.get("mode", "BR"),
            "mode_label": a.get("mode_label", "Battle Royale"),
            "is_paused": bot_state.is_paused(uid),
            "uptime": bot_state.get_account_uptime(uid),
            "squad_id": a.get("squad_id", 0),
            "last_updated": a.get("last_updated", "—"),
        })
    accounts.sort(key=lambda x: x.get("gained_exp", 0), reverse=True)
    total_gained = sum(a["gained_exp"] for a in accounts)
    total_matches = sum(a["matches"] for a in accounts)
    uptime = max(1, int(time.time() - bot_state.start_time))
    active = sum(1 for a in accounts if str(a.get("status", "")).upper() == "IN_MATCH")
    return aioweb.json_response({
        "ok": True,
        "brand": BRAND_NAME,
        "total_accounts": len(accounts),
        "total_gained_exp": total_gained,
        "total_matches": total_matches,
        "active_matches": active,
        "exp_per_hour": int((total_gained / uptime) * 3600),
        "uptime": uptime,
        "accounts": accounts,
    })

async def web_antiban_get(request):
    chk = _require_admin(request)
    if chk: return chk
    return aioweb.json_response({"ok": True, **antiban_snapshot()})

async def web_antiban_set(request):
    chk = _require_admin(request)
    if chk: return chk
    global ANTI_BAN_LEVEL
    try:
        body = await request.json()
        lvl = str(body.get("level", "")).lower()
        if lvl != "max":
            return aioweb.json_response({
                "ok": False,
                "error": "Anti-ban is locked to MAX for account safety — fast speed profile was removed",
                **antiban_snapshot(),
            })
        ANTI_BAN_LEVEL = "max"
        return aioweb.json_response({"ok": True, **antiban_snapshot()})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})


async def web_network_get(request):
    chk = _require_admin(request)
    if chk: return chk
    return aioweb.json_response({"ok": True, **network_snapshot()})

async def web_network_set(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        proxies = body.get("proxies", [])
        if isinstance(proxies, str):
            proxies = [p.strip() for p in proxies.replace("\r", "").split("\n") if p.strip()]
        enabled = bool(body.get("enabled", True))
        set_proxy_list(proxies, enabled=enabled)
        bot_state.log_sync("system", f"🌐 Proxy pool updated: {len(PROXY_LIST)} entries | enabled={USE_PROXY}", "info")
        return aioweb.json_response({"ok": True, **network_snapshot()})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_proxy_fetch(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        limit = int(body.get("limit", MAX_AUTO_PROXIES) or MAX_AUTO_PROXIES)
        validate = bool(body.get("validate", True))
        # run in background so the HTTP request does not hang for a minute
        asyncio.create_task(fetch_free_proxies(limit=min(limit, 1000), validate=validate))
        return aioweb.json_response({"ok": True, "started": True, **PROXY_FETCH_STATE})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_proxy_status(request):
    chk = _require_admin(request)
    if chk: return chk
    return aioweb.json_response({"ok": True, **PROXY_FETCH_STATE, **network_snapshot()})


async def web_squad_create(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        members_raw = body.get("members", [])
        members = []
        for m in members_raw:
            u = str(m.get("uid","")).strip()
            p = str(m.get("password","")).strip()
            if u and p: members.append((u, p))
        if not members:
            return aioweb.json_response({"ok": False, "error": "No valid members"})
        ok, msg, sid = await squad_mgr.create_squad(members)
        return aioweb.json_response({"ok": ok, "squad_id": sid, "msg": msg, "error": None if ok else msg})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_squad_start(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        sid = int(body.get("squad_id", 0))
        ok, msg = await squad_mgr.start_squad(sid)
        return aioweb.json_response({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_squad_restart(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        sid = int(body.get("squad_id", 0))
        ok, msg = await squad_mgr.restart_squad(sid)
        return aioweb.json_response({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_squad_stop(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        sid = int(body.get("squad_id", 0))
        ok, msg = await squad_mgr.stop_squad(sid)
        return aioweb.json_response({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_squad_delete(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        sid = int(body.get("squad_id", 0))
        ok, msg = await squad_mgr.delete_squad(sid)
        return aioweb.json_response({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_squad_remove(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        sid = int(body.get("squad_id", 0))
        uid = str(body.get("uid","")).strip()
        ok, msg = await squad_mgr.remove_member(sid, uid)
        return aioweb.json_response({"ok": ok, "error": None if ok else msg})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_account_remove(request):
    """Hard-remove a UID from the dashboard: stop its worker, detach it from any
    squad, drop every trace, and block it from re-registering."""
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        uid = str(body.get("uid", "")).strip()
        if not uid:
            return aioweb.json_response({"ok": False, "error": "uid required"})
        detached = []
        for sid, sq in list(squad_mgr.squads.items()):
            if uid in [str(u) for u in sq.get("uids", [])]:
                try:
                    ok, _msg = await squad_mgr.remove_member(sid, uid)
                    if ok: detached.append(sid)
                except Exception:
                    pass
        bot_state.remove_account(uid)
        bot_state.log_sync(uid, "Removed from dashboard by admin", "warning")
        return aioweb.json_response({"ok": True, "uid": uid, "squads": detached})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_squad_logs(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        sid_str = request.query.get("squad_id", "0")
        sid = int(sid_str)
        return aioweb.json_response({"ok": True, "logs": bot_state.squad_logs.get(sid, [])})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_auto_setup(request):
    """Full automation: create guest accounts → squads → join guild → start all → glory."""
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        squad_count = int(body.get("squad_count", 1) or 1)
        guild_id = str(body.get("guild_id", "")).strip()
        if squad_count < 1 or squad_count > 20:
            return aioweb.json_response({"ok": False, "error": "squad_count must be 1-20"})
        if not guild_id:
            return aioweb.json_response({"ok": False, "error": "guild_id required"})

        created = []
        errors = []

        for i in range(squad_count):
            try:
                # Try auto guest creation via Garena
                ad = await _auto_create_guest_account()
                if not ad:
                    errors.append(f"Squad {i+1}: Garena guest creation failed — create guest in Free Fire app manually")
                    continue

                # Register account
                acc_id = str(ad["account_id"])
                pw = ad.get("password", str(ad.get("auth_uid", acc_id)))
                bot_state.register_account(
                    uid=acc_id,
                    nickname=f"Auto_{acc_id[:6]}",
                    region=DEFAULT_REGION,
                    level=ad.get("level", 1),
                    exp=ad.get("exp", 0),
                    likes=ad.get("likes", 0),
                    password=pw,
                    slot=1,
                )
                bot_state.accounts[acc_id]["auth_type"] = "guest"
                bot_state.accounts[acc_id]["auth_uid"] = str(ad.get("auth_uid", acc_id))
                bot_state.accounts[acc_id]["auth_password"] = pw
                created.append((acc_id, pw))

                # Create 1-account squad
                ok, msg, sid = await squad_mgr.create_squad([(acc_id, pw)])
                if not ok:
                    errors.append(f"Squad {i+1}: {msg}")
                    continue

                # Start squad
                ok2, msg2 = await squad_mgr.start_squad(sid)
                if not ok2:
                    errors.append(f"Squad {sid}: start failed — {msg2}")

            except Exception as e:
                errors.append(f"Squad {i+1}: {str(e)}")

        # Join all created accounts to guild
        guild_results = []
        if created and guild_id:
            uids = [u for u, _ in created]
            jid = await bot_state.new_guild_job(guild_id, "JOIN", uids)
            delay = 0.8; workers = 3
            asyncio.create_task(guild_run_join_or_leave(jid, guild_id, "JOIN", created, delay, workers))
            guild_results.append({"job_id": jid, "guild_id": guild_id, "accounts": len(uids)})

        return aioweb.json_response({
            "ok": True,
            "squads_created": len(created),
            "squads_requested": squad_count,
            "guild_id": guild_id,
            "guild_jobs": guild_results,
            "errors": errors,
            "message": f"{len(created)} squad(s) created and started. Join guild job(s) dispatched.",
        })
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def _auto_create_guest_account():
    """Try to auto-create a Free Fire guest account via Garena OAuth grant endpoint."""
    try:
        import uuid, json
        device_id = str(uuid.uuid4())
        grant_url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        hdrs = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
        }
        grant_data = {
            "response_type": "token",
            "client_type": "2",
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_id": "100067",
            "device_id": device_id,
        }

        oid = at = pf = None
        for attempt in range(5):
            try:
                r = await client.post(grant_url, headers=hdrs, data=grant_data)
                if r.status_code == 200:
                    d = r.json()
                    oid = d.get("open_id") or d.get("uid")
                    at = d.get("access_token") or d.get("token")
                    pf = d.get("platform", 4)
                    if oid and at:
                        break
                if r.status_code == 429:
                    await asyncio.sleep(1); continue
            except Exception:
                pass
            await asyncio.sleep(0.5)

        if not oid or not at:
            return None

        uid = str(oid)
        vc = await version_config()
        if not vc:
            return None
        rel, cv, su = vc

        dev = get_device_for_account(uid)
        lpd = await build_majorlogin_payload(uid, at, str(pf), cv, dev)
        if not lpd:
            return None

        mresp = await send_majorlogin(lpd, rel, su)
        if mresp is None:
            return None

        gl = await send_getlogin(lpd, mresp.url, mresp.token, rel)
        if gl is None:
            return None

        rp, dd = gl
        acc_id = str(mresp.account_id)
        level = int(get_proto_field(dd, 6, 1) or 1)
        exp = int(get_proto_field(dd, 7, 0) or 0)
        likes = int(get_proto_field(dd, 8, 0) or 0)
        nick = rp.nickname or get_proto_field(dd, 4, f"Player_{acc_id}")
        region = mresp.region or get_proto_field(dd, 3, "BD")

        return {
            "account_id": acc_id,
            "nickname": nick,
            "region": region,
            "level": level,
            "exp": exp,
            "likes": likes,
            "auth_uid": uid,
            "password": device_id,
        }
    except Exception:
        return None

async def web_guild_one(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        guild_id = str(body.get("guild_id","")).strip()
        action = str(body.get("action","JOIN")).upper()
        uid = str(body.get("uid","")).strip()
        password = str(body.get("password","")).strip()
        if not (guild_id and uid and password):
            return aioweb.json_response({"ok": False, "error": "guild_id + uid + password required"})
        if action not in ("JOIN", "LEAVE", "OWNER_SPAM"):
            return aioweb.json_response({"ok": False, "error": "invalid action"})
        async def run_one():
            try:
                if action == "OWNER_SPAM":
                    owner_uid = await asyncio.to_thread(get_guild_owner_uid, guild_id)
                    if not owner_uid:
                        bot_state.update_guild(uid, "FAILED", "Owner UID auto-detect failed")
                        bot_state.log_sync(uid, "❌ Owner UID auto-detect failed", "error")
                        return
                    g_ok, g_code, g_body, ep, retries = await asyncio.to_thread(
                        guild_call_with_retry, guild_do_join, guild_id, uid, password, 2)
                    f_status = "Skipped"
                    jwt, _, jwt_err = await asyncio.to_thread(guild_get_jwt, uid, password, 1)
                    if jwt:
                        ok_f, scode, f_err = await asyncio.to_thread(guild_send_friend_request, jwt, owner_uid, 1)
                        f_status = f"Sent({scode})" if ok_f else f"Fail({scode})"
                    extra = f"Guild:{'OK' if g_ok else 'FAIL'} | FR:{f_status}"
                    bot_state.update_guild(uid, "SUCCESS" if g_ok else "FAILED", extra)
                    if g_ok:
                        bot_state.log_sync(uid, f"👑 Owner-Spam OK — {extra}", "success")
                        print_success(f"👑 [OWNER-SPAM-ONE] {uid} — {extra}", uid)
                    else:
                        bot_state.log_sync(uid, f"❌ Owner-Spam FAIL — {extra}", "error")
                        print_error(f"👑 [OWNER-SPAM-ONE] {uid} — {extra}", uid)
                        guild_record_failed(uid, password)
                else:
                    fn = guild_do_join if action == "JOIN" else guild_do_leave
                    ok, code, resp_body, ep, retries = await asyncio.to_thread(
                        guild_call_with_retry, fn, guild_id, uid, password, 3)
                    msg = ""
                    try:
                        if resp_body:
                            j = json.loads(resp_body)
                            msg = str(j.get("message") or j.get("msg") or j.get("error") or "")[:120]
                    except Exception:
                        msg = (resp_body or "")[:120]
                    detail = f"HTTP {code}"
                    bot_state.update_guild(uid, "SUCCESS" if ok else "FAILED", detail)
                    if ok:
                        bot_state.log_sync(uid, f"🏰 Guild {action} OK | {msg}", "success")
                        print_success(f"🏰 [GUILD-ONE] {uid} {action} OK | {msg}", uid)
                    else:
                        bot_state.log_sync(uid, f"🏰 Guild {action} FAIL | {msg}", "error")
                        print_error(f"🏰 [GUILD-ONE] {uid} {action} FAIL | {msg}", uid)
                        guild_record_failed(uid, password)
            except Exception as e:
                bot_state.log_sync(uid, f"Guild error: {e}", "error")
        asyncio.create_task(run_one())
        return aioweb.json_response({"ok": True})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_guild_run(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        body = await request.json()
        guild_id = str(body.get("guild_id","")).strip()
        action = str(body.get("action","JOIN")).upper()
        owner_uid_raw = str(body.get("owner_uid","")).strip()
        if not guild_id:
            return aioweb.json_response({"ok": False, "error": "guild_id required"})
        if action not in ("JOIN", "LEAVE", "OWNER_SPAM"):
            return aioweb.json_response({"ok": False, "error": "invalid action"})
        accounts = []
        for uid, acc in bot_state.accounts.items():
            pw = acc.get("password", "")
            if uid and pw: accounts.append((uid, pw))
        if not accounts:
            return aioweb.json_response({"ok": False, "error": "No accounts in squads"})
        owner_uid = None
        if action == "OWNER_SPAM":
            if owner_uid_raw.isdigit(): owner_uid = int(owner_uid_raw)
            else: owner_uid = await asyncio.to_thread(get_guild_owner_uid, guild_id)
            if not owner_uid:
                return aioweb.json_response({"ok": False, "error": "Owner UID required (auto-detect failed)"})
        uids = [u for u, _ in accounts]
        jid = await bot_state.new_guild_job(guild_id, action, uids)
        bot_state.guild_jobs[jid]["owner_uid"] = owner_uid
        delay = 0.8; workers = 3
        if action == "OWNER_SPAM":
            asyncio.create_task(guild_run_owner_spam(jid, guild_id, owner_uid, accounts, delay, workers))
        else:
            asyncio.create_task(guild_run_join_or_leave(jid, guild_id, action, accounts, delay, workers))
        return aioweb.json_response({"ok": True, "job_id": jid, "total": len(uids)})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

async def web_guild_jobs(request):
    chk = _require_admin(request)
    if chk: return chk
    try:
        jobs = []
        for jid, j in bot_state.guild_jobs.items():
            jobs.append({
                "id": j["id"], "guild_id": j["guild_id"], "action": j["action"],
                "uids": j["uids"], "results": j["results"],
                "started": j["started"], "done": j["done"],
                "owner_uid": j.get("owner_uid"),
            })
        jobs.sort(key=lambda x: x["started"])
        return aioweb.json_response({"ok": True, "jobs": jobs})
    except Exception as e:
        return aioweb.json_response({"ok": False, "error": str(e)})

def _add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-Token, Authorization"
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    return resp

APP_VERSION = "7.0.0"
APP_BUILD = os.environ.get("RENDER_GIT_COMMIT", os.environ.get("GIT_COMMIT", "local"))

@aioweb.middleware
async def _error_middleware(request, handler):
    """Never let a bare 500 escape — always return JSON with the real error."""
    try:
        resp = await handler(request)
        if isinstance(resp, aioweb.Response):
            _add_cors_headers(resp)
            p = request.path
            if p == "/" or p.endswith((".html", ".js", ".css")):
                resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                resp.headers["Pragma"] = "no-cache"
                resp.headers["Expires"] = "0"
        return resp
    except aioweb.HTTPException as ex:
        _add_cors_headers(ex)
        return ex
    except Exception as ex:
        tb = traceback.format_exc()
        print_error(f"[500] {request.method} {request.path} -> {ex}\n{tb}")
        return aioweb.json_response(
            {"ok": False, "error": f"{type(ex).__name__}: {ex}", "path": request.path},
            status=500, headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
                "Access-Control-Allow-Headers": "Content-Type, X-Admin-Token, Authorization",
            },
        )

async def _boot_proxy_refresh():
    """Non-blocking: wait for the server to be healthy, then top up the proxy pool."""
    try:
        await asyncio.sleep(10)
        if len(PROXY_LIST) >= 20:
            print_info(f"🌐 Proxy pool already has {len(PROXY_LIST)} entries — skipping auto-fetch")
            return
        print_info("🌐 Auto-fetching free proxy pool from GitHub…")
        res = await fetch_free_proxies()
        if res.get("ok"):
            print_success(f"🌐 Proxy pool ready: {res.get('alive', 0)} live proxies")
        else:
            print_warning(f"🌐 Proxy auto-fetch failed: {res.get('error')}")
    except Exception as e:
        try:
            print_warning(f"🌐 Proxy auto-fetch skipped: {e}")
        except Exception:
            pass

async def start_web_server():
    if not _HAS_AIOHTTP:
        print_error("aiohttp not installed! Run: pip install aiohttp")
        return None
    try:
        app = aioweb.Application(middlewares=[_error_middleware])
        # Static files
        app.router.add_static('/static/', path=STATIC_DIR, name='static')
        app.router.add_get("/", web_index)
        app.router.add_get("/health", web_health)
        app.router.add_get("/healthz", web_health)
        app.router.add_get("/api/health", web_health)
        app.router.add_post("/api/account/guest", web_create_guest)
        app.router.add_post("/api/login", web_login)
        app.router.add_get("/api/status", web_status)
        app.router.add_get("/api/glory", web_glory)
        app.router.add_get("/api/antiban", web_antiban_get)
        app.router.add_post("/api/antiban", web_antiban_set)
        app.router.add_get("/api/network", web_network_get)
        app.router.add_post("/api/network", web_network_set)
        app.router.add_post("/api/proxy/fetch", web_proxy_fetch)
        app.router.add_get("/api/proxy/status", web_proxy_status)
        app.router.add_post("/api/squad/create", web_squad_create)
        app.router.add_post("/api/squad/start", web_squad_start)
        app.router.add_post("/api/squad/restart", web_squad_restart)
        app.router.add_post("/api/squad/stop", web_squad_stop)
        app.router.add_post("/api/squad/delete", web_squad_delete)
        app.router.add_post("/api/squad/remove", web_squad_remove)
        app.router.add_post("/api/account/remove", web_account_remove)
        app.router.add_get("/api/squad/logs", web_squad_logs)
        app.router.add_post("/api/guild/one", web_guild_one)
        app.router.add_post("/api/guild/run", web_guild_run)
        app.router.add_post("/api/auto/setup", web_auto_setup)
        app.router.add_get("/api/guild/jobs", web_guild_jobs)

        async def handle_ping(request):
            return _add_cors_headers(aioweb.json_response({"ok": True, "brand": BRAND_NAME, "status": "alive"}))

        async def handle_version(request):
            return _add_cors_headers(aioweb.json_response({
                "ok": True, "brand": BRAND_NAME, "version": APP_VERSION,
                "build": APP_BUILD, "python": sys.version.split()[0],
                "aiohttp": getattr(aioweb, "__version__", "?"),
                "password_set": "env" if "ADMIN_PASSWORD" in os.environ else "default",
            }))
        app.router.add_get("/api/version", handle_version)
        app.router.add_get("/api/ping", handle_ping)

        async def handle_options(request):
            return _add_cors_headers(aioweb.Response(text="", status=200))
        app.router.add_options("/{path:.*}", handle_options)

        async def on_response_prepare(request, response):
            _add_cors_headers(response)
        app.on_response_prepare.append(on_response_prepare)

        runner = aioweb.AppRunner(app)
        await runner.setup()
        site = aioweb.TCPSite(runner, WEB_HOST, WEB_PORT)
        await site.start()
        print_success(f"🌐 Web Dashboard: http://{WEB_HOST}:{WEB_PORT}")
        print_info(f"🔑 Admin Password: {'(set via env)' if 'ADMIN_PASSWORD' in os.environ else ADMIN_PASSWORD}")
        asyncio.create_task(_boot_proxy_refresh())
        return runner
    except Exception as e:
        print_error(f"Web server error: {e}")
        return None

# ═══════════════════════════ MAIN ═══════════════════════════
async def main():
    print_banner()
    print_section("⚙️  SYSTEM CONFIGURATION", Colors.PURPLE)
    print_info(f"🎮 Mode          : MANUAL SQUAD + GUILD 🇮🇳")
    print_info(f"🌏 Default Region: {DEFAULT_REGION}")
    print_success(f"👥 SQUAD size={TEAM_SIZE} | manual create/start/stop")
    print_info(f"📡 HTTP Ping     : {'ENABLED' if ENABLE_HTTP_PING else 'DISABLED'}")
    print_info(f"🏃 Speed Movement: {'ENABLED' if ENABLE_SPEED_MOVEMENT else 'DISABLED'}")
    print_info(f"🛡️  Safe Mode     : {'ENABLED' if SAFE_PLAY_MODE else 'DISABLED'}")
    print_info(f"🏰 Guild Tag     : {GUILD_TAG}")
    print_info(f"🔐 Admin Password: {'(set via env)' if 'ADMIN_PASSWORD' in os.environ else ADMIN_PASSWORD}")
    await start_web_server()
    print_colored(f"\n{Colors.BDGREEN}  ✅ {BRAND_WEB_NAME} is running — Open http://localhost:{WEB_PORT}{Colors.ENDC}\n")
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print_section("🛑 SHUTTING DOWN", Colors.BDRED)
        for t in list(bot_state.account_workers.values()):
            t.cancel()
        await asyncio.gather(*bot_state.account_workers.values(), return_exceptions=True)
        print_success(f"👋 {BRAND_WEB_NAME} closed. Goodbye! 🇮🇳")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("stopped")