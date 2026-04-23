from dotenv import load_dotenv
import os
import json
from pathlib import Path
import pprint

load_dotenv()  # 自动加载 .env 里的所有变量
import http.client

FIXTURES_YAML = Path(__file__).resolve().parents[1] / "configs" / "fixtures.yaml"


def get_id(league=94, date="2026-04-19", season=2025, team=None):
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")

    headers = {
        'x-apisports-key': os.getenv("API_FOOTBALL_KEY")
        }

    conn.request("GET", f"/fixtures?date={date}&league={league}&season={season}", headers=headers)

    res = conn.getresponse()
    data = res.read()
    data = json.loads(data.decode("utf-8"))["response"]

    if team is None:
        # print(data)
        if len(data) == 1:
            return data[0]["fixture"]["id"]
        return pprint.pformat(data)

    # import ipdb; ipdb.set_trace()
    ids = []
    for fixture in data:
        if team.lower() in fixture['teams']['home']['name'].lower() or team.lower() in fixture['teams']['away']['name'].lower():
            ids.append(fixture["fixture"]["id"])
    assert len(ids) == 1, ids
    # print(ids[0])
    return ids[0]

    # bayern madrid: 1534911


def get_fixture(id):
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")

    headers = {
        'x-apisports-key': os.getenv("API_FOOTBALL_KEY")
        }

    conn.request("GET", f"/fixtures?id={id}", headers=headers)

    res = conn.getresponse()
    data = res.read()

    # print(data.decode("utf-8"))
    return json.loads(data)



def add_fixture(fixture_id, wca_id=None) -> None:
    """Append a new fixture entry to configs/fixtures.yaml.

    Raises ValueError if wca_id already exists in the file.
    """
    fixture = get_fixture(fixture_id)["response"][0]
    assert fixture["fixture"]["id"] == fixture_id
    kickoff_utc = fixture["fixture"]["date"]

    if wca_id is None:
        wca_id = fixture["league"]["name"] + "_" + fixture["teams"]["home"]["name"] \
            + "_" + fixture["teams"]["away"]["name"] + "_" + kickoff_utc.split("T")[0]
        wca_id = wca_id.replace(" ", "-")

    text = FIXTURES_YAML.read_text()

    if f"wca_id: {wca_id}" in text:
        raise ValueError(f"wca_id '{wca_id}' already exists in fixtures.yaml")
    if f"provider_id: {fixture_id}" in text:
        raise ValueError(f"fixture_id '{fixture_id}' already exists in fixtures.yaml")

    entry = (
        f"  - wca_id: {wca_id}\n"
        f"    provider_id: {fixture_id}\n"
        f"    kickoff_utc: {kickoff_utc}\n"
        f"    enabled: true\n"
    )

    # Insert before the first commented-out block, or append to the fixtures list.
    # if "\n  # -" in text:
    #     insert_pos = text.index("\n  # -")
    #     text = text[:insert_pos] + "\n" + entry + text[insert_pos:]
    # else:
    #     text = text.rstrip("\n") + "\n" + entry

    text = text + "\n" + entry

    FIXTURES_YAML.write_text(text)
    print(f"Added fixture '{wca_id}' (provider_id={fixture_id}, kickoff={kickoff_utc})")


if __name__ == "__main__":
    # print(get_id(team="Tottenham", league=39, date="2026-04-25", season=2025))
    # print(get_id(league=81, date="2026-04-23", season=2025))
    add_fixture(1379308)
