import creds

from db import Messages, get_db
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Connect to Twilio
account_sid = creds.twilio_account_sid
auth_token = creds.twilio_auth_token
twilio_client = Client(account_sid, auth_token)


@app.command("/text_welcome")
async def text_welcome(ack, body, say, client):
    await ack()
    with get_db() as conn:
        with conn.cursor as cursor:
            # sql = "SELECT recipient_id, first_name, phone, store_id FROM cfa_recipients WHERE welcome_sent = false"
            sql = "SELECT recipient_id, first_name, phone, store_id FROM cta_recipients WHERE recipient_id = 1"
            cursor.execute(sql)
            recipients = cursor.fetchall()
    for recipient in recipients:
        msg = (f"{recipient[1]}, welcome to Chick-fil-A S Las Vegas Blvd & I-215 team! We will occasionally "
               f"send you texts about the team and special announcements. Reply STOP to unsubscribe.")
        result = await send_sms(recipient, msg)
        if result != "success":
            await say(channel_id=body['channel']['id'],
                      text=f"There was a problem sending the welcome text to {recipient[2]} ({recipient[0]}). "
                           f"Phone number: {recipient[2]}. I'll let the administrator know.")
            await client.chat_postMessage(channel=creds.pj_user_id,
                                          text=f"There was an error while sending an SMS via Twilio.\n{result}")


@app.command("/text")
async def text(ack, body, client):
    await ack()
    # Validate user (admins only)
    if body['user_id'] not in creds.admin_ids:
        return
    with get_db() as conn:
        with conn.cursor() as cursor:
            sql = "SELECT position_id, name FROM cfa_positions WHERE position_id <> 6 ORDER BY name"
            cursor.execute(sql)
            groups = cursor.fetchall()
    options = [
        {
            "text": {
                "type": "plain_text",
                "text": "Everyone"
            },
            "value": "0"
        }
    ]
    for group in groups:
        options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": group[1]
                },
                "value": f"{group[0]}"
            }
        )
    await client.views_open(
        trigger_id=body['trigger_id'],
        view={
            "type": "modal",
            "callback_id": "text_view",
            "title": {"type": "plain_text", "text": "Send Text"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "input_group",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Select the recipient group"
                    },
                    "accessory": {
                        "action_id": "recipient_group",
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a group"
                        },
                        "options": options
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_message",
                    "label": {"type": "plain_text", "text": "Message"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "message",
                        "multiline": True
                    },
                    "optional": False
                }
            ]
        }
    )


@app.view("text_view")
async def handle_text_input(ack, body, client, view, say):
    """Process input from text form"""
    position_id = view['state']['values']['input_group']['recipient_group']['selected_option']['value']
    msg = view['state']['values']['input_message']['message']['value']
    await ack()
    with get_db() as conn:
        with conn.cursor() as cursor:
            if position_id == 0:
                sql = "SELECT recipient_id, first_name, phone, store_id FROM cfa_recipients WHERE enabled = True"
                cursor.execute(sql)
            else:
                sql = ("SELECT recipient_id, first_name, phone, store_id FROM cfa_recipients "
                       "WHERE enabled = True AND position_id = %s")
                cursor.execute(sql, position_id)
            recipients = cursor.fetchall()
            recipient_count = len(recipients)
    for recipient in recipients:
        result = await send_sms(recipient, msg)
        if result != "success":
            await say(channel_id=creds.exec_channel,
                      text=f"There was a problem sending a text to {recipient[2]} ({recipient[0]}). Phone number: "
                           f"{recipient[2]}. I'll let the administrator know.")
            await client.chat_postMessage(channel=creds.pj_user_id,
                                          text=f"There was an error while sending an SMS via Twilio.\n{result}")
    # All messages have been sent, send notification to Slack
    # Get name of recipient group
    if position_id == 0:
        recipient_group = "Everyone"
    else:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT name FROM cfa_positions WHERE position_id = %s", position_id)
                recipient_group = cursor.fetchone()[0]
    block_text = (f"*Message*: {msg}\n"
                  f"*Sent to:* {recipient_group} (Size: {recipient_count})\n"
                  f"*Sent by:* {body['user']['name']}")
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": block_text}
        }
    ]
    await client.chat_postMessage(channel=creds.exec_channel,
                                  blocks=blocks,
                                  text=f"SMS Message sent to {recipient_group}.")


@app.action("recipient_group")
async def update_menu_select(ack):
    await ack()


async def send_sms(recipient, msg):
    """Send SMS"""
    try:
        recipient_id = recipient[0]
        phone = recipient[2]
        store_id = recipient[3],
        message = twilio_client.messages.create(
            to=phone,
            from_=creds.phone_3930,
            body=msg
        )
        Messages.add_message(message.sid, recipient_id, store_id, msg)
        return "success"
    except TwilioRestException as e:
        return e
