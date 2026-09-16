import os
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from db import get_animal_names, insert_story, story_exists
from ocr import extract_text, match_animal

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "static" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def api_base():
    # Instagram Login: graph.instagram.com / Facebook Login: graph.facebook.com
    return os.getenv("META_API_BASE", "https://graph.instagram.com").rstrip("/")


def graph_version():
    return os.getenv("META_GRAPH_VERSION", "v26.0")


def fetch_active_stories():
    ig_user_id = os.getenv("INSTAGRAM_USER_ID", "").strip()
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not ig_user_id or not token:
        raise RuntimeError("INSTAGRAM_USER_ID / INSTAGRAM_ACCESS_TOKEN 이 설정되지 않았습니다.")

    endpoint = f"{api_base()}/{graph_version()}/{ig_user_id}/stories"
    params = {
        "fields": "id,media_type,media_url,thumbnail_url,timestamp,permalink",
        "access_token": token,
    }
    response = requests.get(endpoint, params=params, timeout=20)
    response.raise_for_status()
    return response.json().get("data", [])


def _extension(url, content_type, media_type):
    guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
    if guessed:
        return ".jpg" if guessed == ".jpe" else guessed
    path_ext = Path(urlparse(url).path).suffix
    if path_ext and len(path_ext) <= 6:
        return path_ext
    return ".mp4" if media_type == "VIDEO" else ".jpg"


def download_media(story):
    media_type = story.get("media_type", "IMAGE")
    url = story.get("media_url")
    if not url:
        raise RuntimeError("media_url이 없는 스토리입니다.")

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    ext = _extension(url, response.headers.get("content-type", ""), media_type)
    filename = f"ig_{story['id']}{ext}"
    filepath = MEDIA_DIR / filename
    filepath.write_bytes(response.content)

    ocr_filepath = filepath
    if media_type == "VIDEO" and story.get("thumbnail_url"):
        thumb = requests.get(story["thumbnail_url"], timeout=30)
        thumb.raise_for_status()
        thumb_path = MEDIA_DIR / f"ig_{story['id']}_thumb.jpg"
        thumb_path.write_bytes(thumb.content)
        ocr_filepath = thumb_path

    return filepath, ocr_filepath


def sync_stories():
    stories = fetch_active_stories()
    animals = get_animal_names()
    result = {"found": len(stories), "saved": 0, "matched": 0, "unmatched": 0, "errors": []}

    for story in stories:
        try:
            if story_exists(story["id"]):
                continue

            filepath, ocr_filepath = download_media(story)
            ocr_text = extract_text(ocr_filepath)
            animal_id, reason, confidence = match_animal(ocr_text, animals)

            created_at = story.get("timestamp") or datetime.now(timezone.utc).isoformat()
            insert_story(
                {
                    "instagram_story_id": story["id"],
                    "animal_id": animal_id,
                    "media_type": story.get("media_type", "IMAGE"),
                    "local_path": f"media/{filepath.name}",
                    "source_url": story.get("media_url", ""),
                    "permalink": story.get("permalink", ""),
                    "ocr_text": ocr_text,
                    "match_reason": reason,
                    "confidence": confidence,
                    "created_at": created_at,
                }
            )
            result["saved"] += 1
            if animal_id:
                result["matched"] += 1
            else:
                result["unmatched"] += 1
        except Exception as exc:
            result["errors"].append({"story_id": story.get("id"), "error": str(exc)})

    return result
