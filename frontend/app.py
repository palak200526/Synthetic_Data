import requests
import streamlit as st


API_URL = "http://127.0.0.1:8000"


st.set_page_config(
    page_title="Synthetic Data Platform",
    page_icon="📊",
    layout="wide"
)


st.title("Synthetic Data Platform")

st.subheader("Dataset Upload")

st.write(
    "Upload a CSV or Excel dataset to begin processing."
)


uploaded_file = st.file_uploader(
    "Choose your dataset",
    type=["csv", "xls", "xlsx"]
)


if uploaded_file is not None:

    st.write(
        f"Selected file: **{uploaded_file.name}**"
    )

    st.write(
        f"File size: **{uploaded_file.size / (1024 * 1024):.2f} MB**"
    )

    if st.button("Upload Dataset"):

        try:

            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    uploaded_file.type
                )
            }

            response = requests.post(
                f"{API_URL}/upload",
                files=files
            )

            if response.status_code == 200:

                result = response.json()

                st.success(
                    "Dataset uploaded successfully!"
                )

                metadata = result["data"]

                st.write(
                    f"**Filename:** {metadata['filename']}"
                )

                st.write(
                    f"**Rows:** {metadata['rows']}"
                )

                st.write(
                    f"**Columns:** {metadata['columns']}"
                )

                st.write("**Column Names:**")

                st.write(
                    metadata["column_names"]
                )

            else:

                error = response.json()

                st.error(
                    error.get(
                        "detail",
                        "Upload failed."
                    )
                )

        except requests.exceptions.ConnectionError:

            st.error(
                "Unable to connect to the backend. "
                "Make sure FastAPI is running."
            )

        except Exception as error:

            st.error(
                f"An unexpected error occurred: {error}"
            )