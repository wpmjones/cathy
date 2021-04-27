import asyncio
import creds
import gspread
import os
import string

# from slack_bolt import App
from datetime import datetime
from db import Messages, get_db
from fuzzywuzzy import fuzz
from loguru import logger
from slack_bolt.async_app import AsyncApp
from slack_bolt.error import BoltError
from slack_sdk.errors import SlackApiError
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Create Slack app
app = AsyncApp(token=creds.bot_token,
               signing_secret=creds.signing_secret)

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)

# Connect to Twilio
account_sid = creds.twilio_account_sid
auth_token = creds.twilio_auth_token
twilio_client = Client(account_sid, auth_token)


# look for whitespace in string
def contains_whitespace(s):
    return True in [c in s for c in string.whitespace]


@app.command("/help")
async def cathy_help(ack, say):
    """Responds with help for Cathy commands"""
    await ack()
    await say("`/symptoms` List the symptoms that require a TM to go home\n"
              "`/illness` List the illnesses that require a TM to stay home\n"
              "`/sick` Open a form to report an illness or unexcused absence\n"
              "`/find [first last]` Retrieve information on missed shifts for the specified TM\n"
              "`/help` List these commands")


# Remove prior messages
@app.command("/clear")
async def clear_messages(ack, body, say, client):
    """Clear the specified number of messages in the channel that called the command"""
    await ack()
    if body['user_id'] not in [creds.pj_user_id, creds.hc_user_id, creds.jc_user_id, creds.pr_user_id]:
        return await say("I'm sorry. Only admins can clear messages.")
    result = await client.conversations_history(channel=body['channel_id'], limit=int(body['text']))
    channel_history = result['messages']
    counter = 0
    for message in channel_history:
        # if counter % 20 == 0:
        #     await asyncio.sleep(2)
        try:
            await client.chat_delete(channel=body['channel_id'],
                                     ts=message['ts'],
                                     token=creds.user_token)
        except BoltError as e:
            print(f"Bolt error: {e}")
        except SlackApiError as e:
            print(f"Error deleting message: {e}")
            await asyncio.sleep(2)
        counter += 1


@app.command("/sick")
async def sick(ack, body, client):
    await ack()
    await client.views_open(
        trigger_id=body['trigger_id'],
        view={
            "type": "modal",
            "callback_id": "sick_view",
            "title": {"type": "plain_text", "text": "Missed Shift"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "input_a",
                    "label": {"type": "plain_text", "text": "Team Member Name"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "tm_name",
                        "multiline": False
                    },
                    "optional": False
                },
                {
                    "type": "input",
                    "block_id": "input_b",
                    "label": {"type": "plain_text", "text": "Callout Reason"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reason",
                        "multiline": False
                    },
                    "optional": False,
                    "hint": {"type": "plain_text", "text": "Use NCNS for No Call/No Show"}
                },
                {
                    "type": "input",
                    "block_id": "input_c",
                    "label": {"type": "plain_text", "text": "Symptoms"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "symptoms",
                        "multiline": False
                    },
                    "optional": True
                },
                {
                    "type": "input",
                    "block_id": "input_d",
                    "label": {"type": "plain_text", "text": "Contact Person/Method"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "contact",
                        "multiline": False
                    },
                    "optional": False,
                    "hint": {
                        "type": "plain_text",
                        "text": "Hot Schedules or the name of the leader that spoke to the TM"
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_e",
                    "label": {"type": "plain_text", "text": "Duration"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "duration",
                        "multiline": False
                    },
                    "optional": True
                },
                {
                    "type": "input",
                    "block_id": "input_f",
                    "label": {"type": "plain_text", "text": "Restrictions"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "restrictions",
                        "multiline": False
                    },
                    "optional": True
                }
            ]
        }
    )


@app.view("sick_view")
async def handle_sick_input(ack, body, client, view, say):
    """Process input from sick form"""
    name = view['state']['values']['input_a']['tm_name']['value']
    reason = view['state']['values']['input_b']['reason']['value']
    symptoms = view['state']['values']['input_c']['symptoms']['value']
    contact = view['state']['values']['input_d']['contact']['value']
    duration = view['state']['values']['input_e']['duration']['value']
    restrictions = view['state']['values']['input_f']['restrictions']['value']
    block_text = (f"*Name*: {name}\n"
                  f"*Callout reason:* {reason}")
    if symptoms:
        block_text += f"\n*Symptoms:* {symptoms}"
    block_text += f"\n*Contact:* {contact}"
    if duration:
        block_text += f"\n*Duration:* {duration}"
    if restrictions:
        block_text += f"\n*Restrictions:* {restrictions}"
    errors = {}
    if not contains_whitespace(name):
        errors['input_a'] = "Please provide both first and last name."
    if len(errors) > 0:
        await ack(response_action="errors", errors=errors)
        return
    await ack()
    # Send data to Google Sheet
    try:
        sh = gc.open_by_key(creds.sick_log_id)
        sheet = sh.get_worksheet(0)
        now = str(datetime.date(datetime.today()))
        to_post = [now, name, reason, symptoms, contact, duration, restrictions]
        sheet.append_row(to_post)
    except gspread.exceptions.GSpreadException as e:
        await client.chat_postMessage(channel=body['user']['id'],
                                      text=e)
        return
    except Exception as e:
        await client.chat_postMessage(channel=body['user']['id'],
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        await client.chat_postMessage(channel=creds.pj_user_id,
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        return
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": block_text}
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "text": f"Submitted by: {body['user']['name']}"
                }
            ]
        }
    ]
    await client.chat_postMessage(channel=creds.sick_channel,
                                  blocks=blocks,
                                  text=f"New callout for {name}.  Review the sheet <{creds.sick_log_link}|here>.")


@app.command("/find")
async def find_names(ack, body, say):
    """Find matching names from Sick & Discipline Logs"""
    await ack()
    sh = gc.open_by_key(creds.sick_log_id)
    sheet = sh.worksheet("Form Responses 1")
    data = sheet.get_all_values()
    count = 0
    block_text = f"*Log records for {body['text']}:*"
    input_name = body['text']
    for row in data:
        ratio = fuzz.token_sort_ratio(input_name.lower(), row[1].lower())
        if ratio > 78:
            count += 1
            block_text += f"\n{row[0]} - {row[2]}"
            if row[3]:
                block_text += f" ({row[3]})"
    if count == 0:
        return await say(f"No records found for {body['text']}.")
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": block_text}
        }
    ]
    await say(blocks=blocks, text=f"Found {count} records for {body['text']}.")


@app.command("/symptoms")
async def symptoms(ack, say):
    """Respond with the symptoms that require a Team Member to go home"""
    await ack()
    await say("*Team Members must be sent home if displaying the following symptoms:*\n"
              "Vomiting\n"
              "Diarrhea\n"
              "Jaundice (yellowing of the skin)\n"
              "Fever\n"
              "Sore throat with fever or lesions containing pus\n"
              "Infected wound or burn that is opening or draining")


@app.command("/illness")
async def illness(ack, say):
    """Respond with the illnesses that require a Team Member to stay home"""
    await ack()
    await say("*Team Members must stay home if they have the following illnesses:*\n"
              "Salmonella Typhi\n"
              "Non-typhoidal Salmonella\n"
              "Shigella spp.\n"
              "Shiga toxin-producing Escherichia coli (E coli)\n"
              "Hepatitis A virus\n"
              "Norovirus (a type of stomach flu)")


@app.command("/text")
async def text(ack, body, client):
    await ack()
    # Validate user (admins only)
    if body['user_id'] not in creds.admin_ids:
        return
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT position_id, name FROM cfa_positions ORDER BY name")
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
    logger.info(view['state']['values']['input_group']['recipient_group'])
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
            await say(f"There was a problem sending a text to {recipient[2]} ({recipient[0]}). Phone number: "
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
                  f"*Sent to:* {recipient_group} ({recipient_count})\n"
                  f"*Sent by:* {body['user']['name']}")
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": block_text}
        }
    ]
    await client.chat_postMessage(channel=body['channel_id'],
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
        return True
    except TwilioRestException as e:
        return e

# Start your app
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
