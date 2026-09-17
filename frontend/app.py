import requests
import streamlit as st
import pandas as pd


API_URL = "http://127.0.0.1:8000"


st.set_page_config(
    page_title="Synthetic Data Platform",
    page_icon="📊",
    layout="wide"
)


# SESSION STATE

if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

if "dataset_id" not in st.session_state:
    st.session_state.dataset_id = None

if "profile_result" not in st.session_state:
    st.session_state.profile_result = None


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


                # Save dataset ID
                st.session_state.dataset_id = result["dataset_id"]


                metadata = result["data"]


                # Save filename in session state
                st.session_state.uploaded_filename = (
                    metadata["filename"]
                )


                # Reset previous profile
                st.session_state.profile_result = None


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


    # Generate profile button
    if st.button("Generate Dataset Profile"):

        try:

            filename = st.session_state.uploaded_filename


            profile_response = requests.get(
                f"{API_URL}/profile/{filename}"
            )


            # Profile generated successfully
            if profile_response.status_code == 200:

                profile_result = profile_response.json()


                # Store complete profile in session state
                st.session_state.profile_result = profile_result


                st.success(
                    "Dataset profile generated successfully!"
                )


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

    # DISPLAY PROFILE AFTER IT HAS BEEN GENERATED

    if st.session_state.profile_result is not None:

        profile_result = st.session_state.profile_result

        profile = profile_result["data"]

        # SENSITIVE / IDENTIFIER REVIEW

        st.divider()

        st.subheader("Sensitive / Identifier Review")

        st.write(
            "The system has detected potential sensitive and identifier "
            "columns. Please review and confirm the classification."
        )


        detections = profile.get(
            "sensitive_detection",
            []
        )

        configurations = []


        if detections:

            for detection in detections:

                column_name = detection["column_name"]


                detected_type = "Normal"


                if detection["is_identifier"]:

                    detected_type = "Identifier"

                elif detection["is_sensitive"]:

                    detected_type = "Sensitive"


                st.write(
                    f"### {column_name}"
                )


                st.write(
                    f"**System Detection:** {detected_type}"
                )


                options = [
                    "Normal",
                    "Sensitive",
                    "Identifier"
                ]


                default_index = options.index(
                    detected_type
                )


                user_decision = st.selectbox(
                    f"Confirm classification for {column_name}",
                    options,
                    index=default_index,
                    key=f"classification_{column_name}"
                )


                configurations.append(
                    {
                        "dataset_id": st.session_state.dataset_id,
                        "column_name": column_name,
                        "column_type": detection["data_type"],
                        "is_sensitive": (
                            user_decision == "Sensitive"
                        ),
                        "is_identifier": (
                            user_decision == "Identifier"
                        ),
                        "action": "pending",
                    }
                )


            # Save button is OUTSIDE the for loop
            if st.button("Save Column Classifications"):

                try:

                    save_response = requests.post(
                        f"{API_URL}/column-configurations",
                        json={
                            "configurations": configurations
                        }
                    )


                    if save_response.status_code == 200:

                        st.success(
                            "Column classifications saved successfully!"
                        )


                    else:

                        error = save_response.json()

                        st.error(
                            error.get(
                                "detail",
                                "Unable to save column classifications."
                            )
                        )


                except requests.exceptions.ConnectionError:

                    st.error(
                        "Unable to connect to the backend."
                    )


                except Exception as error:

                    st.error(
                        f"Unable to save column classifications: {error}"
                    )


        else:

            st.info(
                "No sensitive or identifier columns were detected."
            )


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