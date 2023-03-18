import creds
import requests

from datetime import datetime


def main():
    """Reminder to submit QIC form for missing truck items"""
    webhook_url = creds.webhook_boh

    qic_url = "https://www.cfahome.com/go/appurl.go?app=QIC_FORM"
    content = f"Have you submitted any QIC's yet?  If not, <{qic_url}|click here.>"

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
        "text": "QIC Reminder",
        "blocks": blocks
    }

    r = requests.post(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    main()
