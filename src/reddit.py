import os
import time

import praw


def client(
    username: str | None = None,
    password: str | None = None,
) -> praw.Reddit:
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("USERAGENT"),
        ratelimit_seconds=60 * 14,
        timeout=60,
        username=username,
        password=password,
    )


def get_random_url(
    subreddit: str,
    min_score: int = 10,
    min_comments: int = 10,
) -> str | None:
    c = client()

    sub = c.subreddit(subreddit)
    for i in range(5):
        if i > 0:
            time.sleep(1)
        p = sub.random()
        if (
            p.banned_by
            or p.banned_at_utc
            or p.removed_by
            or p.removal_reason
            or p.is_reddit_media_domain
            or p.is_video
            or p.is_self
            or p.media
            or p.over_18
        ):
            continue
        if p.score < min_score:
            continue
        if p.num_comments < min_comments:
            continue
        if not p.url:
            continue

        return p.url

    return None
