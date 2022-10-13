#!/usr/bin/env python

import base64
import logging
import os
import random
import time
from urllib.parse import quote as url_quote

import requests
import tweepy
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def is_dev():
    return os.getenv("APP_DEPLOYMENT_ENVIRONMENT", "").lower() != "prod"


def tweet(status):
    api_key = os.getenv("TWITTER_ACCESS_API_KEY")
    api_secret_key = os.getenv("TWITTER_ACCESS_API_SECRET_KEY")
    token = os.getenv("TWITTER_BOT_TOKEN")
    token_secret = os.getenv("TWITTER_BOT_TOKEN_SECRET")

    if not api_key or not api_secret_key or not token or not token_secret:
        logger.error("Twitter: non properly configured")
        return

    if is_dev():
        print(status)
        return random.randint(1, 1_000_000)

    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(token, token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    status = api.update_status(status)
    return status.id


def upload_screenshot(url):
    bearer_token = os.getenv("SPIDERAPI_BEARER_TOKEN")
    api_url = "https://spider.xojoc.pw/api/v0/screenshot"
    auth = {"Authorization": f"Bearer {bearer_token}"}
    parameters = {"url": url, "full_page": True}

    resp = requests.get(api_url, parameters, headers=auth)
    if not resp.ok:
        print(resp.status_code)
        print(resp.content)
        return
    jimg = resp.json()
    print(jimg["media_type"])

    access_token = os.getenv("MASTODON_BOT_ACCESS_TOKEN")
    auth = {"Authorization": f"Bearer {access_token}"}
    api_url = "https://mastodon.social/api/v1/media"

    files = {
        "file": (
            "screenshot.png",
            base64.b64decode(jimg["content"]),
            jimg["media_type"],
        ),
    }
    parameters = {
        "description": f"Screenshot of {url} taken with SpiderAPI",
        "focus": "(0,1)",
    }

    media = requests.post(
        api_url, files=files, params=parameters, headers=auth
    )
    if not media.ok:
        print(media.status_code)
        print(media.content)
        return

    media = media.json()

    return media["id"]


def toot(status, media_id=None, ignore_dev=False):
    access_token = os.getenv("MASTODON_BOT_ACCESS_TOKEN")

    if not access_token:
        logger.warning("Mastodon: non properly configured")
        return

    if is_dev() and not ignore_dev:
        print(status)
        return random.randint(1, 1_000_000)

    api_url = "https://mastodon.social/api/v1/statuses"
    auth = {"Authorization": f"Bearer {access_token}"}
    parameters = {"status": status}
    if media_id:
        parameters["media_ids[]"] = [media_id]

    r = requests.post(api_url, data=parameters, headers=auth)
    if r.ok:
        return int(r.json()["id"])
    else:
        logger.error(f"Mastodon post: {r.status_code} {r.reason}\n{status}")
        return


def toot_with_screenshot(status, url, ignore_dev=False):
    media_id = None
    try:
        media_id = upload_screenshot(url)
    except Exception as e:
        logger.warning(f"Screenshot failed: {e}")
        media_id = None

    toot(status, media_id, ignore_dev)


def get_random_website_stumblingon():
    for _ in range(5):
        r = requests.post(
            "https://service.stumblingon.com/getSite",
            json={"userId": "randomwebsitebot", "prevId": ""},
        )

        if r.json().get("ok"):
            return r.json().get("url")


def get_random_website_forestlink():
    for _ in range(5):
        r = requests.get("https://theforest.link/api/site/")
        if r.json().get("content"):
            return r.json().get("content")


random_website_functions = [
    get_random_website_stumblingon,
    get_random_website_forestlink,
]


def get_random_website():
    return random.choice(random_website_functions)()


def get_website_info(url):
    r = requests.get(url)
    if not r or not r.ok:
        return None, None, None, False

    h = BeautifulSoup(r.content, "lxml")

    title = h.title.text.strip()

    twitter_by = (
        h.select_one(
            'meta[name="twitter:creator"], meta[property="twitter:creator"]'
        )
        or {}
    ).get("content", "").removeprefix("@") or None

    twitter_via = (
        h.select_one(
            'meta[name="twitter:site"], meta[property="twitter:site"]'
        )
        or {}
    ).get("content", "").removeprefix("@") or None

    if twitter_by:
        parts = twitter_by.split("/")
        parts = [p for p in parts if p]
        twitter_by = parts[-1]
        twitter_by = twitter_by.strip()

        twitter_by = twitter_by.removeprefix("@")

        if " " in twitter_by:
            twitter_by = None

    if twitter_via:
        parts = twitter_via.split("/")
        parts = [p for p in parts if p]
        twitter_via = parts[-1]
        twitter_via = twitter_via.strip()

        twitter_via = twitter_via.removeprefix("@")

        if " " in twitter_via:
            twitter_via = None

    return title, twitter_by, twitter_via, True


def get_discussions(url):
    endpoint = "https://discu.eu/api/v0/discussion_counts/url/" + url_quote(
        url
    )
    token = os.getenv("DISCU_ACCESS_TOKEN")
    r = requests.get(endpoint, headers={"Authorization": f"Bearer {token}"})
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
    title, url, discussions_url, tags, by_account=None, via_account=None
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
    elif via_account:
        status += f"via @{via_account}\n\n"

    return status.strip()


def execute():
    url = get_random_website()
    if not url:
        return False
    title, twitter_by, twitter_via, success = get_website_info(url)
    if not success:
        logger.warning(f"Cannot fetch website: {url} ...skipping")
        return False
    discussions_url, tags = get_discussions(url)

    status = build_status(
        title, url, discussions_url, tags, twitter_by, twitter_via
    )
    tweet_id = tweet(status)
    logger.info(f"Tweet: {tweet_id}")

    status = build_status(title, url, discussions_url, tags)
    toot_id = toot_with_screenshot(status, url)
    logger.info(f"Toot: {toot_id}")

    return True


def main():
    random.seed()
    while True:
        t = 2 * 60 * 60
        if is_dev():
            t = 30

        logger.info("Sleep...")
        time.sleep(t)

        try:
            success = execute()
            if not success:
                logger.warning("Failed... retry")
                time.sleep(1)
                continue
        except Exception as e:
            import traceback

            logger.error(traceback.format_exc())

            logger.error(f"{e}\n\ntrying again...")
            continue


if __name__ == "__main__":
    main()
