import pprint
import profile
import re
import typing
from pathlib import Path

import instaloader
import pydantic

download_directory = "downloader"


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
    """Extract shortcode from post/reel URL"""
    match = re.search(r"instagram.com/(?:p|reel)/([^/?]+)", url)
    if not match:
        raise ValueError("Could not extract shortcode from URL")
    return match.group(1)


def extract_username(url):
    """Extract username from URL"""
    match = re.search(r"instagram.com/(?:stories/)?([^/?]+)", url)
    if not match:
        raise ValueError("Could not extract username from URL")
    return match.group(1)


def download_post_or_reel(loader, url):
    """Download Instagram post or reel"""
    try:
        shortcode = extract_shortcode(url)
        main_post = instaloader.Post.from_shortcode(loader.context, shortcode)

        posts = main_post.__dict__["_node"]["edge_sidecar_to_children"]["edges"]
        responses = []

        for post in posts:
            node = post["node"]
            display_resources = node.get("display_resources", [])

            if display_resources:
                preview = min(display_resources, key=lambda x: x["config_height"])[
                    "src"
                ]
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

        return {
            "status": "success",
            "message": f"Downloaded post/reel {shortcode}",
            "username": main_post.owner_username,
            "data": responses,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


def download_stories(loader: instaloader.Instaloader, url):
    """Download Instagram stories"""
    try:
        raise Exception("Stories download is not supported")

        username = extract_username(url)
        profile = instaloader.Profile.from_username(loader.context, username)
        loader.download_stories(
            userids=[profile.userid], filename_target=download_directory
        )

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


def cleanup_downloads():
    """Delete non-media files from downloads directory and remove images when videos exist"""
    allowed_extensions = (".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi")
    video_extensions = (".mp4", ".mov", ".avi")
    downloads_path = Path(download_directory)

    if downloads_path.exists():
        # First pass: Find files with same stem that have both image and video
        stems_with_video = set()
        for file in downloads_path.iterdir():
            if file.is_file() and file.suffix.lower() in video_extensions:
                stems_with_video.add(file.stem)

        # Second pass: Delete files
        for file in downloads_path.iterdir():
            if file.is_file():
                # Delete non-media files
                if not file.suffix.lower() in allowed_extensions:
                    file.unlink()
                # Delete images that have corresponding videos
                elif (
                    file.suffix.lower() not in video_extensions
                    and file.stem in stems_with_video
                ):
                    file.unlink()


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

    # cleanup_downloads()

    return result


if __name__ == "__main__":
    url = "https://www.instagram.com/p/DDH-UO5i6Cj/?img_index=1"

    print(download_instagram_content(url))
