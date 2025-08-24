#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اسکریپت بررسی اطلاعات گروه‌ها و سوپرگروه‌ها
نمایش لینک عضویت، یوزرنیم و اطلاعات کامل گروه‌ها
"""

import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User
from telethon.tl.functions.messages import GetFullChannelRequest
from telethon.tl.functions.channels import GetFullChannelRequest as GetFullSupergroupRequest
from telethon.errors import FloodWaitError, ChannelPrivateError, InviteHashExpiredError
import sqlite3
import os
from datetime import datetime

# تنظیمات بات - این مقادیر را با اطلاعات بات خود جایگزین کنید
API_ID = "YOUR_API_ID"
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"

async def get_group_info(client, group_id):
    """دریافت اطلاعات کامل گروه"""
    try:
        # دریافت entity گروه
        entity = await client.get_entity(group_id)
        
        if isinstance(entity, Channel):
            # سوپرگروه
            try:
                full_channel = await client(GetFullChannelRequest(entity))
                invite_link = full_channel.full_chat.exported_invite.link if full_channel.full_chat.exported_invite else "بدون لینک عضویت"
            except Exception as e:
                invite_link = f"خطا در دریافت لینک: {str(e)}"
            
            group_info = {
                'id': entity.id,
                'title': entity.title,
                'username': entity.username or "بدون یوزرنیم",
                'type': 'سوپرگروه',
                'members_count': getattr(full_channel.full_chat, 'participants_count', 'نامشخص'),
                'description': getattr(full_channel.full_chat, 'about', 'بدون توضیحات'),
                'invite_link': invite_link,
                'is_private': entity.broadcast and not entity.username,
                'created_date': datetime.fromtimestamp(entity.date.timestamp()).strftime('%Y-%m-%d %H:%M:%S') if entity.date else 'نامشخص'
            }
        else:
            # گروه معمولی
            group_info = {
                'id': entity.id,
                'title': entity.title,
                'username': getattr(entity, 'username', None) or "بدون یوزرنیم",
                'type': 'گروه معمولی',
                'members_count': 'نامشخص',
                'description': 'بدون توضیحات',
                'invite_link': 'گروه‌های معمولی لینک عضویت ندارند',
                'is_private': True,
                'created_date': 'نامشخص'
            }
        
        return group_info
        
    except Exception as e:
        return {
            'id': group_id,
            'title': 'خطا در دریافت اطلاعات',
            'username': 'نامشخص',
            'type': 'نامشخص',
            'members_count': 'نامشخص',
            'description': f'خطا: {str(e)}',
            'invite_link': 'نامشخص',
            'is_private': 'نامشخص',
            'created_date': 'نامشخص'
        }

async def check_database_groups():
    """بررسی گروه‌های موجود در دیتابیس"""
    try:
        # اتصال به دیتابیس
        db_path = 'karatag.db'
        if not os.path.exists(db_path):
            print("❌ فایل دیتابیس یافت نشد!")
            return []
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # دریافت گروه‌ها از دیتابیس
        cursor.execute("SELECT id, owner, status FROM groups")
        groups = cursor.fetchall()
        
        conn.close()
        return groups
        
    except Exception as e:
        print(f"❌ خطا در خواندن دیتابیس: {e}")
        return []

async def main():
    """تابع اصلی"""
    print("🚀 شروع بررسی اطلاعات گروه‌ها...")
    print("=" * 60)
    
    # بررسی گروه‌های دیتابیس
    db_groups = await check_database_groups()
    print(f"📊 تعداد گروه‌های موجود در دیتابیس: {len(db_groups)}")
    print()
    
    if not db_groups:
        print("❌ هیچ گروهی در دیتابیس یافت نشد!")
        return
    
    # ایجاد کلاینت تلگرام
    try:
        client = TelegramClient('group_checker_session', API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)
        print("✅ اتصال به تلگرام برقرار شد")
        print()
    except Exception as e:
        print(f"❌ خطا در اتصال به تلگرام: {e}")
        return
    
    # بررسی هر گروه
    for i, (group_id, owner, status) in enumerate(db_groups, 1):
        print(f"🔍 بررسی گروه {i}/{len(db_groups)}")
        print(f"🆔 ID: {group_id}")
        print(f"👤 مالک: {owner}")
        print(f"📊 وضعیت: {'فعال' if status else 'غیرفعال'}")
        
        try:
            group_info = await get_group_info(client, int(group_id))
            
            print(f"📝 نام: {group_info['title']}")
            print(f"🏷️ نوع: {group_info['type']}")
            print(f"👥 تعداد اعضا: {group_info['members_count']}")
            print(f"🔗 یوزرنیم: {group_info['username']}")
            print(f"🔐 خصوصی: {'بله' if group_info['is_private'] else 'خیر'}")
            print(f"📅 تاریخ ایجاد: {group_info['created_date']}")
            print(f"📋 توضیحات: {group_info['description'][:100]}{'...' if len(group_info['description']) > 100 else ''}")
            print(f"🔗 لینک عضویت: {group_info['invite_link']}")
            
        except Exception as e:
            print(f"❌ خطا در دریافت اطلاعات: {e}")
        
        print("-" * 60)
        
        # تاخیر برای جلوگیری از محدودیت API
        await asyncio.sleep(1)
    
    await client.disconnect()
    print("✅ بررسی کامل شد!")

def create_summary_report():
    """ایجاد گزارش خلاصه"""
    try:
        db_path = 'karatag.db'
        if not os.path.exists(db_path):
            print("❌ فایل دیتابیس یافت نشد!")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # آمار کلی
        cursor.execute("SELECT COUNT(*) FROM groups")
        total_groups = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM groups WHERE status = 1")
        active_groups = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM groups WHERE status = 0")
        inactive_groups = cursor.fetchone()[0]
        
        print("📊 گزارش خلاصه گروه‌ها:")
        print(f"📈 کل گروه‌ها: {total_groups}")
        print(f"✅ گروه‌های فعال: {active_groups}")
        print(f"❌ گروه‌های غیرفعال: {inactive_groups}")
        
        # گروه‌های اخیر
        cursor.execute("SELECT id, owner, status FROM groups ORDER BY ROWID DESC LIMIT 10")
        recent_groups = cursor.fetchall()
        
        print(f"\n🆕 آخرین گروه‌های اضافه شده:")
        for group_id, owner, status in recent_groups:
            status_text = "✅ فعال" if status else "❌ غیرفعال"
            print(f"  • ID: {group_id} | مالک: {owner} | {status_text}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ خطا در ایجاد گزارش: {e}")

if __name__ == "__main__":
    print("🔧 اسکریپت بررسی اطلاعات گروه‌ها")
    print("=" * 60)
    
    # بررسی دیتابیس
    create_summary_report()
    print()
    
    # درخواست اجرا
    response = input("آیا می‌خواهید اطلاعات کامل گروه‌ها را بررسی کنید؟ (y/n): ")
    
    if response.lower() in ['y', 'yes', 'بله', 'y']:
        # قبل از اجرا، تنظیمات را بررسی کنید
        if API_ID == "YOUR_API_ID" or API_HASH == "YOUR_API_HASH" or BOT_TOKEN == "YOUR_BOT_TOKEN":
            print("\n⚠️  لطفاً ابتدا تنظیمات API را در فایل تنظیم کنید:")
            print("   - API_ID")
            print("   - API_HASH") 
            print("   - BOT_TOKEN")
            print("\nسپس دوباره اجرا کنید.")
        else:
            asyncio.run(main())
    else:
        print("❌ اجرا لغو شد.")
