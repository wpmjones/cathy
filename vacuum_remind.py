import creds
import requests


def main():
    """Reminder to vacuum rugs"""
    webhook_url = creds.webhook_foh

    content = "Please remind staff to vacuum the rugs."

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
        "text": "Rug Reminder",
        "blocks": blocks
    }

    r = requests.post(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    main()
