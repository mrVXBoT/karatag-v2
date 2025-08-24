from typing import Callable
from config import sudo,client
from config import join_channel
from telethon import events,errors,Button,types

from telethon.tl.types import (
    ChannelParticipantAdmin,
    ChannelParticipantCreator
)

from collections import defaultdict
from time import time
from collections import defaultdict
import functools 
import asyncio
import json
_users = defaultdict(list)
from .db import Setting,User,AntiFlood

def status(**kwrgs):
    def decorator(f):
        @functools.wraps(f)
        async def wrapper(event,*a,**k):
            s = json.loads(str(kwrgs.get('status')).lower()) 
            if s:
                return await f(event,*a,**k)
            else:
                text = (
                    '᯽︙ عزيزي موقتا“ معطل'
                )
                return await event.respond(text)
        return wrapper
    return decorator

def is_join(**kwrgs):
    def decorator(f):
        @functools.wraps(f)
        async def wrapper(event,*a,**k):
            db = Setting.select().where(Setting.key == 'JOIN_STATUS')
            if not db.exists():
                Setting.create(
                    key = 'JOIN_STATUS',
                    value = True
                )
            channel = join_channel
            
            status =  json.loads(str(db.get().value).lower()) if db.exists() else True
            if status is False:
                return await f(event,*a,**k)
                
            try:
                check = (await event.client.get_permissions(channel, event.sender_id)).participant
                return await f(event,*a,**k)
            except errors.rpcerrorlist.UserNotParticipantError:
                buttons = [
                    [Button.url('‹اضغط هنا للأشتراك›',f'https://t.me/{channel.replace("@","")}')],
                    [Button.inline('❌','joining')]
                ]
                text = (
                    f'⌔︙عليك الاشتراك في قناة البوت اولاً !'
                    
                )
                return await event.reply(text,buttons = buttons)
        return wrapper
    return decorator


def is_owner(func: Callable) -> Callable:
    async def decorator(event,text=None):
        
        owner = (await event.client.get_permissions(event.chat_id, event.sender_id)).participant
        if   isinstance(owner,types.
    ChannelParticipantCreator) or  event.sender_id in sudo:
            return  await func(event,text=None)
            
        else:
                return await event.reply('᯽︙ أنت لست مالك أو مشرف في المجموعه')
    return decorator


def is_ban(func: Callable) -> Callable:
    async def decorator(event,text=None):
        user = User.select().where(User.userid == event.sender_id)
        if user.exists():
            if user.get().is_ban:
                return await event.respond('᯽︙ عزيزي المستخدم تم حظرك من البوت أن كنت تفكر تم حظرك بالخطاء قم بمراسله الدعم')
            return await func(event)
        else:
            return await func(event)
    return decorator


def join(func):
    async def decorator(event):
        
        
        if event.is_private:
            user = event.sender_id
            
            try:
                check = (await event.client.get_permissions(channel, user)).participant
                return await func(event)
            except errors.rpcerrorlist.UserNotParticipantError:
                text = (
                    '- انت لست مشترك بلقناه'
                    f'اشترك اولا @{channel} ثم اضغط ستارت'
                )
                return await event.respond(text)
    return decorator       

def is_admin(func: Callable) -> Callable:
    async def decorator(event,text = None):
        
        if event.sender_id in sudo:
            return await func(event)
        else:
            pass
    return decorator
	
	
def admin(func):
    async def decorator(event):
        if not event.is_private:
            me = (await event.client.get_me()).id
            check = (await event.client.get_permissions(event.chat.id, me)).participant
            if isinstance(check,(ChannelParticipantAdmin,ChannelParticipantCreator)):
                return await func(event)
            else:
                return await event.reply('im aint admin')
    return decorator



def Message(**args):
    pattern = args.get('pattern', None)
    admin = args.get('admin',False)
    
    
    if admin:
        args['from_users'] = sudo
    del admin
    # if pattern is not None and not pattern.startswith('(?i)'):
    #     args['pattern'] = '(?i)' + pattern
    try:
        del args["admin"]
    except Exception:
        pass
    def decorator(func):
        
        client.add_event_handler(func, events.NewMessage(**args))
                
        return func

    return decorator
def Callback(**args):
    pattern = args.get('pattern', None)
    if pattern is not None and not pattern.startswith(b'(?i)'):
        args['pattern'] = b'(?i)' + pattern
    def decorator(func):
        client.add_event_handler(func, events.CallbackQuery(**args))
        return func

    return decorator

def Action(**args):
    pattern = args.get('pattern', None)
    if pattern is not None and not pattern.startswith('(?i)'):
        args['pattern'] = '(?i)' + pattern
    def decorator(func):
        client.add_event_handler(func, events.ChatAction(**args))
        return func
    return decorator



from datetime import datetime ,timedelta 

def antiflood(messages: int = 5,second: int = 3,until: int = 30,users: defaultdict = _users):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(event,*argv, **k):
            users[event.sender_id].append(time())
            check = list(filter(lambda x: time() - int(x) < second, users[event.sender_id]))
            user = AntiFlood.select().where(AntiFlood.user_id == event.sender_id)
            if not user.exists():
                AntiFlood.create(
                    user_id = event.sender_id,
                    ban_until = 0
                )
            get = user.get()
            if get.ban_until > int(time()):
                return 
            if len(check) > messages:
                users[event.sender_id] = check
                detail = json.loads(get.detail)
                detail = users[event.sender_id]
                AntiFlood.update({AntiFlood.detail: detail,AntiFlood.ban_until: int(time()) + until}).where(AntiFlood.user_id == event.sender_id).execute()
                return await event.respond(
                    f'❌ بسبب التكرار أو التهجم {until} ثانيه تم منعك من استخدام البوت \n'
                    f'📌يمكنك من بعد {until} ثانيه استخدام البوت مره اخرى\n'
                ) 
            for u in AntiFlood.select():
                detail = json.loads(u.detail)
                if not detail == [] :
                    if int(detail[-1])<int(time())-int(until):
                        AntiFlood.delete().where(AntiFlood.user_id == u.user_id).execute()
            return await func(event,*argv, **k)                
        return wrapper 
    return decorator


            




