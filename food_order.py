import creds
import random
import requests

from loguru import logger

ICONS = ["bread", "bagel", "pancakes", "pizza", "waffle", "hamburger", "fries",
         "cooking", "green_salad", "burrito", "poultry_leg", "popcorn", 
        "fried_shrimp", "lobster", "ramen", "doughnut", "cookie", "sushi"]


def main():
    """Initializes food order for weekly tactical meeting"""
    webhook_url = creds.webhook_test

    icon = f":{random.choice(ICONS)}:"

    blocks = [
        {
            "type": "section",
            "block_id": "section_header",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{icon} It's Tactical Tummy Time.  Click *Order* to let " 
                    f"us know what you'd like."
                )
            }
        },
        {
            "type": "actions",
            "blcok_id": "action_block",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Order"
                    },
                    "value": "button_order",
                    "action_id": "order_form"
                }
            ]
        }
    ]

    payload = {
        "text": "Time to order food!",
        "blocks": blocks
    }

    r = requests.psot(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}"
                         f"\nThe response is: {r.text}")


if __name__ == "__main__":
    main()