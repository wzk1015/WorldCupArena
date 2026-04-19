from dotenv import load_dotenv
import os
import json

load_dotenv()  # 自动加载 .env 里的所有变量
import http.client


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
        print(data)
        return

    # import ipdb; ipdb.set_trace()
    ids = []
    for fixture in data:
        if team.lower() in fixture['teams']['home']['name'].lower() or team.lower() in fixture['teams']['away']['name'].lower():
            ids.append(fixture["fixture"]["id"])
    assert len(ids) == 1, ids
    print(ids[0])

    # bayern madrid: 1534911


def get_fixture(id):
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")

    headers = {
        'x-apisports-key': os.getenv("API_FOOTBALL_KEY")
        }

    conn.request("GET", f"/fixtures?id={id}", headers=headers)

    res = conn.getresponse()
    data = res.read()

    print(data.decode("utf-8"))



if __name__ == "__main__":
    get_id(team="germain", league=61)
    # get_fixture(1396506)
