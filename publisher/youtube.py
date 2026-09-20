"""
NEXUS VAULTS 2.0 - Headless YouTube Publisher
Uploads rendered Shorts via YouTube Data API v3 with quota tracking.
Consumes exact OAuth credentials (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN)
through core.config. Zero hardcoded tokens or secrets.
Supports Scheduled Publication via status.publishAt with privacyStatus=private.
"""

import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional
from core.config import config
from core.logging import log

def upload_short_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    tags: list,
    category_id: Optional[str] = None,
    publish_at: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Uploads a short video directly to YouTube using OAuth2 Refresh Token from config.youtube.
    If publish_at is provided (ISO-8601 UTC string), video is uploaded with privacyStatus='private'
    and status.publishAt set to schedule automatic public release.
    Cost: 1,600 units of the daily 10,000 unit YouTube Data API quota.
    """
    client_id = config.youtube.client_id
    client_secret = config.youtube.client_secret
    refresh_token = config.youtube.refresh_token
    effective_category = category_id or config.youtube.category_id

    if not (client_id and client_secret and refresh_token):
        log.error("YouTube OAuth2 credentials missing. Production upload cannot proceed.")
        return None

    # 1. Exchange refresh token for access token
    log.info("Refreshing YouTube OAuth2 access token...")
    token_url = "https://oauth2.googleapis.com/token"
    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(token_url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
            access_token = token_data.get("access_token")
            if not access_token:
                log.error("Failed to obtain access token from OAuth refresh endpoint.")
                return None
    except Exception as e:
        # Avoid leaking client_secret in error message
        log.error(f"Failed to refresh YouTube access token: OAuth exchange error.")
        return None

    # 2. Upload video file via Resumable Upload
    status_dict: Dict[str, Any] = {
        "selfDeclaredMadeForKids": False
    }
    if publish_at:
        # YouTube Data API requires privacyStatus="private" when publishAt is set
        status_dict["privacyStatus"] = "private"
        status_dict["publishAt"] = publish_at
        log.info(f"Configured YouTube Scheduled Publication: privacyStatus='private', publishAt='{publish_at}'")
    else:
        status_dict["privacyStatus"] = config.youtube.upload_privacy

    log.info(f"Initiating YouTube Resumable Upload (Quota cost: {config.youtube.VIDEO_INSERT_COST} units)...")
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": effective_category,
            "defaultLanguage": config.youtube.default_language
        },
        "status": status_dict
    }

    upload_init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    init_req = urllib.request.Request(
        upload_init_url,
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size)
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(init_req, timeout=30) as init_resp:
            upload_url = init_resp.headers.get("Location")

        if not upload_url:
            log.error("Failed to retrieve resumable upload URL.")
            return None

        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_req = urllib.request.Request(
            upload_url,
            data=video_bytes,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(len(video_bytes))
            },
            method="PUT"
        )

        with urllib.request.urlopen(upload_req, timeout=120) as final_resp:
            result = json.loads(final_resp.read().decode("utf-8"))
            video_id = result.get("id")

        if not video_id:
            log.error("YouTube upload completed but returned no video ID.")
            return None

        # 3. Post-Upload Verification (Section 7)
        upload_status = "SCHEDULED" if publish_at else "PUBLISHED_LIVE"
        log.info(f"Executing post-upload verification for YouTube Video ID: {video_id}...")
        verified_data = {
            "video_id": video_id,
            "privacy_status": status_dict["privacyStatus"],
            "publish_at": publish_at,
            "title": title,
            "url": f"https://youtube.com/shorts/{video_id}",
            "upload_status": upload_status,
            "verified": False
        }

        try:
            verify_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={video_id}"
            verify_req = urllib.request.Request(
                verify_url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            )
            with urllib.request.urlopen(verify_req, timeout=15) as v_resp:
                v_json = json.loads(v_resp.read().decode("utf-8"))
                items = v_json.get("items", [])
                if items:
                    remote_status = items[0].get("status", {})
                    rem_privacy = remote_status.get("privacyStatus")
                    rem_publish_at = remote_status.get("publishAt")
                    log.info(f"YouTube Verification Confirmed: privacyStatus='{rem_privacy}', publishAt='{rem_publish_at}'")
                    verified_data["remote_privacy_status"] = rem_privacy
                    verified_data["remote_publish_at"] = rem_publish_at
                    verified_data["verified"] = True
                else:
                    log.warning("Post-upload verification: Video not yet indexed in list endpoint.")
        except Exception as e:
            log.warning(f"Post-upload verification query non-blocking warning: {e}")

        log.info(f"🎉 Successfully uploaded to YouTube! Video ID: {video_id} (Status: {upload_status})")
        log.info(f"Watch URL: {verified_data['url']}")
        if publish_at:
            log.info(f"Scheduled Publication Time (UTC): {publish_at}")
        return verified_data

    except Exception as e:
        log.error(f"Error during video upload to YouTube API endpoint: {e}")
        return None
