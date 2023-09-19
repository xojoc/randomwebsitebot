import base64
import logging
import mimetypes
import os
import random
import time
from urllib.parse import quote as url_quote

import requests
import tweepy
import tweepy.errors
from bs4 import BeautifulSoup

from . import reddit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

headers = {
    "User-Agent": os.getenv("USERAGENT", "Useragent"),
}


def is_dev():
    return os.getenv("APP_DEPLOYMENT_ENVIRONMENT", "").lower() != "prod"


def set_env(env: str) -> None:
    os.environ["APPL_DEPLOYMENT_ENVIRONMENT"] = env


def take_screenshot(url):
    bearer_token = os.getenv("SPIDERAPI_BEARER_TOKEN")
    api_url = "https://spider.xojoc.pw/api/v0/screenshot"
    auth = {"Authorization": f"Bearer {bearer_token}"}
    parameters = {"url": url, "full_page": False}

    if is_dev():
        return None

    try:
        resp = requests.get(api_url, parameters, headers=auth, timeout=120)
    except requests.exceptions.RequestException:
        logger.exception(f"Screenshot: {url}")
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


def twitter_upload_screenshot(file):
    if not file:
        return None

    if is_dev():
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
    api = tweepy.API(auth, wait_on_rate_limit=True)

    media = api.simple_upload(
        file[0],
        file=file[1],
        media_category="tweet_image",
    )

    if media:
        return media.media_id
    return None


def tweet(status, media_id=None):
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

    if is_dev():
        logger.info(status)
        return random.randint(1, 1_000_000)  # noqa: S311

    api = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=True,
    )
    status = api.create_tweet(text=status, media_ids=media_ids)

    # example response:
    #    Response(data={'edit_history_tweet_ids': ['1702054393854464183'], 'id': '1702054393854464183', 'text': 'Hello again'}, includes={}, errors=[], meta={})
    return status.data["id"]


def mastodon_upload_screenshot(file):
    if not file:
        return None
    if is_dev():
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


def toot(status, media_id=None):
    access_token = os.getenv("MASTODON_BOT_ACCESS_TOKEN")

    if not access_token:
        logger.warning("Mastodon: non properly configured")
        return None

    if is_dev():
        logger.info(status)
        return random.randint(1, 1_000_000)  # noqa: S311

    api_url = "https://mastodon.social/api/v1/statuses"
    auth = {"Authorization": f"Bearer {access_token}"}
    parameters = {"status": status}
    if media_id:
        parameters["media_ids[]"] = [media_id]

    r = requests.post(
        api_url,
        data=parameters,
        headers=auth,
        timeout=5 * 60,
    )
    if r.ok:
        return int(r.json()["id"])

    logger.exception(
        f"Mastodon post: {r.status_code} {r.reason}\n{status}",
    )
    return None


def get_random_website_stumblingon():
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


def get_random_website_forestlink():
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


def get_random_website_wiby():
    try:
        r = requests.get("https://wiby.me/surprise/", timeout=1 * 60)
    except requests.exceptions.RequestException:
        logger.exception("Wiby failed")
        return None

    if not r or not r.ok:
        return None

    h = BeautifulSoup(r.content, "lxml")
    meta = h.select('meta[http-equiv="refresh"]')[0]

    return meta["content"].split("'")[1]


def get_random_website_reddit():
    subreddits = ["InternetIsBeautiful"]
    subreddit = random.choice(subreddits)  # noqa: S311
    return reddit.get_random_url(subreddit, min_score=50, min_comments=10)


random_website_functions = [
    # get_random_website_stumblingon,
    get_random_website_forestlink,
    get_random_website_wiby,
    get_random_website_reddit,
]

random_website_weights = [40, 40, 20]


def get_random_website():
    return random.choices(  # noqa: S311
        random_website_functions,
        weights=random_website_weights,
    )[0]()


def get_website_info(url: str) -> tuple[str, str, bool]:
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


def get_discussions(url: str) -> tuple[str | None, list[str] | None]:
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


def __hashtags(tags):
    tags = tags or []
    replacements = {"c": "cprogramming"}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(["#" + t for t in tags])


def build_status(
    title,
    url,
    discussions_url,
    tags,
    by_account=None,
):
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


def url_blacklisted(url):
    if not url:
        return True

    return False


def execute():
    url = None
    url = get_random_website()
    if not url:
        return False
    title, twitter_by, success = get_website_info(url)
    if not success:
        logger.warning(f"Cannot fetch website: {url} ...skipping")
        return False
    discussions_url, tags = get_discussions(url)

    screenshot = take_screenshot(url)

    status = build_status(
        title,
        url,
        discussions_url,
        tags,
        twitter_by,
    )

    try:
        twitter_media_id = twitter_upload_screenshot(screenshot)

        tweet_id = tweet(status, twitter_media_id)
        logger.info(f"Tweet: {tweet_id}")
    except tweepy.errors.Unauthorized as e:
        logger.warning(f"Twitter: {e}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Twitter: {e}")

    mastodon_media_id = mastodon_upload_screenshot(screenshot)

    status = build_status(title, url, discussions_url, tags)
    toot_id = toot(status, mastodon_media_id)
    logger.info(f"Toot: {toot_id}")

    return True


def main():
    logger.info("Started...")
    random.seed()
    while True:
        success = False
        try:
            success = execute()
        except Exception:
            logger.exception("\n\ntrying again...", stack_info=True)
            success = False

        if not success:
            logger.warning("Failed... retry")
            time.sleep(3)
            continue

        t = 2 * 60 * 60
        if is_dev():
            t = 30

        logger.info("Sleep...")
        time.sleep(t)
