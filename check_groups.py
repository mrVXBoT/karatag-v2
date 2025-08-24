#!/usr/bin/env python3
# Script: check_groups.py
# This script connects the bot, reads all Group records from the database,
# and classifies them as valid (bot is present and admin) or invalid (bot removed or not admin).

import asyncio
import time
from config import client, token
from lib.db import Group
from telethon.errors import ChatWriteForbiddenError, ChatAdminRequiredError

async def main():
    # Measure start time
    start_time = time.time()
    # Start the client with the bot token
    await client.start(bot_token=token)
    me = await client.get_me()

    # Prepare result lists and total count
    total_groups = Group.select().count()
    valid_member = []
    valid_admin = []
    non_admin = []
    invalid = []

    # Iterate and test actual membership by sending a test message
    for idx, grp in enumerate(Group.select(), start=1):
        print(f"[{idx}/{total_groups}] Checking group ID: {grp.id}")
        chat_id = int(grp.id)
        # Attempt to send a lightweight test message to verify membership, with supergroup fallback
        sent_id = chat_id
        try:
            test_msg = await client.send_message(chat_id, "🔍 Checking bot membership...")
        except ChatWriteForbiddenError:
            # Bot is in group but cannot write (likely non-admin)
            valid_member.append(grp.id)
            non_admin.append(grp.id)
            await asyncio.sleep(0.1)
            continue
        except ChatAdminRequiredError:
            # Bot is in group but lacks rights
            valid_member.append(grp.id)
            non_admin.append(grp.id)
            await asyncio.sleep(0.1)
            continue
        except Exception:
            # Try supergroup prefix (-100...)
            try:
                alt_id = int(f"-100{grp.id}")
                test_msg = await client.send_message(alt_id, "🔍 Checking bot membership...")
                sent_id = alt_id
            except ChatWriteForbiddenError:
                valid_member.append(grp.id)
                non_admin.append(grp.id)
                await asyncio.sleep(0.1)
                continue
            except ChatAdminRequiredError:
                valid_member.append(grp.id)
                non_admin.append(grp.id)
                await asyncio.sleep(0.1)
                continue
            except Exception:
                # Sending failed — bot not in group or inaccessible
                invalid.append(grp.id)
                await asyncio.sleep(0.1)
                continue
        # Immediately delete the test message
        await client.delete_messages(sent_id, test_msg.id)
        valid_member.append(grp.id)
        # Check for admin rights explicitly
        try:
            perms = await client.get_permissions(sent_id, me.id)
            if getattr(perms.participant, 'admin_rights', None):
                valid_admin.append(grp.id)
            else:
                non_admin.append(grp.id)
        except Exception:
            non_admin.append(grp.id)
        # Small delay to respect rate limits (reduced)
        await asyncio.sleep(0.1)
    # Output results
    print(f"Total groups in DB: {total_groups}")
    print(f"Bot member in {len(valid_member)} groups")
    print(f"Bot admin in {len(valid_admin)} groups")
    print(f"Bot member but not admin in {len(non_admin)} groups")
    print(f"Bot not member or inaccessible in {len(invalid)} groups")
    if invalid:
        print("Invalid or inaccessible groups:", invalid)

    # Disconnect the client
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
