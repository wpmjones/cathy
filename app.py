import asyncio
import creds
import gspread
import os
import string

# from slack_bolt import App
from datetime import datetime
from slack_bolt.async_app import AsyncApp
from slack_bolt.error import BoltError
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_sdk.errors import SlackApiError

oauth_settings = AsyncOAuthSettings(
    client_id=creds.client_id,
    client_secret=creds.client_secret,
    scopes=[
        "app_mentions:read",
        "channels:history",
        "channels:join",
        "channels:read",
        "chat:write",
        "commands",
        "emoji:read",
        "files:read",
        "files:write",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "links:read",
        "links:write",
        "reactions:read",
        "reactions:write",
        "users.profile:read",
        "users:read",
        "users:write",
    ],
    installation_store=FileInstallationStore(base_dir="./data"),
    state_store=FileOAuthStateStore(expiration_seconds=60, base_dir="./data")
)

app = AsyncApp(token=creds.bot_token,
               signing_secret=creds.signing_secret)

gc = gspread.service_account(filename=creds.gspread)


# look for whitespace in string
def contains_whitespace(s):
    return True in [c in s for c in string.whitespace]


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


@app.action("button_click")
async def action_button_click(body, ack, say):
    # Acknowledge the action
    await ack()
    await say(f"<@{body['user']['id']}> clicked the button")


# Start your app
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
