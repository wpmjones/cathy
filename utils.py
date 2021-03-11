import creds

from twilio.rest import Client

# Connect to Twilio
account_sid = creds.twilio_account_sid
auth_token = creds.twilio_auth_token
twilio_client = Client(account_sid, auth_token)


def welcome_recipient(recipient_id, name, phone, store_name, from_phone):
    body = (f"Welcome {name}! You've been added to a group for {store_name} text messages. "
            f"If you have questions, talk to your corps officers. Text 'STOP' to cancel messages.")
    twilio_msg = twilio_client.messages.create(to=phone,
                                               from_=from_phone,
                                               body=body)
    return twilio_msg.sid, "WELCOME", recipient_id, 0, body
