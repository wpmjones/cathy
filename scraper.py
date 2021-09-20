import creds
import datetime
import email
import imaplib
import json
import requests

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
    for i in id_list:
        typ, data = mail.fetch(i, "(RFC822)")
        raw = data[0][1]
        raw_str = raw.decode("utf-8")
        msg = email.message_from_string(raw_str)
        logger.info(msg)
        if msg.is_multipart():
            for part in msg.walk():
                part_type = part.get_content_type()
                if part_type == "text/plain" and "attachment" not in part:
                    body = part.get_payload()
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = msg.get_payload(decode=True).decode("utf-8")
        logger.info(body)
    #     for response_part in data:
    #         if isinstance(response_part, tuple):
    #             msg = email.message_from_bytes(response_part[1])
    #             logger.info(type(msg))
    #             email_msg = str(msg.get_payload(0), "UTF-8")
    #             logger.info(f"Message: {email_msg}")
    #             for j in range(5):
    #                 start = find_nth(email_msg, "%", j + 1) - 3
    #                 end = start + 4
    #                 score_dict[categories[j]] = email_msg[start:end].strip()
    # logger.info(score_dict)
    # webhook_url = creds.webhook_test
    # content = "*Month to Date CEM Scores*\n```"
    # for key, value in score_dict.items():
    #     content += f"{key}{' '*(25-len(key))}{' '*(4-len(value))}{value}\n"
    # content += "```"
    # logger.info(content)
    # payload = {"text": content}
    # r = requests.post(webhook_url, json=payload)


if __name__ == "__main__":
    check_cem()
