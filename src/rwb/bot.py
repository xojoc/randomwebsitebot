# Copyright 2023 Alexandru Cojocaru AGPLv3 or later - no warranty!
"""Main functionality of the bot."""


import base64
import datetime
import logging
import mimetypes
import os
import random
import time
import typing
from urllib.parse import quote as url_quote

import requests
import tweepy
import tweepy.client
import tweepy.errors
from bs4 import BeautifulSoup

from . import reddit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


headers = {
    "User-Agent": os.getenv("USERAGENT", "Useragent"),
}


def __is_dev() -> bool:
    return os.getenv("APP_DEPLOYMENT_ENVIRONMENT", "").lower() != "prod"


def __take_screenshot(url: str) -> None | tuple[str, bytes, str, str]:
    bearer_token = os.getenv("SPIDERAPI_BEARER_TOKEN")
    api_url = "https://spider.xojoc.pw/api/v0/screenshot"
    auth = {"Authorization": f"Bearer {bearer_token}"}
    parameters = {"url": url, "full_page": False}

    if __is_dev():
        return None

    try:
        resp = requests.get(api_url, parameters, headers=auth, timeout=120)
    except requests.exceptions.RequestException:
        logger.exception("Screenshot: %s", url)
        return None
    if not resp or not resp.ok:
        return None
    jimg = resp.json()
    content = base64.b64decode(jimg["content"])
    mime = jimg["media_type"]
    ext = mimetypes.guess_extension(mime) or ".dat"
    return (
        f"screenshot{ext}",
        content,
        mime,
        f"Screenshot of {url} taken with SpiderAPI",
    )


def __twitter_upload_screenshot(
    file: tuple[str, bytes, str, str],
) -> None | str:
    if not file:
        return None

    if __is_dev():
        return None

    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if (
        not consumer_key
        or not consumer_secret
        or not access_token
        or not access_token_secret
    ):
        logger.exception("Twitter: non properly configured")
        return None

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=False)

    media = api.simple_upload(
        file[0],
        file=file[1],
        media_category="tweet_image",
    )

    if media:
        return media.media_id
    return None


def __tweet(status: str, media_id: str | None = None) -> str | None:
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    media_ids = [media_id] if media_id else None

    if (
        not consumer_key
        or not consumer_secret
        or not access_token
        or not access_token_secret
    ):
        logger.exception("Twitter: non properly configured")
        return None

    if __is_dev():
        logger.info(status)
        return str(random.randint(1, 1_000_000))  # noqa: S311

    api = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=False,
    )
    status_response = api.create_tweet(text=status, media_ids=media_ids)
    status_response = typing.cast(tweepy.client.Response, status_response)

    return status_response.data["id"]


def __mastodon_upload_screenshot(
    file: tuple[str, bytes, str, str],
) -> None | str:
    if not file:
        return None
    if __is_dev():
        return None

    access_token = os.getenv("MASTODON_BOT_ACCESS_TOKEN")
    auth = {"Authorization": f"Bearer {access_token}"}
    api_url = "https://mastodon.social/api/v1/media"

    files = {
        "file": (file[0], file[1], file[2]),
    }
    parameters = {
        "description": file[3],
        "focus": "(0,1)",
    }

    try:
        media = requests.post(
            api_url,
            files=files,
            params=parameters,
            headers=auth,
            timeout=3 * 60,
        )
    except requests.exceptions.RequestException:
        logger.exception("mastodon upload")
        return None
    if not media or not media.ok:
        return None

    media = media.json()

    return media["id"]


def __toot(status: str, media_id: str | None = None) -> str | None:
    access_token = os.getenv("MASTODON_BOT_ACCESS_TOKEN")

    if not access_token:
        logger.warning("Mastodon: non properly configured")
        return None

    if __is_dev():
        logger.info(status)
        return str(random.randint(1, 1_000_000))  # noqa: S311

    api_url = "https://mastodon.social/api/v1/statuses"
    auth = {"Authorization": f"Bearer {access_token}"}
    parameters: dict[str, str | list[str]] = {"status": status}
    if media_id:
        parameters["media_ids[]"] = [media_id]

    r = requests.post(
        api_url,
        data=parameters,
        headers=auth,
        timeout=5 * 60,
    )
    if r.ok:
        return str(r.json()["id"])

    logger.exception(
        "Mastodon post: %s %s\n%s",
        r.status_code,
        r.reason,
        status,
    )
    return None


def __get_random_website_stumblingon() -> None | str:
    try:
        r = requests.post(
            "https://service.stumblingon.com/getSite",
            json={"userId": "randomwebsitebot", "prevId": ""},
            timeout=1 * 60,
        )
    except requests.exceptions.RequestException:
        logger.exception("StumblingOn failed")
        return None

    if not r or not r.ok:
        return None
    if r.json().get("ok"):
        return r.json().get("url")
    return None


def __get_random_website_forestlink() -> None | str:
    try:
        r = requests.get("https://theforest.link/api/site/", timeout=1 * 60)
    except requests.exceptions.RequestException:
        logger.exception("The Forest Linke failed")
        return None
    if not r or not r.ok:
        return None
    if r.json().get("content"):
        return r.json().get("content")
    return None


def __get_random_website_wiby() -> None | str:
    try:
        r = requests.get("https://wiby.me/surprise/", timeout=1 * 60)
    except requests.exceptions.RequestException:
        logger.exception("Wiby failed")
        return None

    if not r or not r.ok:
        return None

    h = BeautifulSoup(r.content, "lxml")
    meta = h.select('meta[http-equiv="refresh"]')[0]
    refresh = meta.get("content")
    if not refresh:
        return None

    return " ".join(refresh).split("'")[1]


def __get_random_website_reddit() -> str | None:
    subreddits = ["InternetIsBeautiful"]
    subreddit = random.choice(subreddits)  # noqa: S311
    return reddit.get_random_url(subreddit, min_score=50, min_comments=10)


random_website_functions = [
    # get_random_website_stumblingon,
    __get_random_website_forestlink,
    __get_random_website_wiby,
    __get_random_website_reddit,
]

random_website_weights = [50, 30, 20]


def __get_random_website() -> str | None:
    return random.choices(  # noqa: S311
        random_website_functions,
        weights=random_website_weights,
    )[0]()


def __get_website_info(url: str) -> tuple[str, str, bool]:
    r = requests.get(url, headers=headers, timeout=3 * 60)
    if not r or not r.ok:
        return "", "", False

    h = BeautifulSoup(r.content, "lxml")

    title = ""
    if h.title:
        title = h.title.text.strip()

    if title == "Sign in - Google Accounts":
        return "", "", False

    meta = h.select_one(
        'meta[name="twitter:creator"], meta[property="twitter:creator"]',
    )
    meta_dict = meta.attrs if meta else {}
    twitter_by = meta_dict.get("content", "").removeprefix("@") or ""

    if twitter_by:
        parts = twitter_by.split("/")
        parts = [p for p in parts if p]
        twitter_by = parts[-1]
        twitter_by = twitter_by.strip()

        twitter_by = twitter_by.removeprefix("@")

        if " " in twitter_by:
            twitter_by = ""

    return title, twitter_by, True


def __get_discussions(url: str) -> tuple[str | None, list[str] | None]:
    endpoint = "https://discu.eu/api/v0/discussion_counts/url/" + url_quote(
        url,
    )
    token = os.getenv("DISCU_ACCESS_TOKEN")
    try:
        r = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
    except requests.exceptions.RequestException:
        logger.exception("Discu.eu failed")
        return None, None
    if not r or not r.ok:
        return None, None
    j = r.json()
    if (
        not j.get("total_comments")
        and not j.get("total_discussions")
        and not j.get("articles_count")
    ):
        return None, None

    return j.get("discussions_url"), j.get("tags")


def __hashtags(tags: list[str] | None) -> list[str]:
    tags = tags or []
    replacements = {"c": "cprogramming"}
    return sorted(["#" + t for t in (replacements.get(t, t) for t in tags)])


def __build_status(
    title: str,
    url: str,
    discussions_url: str | None,
    tags: list[str] | None,
    by_account: str | None = None,
) -> str:
    hashtags = __hashtags(tags)

    max_title_len = 50
    if len(title) > max_title_len:
        title = title[: max_title_len - 2] + "…"

    status = ""
    if title:
        status += f"{title}\n\n"

    status += f"{url}\n\n"

    if discussions_url:
        status += f"Discussions: {discussions_url}\n\n"

    if hashtags:
        status += f"{' '.join(hashtags)}\n\n"

    if by_account:
        status += f"by @{by_account}\n\n"

    return status.strip()


def __url_blacklisted(url: str) -> bool:
    if not url:
        return True

    return False


def __execute() -> bool:
    url = None
    url = __get_random_website()
    if not url:
        return False
    if __url_blacklisted(url):
        return False
    title, twitter_by, success = __get_website_info(url)
    if not success:
        logger.warning("Cannot fetch website: %s ...skipping", url)
        return False
    discussions_url, tags = __get_discussions(url)

    screenshot = __take_screenshot(url)

    status = __build_status(
        title,
        url,
        discussions_url,
        tags,
        twitter_by,
    )

    try:
        twitter_media_id = None
        if screenshot:
            twitter_media_id = __twitter_upload_screenshot(screenshot)

        tweet_id = __tweet(status, twitter_media_id)
        logger.info("Tweet: %s", tweet_id)
    except tweepy.errors.Unauthorized:
        logger.warning("Twitter", exc_info=True)
    except Exception:  # noqa: BLE001
        logger.warning("Twitter", exc_info=True)

    mastodon_media_id = None
    if screenshot:
        mastodon_media_id = __mastodon_upload_screenshot(screenshot)

    status = __build_status(title, url, discussions_url, tags)
    toot_id = __toot(status, mastodon_media_id)
    logger.info("Toot: %s", toot_id)

    return True


hours_interval = 12


def __sleep_until_next_time() -> None:
    now = datetime.datetime.now(tz=datetime.UTC)
    hour = now.hour
    later = datetime.datetime(
        now.year,
        now.month,
        now.day,
        hour,
        tzinfo=now.tzinfo,
    )
    later += datetime.timedelta(hours=hours_interval - hour % hours_interval)

    delta = later - now
    logger.info(
        "Sleep for %s seconds until %s (now is %s)...",
        delta.total_seconds(),
        later,
        now,
    )
    time.sleep(delta.total_seconds())


def main() -> None:
    """Loop indefinetly and post to Twitter and Mastodon every few hours."""
    logger.info("Started...")
    random.seed()
    while True:
        now = datetime.datetime.now(tz=datetime.UTC)
        min_slack = 2
        if not (now.hour % hours_interval == 0 and now.minute < min_slack):
            __sleep_until_next_time()

        success = False
        try:
            success = __execute()
        except Exception:
            logger.exception("\n\ntrying again...", stack_info=True)
            success = False

        if not success:
            logger.warning("Failed... retry")
            time.sleep(30)
            continue

        __sleep_until_next_time()
