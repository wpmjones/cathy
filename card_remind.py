import creds
import gspread
import requests

from datetime import datetime, timedelta
from loguru import logger
from operator import itemgetter

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)
spreadsheet = gc.open_by_key(creds.card_id)
sheet = spreadsheet.get_worksheet(0)
sheet.sort((3, "asc"), range="A2:C200")

now_str = datetime.today().strftime("%m/%d/%Y")
now = datetime.today()
then = datetime.today() + timedelta(days=30)
webhook_url = creds.webhook_test


def main():
    """Notifications for soon to expire food handlers cards"""
    data = sheet.get_all_values()
    about_to_expire = {}
    already_expired = {}
    for row in data[1:]:
        try:
            expires = datetime.strptime(row[2], "%m/%d/%Y")
            if expires < now:
                if expires in already_expired:
                    already_expired[expires].append(row[0])
                else:
                    already_expired[expires] = [row[0]]
            elif expires < then:
                if expires in about_to_expire:
                    about_to_expire[expires].append(row[0])
                else:
                    about_to_expire[expires] = [row[0]]
        except ValueError:
            pass
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Food Handler Cards - *Expired*"}
        }
    ]
    for key, value in already_expired.items():
        names = "\n".join(value)
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{key.strftime('%m/%d/%Y')}*\n{names}"}
            }
        )
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Food Handler Cards - Expiring in the next 30 days"}
        }
    )
    for key, value in about_to_expire.items():
        names = "\n".join(value)
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{key.strftime('%m/%d/%Y')}*\n{names}"}
            }
        )

    payload = {
        "text": "Expiring Food Handler Cards",
        "blocks": blocks
    }

    r = requests.post(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    main()
