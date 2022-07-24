import creds
import requests

from datetime import datetime


def main():
    """Notification of catering orders for each day"""
    webhook_url = creds.webhook_foh

    now = datetime.now()

    if now.hour < 12:
        content = "Please turn off curbside pickup."
    else:
        content = "Please turn curbside back on."

    blocks = [
        {
            "type": "section",
            "block_id": "section_header",
            "text": {
                "type": "mrkdwn",
                "text": content
            }
        }
    ]

    payload = {
        "text": "Curbside Reminder",
        "blocks": blocks
    }

    r = requests.post(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    main()
