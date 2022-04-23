import creds
import requests

from loguru import logger


def main():
    webhook_url = creds.webhook_foh

    blocks = [
        {
            "type": "section",
            "block_id": "section_header",
            "text": {
                "type": "mrkdwn",
                "text": ("Time for a cash pickup.")
            }
        }
    ]

    payload = {
        "text": "Reminder: Please do a cash pickup.",
        "blocks": blocks
    }

    r = requests.post(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    main()
