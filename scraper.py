import creds
import datetime
import email
import imaplib

mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(creds.gmail_u, creds.gmail_p)
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
    past_date = datetime.date.today() - datetime.timedelta(days=3)
    tfmt = past_date.strftime('%d-%b-%Y')
    type, sdata = mail.search(None, f'(FROM "SMGMailMgr@whysmg.com" SINCE {tfmt})')
    mail_ids = sdata[0]
    id_list = mail_ids.split()
    score_dict = {}
    for i in id_list:
        typ, data = mail.fetch(i, "(RFC822)")
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                email_msg = str(msg.get_payload(0))
                for j in range(5):
                    start = find_nth(email_msg, "%", j + 1) - 3
                    end = start + 4
                    score_dict[categories[j]] = email_msg[start:end].strip()

