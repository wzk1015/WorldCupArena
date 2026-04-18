from dotenv import load_dotenv
import os

load_dotenv()  # 自动加载 .env 里的所有变量
import http.client


conn = http.client.HTTPSConnection("v3.football.api-sports.io")

headers = {
    'x-apisports-key': os.getenv("API_FOOTBALL_KEY")
    }

conn.request("GET", "/fixtures?date=2026-04-15&league=2&season=2025", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))

# bayern madrid: 1534911