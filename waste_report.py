import creds
import gspread
import requests

from datetime import datetime

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)
spreadsheet = gc.open_by_key(creds.waste_id)


def main():
    webhook_url = creds.webhook_test
    now_today = datetime.today()

    sheet = spreadsheet.worksheet("Data")
    num_rows = sheet.row_count
    values = sheet.get(f"A{num_rows - 10}:J{num_rows}")

    for row in values:
        print(row[0][:10], now_today)
        if row[0][:10] == now_today:
            print(row[1], row[2])

    blocks = [
        {
            "type": "section",
            "block_id": "section_header",
            "text": {
                "type": "mrkdwn",
                "text": f"*Waste Report for {now_today}"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "block_id": "waste_report"
        }
    ]

    payload = {
        "text": "Daily Waste Report",
        "blocks": blocks
    }

    # r = requests.post(webhook_url, json=payload)
    # if r.status_code != 200:
    #     raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
    #                      f"The response is: {r.text}")


if __name__ == "__main__":
    main()
