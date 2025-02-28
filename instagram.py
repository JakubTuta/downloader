import os
import profile
import re
import typing

import instaloader
import pydantic
import requests


class Response(pydantic.BaseModel):
    preview: str
    type: typing.Literal["image", "video"]
    url: str
    width: int
    height: int


def initialize_loader():
    """Initialize and return an Instaloader instance"""
    return instaloader.Instaloader()


def parse_url(url):
    """Parse URL and return normalized form"""
    return url.split("?")[0]


def extract_shortcode(url):
    """Extract shortcode from post/reel URL or GraphQL URL"""
    # Try regular post/reel URL format
    match = re.search(r"instagram.com/(?:p|reel)/([^/?]+)", url)
    if match:
        return match.group(1)

    # Try GraphQL URL format
    match = re.search(r"shortcode%22%3A%22([^%]+)%22", url)
    if match:
        return match.group(1)

    raise ValueError("Could not extract shortcode from URL")


def extract_username(url):
    """Extract username from URL"""
    match = re.search(r"instagram.com/(?:stories/)?([^/?]+)", url)
    if not match:
        raise ValueError("Could not extract username from URL")
    return match.group(1)


# Post / Reel


def _extract_responses_from_node(node):
    """Extract media information from a post node"""
    responses = []
    display_resources = node.get("display_resources", [])

    if display_resources:
        preview = min(display_resources, key=lambda x: x["config_height"])["src"]
        highest_res = max(display_resources, key=lambda x: x["config_height"])
        url = node.get("video_url", highest_res["src"])
        media_type = "video" if node.get("is_video") else "image"

        response = Response(
            preview=preview,
            type=media_type,
            url=url,
            width=highest_res["config_width"],
            height=highest_res["config_height"],
        )
        responses.append(response)

    return responses


def _process_post_data(post_data, shortcode):
    """Process post data and extract media responses"""
    responses = []
    if "edge_sidecar_to_children" in post_data:
        posts = post_data["edge_sidecar_to_children"]["edges"]
    else:
        posts = [{"node": post_data}]

    for post in posts:
        responses.extend(_extract_responses_from_node(post["node"]))

    username = post_data.get("owner", {}).get("username", "unknown")

    return {
        "status": "success",
        "message": f"Downloaded post/reel {shortcode}",
        "username": username,
        "data": responses,
    }


def _fetch_via_graphql(url, error_str):
    """Attempt to fetch post data via GraphQL API"""
    graphql_url_match = re.search(
        r"(https://[^\"'\s]+graphql/query[^\"'\s]+)", error_str
    )
    if not graphql_url_match:
        return None

    graphql_url = graphql_url_match.group(1)
    shortcode = extract_shortcode(url)

    response = requests.get(graphql_url, headers={"User-Agent": "Mozilla/5.0"})
    data = response.json()

    if not "data" in data:
        return None

    # Check for xdt_shortcode_media (new format)
    if "xdt_shortcode_media" in data["data"]:
        return _process_post_data(
            data["data"]["xdt_shortcode_media"], shortcode + " via GraphQL"
        )
    # Check for shortcode_media (old format)
    elif "shortcode_media" in data["data"]:
        return _process_post_data(
            data["data"]["shortcode_media"], shortcode + " via GraphQL"
        )


def download_post_or_reel(loader, url):
    """Download Instagram post or reel"""
    try:
        shortcode = extract_shortcode(url)
        main_post = instaloader.Post.from_shortcode(loader.context, shortcode)

        return _process_post_data(main_post.__dict__["_node"], shortcode)

    except Exception as e:
        error_str = str(e)
        if re.search(r"(https://[^\"'\s]+graphql/query[^\"'\s]+)", error_str):
            try:
                result = _fetch_via_graphql(url, error_str)
                return {
                    "status": "error",
                    "message": str(result),
                    "data": [],
                }
                if result:
                    return result

            except Exception as inner_e:
                return {
                    "status": "error",
                    "message": f"Failed GraphQL fallback: {str(inner_e)}",
                    "data": [],
                }

        return {
            "status": "error",
            "message": error_str,
            "data": [],
        }


# Stories


def download_stories(loader: instaloader.Instaloader, url):
    """Download Instagram stories"""
    try:
        raise Exception("Stories download is not supported")

        username = extract_username(url)
        profile = instaloader.Profile.from_username(loader.context, username)
        stories = loader.get_stories(userids=[profile.userid])

        return {
            "status": "success",
            "message": f"Downloaded stories for {username}",
            "data": [],
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


# Profile


def download_profile(loader, url):
    """Download Instagram profile"""
    try:
        raise Exception("Profile download is not supported")

        username = extract_username(url)
        profile = instaloader.Profile.from_username(loader.context, username)
        loader.download_profile(profile, profile_pic_only=False)

        return {
            "status": "success",
            "message": f"Downloaded profile {username}",
            "data": [],
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


def download_instagram_content(url) -> dict[str, typing.Union[str, list[Response]]]:
    # Initialize instaloader
    loader: instaloader.Instaloader = initialize_loader()

    # Optional: Login (needed for stories and private content)
    # loader.login("username", "password")

    parsed_url = parse_url(url)

    if "instagram.com/p/" in url or "instagram.com/reel/" in url:
        result = download_post_or_reel(loader, parsed_url)

    elif "instagram.com/stories/" in parsed_url:
        result = download_stories(loader, parsed_url)

    elif re.search(r"instagram.com/([^/?]+)", parsed_url):
        result = download_profile(loader, parsed_url)

    else:
        return {
            "status": "error",
            "message": "Unsupported URL format",
            "data": [],
        }

    return result
