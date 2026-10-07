import sqlite3
import csv
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "research_data.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users / Students table
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            score INTEGER DEFAULT 0,
            joined_at TEXT
        )
    ''')
    # Interactions / Answers log for research analysis
    c.execute('''
        CREATE TABLE IF NOT EXISTS research_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            student_name TEXT,
            question_id INTEGER,
            track TEXT,
            track_name TEXT,
            category TEXT,
            step1_chosen TEXT,
            step1_is_correct INTEGER,
            step2_chosen TEXT,
            step2_is_correct INTEGER,
            step3_chosen TEXT,
            step3_is_correct INTEGER,
            is_fully_correct INTEGER,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES students (user_id)
        )
    ''')
    
    # Check if 'track' column exists (in case table was created earlier)
    c.execute("PRAGMA table_info(research_logs)")
    columns = [col[1] for col in c.fetchall()]
    if "track" not in columns:
        try:
            c.execute("ALTER TABLE research_logs ADD COLUMN track TEXT DEFAULT 'integrated'")
            c.execute("ALTER TABLE research_logs ADD COLUMN track_name TEXT DEFAULT 'التكامل'")
        except Exception:
            pass
            
    conn.commit()
    conn.close()

def register_student(user_id, full_name, username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO students (user_id, full_name, username, score, joined_at)
        VALUES (?, ?, ?, 0, ?)
    ''', (user_id, full_name, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def log_interaction(user_id, student_name, question_id, track, track_name, category,
                    s1_chosen, s1_correct,
                    s2_chosen, s2_correct,
                    s3_chosen=None, s3_correct=None):
    if s3_correct is not None:
        is_fully_correct = 1 if (s1_correct and s2_correct and s3_correct) else 0
        points = (int(s1_correct) + int(s2_correct) + int(s3_correct)) * 5
        s3_int = int(s3_correct)
    else:
        is_fully_correct = 1 if (s1_correct and s2_correct) else 0
        points = (int(s1_correct) + int(s2_correct)) * 5
        s3_int = None
        s3_chosen = "-"

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO research_logs (
            user_id, student_name, question_id, track, track_name, category,
            step1_chosen, step1_is_correct,
            step2_chosen, step2_is_correct,
            step3_chosen, step3_is_correct,
            is_fully_correct, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, student_name, question_id, track, track_name, category,
        s1_chosen, int(s1_correct),
        s2_chosen, int(s2_correct),
        s3_chosen, s3_int,
        is_fully_correct, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    
    # Update total student score
    c.execute('''
        UPDATE students SET score = score + ? WHERE user_id = ?
    ''', (points, user_id))
    
    conn.commit()
    conn.close()
    return points

def get_student_score(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT score FROM students WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def export_research_data_csv(output_path=None):
    if not output_path:
        output_path = os.path.join(os.path.dirname(__file__), "student_research_data.csv")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, user_id, student_name, question_id, track_name, category,
               step1_chosen, step1_is_correct,
               step2_chosen, step2_is_correct,
               step3_chosen, step3_is_correct,
               is_fully_correct, timestamp
        FROM research_logs
        ORDER BY timestamp ASC
    ''')
    rows = c.fetchall()
    headers = [
        "سجل_رقم", "معرف_الطالب", "اسم_الطالب", "رقم_السؤال", "مسار_التحدي", "تصنيف_القاعدة",
        "المحطة_الأولى_المختارة", "صحة_المحطة_الأولى",
        "المحطة_الثانية_المختارة", "صحة_المحطة_الثانية",
        "المحطة_الثالثة_المختارة", "صحة_المحطة_الثالثة",
        "إتقان_السؤال_كاملاً", "تاريخ_ووقت_الإجابة"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    
    conn.close()
    return output_path

def get_research_statistics():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(DISTINCT user_id) FROM research_logs')
    total_students = c.fetchone()[0] or 0
    
    c.execute('SELECT COUNT(*) FROM research_logs')
    total_attempts = c.fetchone()[0] or 0
    
    c.execute('SELECT AVG(is_fully_correct) FROM research_logs')
    overall_acc = (c.fetchone()[0] or 0) * 100
    
    # Track statistics
    def get_track_stats(track_name):
        c.execute('SELECT COUNT(*), AVG(is_fully_correct) FROM research_logs WHERE track = ?', (track_name,))
        row = c.fetchone()
        count = row[0] or 0
        acc = round((row[1] or 0) * 100, 1)
        return count, acc

    int_count, int_acc = get_track_stats('integrated')
    gram_count, gram_acc = get_track_stats('grammar')
    spel_count, spel_acc = get_track_stats('spelling')

    conn.close()
    
    return {
        "total_students": total_students,
        "total_attempts": total_attempts,
        "overall_accuracy": round(overall_acc, 1),
        "integrated": {"count": int_count, "accuracy": int_acc},
        "grammar": {"count": gram_count, "accuracy": gram_acc},
        "spelling": {"count": spel_count, "accuracy": spel_acc},
    }

if __name__ == "__main__":
    init_db()
    print("Database upgraded and initialized successfully.")
