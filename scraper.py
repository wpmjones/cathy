import creds
import datetime
import email
import imaplib
import requests
import time

from loguru import logger

mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(creds.gmail_u, creds.gmail_app)
mail.select("INBOX")
today = datetime.date.today()

categories = [
    "Likelihood to Return",
    "Fast Service",
    "Attentive/Courteous",
    "Order Accuracy",
    "Taste",
    "Overall Satisfaction",
]


def find_nth(content, search_string, n):
    start = content.find(search_string)
    while start >= 0 and n > 1:
        start = content.find(search_string, start+len(search_string))
        n -= 1
    return start


def check_cem():
    search_date = datetime.date.today()  # - datetime.timedelta(days=1)
    tfmt = search_date.strftime('%d-%b-%Y')
    _, sdata = mail.search(None, f'(FROM "SMGMailMgr@whysmg.com" SINCE {tfmt})')
    mail_ids = sdata[0]
    id_list = mail_ids.split()
    score_dict = {}
    body = ""
    for i in id_list:
        typ, data = mail.fetch(i, "(RFC822)")
        raw = data[0][1]
        raw_str = raw.decode("utf-8")
        msg = email.message_from_string(raw_str)
        if msg.is_multipart():
            for part in msg.walk():
                part_type = part.get_content_type()
                if part_type == "text/plain" and "attachment" not in part:
                    body = part.get_payload(decode=True).decode("utf-8")
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = msg.get_payload(decode=True).decode("utf-8")
    # find percentages in body
    if body:
        for j in range(6):
            start = find_nth(body, "%", j + 1) - 3
            end = start + 4
            score_dict[categories[j]] = body[start:end].strip()
        # find number of respondents
        start = body.find("n:") + 3
        end = start + 3
        num_responses = body[start:end].strip()
        # post content to Slack
        webhook_url = creds.webhook_all
        content = (f"*Month to Date CEM Scores*\n"
                   f"Out of {num_responses} responses\n```")
        for key, value in score_dict.items():
            content += f"{key}{' '*(25-len(key))}{' '*(4-len(value))}{value}\n"
        content += "```"
        payload = {"text": content}
        r = requests.post(webhook_url, json=payload)
        if r.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                             f"The response is: {r.text}")


def check_oos():
    search_date = datetime.date.today() - datetime.timedelta(days=1)
    tfmt = search_date.strftime('%d-%b-%Y')
    _, sdata = mail.search(None, f'(SUBJECT "OOS Notification" SINCE {tfmt})')
    mail_ids = sdata[0]
    id_list = mail_ids.split()
    body = ""
    for i in id_list:
        typ, data = mail.fetch(i, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        if msg.is_multipart():
            for part in msg.walk():
                part_type = part.get_content_type()
                if part_type == "text/plain" and "attachment" not in part:
                    body = part.get_payload()
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = msg.get_payload()
        # body captured, search for relevant text
        if body:
            start = body.find("item #") + 1
            end = start + 14
            item_number = "I" + body[start:end].strip()
            start = end + 2
            end = body.find("This item was") - 1
            item_name = body[start:end].strip()
            item = f"{item_number} - {item_name}"
            start = end
            end = body.find("The product is")
            truck_date = body[start:end].strip() + "."
            start = end
            end = body.find("pending") + 12
            rescheduled = body[start:end].strip() + " supplier's availability."
            # post content to Slack
            content = f"*{item}*\n{truck_date}\n{rescheduled}"
            payload = {
                "text": "Out of Stock Notification",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": content
                        }
                    }
                ]
            }
            r = requests.post(creds.webhook_boh, json=payload)
            if r.status_code != 200:
                raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                                 f"The response is: {r.text}")


if __name__ == "__main__":
    check_cem()
    time.sleep(60*60*4)
    check_oos()
