import os
import sqlite3
import random
import subprocess
import sys


def list_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    return [row[0] for row in cur.fetchall()]


def get_questions(conn, table):
    cur = conn.cursor()
    cur.execute(
        f"SELECT question_number, question_text, answer_a, answer_b, answer_c, correct_answer, image_path FROM {table} ORDER BY question_number"
    )
    return cur.fetchall()


def display_image(path, viewer):
    """
    Launches the image viewer detached from the terminal and returns the process handle.
    Redirects stdin/stdout/stderr to avoid blocking terminal input.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        proc = subprocess.Popen(
            [viewer, path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True
        )
        return proc
    except Exception as e:
        print(f"[!] Could not open image '{path}' with '{viewer}': {e}")
        return None


def quiz_loop(questions, viewer):
    score = 0
    total = len(questions)
    for idx, (qnum, text, a, b, c, correct, img) in enumerate(questions, start=1):
        print(f"\nQuestion {idx}/{total} (#{qnum}):")
        print(text)

        # Show image and get process handle
        img_proc = display_image(img, viewer) if img else None

        print(f"  a) {a}")
        print(f"  b) {b}")
        print(f"  c) {c}")
        ans = input("Your answer (a/b/c): ").strip().lower()

        # After answer, close the image window if still open
        if img_proc and img_proc.poll() is None:
            try:
                img_proc.terminate()
            except Exception:
                pass

        if ans == correct:
            print("Correct!")
            score += 1
        else:
            print(f"Incorrect. The correct answer was '{correct}'.")

    print(f"\nQuiz complete! You scored {score} out of {total}.")


def main():
    db_path = 'fish_license.db'
    if not os.path.exists(db_path):
        print(f"Error: '{db_path}' not found.")
        sys.exit(1)
    conn = sqlite3.connect(db_path)

    tables = list_tables(conn)
    if not tables:
        print("No quiz tables found.")
        sys.exit(1)

    print("Available quizzes:")
    for i, t in enumerate(tables, 1):
        print(f"  {i}. {t}")
    choice = input(f"Select quiz (1-{len(tables)}): ").strip()
    try:
        idx = int(choice) - 1
        table = tables[idx]
    except Exception:
        print("Invalid selection.")
        sys.exit(1)

    questions = get_questions(conn, table)
    if not questions:
        print(f"No questions in table '{table}'.")
        sys.exit(1)

    num = input(f"Number of questions to attempt (1-{len(questions)}): ").strip()
    try:
        count = int(num)
        if count < 1 or count > len(questions):
            raise ValueError
    except Exception:
        print("Invalid number.")
        sys.exit(1)

    selected = random.sample(questions, count)
    viewer = os.getenv('IMG_VIEWER', 'xdg-open')
    quiz_loop(selected, viewer)


if __name__ == '__main__':
    main()

