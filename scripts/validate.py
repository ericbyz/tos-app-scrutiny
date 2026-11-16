#!/usr/bin/env python3
"""Validate TOS package metadata for scrutiny (official rules, guide ch.4/8/14).

open_path mode (external browser tab, frp-style): checks config.ini required
fields, mutual exclusion of type/open_path, id charset rules, category limits
(official category IDs), lang coverage (26 documented languages, advisory),
icon SVG validity, and port consistency between config.ini path and the
scrutiny.yaml seed + services. Exit code 0 = pass.
"""
import json
import os
import re
import sys

REQUIRED = ["id", "icon", "publisher", "exec", "version", "help",
            "category", "platform", "application_type", "user"]
LANG_BASELINE = [
    "zh-cn", "zh-hk", "en-us", "ko-kr", "ja-jp", "de-de", "fr-fr", "it-it",
    "es-es", "hu-hu", "pl-pl", "tr-tr", "ru-ru", "pt-pt", "cs-cz", "da-dk",
    "nl-nl", "nb-no", "sv-se", "el-gr", "ro-ro", "th-th", "vi-vn", "id-id",
    "ar-sa", "he-il",
]
OFFICIAL_CATEGORIES = {
    "Audio_Video_Entertainment", "Photography_Video", "Backup_Sync",
    "Development_Tools", "Utilities", "Web_Services", "Security",
    "Download", "Driver", "Artificial_Intelligence",
}
ID_FORBIDDEN_PREFIX = "tos"
ID_FORBIDDEN_WORDS = {"docker", "bin", "api", "admin"}
RESERVED_PORTS = {22, 80, 443, 445, 3306, 5050, 5432, 6379, 8181, 8443}

errors: list[str] = []
advisories: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)

    cfg = json.load(open("config.ini", encoding="utf-8"))

    for field in REQUIRED:
        if field not in cfg:
            err(f"missing required field: {field}")

    app_id = cfg.get("id", "")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,49}", app_id):
        err(f"id '{app_id}' violates charset rules (lowercase letters/digits/"
            "hyphen, must start with a letter, <=50 chars)")
    if app_id.startswith(ID_FORBIDDEN_PREFIX):
        err(f"id must not start with reserved prefix '{ID_FORBIDDEN_PREFIX}'")
    if app_id in ID_FORBIDDEN_WORDS:
        err(f"id must not be a generic keyword: {app_id}")

    if cfg.get("application_type") != "deb":
        err(f"application_type must be 'deb', got {cfg.get('application_type')!r}")
    if cfg.get("platform") not in ("x86_64", "aarch64"):
        err(f"platform must be x86_64 or aarch64, got {cfg.get('platform')!r}")
    if len(cfg.get("category", [])) > 3:
        err("category must have at most 3 entries")
    for c in cfg.get("category", []):
        if c not in OFFICIAL_CATEGORIES:
            advisories.append(f"category '{c}' is not an official category ID "
                              "(Appendix A) — may need pre-approval")
    if "type" in cfg and cfg.get("open_path"):
        err("type and open_path are mutually exclusive — choose only one")
    if not cfg.get("help"):
        err("help URL is mandatory and cannot be empty")

    # UI mode check: this package is open_path only (dashboard in new tab)
    path = cfg.get("path", "")
    web_port = None

    if cfg.get("open_path"):
        m = re.match(r"^http://\$\{ip\}:(\d+)$", path)
        if not m:
            err(f"open_path mode expects path like http://${{ip}}:<port>, got {path!r}")
        else:
            web_port = int(m.group(1))
            if web_port in RESERVED_PORTS:
                err(f"port {web_port} is a TOS reserved port")
            if not (8000 <= web_port <= 19999):
                advisories.append(f"port {web_port} is outside the recommended 8000-19999 range")
    else:
        err("scrutiny must use open_path mode (dashboard port)")

    # port consistency with the scrutiny.yaml seed + services
    seed_path = "packaging-extras/scrutiny.yaml.default"
    if not os.path.exists(seed_path):
        err(f"missing {seed_path} (config seed)")
    else:
        seed = open(seed_path, encoding="utf-8").read()
        m = re.search(r"^\s*port:\s*(\d+)", seed, re.M)
        if not m:
            err(f"{seed_path}: missing web.listen.port")
        elif web_port is not None and int(m.group(1)) != web_port:
            err(f"{seed_path} listen port {m.group(1)} != config.ini path port {web_port}")
        if "/var/lib/scrutiny" not in seed:
            err(f"{seed_path}: database/log must live under /var/lib/scrutiny")
        ep = re.search(r"endpoint:\s*'http://127\.0\.0\.1:(\d+)'", seed)
        if not ep:
            err(f"{seed_path}: collector api.endpoint must be http://127.0.0.1:<port>")
        elif web_port is not None and int(ep.group(1)) != web_port:
            err(f"{seed_path} collector endpoint port {ep.group(1)} != web port {web_port}")

    for svc in ("init.d/scrutiny-web.service", "init.d/scrutiny-collector.service"):
        if not os.path.exists(svc):
            err(f"missing {svc}")
        else:
            body = open(svc, encoding="utf-8").read()
            if "--config /etc/scrutiny/scrutiny.yaml" not in body:
                err(f"{svc}: ExecStart must load /etc/scrutiny/scrutiny.yaml")
    if not os.path.exists("init.d/scrutiny-collector.timer"):
        err("missing init.d/scrutiny-collector.timer (daily SMART collection)")

    # lang coverage
    lang_path = f"{app_id}.lang"
    if not os.path.exists(lang_path):
        err(f"missing {lang_path}")
    else:
        content = open(lang_path, encoding="utf-8-sig").read()
        if "\r\n" in content:
            advisories.append("lang file should use LF endings")
        missing = [l for l in LANG_BASELINE if f"[{l}]" not in content]
        if missing:
            advisories.append(f"{len(missing)} documented languages missing: {', '.join(missing)}")
        for section in re.split(r"\n(?=\[)", content):
            sm = re.match(r"\[([a-z-]+)\]", section)
            if not sm:
                continue
            loc = sm.group(1)
            for key in ("name", "auth", "descript"):
                km = re.search(rf'^{key}\s*=\s*"([^"]*)"', section, re.M)
                if km is None or not km.group(1).strip():
                    err(f"{lang_path}: [{loc}] has empty or missing {key}")

    # icon
    icon_rel = cfg.get("icon", "").lstrip("/")
    if not os.path.exists(icon_rel):
        err(f"icon not found: {icon_rel}")
    else:
        svg = open(icon_rel, encoding="utf-8").read()
        if "<svg" not in svg or "</svg>" not in svg:
            err(f"{icon_rel} is not a valid SVG")
        if "viewBox" not in svg:
            err(f"{icon_rel} missing viewBox attribute")
        expected = f"{app_id}.svg"
        if os.path.basename(icon_rel) != expected:
            err(f"icon filename {os.path.basename(icon_rel)} should be {expected}")

    for e in errors:
        print(f"ERROR: {e}")
    for a in advisories:
        print(f"ADVISORY: {a}")
    if errors:
        print(f"\n{len(errors)} error(s), {len(advisories)} advisory(ies)")
        return 1
    print("All validations passed" + (f" ({len(advisories)} advisories)" if advisories else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
