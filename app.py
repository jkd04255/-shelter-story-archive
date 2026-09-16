import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from db import (
    add_demo_story,
    assign_story,
    get_animal,
    get_animals,
    get_unmatched,
    init_db,
    seed_demo,
)
from instagram_sync import sync_stories

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
app.config["SITE_NAME"] = os.getenv("SITE_NAME", "센터의 하루")
app.config["CONTACT_URL"] = os.getenv("CONTACT_URL", "").strip()


def make_demo_svg(filename, animal_name, message, emoji):
    path = BASE_DIR / "static" / "demo" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff2d9"/><stop offset="1" stop-color="#e8f3ea"/></linearGradient></defs>
<rect width="1080" height="1350" rx="48" fill="url(#g)"/>
<circle cx="540" cy="530" r="260" fill="#ffffff" opacity=".8"/>
<text x="540" y="620" text-anchor="middle" font-size="300">{emoji}</text>
<text x="540" y="940" text-anchor="middle" font-family="sans-serif" font-size="76" font-weight="700" fill="#2b312d">{animal_name}</text>
<text x="540" y="1040" text-anchor="middle" font-family="sans-serif" font-size="46" fill="#56615a">{message}</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")


def seed_demo_stories():
    make_demo_svg("dduddu_walk.svg", "뚜뚜", "오늘 산책 완료!", "🐶")
    make_demo_svg("dduddu_rest.svg", "뚜뚜", "낮잠 자는 중", "🐕")
    make_demo_svg("mong.svg", "몽이", "간식 기다리는 중", "🐶")
    make_demo_svg("unknown.svg", "새 친구", "이름 확인이 필요해요", "🐾")

    now = datetime.now(timezone.utc)
    add_demo_story("demo-dduddu-1", 1, "demo/dduddu_walk.svg", "뚜뚜 오늘 산책 완료!", (now - timedelta(hours=2)).isoformat())
    add_demo_story("demo-dduddu-2", 1, "demo/dduddu_rest.svg", "뚜뚜 낮잠 자는 중", (now - timedelta(days=2)).isoformat())
    add_demo_story("demo-mong-1", 2, "demo/mong.svg", "몽이 간식 기다리는 중", (now - timedelta(days=1)).isoformat())
    add_demo_story("demo-unknown-1", None, "demo/unknown.svg", "새 친구가 들어왔어요", (now - timedelta(hours=5)).isoformat())


@app.context_processor
def inject_layout_settings():
    return {
        "site_name": app.config["SITE_NAME"],
        "contact_url": app.config["CONTACT_URL"],
    }


@app.template_filter("pretty_date")
def pretty_date(value):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y.%m.%d %H:%M")
    except Exception:
        return value


@app.route("/")
def index():
    return render_template("index.html", animals=get_animals(), site_name=app.config["SITE_NAME"])


@app.route("/health")
def health():
    return {"ok": True}


@app.route("/animals/<int:animal_id>")
def animal_detail(animal_id):
    animal, stories = get_animal(animal_id)
    if not animal:
        return "동물을 찾을 수 없습니다.", 404
    return render_template("animal.html", animal=animal, stories=stories, site_name=app.config["SITE_NAME"])


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        unmatched=get_unmatched(),
        animals=get_animals(),
        instagram_ready=bool(os.getenv("INSTAGRAM_USER_ID") and os.getenv("INSTAGRAM_ACCESS_TOKEN")),
        site_name=app.config["SITE_NAME"],
    )


@app.post("/admin/assign/<int:story_id>")
def admin_assign(story_id):
    animal_id = request.form.get("animal_id", type=int)
    if animal_id:
        assign_story(story_id, animal_id)
        flash("해당 스토리를 동물 프로필에 연결했습니다.")
    return redirect(url_for("admin"))


@app.post("/admin/sync")
def admin_sync():
    try:
        result = sync_stories()
        flash(
            f"동기화 완료: 발견 {result['found']} / 새 저장 {result['saved']} / 자동분류 {result['matched']} / 미분류 {result['unmatched']}"
        )
        if result["errors"]:
            flash(f"일부 오류 {len(result['errors'])}건이 있습니다.")
    except Exception as exc:
        flash(f"동기화 실패: {exc}")
    return redirect(url_for("admin"))


def start_scheduler():
    if os.getenv("ENABLE_SCHEDULER", "0") != "1":
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        minutes = max(2, int(os.getenv("SYNC_INTERVAL_MINUTES", "10")))
        scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        scheduler.add_job(sync_stories, "interval", minutes=minutes, id="instagram-story-sync", max_instances=1)
        scheduler.start()
        print(f"[scheduler] Instagram story sync every {minutes} minutes")
    except Exception as exc:
        print(f"[scheduler] failed: {exc}")


init_db()
seed_demo()
if os.getenv("SEED_DEMO", "1") == "1":
    seed_demo_stories()
start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
