from config import sudo,client  as app,token,delay,delay1
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError, UserDeactivatedBanError, QueryIdInvalidError, MessageNotModifiedError
from config import log_channel 
from config import files_channel 
from config import join_channel
from telethon import errors,Button,events
from lib.decorators import Message
from lib.decorators import Callback
#rom lib.decorators import is_join()
from lib.decorators import is_ban
from lib.decorators import is_join
from lib.decorators import is_admin
from lib.decorators import antiflood
from lib.decorators import is_owner
from lib.db import User
from lib.db import  Media
from lib.db import  Text
from lib.db import  Group
from lib.db import  Setting
from lib.db import  Support
from lib.db import  PendingSubmission
from telethon.tl import types
from datetime import datetime,timedelta
import random
import asyncio
import json
import sqlite3
from peewee import fn
from telethon.tl.types import (
    ChannelParticipantAdmin,
    ChannelParticipantCreator
)
from lib.Paginator import TelethonPaginator
import logging
# logging.basicConfig(level=logging.DEBUG)
from uuid import UUID

# Helper: notify admins safely (falls back to log channel)
async def notify_admins(app, text, buttons=None, file=None):
    """Send notification to all admins, with fallback to log channel"""
    delivered = False
    admin_count = len(sudo)
    print(f"🔔 Attempting to notify {admin_count} admins...")
    
    for i, admin_id in enumerate(sudo):
        try:
            print(f"📤 Trying to send to admin {i+1}/{admin_count}: {admin_id}")
            await app.send_message(int(admin_id), text, buttons=buttons, file=file)
            delivered = True
            print(f"✅ Successfully sent to admin {admin_id}")
            # Remove break to send to all admins
        except Exception as e:
            print(f"❌ Failed to send to admin {admin_id}: {str(e)}")
            continue
    
    if not delivered:
        print(f"⚠️ All admin notifications failed, trying log channel: {log_channel}")
        try:
            await app.send_message(log_channel, text, buttons=buttons, file=file)
            print(f"✅ Sent to log channel: {log_channel}")
        except Exception as e:
            print(f"❌ Failed to send to log channel: {str(e)}")
    
    return delivered

# Helper: safe answer for callback queries
async def safe_answer(event, text, alert=False):
    try:
        await event.answer(text, alert)
    except QueryIdInvalidError:
        try:
            await event.respond(text)
        except Exception:
            pass

# Add sample data to prevent crashes
async def add_sample_data():
    """Add sample text and media to prevent crashes"""
    try:
        # Add sample text if none exists
        if not Text.select().exists():
            Text.create(
                name="نص تعارف عادي",
                text="مرحباً! كيف حالك؟ 😊"
            )
            print("✅ تم إضافة نص تعارف عادي")
        
        # Add sample media if none exists
        if not Media.select().exists():
            # Create a dummy media entry (will be replaced by real media)
            Media.create(
                name="ميديا عادية",
                msg_id=1,
                channel=files_channel,
                caption="مرحباً! هذه ميديا عادية 😊"
            )
            print("✅ تم إضافة ميديا عادية")
                
    except Exception as e:
        print(f"Error adding sample data: {e}")

# Call this function when bot starts
@app.on(events.NewMessage(pattern='/start'))
async def on_start(event):
    if event.is_private:
        await add_sample_data()

# Helper: safe edit to avoid MessageNotModifiedError
async def safe_edit(event, text, buttons=None):
    try:
        await event.edit(text, buttons=buttons)
    except MessageNotModifiedError:
        try:
            await event.answer('تم التحديث', True)
        except Exception:
            pass

# Helper: cleanup invalid groups and users based on get_entity checks
async def cleanup_invalid_entities(client):
    removed_groups = 0
    removed_users = 0
    try:
        # Fast cleanup using the same logic as check_groups.py
        for g in list(Group.select()):
            try:
                chat_id = int(g.id)
                # Try to send a test message to verify membership
                test_msg = await client.send_message(chat_id, "🔍")
                await client.delete_messages(chat_id, test_msg.id)
                # If successful, group is valid
            except Exception:
                # Group is invalid, remove it
                try:
                    Group.delete().where(Group.id == g.id).execute()
                    removed_groups += 1
                except Exception:
                    pass
        # Enhanced user cleanup - check each user individually
        for u in list(User.select()):
            try:
                await client.get_entity(int(u.userid))
                # If successful, user is valid
            except Exception:
                # User is invalid (deleted, banned, etc.), remove it
                try:
                    User.delete().where(User.userid == u.userid).execute()
                    removed_users += 1
                except Exception:
                    pass
    except Exception:
        pass
    return removed_groups, removed_users

# New function: get real-time accurate statistics
async def get_real_statistics(client):
    """Get real-time statistics by checking actual group membership and user validity"""
    valid_member = 0
    valid_admin = 0
    non_admin = 0
    invalid = 0
    real_users = 0
    
    # Quick check of all groups
    for grp in Group.select():
        try:
            chat_id = int(grp.id)
            # Try to send a test message
            test_msg = await client.send_message(chat_id, "🔍")
            await client.delete_messages(chat_id, test_msg.id)
            valid_member += 1
            # Check admin rights
            try:
                perms = await client.get_permissions(chat_id, (await client.get_me()).id)
                if getattr(perms.participant, 'admin_rights', None):
                    valid_admin += 1
                else:
                    non_admin += 1
            except Exception:
                non_admin += 1
        except Exception:
            invalid += 1
    
    # Check user validity by attempting to get entity for each user
    for user in User.select():
        try:
            await client.get_entity(int(user.userid))
            real_users += 1
        except Exception:
            # User is invalid (deleted, banned, etc.)
            pass
    
    return {
        'valid_member': valid_member,
        'valid_admin': valid_admin,
        'non_admin': non_admin,
        'invalid': invalid,
        'total_groups': Group.select().count(),
        'users': real_users,  # Real users count
        'total_users_in_db': User.select().count(),  # Total users in database
        'texts': Text.select().count(),
        'media': Media.select().count()
    }

@Message(pattern = '/start',func = lambda i:i.is_private)
@Callback(pattern = b'start')
@antiflood()
@is_join()
async def start(event):
    try:
        conv = app.conversation(event.sender_id)
        await conv.cancel_all()
    except:
        pass
    User.get_or_create(userid = event.sender_id)
    username = (await event.client.get_entity('me')).username
    buttons = [
        [Button.url('اضافه البوت ✹',f'https://t.me/{username}?startgroup=new'),(Button.inline('الدعم','support'))],
        [Button.inline('اضف نص','user_add_text_btn'), Button.inline('اضف ميديا','user_add_media_btn')],
        [(Button.inline('شرح','khaled'))]
        ]
    if isinstance(event, events.CallbackQuery.Event):
        return await event.edit('#هلا_عمري 🤍🫂\n\n⌁ : تعرف على بوُت التاكات\n⌁ : أفضل بوت لإرسال تاك للكل .\n⌁ : أفضل بوت لإرسال تاك بلميديا والصوت والتعارف .\n┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉\n⌁ : نقوم بتحديث بوت التاكات بشكل شهري وعلا آخر اصدار للغه بايثون واضافه مميزات لا تتوفر في باقي البوتات 🍇 فقط في تيم ماکس .',buttons = buttons)
    return await event.reply('#هلا_عمري 🤍🫂\n\n⌁ : تعرف على بوُت التاكات\n⌁ : أفضل بوت لإرسال تاك للكل .\n⌁ : أفضل بوت لإرسال تاك بلميديا والصوت والتعارف .\n┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉\n⌁ : نقوم بتحديث بوت التاكات بشكل شهري وعلا آخر اصدار للغه بايثون واضافه مميزات لا تتوفر في باقي البوتات 🍇 فقط في تيم ماکس .',buttons = buttons)

# ===== User submission flow (text/media) with admin approval =====
@Callback(pattern=b'user_add_text_btn')
@is_ban
async def cb_user_add_text(event):
    # Step 1: ask for text via edit; wait for user's next private message
    await event.edit('📝 ارسل نص التعارف الذي تريد إضافته:', buttons=Button.inline('عودة','start'))
    async with app.conversation(event.sender_id) as conv:
        text_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        while not text_msg.text:
            await event.edit('❌ يجب إرسال نص. حاول مرة اخرى:', buttons=Button.inline('عودة','start'))
            text_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        
        # Delete text message immediately after receipt
        try:
            await event.client.delete_messages(event.sender_id, [text_msg.id])
        except Exception:
            pass
            
        # Step 2: ask for name
        await event.edit('🏷️ ارسل اسماً لهذا النص:', buttons=Button.inline('عودة','start'))
        name_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        while not name_msg.text:
            await event.edit('❌ يجب إرسال اسم صحيح. حاول مرة اخرى:', buttons=Button.inline('عودة','start'))
            name_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        
        # Delete name message immediately after receipt
        try:
            await event.client.delete_messages(event.sender_id, [name_msg.id])
        except Exception:
            pass
            
        sub = PendingSubmission.create(
            submitter_id=event.sender_id,
            type='text',
            name=name_msg.text,
            text=text_msg.text
        )
        
    # Notify admins with approve/reject buttons + profile button
    try:
        submitter = await event.client.get_entity(event.sender_id)
        submitter_name = submitter.first_name or 'مستخدم'
        submitter_username = f'@{submitter.username}' if getattr(submitter, 'username', None) else ''
    except Exception:
        submitter_name = 'مستخدم'
        submitter_username = ''
    btns = [
        [Button.inline('✅ قبول', f'approve_sub {str(sub.id)}'), Button.inline('❌ رفض', f'reject_sub {str(sub.id)}')],
        [Button.url('👤 الملف الشخصي', f'tg://user?id={event.sender_id}')]
    ]
    
    admin_text = (
        '🆕 طلب نص جديد\n'
        f'الاسم: {name_msg.text}\n'
        f'المحتوى:\n{text_msg.text}\n\n'
        f'المُرسل: {submitter_name} {submitter_username} (ID: {event.sender_id})'
    )
    
    print(f"🔔 Notifying admins about text submission: {sub.id}")
    await notify_admins(app, admin_text, buttons=btns)
    await event.edit('✅ تم إرسال طلبك للمراجعة من قبل الإدارة', buttons=Button.inline('عودة','start'))

@Callback(pattern=b'user_add_media_btn')
@is_ban
async def cb_user_add_media(event):
    await event.edit('📸 ارسل الميديا الآن (صورة/فيديو/صوت):', buttons=Button.inline('عودة','start'))
    fwd = None  # Declare fwd at function level
    
    async with app.conversation(event.sender_id) as conv:
        media_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        while not getattr(media_msg, 'media', None):
            await event.edit('❌ يجب إرسال ميديا صالحة. حاول مرة اخرى:', buttons=Button.inline('عودة','start'))
            media_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        
        # Forward immediately and delete user's media
        try:
            fwd = await media_msg.forward_to(files_channel)
            print(f"✅ Media forwarded to {files_channel}, message ID: {fwd.id}")
        except Exception as e:
            print(f"❌ Failed to forward media: {e}")
            fwd = None
            
        try:
            await event.client.delete_messages(event.sender_id, [media_msg.id])
        except Exception:
            pass
            
        await event.edit('🏷️ ارسل اسماً لهذه الميديا:', buttons=Button.inline('عودة','start'))
        name_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        while not name_msg.text:
            await event.edit('❌ يجب إرسال اسم صحيح. حاول مرة اخرى:', buttons=Button.inline('عودة','start'))
            name_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        
        # Delete name message immediately after receipt
        try:
            await event.client.delete_messages(event.sender_id, [name_msg.id])
        except Exception:
            pass
            
        await event.edit('📝 ارسل وصف للميديا (اكتب "بدون وصف" للتخطي):', buttons=Button.inline('عودة','start'))
        caption_msg = await conv.wait_event(events.NewMessage(from_users=event.sender_id))
        caption_text = caption_msg.text if caption_msg.text != 'بدون وصف' else None
        
        # Delete caption message immediately after receipt
        try:
            await event.client.delete_messages(event.sender_id, [caption_msg.id])
        except Exception:
            pass
        
        sub = PendingSubmission.create(
            submitter_id=event.sender_id,
            type='media',
            name=name_msg.text,
            text=None,
            temp_chat_id=str(files_channel if fwd else media_msg.chat_id),
            temp_msg_id=int(fwd.id if fwd else media_msg.id),
            caption=caption_text
        )
        
    # Notify admins with approve/reject buttons + profile button
    try:
        submitter = await event.client.get_entity(event.sender_id)
        submitter_name = submitter.first_name or 'مستخدم'
        submitter_username = f'@{submitter.username}' if getattr(submitter, 'username', None) else ''
    except Exception:
        submitter_name = 'مستخدم'
        submitter_username = ''
    btns = [
        [Button.inline('✅ قبول', f'approve_sub {str(sub.id)}'), Button.inline('❌ رفض', f'reject_sub {str(sub.id)}')],
        [Button.url('👤 الملف الشخصي', f'tg://user?id={event.sender_id}')]
    ]
    
    admin_text = (
        '🆕 طلب ميديا جديد\n'
        f'الاسم: {name_msg.text}\n'
        f'الوصف: {caption_text or "لا يوجد"}\n'
        f'المُرسل: {submitter_name} {submitter_username} (ID: {event.sender_id})'
    )
    
    print(f"🔔 Notifying admins about media submission: {sub.id}")
    if fwd:
        try:
            print(f"📤 Sending media notification with file: {fwd.id} from {fwd.chat_id}")
            await notify_admins(app, admin_text, buttons=btns, file=fwd)
        except Exception as e:
            print(f"❌ Failed to notify with file: {e}")
            await notify_admins(app, admin_text, buttons=btns)
    else:
        print(f"⚠️ No forwarded media, sending text-only notification")
        await notify_admins(app, admin_text, buttons=btns)
    
    await event.edit('✅ تم إرسال طلبك للمراجعة من قبل الإدارة', buttons=Button.inline('عودة','start'))

@Callback(pattern=b'review_queue')
@is_admin
async def review_queue(event):
    q = PendingSubmission.select().where(PendingSubmission.approved == False)
    if not q.exists():
        return await event.edit('لا توجد طلبات قيد المراجعة حالياً', buttons=Button.inline('عودة','panel'))
    sub = q.order_by(PendingSubmission.created_at.asc()).get()
    if sub.type == 'text':
        text = f'طلب نص\nالاسم: {sub.name}\nالمحتوى:\n{sub.text}\n\nالمُرسل: {sub.submitter_id}'
        btns = [[Button.inline('✅ قبول', f'approve_sub {str(sub.id)}'), Button.inline('❌ رفض', f'reject_sub {str(sub.id)}')], [Button.inline('عودة','panel')]]
        return await event.edit(text, buttons=btns)
    else:
        text = f'طلب ميديا\nالاسم: {sub.name}\nالوصف: {sub.caption or "لا يوجد"}\nالمُرسل: {sub.submitter_id}'
        btns = [[Button.inline('✅ قبول', f'approve_sub {str(sub.id)}'), Button.inline('❌ رفض', f'reject_sub {str(sub.id)}')], [Button.inline('عودة','panel')]]
        try:
            msg = await app.get_messages(int(sub.temp_chat_id), ids=int(sub.temp_msg_id))
            return await event.edit(text, buttons=btns, file=msg)
        except Exception:
            return await event.edit(text, buttons=btns)

@Callback(pattern=b'(approve_sub|reject_sub) (.*)')
@is_admin
async def decide_submission(event):
    action = event.pattern_match.group(1).decode()
    sid = event.pattern_match.group(2).decode()
    try:
        sid_uuid = UUID(sid)
    except Exception:
        sid_uuid = sid
    subq = PendingSubmission.select().where(PendingSubmission.id == sid_uuid)
    if not subq.exists():
        return await event.answer('الطلب غير موجود', True)
    sub = subq.get()
    if action == 'approve_sub':
        if sub.type == 'text':
            Text.create(name=sub.name, text=sub.text)
            try:
                await app.send_message(sub.submitter_id, '✅ تم قبول نصك وإضافته بنجاح!')
            except Exception:
                pass
        else:
            try:
                # forward the temp media to files channel
                chat_ref = sub.temp_chat_id or files_channel
                try:
                    # If it's an integer id stored as string
                    chat_ref = int(chat_ref)
                except Exception:
                    pass
                msg = await app.get_messages(chat_ref, ids=int(sub.temp_msg_id))
                fwd = await msg.forward_to(files_channel)
                Media.create(name=sub.name, msg_id=fwd.id, channel=files_channel, caption=sub.caption)
                try:
                    await app.send_message(sub.submitter_id, '✅ تم قبول الميديا الخاصة بك وإضافتها!')
                except Exception:
                    pass
            except Exception as e:
                return await event.answer(f'خطأ اثناء نسخ الميديا: {e}', True)
        sub.approved = True
        sub.save()
        try:
            await event.edit('✅ تم قبول الطلب وإضافته', buttons=Button.inline('عودة','panel'))
        except Exception:
            pass
    else:
        try:
            await app.send_message(sub.submitter_id, '❌ تم رفض طلبك، يمكنك المحاولة مجدداً')
        except Exception:
            pass
        sub.delete_instance()
        try:
            await event.edit('❌ تم رفض الطلب وحذفه', buttons=Button.inline('عودة','panel'))
        except Exception:
            pass

@Callback(pattern = b'joining')
@is_ban
async def check_join(event):
    try:
        
        channel = join_channel
        check = (await event.client.get_permissions(channel, event.sender_id)).participant
        await event.delete()
        return await start(event)
    except errors.rpcerrorlist.UserNotParticipantError:
        return await event.answer('أنت لحد الان لم تقم بالاشتراك ‼️',True)
        buttons = [
            [Button.url('‹ اضغط هنا للأشتراك ›',f'https://t.me/{channel.replace("@","")}')],
            [Button.inline('❌','joining')]
        ]
        text = (
            f'⌔︙عليك الاشتراك في قناة البوت اولاً !'
            
        )
        
        return await event.edit(text,buttons = buttons)   


@Callback(pattern = b'support',func = lambda i:i.is_private)
@is_ban
@antiflood()
async def Supportt(event):
    try:
        async with app.conversation(event.sender_id) as conv:
            await event.delete()
            await conv.send_message('⌁ : حسننا عزيزي أرسل رسالتك الان: ',buttons = Button.inline('عوده :➧','start'))
            response = await conv.get_response()
        
        if response.raw_text in ('🔙','/start','عوده :➧'):   return
        fwd = await response.forward_to(sudo[0])
        Support.create(
            from_id = event.sender_id,
            to_id = sudo[0],
            reply_to = fwd.id,
            message_id = response.id
        )
        
        await event.client.send_message(sudo[0],f'from : {event.sender_id} | first_name: {event.sender.first_name}')
        await event.client.send_message(event.sender_id,'⌁ :حسننا تم ارسال رسالتك انتظر الرد بأسرع وقت ممكن ')
        return await start(event)
    except asyncio.exceptions.TimeoutError:
        await event.respond(':➧ عزيزي لقد انتها الوقت ',buttons = Button.clear())  
        return await panel_admin(event)     
    
@Message(func = lambda x:x.is_reply,admin=True)
async def answer(event):
    reply = await event.get_reply_message()
    chats = Support.get_or_none(Support.reply_to == reply.id)
    if not chats is None:
        from_id = chats.from_id 
        msg_id = chats.message_id 
        res = await event.client.send_message(from_id,event.text,reply_to=int(msg_id))
        Support.create(
            from_id = event.sender_id,
            to_id = from_id,
            reply_to = res.id,
            message_id = event.id
        )
        return await event.reply('⌁ :تم ارسال رسالتك')
    
@Message(pattern = '/panel',func = lambda i:i.is_private)
@Callback(pattern = b'panel')
@is_admin

async def panel_admin(event,text = None):
    try:
        conv = app.conversation(event.sender_id)
        await conv.cancel_all()
    except:
        
        pass
    db = Setting.select().where(Setting.key == 'JOIN_STATUS')
    if not db.exists():
        Setting.create(
            key = 'JOIN_STATUS',
            value = True
        )
    
    join_status =  json.loads(str(db.get().value).lower()) if db.exists() else True
    join = '❬ ✓ ❭' if join_status else '❬ ✗ ❭'
    buttons = [
        [Button.inline('الاحصائيات','stat')],
        [Button.inline('اصلاح الامار','fix_statistics'),Button.inline('احصائيات دقيقة','accurate_statistics')],
        [Button.inline('مراجعة الطلبات','review_queue')],
        [Button.inline('اذاعه','send_all'),Button.inline('اذاعه بالتوجيه','fwd_all')],
         [Button.inline('اذاعه للمجموعات','xsend_all_gp'),Button.inline('توجيه للمجموعه','xfwd_all_gp')],
        [Button.inline('معلومات العضو','userinfo')],
        [Button.inline('اضف ميديا','add_media'),Button.inline('مسح ميديا','delete_media')],
         [Button.inline('اضف نص للتعارف','add_text'),Button.inline('مسح نص التعارف','delete_text')],
        [Button.inline(join,'joiner'),Button.inline('الاشتراك الاجباري')],
        [Button.inline('التعارف ','texts 1'),Button.inline('الميديا','medias 1')],
        [Button.inline('عوده للرئيسيه','start')]
    ]
    if isinstance(event, events.CallbackQuery.Event):
        return await event.edit(text if not text is None else 'select',buttons = buttons)
    return await event.respond('⌁ : حسننا عزيزي المطور اختر الان',buttons = buttons)

@Callback(pattern = b'joiner')
@is_admin
async def Joiner(event):
    db = Setting.select().where(Setting.key == 'JOIN_STATUS')
    if not db.exists():
        Setting.create(
            key = 'JOIN_STATUS',
            value = True
        )
    
    status =  json.loads(str(db.get().value).lower()) if db.exists() else True
    
    if status:
        get = db.get()
        get.value = False 
        get.save()
        # await event.delete()
        await panel_admin(event,'✹ تم تعطيل الاشتراك الاجباري')
    else:
        get = db.get()
        get.value = True 
        get.save()
        # await event.delete()
        await panel_admin(event,'✹ تم تفعيل الاشتراك الاجباري')
    
@Callback(pattern = b'khaled')
async def Stat(event): 
    text = (f'#أهلا_عزيزي في الاوامر 🤍\n\n\n⌁ : قم باضافه البوت ورفع مشرف\n≈ ┉ ≈ ┉ باقي الاوامر👇 ┉ ≈ ┉ ≈ ┉\n\n⌁ : اوامر التاك لروئية اوامر تاك شفافه\n\n¹↫ تاك للتعارف لعمل تاك للاعضاء\n\n²↫ تاك صوتي لأرسال صوتيات وميديا .\n\n³↫ تاك للكل أو تام عام لعمل تاك لجميع الاعضاء .\n┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉\n⌁ : نقوم بتحديث التاكات بشكل شهري وعلا آخر اصدار للغه بايثون واضافه مميزات لا تتوفر في باقي البوتات 🍇 فقط في تيم ماکس .')
    return await event.edit(text,buttons = Button.inline('عوده :➧','start'))

@Callback(pattern = b'help')
async def Stat(event): 
    text = (f'#أهلا_عزيزي في الاوامر 🤍\n\n\n⌁ : قم باضافه البوت ورفع مشرف\n≈ ┉ ≈ ┉ باقي الاوامر👇 ┉ ≈ ┉ ≈ ┉\n\n⌁ : اوامر التاك لروئية اوامر تاك شفافه\n\n¹↫ تاك للتعارف لعمل تاك للاعضاء\n\n²↫ تاك صوتي لأرسال صوتيات وميديا .\n\n³↫ تاك للكل أو تام عام لعمل تاك لجميع الاعضاء .\n┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉\n⌁ : نقوم بتحديث التاكات بشكل شهري وعلا آخر اصدار للغه بايثون واضافه مميزات لا تتوفر في باقي البوتات 🍇 فقط في تيم ماکس .')
    return await event.edit(text,buttons = Button.inline('عوده :➧','kara'))

@Callback(pattern = b'stat')
@is_admin
async def Stat(event):
    # Get quick general statistics without cleanup
    try:
        await safe_edit(event, '🔍 جاري حساب الإحصائيات...')
        
        # Get basic counts from database
        total_users = User.select().count()
        total_groups = Group.select().count()
        total_texts = Text.select().count()
        total_media = Media.select().count()
        
        # Calculate weekly users (users joined in last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        weekly_users = User.select().where(User.joined_at >= week_ago).count()
        
        # Calculate daily media (media added in last 24 hours)
        day_ago = datetime.now() - timedelta(days=1)
        daily_media = Media.select().where(Media.created_at >= day_ago).count()
        
        # Calculate weekly media (media added in last 7 days)
        weekly_media = Media.select().where(Media.created_at >= week_ago).count()
    
        text = (
            f'📊 الإحصائيات العامة:\n\n'
            f'👥 عدد المشتركين: {total_users}\n'
            f'👥 عدد المشتركين الاسبوع: {weekly_users}\n'
            f'👥 عدد المشتركين: 0\n'
            f'📝 عدد نص التعارف: {total_texts}\n'
            f'🎬 عدد الميديا: {total_media}\n'
            f'🎬 عدد الميديا اليوم: {daily_media}\n'
            f'🎬 عدد الميديا السبوع: {weekly_media}\n'
            f'👥 عدد المجموعات: {total_groups}\n\n'
            f'⚡ هذه إحصائيات سريعة (بدون تنظيف)'
        )
        await safe_edit(event, text, buttons=Button.inline('عوده :➧','panel'))
    except Exception as e:
        await safe_edit(event, f'❌ حدث خطأ: {str(e)}', buttons=Button.inline('عوده :➧','panel'))

@Callback(pattern = b'userinfo')
@is_admin
async def user_info(event):
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message('⌁ : حسننا عزيزي قم بأرسال المعرف أو الايدي الان',buttons = Button.inline('عوده :➧','panel'))
        userid = await conv.get_response()
        
        user = User.select().where(User.userid == userid.raw_text)
        if not user.exists():
            return await event.respond('⌁ :المعرف غير موجود')
        user = user.get()
        is_ban = '✹ تم حظره ' if user.is_ban else '✹ تم الغاء حظره '
        text = (
            f'> الايدي: {user.userid}\n'
            f'> تأريخ الانضمام: {user.joined_at}\n'
            f'> حاله الحظر: {is_ban}\n'
            
        )
        buttons = [
            [Button.inline('حظر',f'ban {user.userid}'),Button.inline('الغاء حظر',f'unban {user.userid}')],
            [Button.inline('عوده :➧','panel')]
        ]
        return await event.respond(text,buttons = buttons)
    
    
@Callback(pattern = b'(ban|unban|) (\d+)')
@is_admin
async def ban_unban_ignore(event):
    type = event.pattern_match.group(1).decode()
    userid = int(event.pattern_match.group(2).decode())
    if type == 'ban':
        user = User.update({User.is_ban:True}).where((User.userid == userid) & (User.is_ban == False))
        result = user.execute()
        if result == 0:
            return await event.answer('✹ تم حظره سابقا')
        try:
            await event.client.send_message(int(userid),'⌁ :مرحبا" تم حظرك م̷ـــِْن البوت ')
        except:
            pass
        return await event.answer('✹ تم حظره بنجاح')
        
    if type == 'unban':
        user = User.update({User.is_ban:False}).where((User.userid == userid) & (User.is_ban == True))
        result = user.execute()
        if result == 0:
            return await event.answer('✹ تم الغاء حظره سابقا')
        return await event.answer('✹ تم الغاء حظره بنجاح')
    
@Callback(pattern = b'add_media')
@is_admin
async def add_media(event):
    await event.delete()
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message('⌁ :حسننا عزيزي قم بأرسال الميديا الان',buttons =Button.inline('عوده :➧','panel'))
        media = await conv.get_response()
        while not media.media:
            await conv.send_message('⌁ :مرحبا" عزيزي ارسل الميديا بصوره صحيحه',buttons =Button.inline('عوده :➧','panel'))
            media = await conv.get_response()
        await conv.send_message('⌁ : حسننا ارسل أسم للميديا الان',buttons =Button.inline('عوده :➧','panel'))
        name = await conv.get_response()
        while not name.text:
            await conv.send_message('⌁ : حسننا عزيزي قم بأرسال أسم للميديا بشكل صحيح',buttons =Button.inline('عوده :➧','panel'))
            name = await conv.get_response()
        while Media.select().where(Media.name == name.text).exists():
            await conv.send_message('⌁ : حسننا ارسل الاسم للميديا بشكل صحيح م̷ـــِْن فضلك ',buttons =Button.inline('عوده :➧','panel'))
            name = await conv.get_response()
            
        await conv.send_message('⌁ :حسننا عزيزي الان قم بأرسال وصف اذ لم تريد وصف ارسل امر nocaption',buttons =Button.inline('عوده :➧','panel'))
        caption = await conv.get_response()
        
        caption = caption.raw_text
        if caption == 'nocaption':
            caption = None
        fwd = await media.forward_to(files_channel)
        Media.create(
            name = name.raw_text,  
            msg_id = fwd.id,
            channel = files_channel,
            caption = caption 
        )
        return await event.respond('⌁ : تم الحفظ بنجاح',buttons =Button.inline('عوده :➧','panel'))
@Callback(pattern = b'add_text')
@is_admin
async def add_media(event):
    await event.delete()
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message('⌁ : حسننا عزيزي قم بأرسال نص للتعارف',buttons =Button.inline('عوده :➧','panel'))
        text = await conv.get_response()
        while not text.text:
            await conv.send_message('⌁ : حسننا عزيزي قم بأرسال نص للتعارف بشكل صحيح',buttons =Button.inline('عوده :➧','panel'))
            text = await conv.get_response()
        await conv.send_message('⌁ : حسننا ارسل اسم لنص التعارف الان',buttons =Button.inline('عوده :➧','panel'))
        name = await conv.get_response()
        while not name.text:
            await conv.send_message('⌁ : حسننا ارسل اسم لنص التعارف بشكل صحيح',buttons =Button.inline('عوده :➧','panel'))
            name = await conv.get_response()
        while Text.select().where(Text.name == name.text).exists():
            await conv.send_message('⌁ :مرحبا" عزيزي هذه الاسم موجود سابقا أرسل اسم جديد من فضلك',buttons =Button.inline('عوده :➧','panel'))
            name = await conv.get_response()
            
        # fwd = await media.forward_to(files_channel)
        Text.create(
            name = name.raw_text,  
            text = text.text 
        )
        return await event.respond('⌁ : تم الحفظ بنجاح',buttons =Button.inline('عوده :➧','panel'))
@Callback(pattern = b'delete_media')
@is_admin
async def delete_media(event):
    await event.delete()
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message('⌁ : حسننا رجاء قم بأدخال أسم الميديا الان',buttons =Button.inline('عوده :➧','panel'))
        name = await conv.get_response()
        
        db = Media.select().where(Media.name == name.raw_text)
        if not db.exists():
            await event.respond('⌁ :عزيزي الميديا غير موجوده')
            return await panel_admin(event)
        Media.delete().where(Media.name == name.raw_text).execute()
        return await event.respond('⌁ :عزيزي تم مسحها بنجاح',buttons =Button.inline('عوده :➧','panel'))
@Callback(pattern = b'delete_text')
@is_admin
async def delete_media(event):
    await event.delete()
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message('⌁ : حسننا رجاء قم بأدخال أسم نص التعارف الان',buttons =Button.inline('عوده :➧','panel'))
        name = await conv.get_response()
        
        db = Text.select().where(Text.name == name.raw_text)
        if not db.exists():
            await event.respond('⌁ :عزيزي لايوجد نص للتعارف')
            return await panel_admin(event)
        Text.delete().where(Text.name == name.raw_text).execute()
        return await event.respond('⌁ :عزيزي تم مسحها بنجاح',buttons =Button.inline('عوده :➧','panel'))   
    
@Callback(pattern = b'send_all',func = lambda i:i.is_private)
@is_admin
async def send_all(event):
    try:
        
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : حسننا عزيزي أرسل رسالتك الان',buttons = Button.inline('عوده :➧','panel'))
            response = await conv.get_response()
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : هل أنت واثق أنك تريد الأرسال',buttons = [[Button.inline('نعم 🤓','yeso')],[Button.inline('لا 🫠','panel')]])
            answer =  await conv.wait_event(events.CallbackQuery())
            data = answer.data.decode()
            if data == 'yeso':
                await answer.delete()
                
                try:
                    user = User.select()
                    sent = 0
                    for i in user:
                        try:
                            await event.client.send_message(int(i.userid),response)
                            sent += 1
                        except Exception:
                            # Clean invalid users from DB to avoid fake stats
                            try:
                                User.delete().where(User.userid == i.userid).execute()
                            except Exception:
                                pass
                except Exception:
                    pass 
                return await event.respond(f'⌁ : حسننا إلي {sent} مشترك تم إرسالها',buttons = Button.inline('عوده :➧','panel'))  
            
    except asyncio.exceptions.TimeoutError:
        await event.respond(':➧ عزيزي لقد انتها الوقت ',buttons = Button.clear())  
        return await panel_admin(event)     
@Callback(pattern = b'xsend_all_gp',func = lambda i:i.is_private)
@is_admin
async def send_all_gp(event):
    try:
        
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : حسننا عزيزي أرسل رسالتك الان',buttons = Button.inline('عوده :➧','panel'))
            response = await conv.get_response()
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : هل أنت واثق أنك تريد الأرسال',buttons = [[Button.inline('نعم 🤓','yesoo')],[Button.inline('لا 🫠','panel')]])
            answer =  await conv.wait_event(events.CallbackQuery())
            data = answer.data.decode()
            if data == 'yesoo':
                await answer.delete()
                
                try:
                    gp = Group.select()
                    sent = 0
                    for i in gp:
                        try:
                            await event.client.send_message(int(i.id),response)
                            sent += 1
                        except Exception:
                            # Remove invalid groups to keep stats real
                            try:
                                Group.delete().where(Group.id == i.id).execute()
                            except Exception:
                                pass
                except Exception:
                    pass 
                return await event.respond(f'⌁ : حسننا إلي  {sent} مجموعه تم إرسالها',buttons = Button.inline('عوده :➧','panel'))  
            
    except asyncio.exceptions.TimeoutError:
        await event.respond(':➧ عزيزي لقد انتها الوقت ',buttons = Button.clear())  
        return await panel_admin(event)     
        
@Callback(pattern = b'fwd_all',func = lambda i:i.is_private)
@is_admin
async def send_all(event):
    try:
        
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : حسننا عزيزي أرسل رسالتك الان',buttons = Button.inline('عوده :➧','panel'))
            response = await conv.get_response()
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : هل أنت واثق أنك تريد الأرسال',buttons = [[Button.inline('نعم 🤓','yeso')],[Button.inline('لا 🫠','panel')]])
            answer =  await conv.wait_event(events.CallbackQuery())
            data = answer.data.decode()
            if data == 'yeso':
                await answer.delete()
                
                try:
                    user = User.select()
                    sent = 0
                    for i in user:
                        try:
                            await response.forward_to(int(i.userid))
                            sent += 1
                            
                        except:
                            pass
                except:
                    pass 
                return await event.respond(f'⌁ : حسننا إلي  {sent} مشترك تم إرسالها')  
            elif data == 'noo':
                await answer.delete()
                return await panel_admin(event)
    except asyncio.exceptions.TimeoutError:
        await event.respond(':➧ عزيزي لقد انتها الوقت ',buttons = Button.clear())  
        return await panel_admin(event)     
    
@Callback(pattern = b'xfwd_all_gp',func = lambda i:i.is_private)
@is_admin

async def fwd_all_gp(event):
    try:
        
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : حسننا عزيزي أرسل رسالتك الان',buttons = Button.inline('عوده :➧','panel'))
            response = await conv.get_response()
        async with event.client.conversation(event.sender_id) as conv:
            await conv.send_message('⌁ : هل أنت واثق أنك تريد الأرسال',buttons = [[Button.inline('نعم 🤓','yesoo')],[Button.inline('لا 🫠','panel')]])
            answer =  await conv.wait_event(events.CallbackQuery())
            data = answer.data.decode()
            if data == 'yesoo':
                await answer.delete()
                
                try:
                    gp = Group.select()
                    sent = 0
                    for i in gp:
                        try:
                            await response.forward_to(int(i.id))
                            sent += 1
                            
                        except:
                            pass
                except:
                    pass 
                return await event.respond(f'⌁ : حسننا إلي  {sent}  بالتوجيه مجموعه تم إرسالها')  
            elif data == 'noo':
                await answer.delete()
                return await panel_admin(event)
    except asyncio.exceptions.TimeoutError:
        await event.respond(':➧ عزيزي لقد انتها الوقت ',buttons = Button.clear())  
        return await panel_admin(event)     
       
@Message(pattern = '^تفعيل$',func = lambda i:i.is_group)
@is_join()
@is_ban
async def install(event):
    db = Group.select().where(Group.id == str(event.chat.id))
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    if db.exists():
        return await event.reply(f'#أهلا_عزيزي تم تفعيل البوت سابقا 🤍\n\n\n≈ ┉ ≈ ┉ باقي الاوامر👇 ┉ ≈ ┉ ≈ ┉\n\n⌁ : **`اوامر التاك**` لروئية اوامر تاك شفافهه\n\n¹↫ `تاك للتعارف` لعمل تاك للاعضاء\n\n²↫` تاك صوتي` لأرسال صوتيات وميديا .\n\n³↫ `تاك للكل` أو تاك عام لعمل تاك لجميع الاعضاء .\n┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉ ≈ ┉\n⌁ : نقوم بتحديث التاكات بشكل شهري وعلا آخر اصدار للغه بايثون واضافه مميزات لا تتوفر في باقي البوتات 🍇 فقط في تيم ماکس .')

    Group.create(
        id = str(event.chat.id),
        owner = event.sender_id
    )
    return await event.reply(f'⋆︙بواسطه ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙تم تفعيل بوت التاك بنجاح\n✓')
@Message(pattern = '^تعطيل$',func = lambda i:i.is_group)

@is_join()
@is_ban
async def uninstall(event):
    db = Group.select().where(Group.id == str(event.chat.id))
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    if not db.exists():
        return await event.reply('⌁ :تم تعطيل المجموعه سابقا')
    # owner = (await event.client.get_permissions(event.chat_id, event.sender_id)).participant
    # if not isinstance(owner,types.ChannelParticipantCreator): 
    #     return await event.respond('⌁ : انت لست مالك المجموعه')
    Group.delete().where(Group.id == str(event.chat.id)).execute()
    return await event.reply('⌁ :تم تعطيل المجموعه')



@Message(pattern = '^(ايدي|ا|كت|الالعاب)$',func = lambda i:i.is_group)
@is_join()
async def x(event):
    pass

@Message(pattern = '^بوت$',func = lambda i:i.is_group)
@is_join()
async def x(event):
    words = ['ها يحيلي 🫂💗','لبيه يعمري 🤍🫂','ها يحلو اامرني 💗🦋','سم طال عمرك 🤍','ها نروح للسينما 😉🍷']
    import random
    x  = random.choice(words)
    await event.reply(str(f'{x}'))    

@Message(pattern = 'المطور',func = lambda i:i.is_group)
@Callback(pattern = b'kara')
@antiflood()
@is_join()
async def kara(event):
    try:
        conv = app.conversation(event.sender_id)
        await conv.cancel_all()
    except:
        pass
    User.get_or_create(userid = event.sender_id)
    username = (await event.client.get_entity('me')).username
    buttons = [
        [(Button.url('المطور',f'https://t.me/EIKOei'))],
        [Button.inline('شرح','help'),(Button.inline('❌','joining'))],
        ]
    if isinstance(event, events.CallbackQuery.Event):
        return await event.edit('#هلا_عمري 🤍🫂\n.',buttons = buttons)
    return await event.reply('#هلا_عمري 🤍🫂\n.',buttons = buttons)

@Message(pattern = '^اوامر التاك|الاوامر$',func = lambda i:i.is_group)
@is_join()
async def settings(event,text = None):
    # print(str(event))
    if isinstance(event, events.NewMessage.Event):
        if event.fwd_from:
            return await event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ممنوع الامر بالتوجيه ✖️\n✓')
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    gp = Group.select().where((Group.id == str(event.chat.id)))
    if not gp.exists():
        # Auto-heal: create group record if missing
        try:
            Group.get_or_create(id=str(event.chat.id), defaults={
                'owner': event.sender_id,
                'status': True,
                'tag_all': False,
                'media_tag': False,
                'text_tag': False,
            })
            gp = Group.select().where((Group.id == str(event.chat.id)))
        except Exception:
            return await event.reply('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
    
    gp = gp.get()
    tag_all = '❬ ✓ ❭' if gp.tag_all else '❬ ✗ ❭'
    media_tag =  '❬ ✓ ❭' if gp.media_tag else '❬ ✗ ❭'
    
    
    text_tag =  '❬ ✓ ❭' if gp.text_tag else '❬ ✗ ❭'
    buttons = [
        [Button.inline(str(tag_all),f'tag_all_status {event.chat.id} {event.sender_id}'),Button.inline('تاك للكل'),],
        [Button.inline(str(media_tag),f'media_tag_status {event.chat.id} {event.sender_id}'),Button.inline('تاك بالميديا'),],
        [Button.inline(str(text_tag),f'text_tag_status {event.chat.id} {event.sender_id}'),Button.inline('تاك للتعارف'),],
        [Button.inline('❌','joining')]
    ]
    if isinstance(event, events.CallbackQuery.Event):
        return await event.edit(text if not None else 'tttt',buttons = buttons)
    return await event.reply('⌁ : اهلا بك في اوامر التاك',buttons = buttons)

# import threading

            
        
            # await asyncio.sleep(3)           
    
@Callback(pattern = b'tag_all_status (\d+) (\d+)')
async def tag_all_in_group(event,text=None):
    try:
        
        gpid = int(event.pattern_match.group(1).decode())
        userid = event.pattern_match.group(2).decode()
        
        if not event.sender_id == int(userid):
            return await event.answer('⋆︙عزيزي القائمه ليس لك ✖️\n✓',True)
        gp = Group.select().where(Group.id == str(gpid))
        
        if not gp.exists():
            # Auto-heal: create missing group record
            try:
                Group.get_or_create(id=str(gpid), defaults={
                    'owner': event.sender_id,
                    'status': True,
                    'tag_all': False,
                    'media_tag': False,
                    'text_tag': False,
                })
                gp = Group.select().where(Group.id == str(gpid))
            except Exception:
                return await event.respond('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
        check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
        if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
            return await  event.answer(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
        Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
        Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
        
        
        if Group.select().where((Group.id == str(gpid)) & (Group.tag_all == True)).exists():
            Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()
            await settings(event,'⌁ : تم تعطيل أمر التاك للكل')
        else:
            
            Group.update({Group.tag_all:True}).where((Group.id == str(gpid)) & (Group.tag_all == False)).execute()
            await settings(event,'⌁ : تم تفعيل أمر التاك للكل')
        
    
        print(1)
        users = event.client.iter_participants(entity=gpid)
        
        n = 0
        txt = ''
        if Group.select().where((Group.id == str(gpid)) & (Group.tag_all == True)).exists():
            sent = await event.reply('⋆︙مرحباً عزيزي⚡️\n⋆︙تم ألامر بنجاح\n✓')
        async for i in users:
            if Group.select().where((Group.id == str(gpid)) & (Group.tag_all == True)).exists():
                if not i.deleted and not i.bot:
                    n +=1
                    txt += f'ٴ{n}- [{i.first_name}](tg://user?id={i.id})\n' 
                    if n ==10:
                        await event.respond(txt)
                        tasks.append(asyncio.ensure_future(task(i)))
                        await asyncio.sleep(delay1)
                        await asyncio.gather(*tasks, return_exceptions=True)
                        n = 0
                        txt = ""
        if Group.select().where((Group.id == str(gpid)) & (Group.tag_all == True)).exists():
            Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()
            await sent.delete()
            return await event.reply('⋆︙تم انتهاء عملية التاك للكل بنجاح\n✓')
    except errors.FloodWaitError as e:
        asyncio.sleep(e.x)

@Callback(pattern = b'text_tag_status (\d+) (\d+)')

async def tag_all_in_group(event):
    gpid = int(event.pattern_match.group(1).decode())
    userid = event.pattern_match.group(2).decode()
    if not event.sender_id == int(userid):
        return await event.answer('⋆︙عزيزي القائمه ليس لك ✖️\n✓',True)
    gp = Group.select().where(Group.id == str(gpid))
    if not gp.exists():
        # Auto-heal: create missing group record
        try:
            Group.get_or_create(id=str(gpid), defaults={
                'owner': event.sender_id,
                'status': True,
                'tag_all': False,
                'media_tag': False,
                'text_tag': False,
            })
            gp = Group.select().where(Group.id == str(gpid))
        except Exception:
            return await event.respond('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.answer(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    owner = (await event.client.get_permissions(event.chat_id, event.sender_id)).participant
    # if not isinstance(owner,types.ChannelParticipantCreator) or not event.sender_id in sudo: 
    #     return await event.respond('⌁ : انت لست مالك المجموعه')
    Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
    Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()  
    get = gp.get()
    status = get.text_tag
    if Group.select().where((Group.id == str(gpid)) & (Group.text_tag == True)).exists():
        Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
        await settings(event,'⌁ : تم تعطيل أمر التاك للتعارف')
    else:
        Group.update({Group.text_tag:True}).where((Group.id == str(gpid)) & (Group.text_tag == False)).execute()
        await settings(event,'⌁ : تم تفعيل أمر التاك للتعارف')
        
    # Group.update({Group.text_tag:True}).where(Group.id == event.chat.id & Group.text_tag is False).execute()
    
    get = gp.get()
    status = get.text_tag
    print(status)
    
    
    
    users = event.client.iter_participants(entity=gpid)
    texts = Text.select()
    
    texts = [i.text for i in texts]
    if Group.select().where((Group.id == str(gpid)) & (Group.text_tag == True)).exists():
        sent = await event.reply('⋆︙مرحباً عزيزي⚡️\n⋆︙تم ألامر بنجاح\n✓')
    async for i in users:
        if gp.select().where((Group.id == str(gpid)) & (Group.text_tag == True)).exists():
            if not i.deleted and not i.bot:
                first_name = i.first_name 
                user_id = i.id
                await event.respond(
                    f'{random.choice(texts)}  [{i.first_name}](tg://user?id={i.id})'
                )
                await asyncio.sleep(delay)
    if Group.select().where((Group.id == str(gpid)) & (Group.text_tag == True)).exists():
            Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
            await sent.delete()
            return await event.reply('⋆︙تم انتهاء عملية التاك للتعارف بنجاح\n✓')




@Callback(pattern = b'media_tag_status (\d+) (\d+)')
async def media_tag(event):
    gpid = int(event.pattern_match.group(1).decode())
    userid = event.pattern_match.group(2).decode()
    if not event.sender_id == int(userid):
        return await event.answer('⋆︙عزيزي القائمه ليس لك ✖️\n✓',True)
    gp = Group.select().where(Group.id == str(gpid))
    if not gp.exists():
        # Auto-heal: create missing group record
        try:
            Group.get_or_create(id=str(gpid), defaults={
                'owner': event.sender_id,
                'status': True,
                'tag_all': False,
                'media_tag': False,
                'text_tag': False,
            })
            gp = Group.select().where(Group.id == str(gpid))
        except Exception:
            return await event.respond('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.answer(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
    Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()  
    if Group.select().where((Group.id == str(gpid)) & (Group.media_tag == True)).exists():
        Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
        # await event.edit('⌁ : تم تعطيل الامر بنجاح')
        await settings(event,'⌁ : تم تعطيل أمر التاك بالميديا')
    else:
        Group.update({Group.media_tag:True}).where((Group.id == str(gpid)) & (Group.media_tag == False)).execute()
        # await event.edit('⌁ : تم تفعيل الامر بنجاح')
        await settings(event,'⌁ : تم تفعيل أمر التاك بالميديا')
    users = event.client.iter_participants(entity=gpid)
    texts = Media.select()
    medias = [i.msg_id for i in texts]
    if Group.select().where((Group.id == str(gpid)) & (Group.media_tag == True)).exists():
        sent = await event.reply('⋆︙مرحباً عزيزي⚡️\n⋆︙تم ألامر بنجاح\n✓')
    async for i in users:
        if Group.select().where((Group.id == str(gpid)) & (Group.media_tag == True)).exists():
            if not i.deleted and not i.bot:
                first_name = i.first_name 
                user_id = i.id

                m = Media.select().order_by(fn.Random()).limit(1)
                m = m.get()
                caption = m.caption if m.caption else ''
                media  = await event.client.get_messages(m.channel,ids = m.msg_id)
                if media:
                    
                    
                    await event.respond(f'{caption}  [{i.first_name}](tg://user?id={i.id})',file = media )
                    await asyncio.sleep(delay)
    if Group.select().where((Group.id == str(gpid)) & (Group.media_tag == True)).exists():
            Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
            await sent.delete()
            return await event.reply('⋆︙تم انتهاء عملية التاك بنجاح\n✓')





@Callback(pattern = b'texts (\d+)')
@is_admin
async def paginated_texts(event, page_num=None):
    try:
        if page_num is None:
            page = int(event.pattern_match.group(1).decode())
        else:
            page = page_num
        all_texts = list(Text.select())
        items_per_page = 5
        total_pages = (len(all_texts) + items_per_page - 1) // items_per_page
        
        if page < 1 or page > total_pages:
            page = 1
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = all_texts[start_idx:end_idx]
        
        text = '⌁ : حسننا عزيزي اختر الان'
        paginator = TelethonPaginator(total_pages, data_pattern='texts {page}')
        paginator.current_page = page
        
        for i in page_items:
            paginator.add_before(Button.inline(str(i.name), f'tex {i.id}'))
            
        paginator.add_after(Button.inline('عوده', b'panel'))
        return await event.edit(text, buttons=paginator.create())
    except (ValueError, AttributeError):
        return await event.answer('خطأ في رقم الصفحة', True)

@Callback(pattern = b'medias (\d+)')
@is_admin
async def paginated_medias(event):
    try:
        page = int(event.pattern_match.group(1).decode())
        all_medias = list(Media.select())
        items_per_page = 5
        total_pages = (len(all_medias) + items_per_page - 1) // items_per_page
        
        if page < 1 or page > total_pages:
            page = 1
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = all_medias[start_idx:end_idx]
        
        text = '⌁ : حسننا عزيزي اختر الان'
        paginator = TelethonPaginator(total_pages, data_pattern='medias {page}')
        paginator.current_page = page
        
        for i in page_items:
            paginator.add_before(Button.inline(str(i.name), f'med {i.id}'))
            
        paginator.add_after(Button.inline('عوده', b'panel'))
        return await event.edit(text, buttons=paginator.create())
    except (ValueError, AttributeError):
        return await event.answer('خطأ في رقم الصفحة', True)

@Callback(pattern = b'med (.*)')
@is_admin
async def get_media(event):
    id = event.pattern_match.group(1).decode()
    db = Media.select().where(Media.id == id)
    if not db.exists():
        return await event.answer('⌁ : الميديا غير موجوده',True)
    get = db.get()
    msg_id = get.msg_id
    
    
    channel = get.channel
    print(get.created_at)
    media  = await event.client.get_messages(channel,ids = msg_id)
    if media is None:
        Media.delete().where(Media.id == id).execute()
        return await event.answer('این ⌁ : الميديا غير موجوده أو ممسوحه',True)
    buttons = [
        [ Button.inline('❌','del')]
    ]
    if event.sender_id in sudo:
        buttons.append([Button.inline('مسح من ديتابيس',f'deletadmin {id}')])
        buttons.append([Button.inline('معلومات الميديا',f'mediainfo {id}')])
    return await event.reply(get.caption,file=media,buttons =buttons)
@Callback(pattern = b'mediainfo (.*)')
@is_admin
async def meia_info(event):
    id = event.pattern_match.group(1).decode()
    db = Media.select().where(Media.id == id)
    if not db.exists():
        await event.respond('⌁ : الميديا غير موجوده')
        return await panel_admin(event)
    db = db.get()
    text = (
        f'>الايدي: {db.id}\n'
        f'>الاسم: {db.name}\n'
        f'>الوصف: {db.caption}\n'
        f'> وضعت في تاريخ: {db.created_at}\n'
    )
    buttons = [
        [Button.inline('مسح الميديا',f'deletadmin {id}')],
        [ Button.inline('❌','del')]
    ]
    return await event.edit(text,buttons = buttons)

@Callback(pattern = b'deletadmin (.*)')
@is_admin
async def delete_from_database(event):
    id = event.pattern_match.group(1).decode()
    db = Media.select().where(Media.id == id)
    if not db.exists():
        await event.respond('⌁ : الميديا غير موجوده')
        return await panel_admin(event)
    Media.delete().where(Media.id == id).execute()
    await event.answer('⌁ : تم المسح بنجاح',True)
    return await paginated_medias(event)
@Callback(pattern = b'tex (.*)')
async def get_media(event):
    id = event.pattern_match.group(1).decode()
    db = Text.select().where(Text.id == id)
    if not db.exists():
        return await event.answer('⌁ : نص التعارف غير موجود',True)
    get = db.get()
    
    print(get.created_at)
    buttons = [
        [ Button.inline('❌','del')]
    ]
    if event.sender_id in sudo:
        buttons.append([Button.inline('مسح من ديتابيس',f'deltext {id}')])
        
    return await event.reply(get.text,buttons =buttons)
    
@Callback(pattern = b'del')
@is_ban
@antiflood()
async def delete_from_chat(event):
    return await event.delete()



@Callback(pattern = b'deltext (.*)')
@is_admin
async def delete_from_database(event):
    id = event.pattern_match.group(1).decode()
    db = Text.select().where(Text.id == id)
    if not db.exists():
        await event.respond('⌁ : نص التعارف غير موجود')
        return await panel_admin(event)
    Text.delete().where(Text.id == id).execute()
    await event.answer('⌁ : تم المسح بنجاح',True)
    return await paginated_texts(event, 1)









@Message(pattern = '^تاك للكل|تاك عام$')
@is_join()
@is_ban
async def tag_all_in_group_msg(event):
    try:
        if event.fwd_from:
            return await event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ممنوع الامر بالتوجيه ✖️\n✓')
        gpid = event.chat.id
        userid = event.sender_id
        
        check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
        if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
            return await  event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
        gp = Group.select().where(Group.id == str(gpid))
        
        if not gp.exists():
            # Auto-heal: create missing group record
            try:
                Group.get_or_create(id=str(gpid), defaults={
                    'owner': event.sender_id,
                    'status': True,
                    'tag_all': False,
                    'media_tag': False,
                    'text_tag': False,
                })
                gp = Group.select().where(Group.id == str(gpid))
            except Exception:
                return await event.respond('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
        
        Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
        Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
        
        
        if Group.select().where((Group.id == str(gpid)) & (Group.tag_all == False)).exists():
            Group.update({Group.tag_all:True}).where((Group.id == str(gpid)) & (Group.tag_all == False)).execute()
            users = event.client.iter_participants(entity=gpid)
        
            n = 0
            txt = ''
            sent = await event.reply(f'⋆︙بواسطة ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙جاري عمل التاك للكل بنجاح\n✓')
            async for i in users:
               
                if Group.select().where((Group.id == str(gpid)) & (Group.tag_all == True)).exists():
                    if not i.deleted and not i.bot:
                        n +=1
                        txt += f'ٴ{n}- [{i.first_name}](tg://user?id={i.id})\n' 
                        if n ==10:
                            # await asyncio.sleep(delay)
                            await event.respond(txt)
                            await asyncio.sleep(delay1)
                            n = 0
                            txt = ""
                            
            if Group.select().where((Group.id == str(gpid)) & (Group.tag_all == True)).exists():
                Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()
                await sent.delete()
                return await event.reply('⋆︙تم انتهاء عملية التاك للكل بنجاح\n✓')
        else:
            
            await event.reply('⋆︙يوجد عمليه تاك للكل حالياً⚡️\n⋆︙أرسل ايقاف ثم أستخدم امر اخر.\n✓')
            # await settings(event,'⌁ : تم تفعيل أمر التاك للكل')
        
    
        print(1)
        
    except errors.FloodWaitError as e:
        asyncio.sleep(e.x)

@Message(pattern = '^تاك التعارف|تاك للتعارف$')
@is_join()
@is_ban
async def tag_text_in_group(event):
    gpid = event.chat.id
    userid = event.sender_id
    if event.fwd_from:
        return await event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ممنوع الامر بالتوجيه ✖️\n✓')
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    gp = Group.select().where(Group.id == str(gpid))
    if not gp.exists():
        # Auto-heal: create missing group record automatically
        try:
            Group.get_or_create(id=str(gpid), defaults={
                'owner': event.sender_id,
                'status': True,
                'tag_all': False,
                'media_tag': False,
                'text_tag': False,
            })
            gp = Group.select().where(Group.id == str(gpid))
        except Exception:
            return await event.respond('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.answer(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    owner = (await event.client.get_permissions(event.chat_id, event.sender_id)).participant
    # if not isinstance(owner,types.ChannelParticipantCreator) or not event.sender_id in sudo: 
    #     return await event.respond('⌁ : انت لست مالك المجموعه')
    Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
    Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()  
    # Self-heal: clear stale running flag if any
    if Group.select().where((Group.id == str(gpid)) & (Group.text_tag == True)).exists():
        Group.update({Group.text_tag: False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
    
    get = gp.get()
    status = get.text_tag
    if Group.select().where((Group.id == str(gpid)) & (Group.text_tag == False)).exists():
        Group.update({Group.text_tag: True}).where(Group.id == str(gpid)).execute()  
        users = event.client.iter_participants(entity=gpid)
        texts = Text.select()
        
        # Check if there are any texts in database
        if not texts.exists():
            Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
            return await event.reply('❌ لا توجد نصوص تعارف في قاعدة البيانات!\n\n📝 استخدم أمر "اضف نص" لإضافة نصوص تعارف أولاً')
        
        texts = [i.text for i in texts]
        sent = await event.reply(f'⋆︙بواسطة ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙جاري العمل التاك للتعارف بنجاح\n✓')
        tasks = []  # Initialize tasks list
        async for i in users:
            if Group.select().where((Group.id == str(gpid)) & (Group.text_tag == True)).exists():
                if not i.deleted and not i.bot:
                    first_name = i.first_name 
                    user_id = i.id
                    
                    await event.respond(
                        f'{random.choice(texts)}  [{i.first_name}](tg://user?id={i.id})'
                    )
                    await asyncio.sleep(delay)
        if Group.select().where((Group.id == str(gpid)) & (Group.text_tag == True)).exists():
            Group.update({Group.text_tag: False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
            await sent.delete()
    else:
        await event.reply('⋆︙تم إصلاح حالة قديمة والآن يمكنك المحاولة مجدداً\n✓')
        
    # Group.update({Group.text_tag:True}).where(Group.id == event.chat.id & Group.text_tag is False).execute()
    
@Message(pattern = '^تاك صوتي للتعارف|تاك للتعارف صوتي| تاك ميديا|تاك صوتي$')
@is_join()
@is_ban
async def media_tag(event):
    gpid = event.chat.id
    userid = event.sender_id
    if event.fwd_from:
        return await event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ممنوع الامر بالتوجيه ✖️\n✓')
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    gp = Group.select().where(Group.id == str(gpid))
    if not gp.exists():
        return await event.respond('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
    
    Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
    Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()  
    if Group.select().where((Group.id == str(gpid)) & (Group.media_tag == False)).exists():
        Group.update({Group.media_tag:True}).where((Group.id == str(gpid)) & (Group.media_tag == False)).execute()
        users = event.client.iter_participants(entity=gpid)
        texts = Media.select()
        
        # Check if there are any media in database
        if not texts.exists():
            Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
            return await event.reply('❌ لا توجد ميديا في قاعدة البيانات!\n\n📸 استخدم أمر "اضف ميديا" لإضافة ميديا أولاً')
        
        medias = [i.msg_id for i in texts]
        sent = await event.reply(f'⋆︙بواسطة ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙جاري عمل التاك بالميديا بنجاح\n✓')
        async for i in users:
            if Group.select().where((Group.id == str(gpid)) & (Group.media_tag == True)).exists():
                if not i.deleted and not i.bot:
                    first_name = i.first_name 
                    user_id = i.id

                    m = Media.select().order_by(fn.Random()).limit(1)
                    m = m.get()
                    caption = m.caption if m.caption else ''
                    media  = await event.client.get_messages(m.channel,ids = m.msg_id)
                    if media:
                        
                        await event.respond(f'{caption}  [{i.first_name}](tg://user?id={i.id})',file = media )
                        await asyncio.sleep(delay)
        if Group.select().where((Group.id == str(gpid)) & (Group.media_tag == True)).exists():
                Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
                await sent.delete()
                return await event.reply('⋆︙تم انتهاء عملية التاك بنجاح\n✓')   
    else:
        await event.reply('⋆︙يوجد عمليه تاك بالميديا حالياً⚡️\n⋆︙أرسل ايقاف ثم أستخدم امر اخر.\n✓')
    
    
    
    
@Message(pattern = '^توقف|ايقاف|ايقاف التاك$')
@is_join()
@is_ban
async def stop(event):
    gpid =event.chat.id
    userid = event.sender_id
    if event.fwd_from:
        return await event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ممنوع الامر بالتوجيه ✖️\n✓')
    
    gp = Group.select().where(Group.id == str(gpid))
    check = (await event.client.get_permissions(event.chat.id, event.sender_id)).participant
    if not isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
        return await  event.reply(f'⋆︙عذراً ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙عزيزي ليس لديك رتبه ✖️\n✓')
    if not gp.exists():
        return await event.reply('⋆︙عذراً البوت ليس مفعل في المجموعه⚡️\n⋆︙عليك أرسال امر ❲ تفعيل ❳\n✓')
    
    media = Group.update({Group.media_tag:False}).where((Group.id == str(gpid)) & (Group.media_tag == True)).execute()
    text = Group.update({Group.text_tag:False}).where((Group.id == str(gpid)) & (Group.text_tag == True)).execute()
    tall = Group.update({Group.tag_all:False}).where((Group.id == str(gpid)) & (Group.tag_all == True)).execute()
    out = [media,text,tall]
    print(out)
    if 1 in out:
        
        return  await event.reply(f'⋆︙بواسطة ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙تم ايقاف التاك بنجاح\n✓')
    
    else:    
        return await event.reply(f'⋆︙بواسطة ☻ [{event.sender.first_name}](tg://user?id={event.sender.id})\n⋆︙لايوجد عمليه تاك حالياً\n✓')

@Message(pattern = '^اضف ميديا$')
@is_join()
@is_ban
async def user_add_media(event):
    """Users submit media for approval; admins approve from queue."""
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message('📸 ارسل الميديا الآن:', buttons=Button.inline('عودة', 'start'))
        media = await conv.get_response()
        if not media.media:
            return await conv.send_message('❌ يجب إرسال ميديا (صورة/فيديو/صوت).')
        await conv.send_message('📝 ارسل اسماً للميديا:', buttons=Button.inline('عودة', 'start'))
        name = await conv.get_response()
        if not name.text:
            return await conv.send_message('❌ يجب إرسال اسم صحيح.')
        await conv.send_message('📄 أرسل وصفاً للميديا (اكتب "بدون وصف" للتخطي):', buttons=Button.inline('عودة', 'start'))
        caption = await conv.get_response()
        caption_text = caption.text if caption.text != 'بدون وصف' else None
        sub = PendingSubmission.create(
            submitter_id=event.sender_id,
            type='media',
                name=name.text,
            temp_chat_id=str(media.chat_id),
            temp_msg_id=int(media.id),
            caption=caption_text
        )
        btns = [[Button.inline('✅ قبول', f'approve_sub {str(sub.id)}'), Button.inline('❌ رفض', f'reject_sub {str(sub.id)}')]]
        try:
            await event.client.send_message(sudo[0], f'🆕 طلب ميديا جديد\nالاسم: {name.text}\nالوصف: {caption_text or "لا يوجد"}\nالمُرسل: {event.sender_id}', buttons=btns, file=media)
        except Exception:
            await event.client.send_message(sudo[0], f'🆕 طلب ميديا جديد\nالاسم: {name.text}\nالوصف: {caption_text or "لا يوجد"}\nالمُرسل: {event.sender_id}', buttons=btns)
        return await conv.send_message('✅ تم إرسال طلبك للمراجعة من قبل الإدارة.')

@Message(pattern = '^اضف نص$')
@is_join()
@is_ban
async def user_add_text(event):
    """Users submit text for approval; admins approve from queue."""
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message('📝 أرسل نص التعارف:', buttons=Button.inline('عودة', 'start'))
        text = await conv.get_response()
        if not text.text:
            return await conv.send_message('❌ يجب إرسال نص صحيح', buttons=Button.inline('عودة', 'start'))
        await conv.send_message('🏷️ أرسل اسم للنص:', buttons=Button.inline('عودة', 'start'))
        name = await conv.get_response()
        if not name.text:
            return await conv.send_message('❌ يجب إرسال اسم صحيح', buttons=Button.inline('عودة', 'start'))
        sub = PendingSubmission.create(
            submitter_id=event.sender_id,
            type='text',
            name=name.text,
            text=text.text
        )
        btns = [[Button.inline('✅ قبول', f'approve_sub {str(sub.id)}'), Button.inline('❌ رفض', f'reject_sub {str(sub.id)}')]]
        await event.client.send_message(sudo[0], f'🆕 طلب نص جديد\nالاسم: {name.text}\nالمحتوى:\n{text.text}\n\nالمُرسل: {event.sender_id}', buttons=btns)
        return await conv.send_message('✅ تم إرسال طلبك للمراجعة من قبل الإدارة.')

@Message(pattern = '^اصلاح الامار$')
@is_admin
async def fix_statistics(event):
    """Fix statistics by cleaning up invalid groups and users"""
    try:
        msg = await event.reply('🔍 جاري إصلاح الإحصائيات، يرجى الانتظار...')
        
        # Get statistics before cleanup
        stats_before = await get_real_statistics(event.client)
        
        # Perform cleanup
        removed_groups, removed_users = await cleanup_invalid_entities(event.client)
        
        # Get statistics after cleanup
        stats_after = await get_real_statistics(event.client)
        
        text = (
            f'✅ تم إصلاح الإحصائيات:\n\n'
            f'🗑️ تم حذف {removed_groups} مجموعة غير صالحة\n'
            f'👤 تم حذف {removed_users} مستخدم غير صالح\n\n'
            f'📊 قبل الإصلاح:\n'
            f'   • مجموعات صالحة: {stats_before["valid_member"]}\n'
            f'   • مجموعات غير صالحة: {stats_before["invalid"]}\n'
            f'   • مستخدمين فعليين: {stats_before["users"]}\n'
            f'   • إجمالي المستخدمين: {stats_before["total_users_in_db"]}\n\n'
            f'📊 بعد الإصلاح:\n'
            f'   • مجموعات صالحة: {stats_after["valid_member"]}\n'
            f'   • مجموعات غير صالحة: {stats_after["invalid"]}\n'
            f'   • مستخدمين فعليين: {stats_after["users"]}\n'
            f'   • إجمالي المستخدمين: {stats_after["total_users_in_db"]}\n\n'
            f'📝 النصوص: {stats_after["texts"]}\n'
            f'🎬 الميديا: {stats_after["media"]}'
        )
        
        await event.client.edit_message(msg, text, buttons=Button.inline('عودة','panel'))
    except Exception as e:
        await event.reply(f"❌ حدث خطأ: {str(e)}")

@Message(pattern = '^احصائيات دقيقة$')
@is_admin
async def accurate_statistics(event):
    try:
        msg = await event.reply('🔍 جاري حساب الإحصائيات الدقيقة مع تنظيف تلقائي...')
        
        # Get statistics before cleanup
        stats_before = await get_real_statistics(event.client)
        
        # Perform automatic cleanup
        removed_groups, removed_users = await cleanup_invalid_entities(event.client)
        
        # Get statistics after cleanup
        stats_after = await get_real_statistics(event.client)
        
        text = (
            f'📊 الإحصائيات الدقيقة (مع تنظيف تلقائي):\n\n'
            f'🧹 تم تنظيف:\n'
            f'   • مجموعات محذوفة: {removed_groups}\n'
            f'   • مستخدمين محذوفين: {removed_users}\n\n'
            f'👥 المجموعات:\n'
            f'   • إجمالي المجموعات: {stats_after["total_groups"]}\n'
            f'   • البوت عضو في: {stats_after["valid_member"]}\n'
            f'   • البوت أدمين في: {stats_after["valid_admin"]}\n'
            f'   • البوت عضو فقط: {stats_after["non_admin"]}\n'
            f'   • مجموعات غير صالحة: {stats_after["invalid"]}\n\n'
            f'👤 المستخدمين:\n'
            f'   • المستخدمين الفعليين: {stats_after["users"]}\n'
            f'   • إجمالي المستخدمين في DB: {stats_after["total_users_in_db"]}\n'
            f'   • المستخدمين المحذوفين: {stats_after["total_users_in_db"] - stats_after["users"]}\n\n'
            f'📝 النصوص: {stats_after["texts"]}\n'
            f'🎬 الميديا: {stats_after["media"]}\n\n'
            f'✅ تم تنظيف قاعدة البيانات تلقائياً'
        )
        
        await event.client.edit_message(msg, text, buttons=Button.inline('عودة','panel'))
    except Exception as e:
        await event.reply(f"❌ حدث خطأ: {str(e)}")

@Callback(pattern = b'fix_statistics')
@is_admin
async def fix_statistics_callback(event):
    """Fix statistics by cleaning up invalid groups and users"""
    try:
        await safe_edit(event, '🔍 جاري إصلاح الإحصائيات، يرجى الانتظار...')
        
        # Get statistics before cleanup
        stats_before = await get_real_statistics(event.client)
        
        # Perform cleanup
        removed_groups, removed_users = await cleanup_invalid_entities(event.client)
        
        # Get statistics after cleanup
        stats_after = await get_real_statistics(event.client)
        
        text = (
            f'✅ تم إصلاح الإحصائيات:\n\n'
            f'🗑️ تم حذف {removed_groups} مجموعة غير صالحة\n'
            f'👤 تم حذف {removed_users} مستخدم غير صالح\n\n'
            f'📊 قبل الإصلاح:\n'
            f'   • مجموعات صالحة: {stats_before["valid_member"]}\n'
            f'   • مجموعات غير صالحة: {stats_before["invalid"]}\n'
            f'   • مستخدمين فعليين: {stats_before["users"]}\n'
            f'   • إجمالي المستخدمين: {stats_before["total_users_in_db"]}\n\n'
            f'📊 بعد الإصلاح:\n'
            f'   • مجموعات صالحة: {stats_after["valid_member"]}\n'
            f'   • مجموعات غير صالحة: {stats_after["invalid"]}\n'
            f'   • مستخدمين فعليين: {stats_after["users"]}\n'
            f'   • إجمالي المستخدمين: {stats_after["total_users_in_db"]}\n\n'
            f'📝 النصوص: {stats_after["texts"]}\n'
            f'🎬 الميديا: {stats_after["media"]}'
        )
        
        await safe_edit(event, text, buttons=Button.inline('عودة', 'panel'))
        
    except Exception as e:
        await safe_edit(event, f"❌ حدث خطأ: {str(e)}", buttons=Button.inline('عودة', 'panel'))

@Callback(pattern = b'accurate_statistics')
@is_admin
async def accurate_statistics_callback(event):
    """Show accurate statistics by checking each group individually with automatic cleanup"""
    try:
        await safe_edit(event, '🔍 جاري حساب الإحصائيات الدقيقة مع تنظيف تلقائي...')
        
        # Get statistics before cleanup
        stats_before = await get_real_statistics(event.client)
        
        # Perform automatic cleanup
        removed_groups, removed_users = await cleanup_invalid_entities(event.client)
        
        # Get statistics after cleanup
        stats_after = await get_real_statistics(event.client)
        
        text = (
            f'📊 الإحصائيات الدقيقة (مع تنظيف تلقائي):\n\n'
            f'🧹 تم تنظيف:\n'
            f'   • مجموعات محذوفة: {removed_groups}\n'
            f'   • مستخدمين محذوفين: {removed_users}\n\n'
            f'👥 المجموعات:\n'
            f'   • إجمالي المجموعات: {stats_after["total_groups"]}\n'
            f'   • البوت عضو في: {stats_after["valid_member"]}\n'
            f'   • البوت أدمين في: {stats_after["valid_admin"]}\n'
            f'   • البوت عضو فقط: {stats_after["non_admin"]}\n'
            f'   • مجموعات غير صالحة: {stats_after["invalid"]}\n\n'
            f'👤 المستخدمين:\n'
            f'   • المستخدمين الفعليين: {stats_after["users"]}\n'
            f'   • إجمالي المستخدمين في DB: {stats_after["total_users_in_db"]}\n'
            f'   • المستخدمين المحذوفين: {stats_after["total_users_in_db"] - stats_after["users"]}\n\n'
            f'📝 النصوص: {stats_after["texts"]}\n'
            f'🎬 الميديا: {stats_after["media"]}\n\n'
            f'✅ تم تنظيف قاعدة البيانات تلقائياً'
        )
        
        await safe_edit(event, text, buttons=Button.inline('عودة', 'panel'))
        
    except Exception as e:
        await safe_edit(event, f"❌ حدث خطأ: {str(e)}", buttons=Button.inline('عودة', 'panel'))

# ===== Automatic Installation/Removal System =====
@app.on(events.ChatAction)
async def auto_install_remove(event):
    """Automatically install bot when added to group, remove when kicked/left"""
    try:
        me = await event.client.get_me()
        # Bot added or joined
        if (getattr(event, 'user_added', False) or getattr(event, 'user_joined', False)) and event.user_id == me.id:
            chat_id = str(event.chat_id)
            chat_title = event.chat.title if hasattr(event.chat, 'title') else f"Group {chat_id}"
            if not Group.select().where(Group.id == chat_id).exists():
                try:
                    Group.create(
                        id=chat_id,
                        owner=(getattr(getattr(event, 'action_message', None), 'from_id', None).user_id
                               if getattr(event, 'action_message', None) and getattr(getattr(event, 'action_message', None), 'from_id', None)
                               else 0),
                        status=True,
                        text_tag=False,
                        media_tag=False,
                        tag_all=False
                    )
                except Exception:
                    # Last resort, ensure record exists
                    Group.get_or_create(id=chat_id, defaults={
                        'owner': 0,
                        'status': True,
                        'text_tag': False,
                        'media_tag': False,
                        'tag_all': False
                    })
                print(f"✅ Bot automatically installed in group: {chat_title} ({chat_id})")
                try:
                    welcome_text = (
                        f"🎉 مرحباً! تم إضافة البوت تلقائياً إلى المجموعة\n\n"
                        f"📋 معلومات المجموعة:\n"
                        f"• الاسم: {chat_title}\n"
                        f"• المعرف: {chat_id}\n\n"
                        f"✅ البوت جاهز للاستخدام!\n"
                        f"💡 استخدم /start لرؤية الأوامر المتاحة"
                    )
                    await event.respond(welcome_text)
                except Exception as e:
                    print(f"Warning: Could not send welcome message: {e}")
        # Bot promoted to admin
        elif (getattr(event, 'user_promoted', False) or getattr(event, 'user_admin', False)) and event.user_id == me.id:
            chat_id = str(event.chat_id)
            chat_title = event.chat.title if hasattr(event.chat, 'title') else f"Group {chat_id}"
            if not Group.select().where(Group.id == chat_id).exists():
                Group.get_or_create(id=chat_id, defaults={
                    'owner': 0,
                    'status': True,
                    'text_tag': False,
                    'media_tag': False,
                    'tag_all': False
                })
            try:
                await event.respond(f"✅ تم ترقية البوت إلى مشرف في المجموعة\n• الاسم: {chat_title}\n• المعرف: {chat_id}\n\nالبوت جاهز للاستخدام")
            except Exception:
                pass

        # Bot removed
        elif getattr(event, 'user_kicked', False) and event.user_id == me.id:
            chat_id = str(event.chat_id)
            try:
                deleted = Group.delete().where(Group.id == chat_id).execute()
                if deleted > 0:
                    print(f"🗑️ Bot automatically removed from group: {chat_id}")
            except Exception as e:
                print(f"Error removing group {chat_id}: {e}")
        # Bot left
        elif getattr(event, 'user_left', False) and event.user_id == me.id:
            chat_id = str(event.chat_id)
            try:
                deleted = Group.delete().where(Group.id == chat_id).execute()
                if deleted > 0:
                    print(f"🚪 Bot automatically left group: {chat_id}")
            except Exception as e:
                print(f"Error removing group {chat_id}: {e}")
    except Exception as e:
        print(f"Error in auto_install_remove: {e}")

# ===== Manual Install Command =====
@Message(pattern='^تفعيل$')
@is_admin
async def manual_install(event):
    """Manual install command for admins"""
    try:
        chat_id = str(event.chat_id)
        chat_title = event.chat.title if hasattr(event.chat, 'title') else f"Group {chat_id}"
        
        # Check if group already exists
        if Group.select().where(Group.id == chat_id).exists():
            await event.reply('✅ البوت مفعل بالفعل في هذه المجموعة!')
            return
        
        # Create new group record
        Group.create(
            id=chat_id,
            owner=event.sender_id,
            status=True,
            text_tag=False,
            media_tag=False,
            tag_all=False
        )
        
        await event.reply(
            f'✅ تم تفعيل البوت بنجاح!\n\n'
            f'📋 معلومات المجموعة:\n'
            f'• الاسم: {chat_title}\n'
            f'• المعرف: {chat_id}\n\n'
            f'💡 استخدم /start لرؤية الأوامر المتاحة'
        )
        print(f"✅ Bot manually installed in group: {chat_title} ({chat_id})")
            
    except Exception as e:
        await event.reply(f'❌ حدث خطأ أثناء التفعيل: {str(e)}')
        print(f"Error in manual_install: {e}")

# ===== Manual Remove Command =====
@Message(pattern='^إلغاء التفعيل$')
@is_admin
async def manual_remove(event):
    """Manual remove command for admins"""
    try:
        chat_id = str(event.chat_id)
        
        # Check if group exists
        if not Group.select().where(Group.id == chat_id).exists():
            await event.reply('❌ البوت غير مفعل في هذه المجموعة!')
            return
        
        # Remove group from database
        deleted = Group.delete().where(Group.id == chat_id).execute()
        
        if deleted > 0:
            await event.reply('✅ تم إلغاء تفعيل البوت بنجاح!')
            print(f"🗑️ Bot manually removed from group: {chat_id}")
        else:
            await event.reply('❌ حدث خطأ أثناء إلغاء التفعيل!')
        
    except Exception as e:
        await event.reply(f'❌ حدث خطأ: {str(e)}')
        print(f"Error in manual_remove: {e}")



