import pandas as pd

from scripts import preprocess


def test_build_preprocess_result_generates_sequences_and_ids():
    df = pd.DataFrame(
        {
            "SCHOOL NAME": ["Tunnel Academy", "Cheese Wheel Academy"],
            "CLIENT ID": ["C1", "C2"],
            "FIRST NAME": ["Allie", "Benoit"],
            "LAST NAME": ["Zephyr", "Arnaud"],
            "DATE OF BIRTH": ["2015-01-02", "2014-05-06"],
            "CITY": ["Guelph", "Guelph"],
            "POSTAL CODE": ["", None],
            "PROVINCE/TERRITORY": ["ON", "ON"],
            "OVERDUE DISEASE": ["Foo", "Haemophilus influenzae infection, invasive"],
            "IMMS GIVEN": ["May 1, 2020 - DTaP", ""],
            "STREET ADDRESS LINE 1": ["123 Main St", "456 Side Rd"],
            "STREET ADDRESS LINE 2": ["", "Suite 5"],
        }
    )

    normalized = preprocess.ensure_required_columns(df)

    disease_map = {"Foo": "Foo Vaccine"}
    vaccine_reference = {"DTaP": ["Diphtheria", "Tetanus"]}

    result = preprocess.build_preprocess_result(
        normalized,
        language="en",
        disease_map=disease_map,
        vaccine_reference=vaccine_reference,
        ignore_agents=[],
    )

    assert len(result.clients) == 2
    assert result.client_ids == ["C2", "C1"]

    first_client = result.clients[0]
    assert first_client["sequence"] == "00001"
    assert first_client["school"]["id"].startswith("sch_")
    assert first_client["board"]["id"].startswith("brd_")
    assert first_client["person"]["full_name"] == "Benoit Arnaud"
    assert first_client["vaccines_due"].startswith("Invasive Haemophilus")

    second_client = result.clients[1]
    assert second_client["vaccines_due"] == "Foo Vaccine"
    assert second_client["received"][0]["date_given"] == "2020-05-01"
    assert second_client["received"][0]["diseases"] == ["Diphtheria", "Tetanus"]

    assert "Missing board name" in result.warnings[0]
    assert result.legacy_payload["C1"]["sequence"] == "00002"
    assert result.legacy_payload["C1"]["postal_code"] == "Not provided"
    assert result.legacy_payload["C2"]["language"] == "en"
