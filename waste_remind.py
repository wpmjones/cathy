import creds
import requests


def main():
    webhook_url = creds.webhook_boh
    waste_tracking_sheet = creds.waste_tracking_sheet

    blocks = [
        {
            "type": "section",
            "block_id": "section_header",
            "text": {
                "type": "mrkdwn",
                "text": ("It's time to record waste!\nPlease click the button below to launch the waste form. "
                         "All waste must be recorded in decimals.\n\n*Examples:*\n1 lb 12 oz = 1.75 lbs.\n"
                         ".4 oz = .25 lbs.\n\nPlease remember to replace stickers on all waste containers.")
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "actions",
            "block_id": "action_block",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Record Waste"
                    },
                    "value": "button_record_waste",
                    "action_id": "waste_tracking_form"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Waste Sheet"
                    },
                    "value": "button_waste_Sheet",
                    "action_id": "waste_sheet",
                    "url": waste_tracking_sheet,
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "No Waste"
                    },
                    "value": "button_no_waste",
                    "action_id": "no_waste"
                }
            ]
        }
    ]

    payload = {
        "text": "Reminder: Please record waste",
        "blocks": blocks
    }

    r = requests.post(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    main()
