import csv
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00247"
serviceKey = "FUXYXR27918FPX4K"
payloads = {
    "serviceKey": serviceKey,
    "returnType": "json",
    "pageNo": "60",
    "numOfRows": "10",
}
OUT_CSV = "safety_data.csv"

response = requests.get(url, params=payloads, verify=False)
response.raise_for_status()
data = response.json()

rows = data.get("body", [])
if rows:
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved {len(rows)} rows -> {OUT_CSV}")
else:
    print("no rows returned:", data)


def demo():
    # ponytail: hits the real API; only checks the response shape, not live data values
    assert response.status_code == 200
    assert "returnType" not in payloads or payloads["returnType"] == "json"
    assert isinstance(data, dict)


if __name__ == "__main__":
    demo()
