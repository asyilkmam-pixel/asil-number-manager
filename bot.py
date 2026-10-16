
import os
import re
import socket
import platform
from functools import wraps
import sqlite3
from datetime import datetime, timezone
from telegram import Update, ReplyKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

DB_PATH = os.path.join(os.path.dirname(__file__), "stats.db")


def  init_stats_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                user_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                used_at TEXT NOT NULL
            )
        """)


def record_usage(user_id: int, command: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO usage_stats (user_id, command, used_at)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                command,
                datetime.now(timezone.utc).isoformat(),
            ),
        )



KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🖥️ حالة النظام", "🌐 فحص DNS"],
        ["🛡️ إرشادات الأمن", "ℹ️ المساعدة"],
    ],
    resize_keyboard=True,
)


async def is_admin(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return False

    if user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.reply_text("عذرًا، هذا البوت خاص بمديره.")
        return False

    return True


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    record_usage(update.effective_user.id, "start")

    await update.effective_message.reply_text(
        "مرحبًا بك في Asil Cyber Security Bot\n\n"
        "اختر أداة من القائمة، أو استخدم /help.",
        reply_markup=KEYBOARD,
    )


async def show_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    record_usage(update.effective_user.id, "id")

    await update.effective_message.reply_text(
        f"Telegram ID: {update.effective_user.id}"
    )


async def system_info(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    record_usage(update.effective_user.id, "system")

    info = (
        "🖥️ معلومات بيئة التشغيل\n\n"
        f"النظام: {platform.system()}\n"
        f"الإصدار: {platform.release()}\n"
        f"المعمارية: {platform.machine()}\n"
        f"Python: {platform.python_version()}\n"
    )

    await update.effective_message.reply_text(info)


async def dns_lookup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    record_usage(update.effective_user.id, "dns")

    if not context.args:
        await update.effective_message.reply_text(
            "استخدم الأمر هكذا:\n/dns example.com"
        )
        return

    host = context.args[0].strip().lower()

    if (
        len(host) > 253
        or not re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
            r"\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
            host,
        )
    ):
        await update.effective_message.reply_text(
            "اسم المضيف غير صالح. أدخل اسم نطاق فقط، "
            "مثل example.com."
        )
        return

    try:
        results = socket.getaddrinfo(
            host, None, type=socket.SOCK_STREAM
        )
        addresses = sorted({item[4][0] for item in results})

        await update.effective_message.reply_text(
            f"نتائج DNS للنطاق {host}:\n\n"
            + "\n".join(f"• {ip}" for ip in addresses)
        )
    except socket.gaierror:
        await update.effective_message.reply_text(
            "تعذر حل اسم النطاق. تحقق من الاسم والاتصال."
        )
    except OSError:
        await update.effective_message.reply_text(
            "حدث خطأ في الشبكة أثناء الاستعلام."
        )


async def security_tips(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    record_usage(update.effective_user.id, "security_tips")

    await update.effective_message.reply_text(
        "🛡️ أساسيات الأمن السيبراني\n\n"
        "• حدّث النظام والأدوات باستمرار.\n"
        "• استخدم كلمات مرور فريدة والمصادقة الثنائية.\n"
        "• لا تشارك BOT_TOKEN أو كلمات المرور.\n"
        "• افحص الأنظمة التي تملكها أو لديك إذن باختبارها.\n"
        "• احتفظ بنسخة احتياطية من ملفاتك المهمة."
    )


async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM usage_stats"
        ).fetchone()[0]

        users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM usage_stats"
        ).fetchone()[0]

        rows = conn.execute(
            """
            SELECT command, COUNT(*)
            FROM usage_stats
            GROUP BY command
            ORDER BY COUNT(*) DESC
            LIMIT 10
            """
        ).fetchall()

    report = (
        "📊 إحصائيات Asil Number Manager\n\n"
        f"إجمالي الاستخدامات: {total}\n"
        f"عدد المستخدمين: {users}\n\n"
        "أكثر الأوامر استخدامًا:\n"
    )

    if rows:
        report += "\n".join(
            f"• {command}: {count}"
            for command, count in rows
        )
    else:
        report += "لا توجد استخدامات مسجلة حتى الآن."

    await update.effective_message.reply_text(report)

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    record_usage(update.effective_user.id, "help")

    await update.effective_message.reply_text(
        "الأوامر المتاحة:\\n\\n"
        "/start - القائمة الرئيسية\\n"
        "/id - رقم حساب Telegram\\n"
        "/system - معلومات بيئة التشغيل\\n"
        "/dns example.com - استعلام DNS\\n"
        "/help - المساعدة",
        reply_markup=KEYBOARD,
    )

async def menu_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await is_admin(update):
        return

    text = update.effective_message.text

    if text == "🖥️ حالة النظام":
        await system_info(update, context)
    elif text == "🌐 فحص DNS":
        record_usage(update.effective_user.id, "menu_dns")
        await update.effective_message.reply_text(
            "أرسل الأمر مع اسم النطاق، مثل:\n/dns example.com"
        )
    elif text == "🛡️ إرشادات الأمن":
        await security_tips(update, context)
    elif text == "ℹ️ المساعدة":
        await help_command(update, context)
    else:
        await update.effective_message.reply_text(
            "اختر أداة من القائمة أو استخدم /help."
        )


def main():
    if not TOKEN or not ADMIN_ID:
        raise RuntimeError(
            "يجب إعداد BOT_TOKEN و ADMIN_ID أولًا."
        )

    init_stats_db()

    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
    )

    get_updates_request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=40,
        write_timeout=30,
        pool_timeout=30,
    )

    app = (
        Application.builder()
        .token(TOKEN)
        .request(request)
        .get_updates_request(get_updates_request)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("system", system_info))
    app.add_handler(CommandHandler("dns", dns_lookup))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_handler,
        )
    )

    print("Asil Cyber Security Bot يعمل...")
    app.run_polling()


if __name__ == "__main__":
    main()
