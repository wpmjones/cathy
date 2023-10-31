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

now_str = datetime.today().strftime("%m/%d/%Y")
now = datetime.today()
then = datetime.today() + timedelta(days=30)
webhook_url = creds.webhook_test


def main():
    """Notifications for soon to expire food handlers cards"""
    data = sheet.get_all_values()
    about_to_expire = []
    for row in data[1:]:
        try:
            expires = datetime.strptime(row[2], "%m/%d/%Y")
            if expires < then:
                about_to_expire.append([row[0], expires])
        except ValueError:
            pass
    data = sorted(data, key=itemgetter(1))
    data_dict = {}
    for row in data:
        if row[1] in data_dict.keys():
            data_dict[row[1]].append(row[0])
        else:
            data_dict[row[1]] = [row[0]]
    if not data_dict:
        return
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Food Handler Cards*\nExpiring in the next 30 days"}
        }
    ]
    for key, value in data_dict.items():
        names = "\n".join(value)
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{key}*\n{names}"}
            }
        )

    logger.info(blocks)

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
