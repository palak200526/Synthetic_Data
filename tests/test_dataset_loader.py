from pathlib import Path

from backend.services.dataset_loader import load_dataset


def test_load_csv_splits_standard_sentiment_header(tmp_path: Path):
    path = tmp_path / "sentiment-analysis.csv"
    path.write_text(
        "Text, Sentiment, Source, Date/Time, User ID, Location, Confidence Score\n"
        "Loved the product,Positive,Twitter,2024-01-01,u1,NYC,0.92\n"
        "Not great,Negative,Facebook,2024-01-02,u2,LA,0.81\n",
        encoding="utf-8",
    )

    dataframe = load_dataset(str(path))

    assert list(dataframe.columns) == [
        "Text",
        "Sentiment",
        "Source",
        "Date/Time",
        "User ID",
        "Location",
        "Confidence Score",
    ]
    assert len(dataframe) == 2
    assert dataframe.iloc[0]["Text"] == "Loved the product"


def test_load_csv_unwraps_excel_single_quoted_row(tmp_path: Path):
    path = tmp_path / "sentiment-analysis.csv"
    path.write_text(
        '"Text, Sentiment, Source, Date/Time, User ID, Location, Confidence Score"\n'
        '"Loved the product,Positive,Twitter,2024-01-01,u1,NYC,0.92"\n',
        encoding="utf-8",
    )

    dataframe = load_dataset(str(path))

    assert "Text" in dataframe.columns
    assert "Sentiment" in dataframe.columns
    assert dataframe.shape[1] == 7


def test_load_semicolon_csv(tmp_path: Path):
    path = tmp_path / "europe.csv"
    path.write_text("a;b;c\n1;2;3\n", encoding="utf-8")

    dataframe = load_dataset(str(path))
    assert list(dataframe.columns) == ["a", "b", "c"]
