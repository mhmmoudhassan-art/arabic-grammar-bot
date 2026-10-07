import os
import sys
import io
import json
import random
import logging

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import database

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
database.init_db()

async def safe_answer(query):
    if query:
        try:
            await query.answer()
        except Exception:
            pass

# Load questions bank (100 questions)
BASE_DIR = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.join(BASE_DIR, "questions_bank.json")

with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

print(f"Loaded {len(QUESTIONS)} questions successfully.")

# Helper to filter questions by track
def get_track_questions(track_key):
    if track_key == "random":
        shuffled = list(QUESTIONS)
        random.shuffle(shuffled)
        return shuffled
    return [q for q in QUESTIONS if q.get("track") == track_key]

# Command: /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.register_student(user.id, user.full_name, user.username or "")
    
    welcome_text = (
        f"أهلاً بك يا بطل لغة الضاد، **{user.first_name}**! 🌟\n\n"
        "مرحبًا بك في **«المُعرِب الإملائي الذكي»** 🧠✏️\n"
        "منصة البحث العلمي التفاعلية لطلاب المرحلة الإعدادية.\n\n"
        "📚 **بنك الأسئلة يضم الآن 100 سؤال لغوي متكامل!**\n"
        "اختر المسار التدريبي الذي ترغب في خوضه الآن:"
    )
    keyboard = [
        [InlineKeyboardButton("🌟 التحدي التكاملي (نحو + إملاء)", callback_data="track:integrated")],
        [InlineKeyboardButton("⚖️ مسار النحو والإعراب (نحو فقط)", callback_data="track:grammar")],
        [InlineKeyboardButton("✍️ مسار الإملاء وقواعد الرسم (إملاء فقط)", callback_data="track:spelling")],
        [InlineKeyboardButton("🎲 تحدي عشوائي شامل (من 100 سؤال)", callback_data="track:random")],
        [
            InlineKeyboardButton("⭐ رصيدي من النقاط", callback_data="my_score"),
            InlineKeyboardButton("🔬 حول المشروع العلمي", callback_data="about_research")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# About research callback
async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    
    text = (
        "🔬 **حول هذا البحث العلمي:**\n\n"
        "هذا التطبيق هو أداة تجريبية في بحث علمي لطلاب المرحلة الإعدادية يهدف إلى دراسة:\n"
        "*«أثر التكامل النحوي-الإملائي في علاج الأخطاء الكتابية وتنمية التفكير المنطقي»*.\n\n"
        "📊 **يقارن البحث بين 3 مسارات:**\n"
        "1. مسار التدريب التكاملي (ربط الإعراب بالرسم).\n"
        "2. مسار النحو المنفصل.\n"
        "3. مسار الإملاء المنفصل.\n\n"
        "كل إجابة تسجل في قاعدة البيانات لخدمة التحليل الإحصائي للبحث. 🌟"
    )
    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Show score callback
async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    user_id = query.from_user.id
    score = database.get_student_score(user_id)
    
    text = (
        f"🏆 **لوحة إنجازاتك:**\n\n"
        f"• اسم الطالب: **{query.from_user.first_name}**\n"
        f"• رصيدك الحالي: **{score} نقطة** ⭐\n\n"
        "كلما أنجزت تحديات أكثر، ارتفعت مرتبتك نحو وسام «فصيح الضاد»!"
    )
    keyboard = [
        [InlineKeyboardButton("🚀 اختيار مسار للتحدي", callback_data="main_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Start track
async def start_track(update: Update, context: ContextTypes.DEFAULT_TYPE, track_key: str):
    query = update.callback_query
    await safe_answer(query)
    
    track_questions = get_track_questions(track_key)
    if not track_questions:
        await query.edit_message_text("عذراً، لا توجد أسئلة متاحة في هذا المسار حالياً.")
        return

    # Store track queue in user_data
    context.user_data["current_track"] = track_key
    context.user_data["track_q_ids"] = [q["id"] for q in track_questions]
    context.user_data["track_q_index"] = 0
    
    await serve_question(update, context, q_index=0)

# Serve Question & Current Step
async def serve_question(update: Update, context: ContextTypes.DEFAULT_TYPE, q_index: int):
    query = update.callback_query
    track_q_ids = context.user_data.get("track_q_ids", [])
    
    if q_index >= len(track_q_ids):
        # Track finished
        text = (
            "🎉 **مبارك! لقد أتممت جميع أسئلة هذا المسار بنجاح باهر!** 🌟\n\n"
            "لقد ساهمت محاولاتك في تقديم بيانات قيمة للبحث العلمي.\n"
            "يمكنك تجربة مسار آخر أو مراجعة رصيدك."
        )
        keyboard = [
            [InlineKeyboardButton("⭐ عرض رصيدي من النقاط", callback_data="my_score")],
            [InlineKeyboardButton("🔄 اختيار مسار آخر", callback_data="main_menu")]
        ]
        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    qid = track_q_ids[q_index]
    # find question by id
    q = next((item for item in QUESTIONS if item["id"] == qid), None)
    if not q:
        return

    # Set question state
    context.user_data["active_q"] = q
    context.user_data["active_step_index"] = 0
    context.user_data["step_answers"] = []  # list of (chosen, is_correct)
    
    await render_step(update, context, step_index=0)

# Render specific step of active question
async def render_step(update: Update, context: ContextTypes.DEFAULT_TYPE, step_index: int):
    query = update.callback_query
    q = context.user_data["active_q"]
    steps = q["steps"]
    step = steps[step_index]
    
    total_q_in_track = len(context.user_data["track_q_ids"])
    current_q_num = context.user_data["track_q_index"] + 1
    
    # Progress text
    header = (
        f"📌 **السؤال ({current_q_num} من {total_q_in_track})** | [{q.get('track_name', '')}]\n"
        f"📖 *« {q['prompt']} »*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    # If there are previous step summaries, show them:
    history_text = ""
    for i, (ans, is_corr) in enumerate(context.user_data["step_answers"]):
        prev_step = steps[i]
        icon = "✅" if is_corr else "⚠️"
        history_text += f"{icon} *{prev_step['title']}*: {ans}\n"
    if history_text:
        history_text += "━━━━━━━━━━━━━━━━━━━━━\n"

    step_body = f"👉 **{step['title']}**\n{step['question']}"
    full_text = header + history_text + step_body
    
    keyboard = []
    for opt_idx, opt in enumerate(step["options"]):
        # callback: step_ans:<step_index>:<opt_idx>
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"step_ans:{step_index}:{opt_idx}")])
    keyboard.append([InlineKeyboardButton("❌ إنهاء والعودة للقائمة", callback_data="main_menu")])

    markup = InlineKeyboardMarkup(keyboard)
    if query:
        await query.edit_message_text(full_text, reply_markup=markup, parse_mode="Markdown")

# Handle step answer
async def handle_step_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    
    parts = query.data.split(":")
    step_index = int(parts[1])
    opt_index = int(parts[2])
    
    q = context.user_data["active_q"]
    step = q["steps"][step_index]
    chosen = step["options"][opt_index]
    is_correct = (chosen == step["correct"])
    
    context.user_data["step_answers"].append((chosen, is_correct))
    
    next_step_index = step_index + 1
    if next_step_index < len(q["steps"]):
        # Move to next step of the same question
        context.user_data["active_step_index"] = next_step_index
        await render_step(update, context, next_step_index)
    else:
        # All steps of this question completed! Finalize and log.
        await finalize_question(update, context)

# Finalize question and show feedback
async def finalize_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    q = context.user_data["active_q"]
    answers = context.user_data["step_answers"]
    user = query.from_user
    
    all_correct = all(corr for _, corr in answers)
    
    # Prepare parameters for database log
    s1_chosen, s1_correct = answers[0] if len(answers) > 0 else ("-", False)
    s2_chosen, s2_correct = answers[1] if len(answers) > 1 else ("-", False)
    if len(answers) > 2:
        s3_chosen, s3_correct = answers[2]
    else:
        s3_chosen, s3_correct = None, None

    points = database.log_interaction(
        user_id=user.id,
        student_name=user.full_name,
        question_id=q["id"],
        track=q.get("track", "integrated"),
        track_name=q.get("track_name", "عام"),
        category=q.get("category", ""),
        s1_chosen=s1_chosen, s1_correct=s1_correct,
        s2_chosen=s2_chosen, s2_correct=s2_correct,
        s3_chosen=s3_chosen, s3_correct=s3_correct
    )
    
    if all_correct:
        status_header = "🎉 **إجابة نموذجية ومكتملة! أحسنت يا بطل!** ⭐⭐⭐"
    else:
        status_header = "💡 **محاولة جيدة! انتبه للشرح التربوي:**"
        
    result_text = (
        f"{status_header}\n\n"
        f"📖 الجملة: *« {q['prompt']} »*\n"
        f"⭐ النقاط المكتسبة: **+{points} نقطة**\n\n"
        f"📝 **الشرح السقراطي للقاعدة:**\n"
        f"{q.get('explanation', '')}\n"
    )
    
    next_q_index = context.user_data["track_q_index"] + 1
    context.user_data["track_q_index"] = next_q_index
    
    keyboard = [
        [InlineKeyboardButton("➡️ الانتقال للسؤال التالي", callback_data=f"next_q:{next_q_index}")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
    ]
    await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Admin command: /stats (for teacher & student researchers)
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = database.get_research_statistics()
    text = (
        "📊 **إحصائيات البحث العلمي المباشرة (100 سؤال):**\n\n"
        f"👥 إجمالي الطلاب المشاركين: **{stats['total_students']}**\n"
        f"📝 إجمالي المحاولات المسجلة: **{stats['total_attempts']}**\n"
        f"🎯 الدقة العامة لجميع المحاولات: **%{stats['overall_accuracy']}**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔬 **مقارنة دقة الطلاب عبر المسارات الثلاثة:**\n"
        f"1️⃣ **المسار التكاملي (نحو + إملاء):**\n"
        f"   • عدد المحاولات: {stats['integrated']['count']} | نسبة الدقة: **%{stats['integrated']['accuracy']}**\n\n"
        f"2️⃣ **مسار النحو والإعراب (نحو فقط):**\n"
        f"   • عدد المحاولات: {stats['grammar']['count']} | نسبة الدقة: **%{stats['grammar']['accuracy']}**\n\n"
        f"3️⃣ **مسار الإملاء وقواعد الرسم (إملاء فقط):**\n"
        f"   • عدد المحاولات: {stats['spelling']['count']} | نسبة الدقة: **%{stats['spelling']['accuracy']}**\n\n"
        "💡 *تتيح لك هذه المقارنة إثبات أثر المدخل التكاملي أمام المحكمين.*\n"
        "📁 لتحميل جدول البيانات الكامل كملف إكسل، أرسل: `/export`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# Admin command: /export (sends CSV directly in chat!)
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    csv_file = database.export_research_data_csv()
    await update.message.reply_text("⏳ جارٍ استخراج ملف بيانات البحث العلمي بتنسيق Excel/CSV...")
    with open(csv_file, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="student_research_data.csv",
            caption="📊 ملف بيانات تفاعلات الطلاب المسجلة في المسارات الثلاثة (جاهز للتحليل في SPSS / Excel)."
        )

# Main router for callbacks
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    data = query.data
    
    if data == "main_menu":
        await start_command(update, context)
    elif data.startswith("track:"):
        track_key = data.split(":")[1]
        await start_track(update, context, track_key)
    elif data == "about_research":
        await show_about(update, context)
    elif data == "my_score":
        await show_score(update, context)
    elif data.startswith("step_ans:"):
        await handle_step_answer(update, context)
    elif data.startswith("next_q:"):
        next_idx = int(data.split(":")[1])
        await serve_question(update, context, q_index=next_idx)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning("Update caused error: %s", context.error)

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class CloudHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Bot is running 24/7 on Cloud!".encode("utf-8"))
    def log_message(self, format, *args):
        pass

def start_cloud_health_server():
    port_str = os.environ.get("PORT")
    if port_str:
        try:
            port = int(port_str)
            server = HTTPServer(("0.0.0.0", port), CloudHealthHandler)
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            print(f"Cloud health server started on port {port}")
        except Exception as e:
            print(f"Could not start cloud health server: {e}")

def main():
    start_cloud_health_server()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not token:
        config_path = os.path.join(BASE_DIR, "bot_token.txt")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                token = f.read().strip()
                
    if not token:
        print("="*60)
        print("⚠️ لم يتم العثور على رمز البوت (TELEGRAM_BOT_TOKEN)!")
        print("="*60)
        return

    print("🚀 جارٍ تشغيل بوت «المُعرِب الإملائي» (النسخة الموسعة - 100 سؤال)...")
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_error_handler(error_handler)
    
    print("✅ البوت متصل ويعمل الآن بنجاح مع 100 سؤال على تيليجرام!")
    app.run_polling()

if __name__ == "__main__":
    main()
