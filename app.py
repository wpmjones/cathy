import asyncio
import creds
import csv
import gspread
import os
import string

# from slack_bolt import App
from datetime import datetime, date
from fuzzywuzzy import fuzz
from loguru import logger
from slack_bolt.async_app import AsyncApp
from slack_sdk.web import WebClient
from slack_bolt.error import BoltError
from slack_sdk.errors import SlackApiError

# Create Slack app
app = AsyncApp(token=creds.bot_token,
               signing_secret=creds.signing_secret)
client = WebClient(token=creds.bot_token)

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)


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
              "`/tardy [first last]` Records a tardy for the specified TM\n"
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


@app.command("/tardy")
async def tardy(ack, body, say, client):
    await ack()
    try:
        sh = gc.open_by_key(creds.pay_scale_id)
        sheet = sh.worksheet("Tardy")
        now = date.strftime(date.today(), "%m/%d/%Y")
        logger.info(f"{now} - {body['text']} was tardy")
        logger.info(body)
        to_post = [body['text'], now]
        sheet.append_row(to_post, value_input_option='USER_ENTERED')
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Tardy record added for {body['text']}. No meal credit today ({now})."
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"Submitted by: {body['user_name']}"
                    }
                ]
            }
        ]
        await client.chat_postMessage(channel=creds.sick_channel,
                                      blocks=blocks,
                                      text=f"{body['text']} was tardy on {now}.")
    except gspread.exceptions.GSpreadException as e:
        await client.chat_postMessage(channel=body['user']['id'], text=e)
    except Exception as e:
        await client.chat_postMessage(channel=body['user']['id'],
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        await client.chat_postMessage(channel=creds.pj_user_id,
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")


@app.command("/sick")
async def sick(ack, body, client):
    await ack()
    # Create options for select menu
    options = []
    with open('staff.csv', newline="") as f:
        reader = csv.reader(f)
        data = list(reader)
    for n in data:
        options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": n[0]
                },
                "value": n[0]
            }
        )
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
                    "label": {"type": "plain_text", "text": "Name"},
                    "element": {
                        "type": "static_select",
                        "action_id": "tm_name",
                        "placeholder": {"type": "plain_text", "text": "Select a name"},
                        "options": options
                    }
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
                    "label": {"type": "plain_text", "text": "Missed Shift"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "shift",
                        "multiline": False
                    },
                    "optional": True,
                    "hint": {"type": "plain_text", "text": "Position and Time"}
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
                    "label": {"type": "plain_text", "text": "Other notes"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "other",
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
    logger.info("Processing input...")
    name = view['state']['values']['input_a']['tm_name']['selected_option']['value']
    reason = view['state']['values']['input_b']['reason']['value']
    shift = view['state']['values']['input_c']['shift']['value']
    contact = view['state']['values']['input_d']['contact']['value']
    other = view['state']['values']['input_e']['other']['value']
    block_text = (f"*Name*: {name}\n"
                  f"*Callout reason:* {reason}\n"
                  f"*Shift:* {shift}\n"
                  f"*Contact:* {contact}")
    if other:
        block_text += f"\n*Other notes:* {other}"
    errors = {}
    if len(errors) > 0:
        await ack(response_action="errors", errors=errors)
        return
    await ack()
    # Send data to Google Sheet
    try:
        sh = gc.open_by_key(creds.sick_log_id)
        sheet = sh.get_worksheet(0)
        now = str(datetime.date(datetime.today()))
        to_post = [now, name, reason, shift, contact, other]
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


# async def cem_poster():
#     """Repeating task for CEM score posting"""
#     msg = "This is a test message"
#     client.chat_postMessage(channel=creds.all_channel, text=msg)
#     await asyncio.sleep(60 * 60)


# Start your app
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
    # while True:
    #     asyncio.run(cem_poster())
