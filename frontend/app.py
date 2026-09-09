import requests
import streamlit as st
import pandas as pd


API_URL = "http://127.0.0.1:8000"


st.set_page_config(
    page_title="Synthetic Data Platform",
    page_icon="📊",
    layout="wide"
)


if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

st.title("Synthetic Data Platform")

# DATASET UPLOAD

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


            # Upload successful
            if response.status_code == 200:

                result = response.json()

                st.success(
                    "Dataset uploaded successfully!"
                )

                metadata = result["data"]


                # Save filename in session state
                st.session_state.uploaded_filename = (
                    metadata["filename"]
                )


                # Display metadata
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


            # Upload failed
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


# DATASET PROFILE

if st.session_state.uploaded_filename is not None:

    st.divider()

    st.subheader("Dataset Profile")


    if st.button("Generate Dataset Profile"):

        try:

            filename = st.session_state.uploaded_filename


            profile_response = requests.get(
                f"{API_URL}/profile/{filename}"
            )


            # Profile generated successfully
            if profile_response.status_code == 200:

                profile_result = (
                    profile_response.json()
                )

                profile = profile_result["data"]

                # BASIC INFORMATION

                st.subheader("Basic Information")

                basic = profile["basic"]


                col1, col2 = st.columns(2)


                with col1:

                    st.metric(
                        "Rows",
                        basic["row_count"]
                    )


                with col2:

                    st.metric(
                        "Columns",
                        basic["column_count"]
                    )


                # COLUMN CLASSIFICATION

                st.subheader(
                    "Column Classification"
                )


                column_types = profile[
                    "column_types"
                ]


                st.write(
                    "### Numerical Columns"
                )

                st.write(
                    column_types[
                        "numerical_columns"
                    ]
                )


                st.write(
                    "### Categorical Columns"
                )

                st.write(
                    column_types[
                        "categorical_columns"
                    ]
                )


                # COLUMN INFORMATION

                st.subheader(
                    "Column Information"
                )


                column_information = profile[
                    "columns"
                ]


                st.dataframe(
                    column_information,
                    use_container_width=True
                )

                # MISSING VALUES

                st.subheader(
                    "Missing Values"
                )


                missing_values = profile[
                    "missing_values"
                ]


                st.dataframe(
                    missing_values,
                    use_container_width=True
                )


                # NUMERICAL STATISTICS

                st.subheader(
                    "Numerical Statistics"
                )


                numerical_statistics = profile[
                    "numerical_statistics"
                ]


                if numerical_statistics:

                    statistics_dataframe = pd.DataFrame(
                        numerical_statistics
                    )


                    st.dataframe(
                        statistics_dataframe,
                        use_container_width=True
                    )


                else:

                    st.info(
                        "No numerical columns found."
                    )


                # CATEGORICAL FREQUENCIES

                st.subheader(
                    "Categorical Frequencies"
                )


                categorical_frequencies = profile[
                    "categorical_frequencies"
                ]


                if categorical_frequencies:

                    for column, frequencies in (
                        categorical_frequencies.items()
                    ):

                        st.write(
                            f"### {column}"
                        )


                        frequency_dataframe = pd.DataFrame(
                            list(
                                frequencies.items()
                            ),
                            columns=[
                                "Value",
                                "Frequency"
                            ]
                        )


                        st.dataframe(
                            frequency_dataframe,
                            use_container_width=True
                        )


                else:

                    st.info(
                        "No categorical columns found."
                    )


                # SUCCESS

                st.success(
                    "Dataset profile generated successfully!"
                )


            # Profile failed
            else:

                error = profile_response.json()

                st.error(
                    error.get(
                        "detail",
                        "Unable to generate profile."
                    )
                )


        except requests.exceptions.ConnectionError:

            st.error(
                "Unable to connect to the backend."
            )


        except Exception as error:

            st.error(
                f"An unexpected error occurred: {error}"
            )