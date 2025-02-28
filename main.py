import io
import os
import time
import typing
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import pydantic
import requests
import streamlit as st
from PIL import Image

import instagram


class Response(pydantic.BaseModel):
    preview: str
    type: typing.Literal["image", "video"]
    url: str
    width: int
    height: int


def get_downloads_dir():
    # Check if user is on mobile
    if st.session_state.get("is_mobile", False) or (
        hasattr(st, "session_state")
        and st.session_state.get("_is_running_with_streamlit", False)
        and "user_agent" in st.session_state
        and any(
            device in st.session_state.get("user_agent", "").lower()
            for device in ["android", "iphone", "ipad", "mobile"]
        )
    ):
        # For mobile devices, use Gallery directory
        return os.path.join(os.path.expanduser("~"), "Gallery")
    else:
        # For desktop systems use Downloads folder
        return os.path.join(os.path.expanduser("~"), "Downloads")


def download_file(url, filename, save_dir=None):
    try:
        # Use default downloads directory if none specified
        if save_dir is None:
            save_dir = get_downloads_dir()

        # Create directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)

        # Full path to save the file
        save_path = os.path.join(save_dir, filename)

        # Download the file
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses

        # Write file
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        return save_path

    except Exception as e:
        return f"Error downloading {url}: {str(e)}"


def download_multiple_files(files_data):
    results = []
    downloads_dir = get_downloads_dir()

    # Use ThreadPoolExecutor for concurrent downloads
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all download tasks
        future_to_file = {
            executor.submit(
                download_file, file_info["url"], file_info["filename"], downloads_dir
            ): file_info
            for file_info in files_data
        }

        # Process results as they complete
        for future in future_to_file:
            file_info = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
                print(f"Downloaded: {result}")
            except Exception as exc:
                results.append(f"Error downloading {file_info['url']}: {str(exc)}")
                print(f"Error downloading {file_info['url']}: {str(exc)}")

    return results


def process_input(url):
    response = instagram.download_instagram_content(url)

    if response["status"] == "error":
        st.error(response["message"])
        return

    # Store the response data in session state
    st.session_state.processed_data = response
    display_posts()


def display_posts():
    if st.session_state.processed_data is None:
        return

    response = st.session_state.processed_data
    posts: typing.List[Response] = response["data"]  # type: ignore

    for idx, post in enumerate(posts):
        with st.container():
            # Display preview image
            try:
                preview_image = requests.get(post.preview)
                preview_image = Image.open(BytesIO(preview_image.content))
                st.image(preview_image)
            except Exception as e:
                st.error(f"Failed to load preview: {str(e)}")

            # Generate unique filename
            file_name = f"{response['username']}_{int(time.time())}_{idx}"
            file_extension = "jpg" if post.type == "image" else "mp4"
            full_filename = f"{file_name}.{file_extension}"

            # Get file content for download button
            try:
                file_response = requests.get(post.url)
                file_response.raise_for_status()
                file_content = file_response.content

                # Create download button for each file
                mime_type = "image/jpeg" if post.type == "image" else "video/mp4"
                st.download_button(
                    label=f"Download {post.type}",
                    data=file_content,
                    file_name=full_filename,
                    mime=mime_type,
                    key=f"download_{post.url}_{idx}",
                )
            except Exception as e:
                st.error(f"Failed to prepare download: {str(e)}")

            st.divider()


# Initialize session state to store selected files
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

if "processed_data" not in st.session_state:
    st.session_state.processed_data = None

st.markdown(
    """
    ## Available downloads

    - Instagram: Posts/Reels
    - new update
"""
)

input_text = st.text_input("Enter url")

if st.button("Submit"):
    if not input_text:
        st.error("Please enter a URL")
        st.stop()

    # Clear previous selections when submitting a new URL
    st.session_state.selected_files = []
    process_input(input_text)
else:
    # Display posts if we have processed data but didn't just submit
    display_posts()
