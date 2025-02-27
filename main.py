import time
import typing
from io import BytesIO

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


def process_input(url):
    response = instagram.download_instagram_content(url)

    if response["status"] == "error":
        st.error(response["message"])

        return

    posts: typing.List[Response] = response["data"]  # type: ignore

    for idx, post in enumerate(posts):
        with st.container():
            # Display preview image
            try:
                # Download and display preview image
                preview_image = requests.get(post.preview)
                preview_image = Image.open(BytesIO(preview_image.content))
                st.image(preview_image)
            except Exception as e:
                st.error(f"Failed to load preview: {str(e)}")

            # Center the download button using columns
            _, col2, _ = st.columns([1, 2, 1])
            with col2:
                if post.type == "image":
                    download_label = "Download Image"
                else:
                    download_label = "Download Video"

                # Center align the buttons using columns
                button_col1, button_col2, button_col3 = st.columns([1, 2, 1])

                with button_col2:
                    try:
                        file_name = f"{response['username']}_{int(time.time())}_{idx}"
                        file_extension = "jpg" if post.type == "image" else "mp4"

                        content_response = requests.get(post.url)
                        st.download_button(
                            label=download_label,
                            data=content_response.content,
                            file_name=f"{file_name}.{file_extension}",
                            mime=(
                                "image/jpeg" if post.type == "image" else "video/mp4"
                            ),
                            key=f"download_{idx}",
                        )
                    except Exception as e:
                        st.error(f"Failed to download: {str(e)}")

            st.divider()  # Add separator between cards


input_text = st.text_input("Enter url")

if st.button("Submit"):
    process_input(input_text)
