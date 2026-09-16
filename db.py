import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "shelter.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS animals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                species TEXT NOT NULL DEFAULT '강아지',
                sex TEXT DEFAULT '',
                age_text TEXT DEFAULT '',
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT '보호중',
                cover_image TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS story_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instagram_story_id TEXT UNIQUE,
                animal_id INTEGER,
                media_type TEXT NOT NULL DEFAULT 'IMAGE',
                local_path TEXT NOT NULL,
                source_url TEXT DEFAULT '',
                permalink TEXT DEFAULT '',
                ocr_text TEXT DEFAULT '',
                match_reason TEXT DEFAULT '',
                confidence REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(animal_id) REFERENCES animals(id)
            );
            """
        )


def seed_demo():
    animals = [
        ("뚜뚜", "강아지", "남아", "5살 추정", "사람을 좋아하고 산책을 무척 좋아해요.", "보호중", ""),
        ("몽이", "강아지", "여아", "3살 추정", "조금 낯을 가리지만 친해지면 애교가 많아요.", "보호중", ""),
        ("나비", "고양이", "여아", "2살 추정", "조용하고 창가에서 쉬는 걸 좋아해요.", "보호중", ""),
    ]
    with connect() as conn:
        for row in animals:
            conn.execute(
                """INSERT OR IGNORE INTO animals
                (name, species, sex, age_text, description, status, cover_image)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                row,
            )


def get_animals():
    with connect() as conn:
        return conn.execute(
            """
            SELECT a.*,
                   COUNT(s.id) AS story_count,
                   MAX(s.created_at) AS last_update
            FROM animals a
            LEFT JOIN story_media s ON s.animal_id = a.id
            GROUP BY a.id
            ORDER BY a.id
            """
        ).fetchall()


def get_animal(animal_id):
    with connect() as conn:
        animal = conn.execute("SELECT * FROM animals WHERE id = ?", (animal_id,)).fetchone()
        stories = conn.execute(
            "SELECT * FROM story_media WHERE animal_id = ? ORDER BY created_at DESC",
            (animal_id,),
        ).fetchall()
        return animal, stories


def get_animal_names():
    with connect() as conn:
        return conn.execute("SELECT id, name FROM animals ORDER BY length(name) DESC").fetchall()


def get_unmatched():
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM story_media WHERE animal_id IS NULL ORDER BY created_at DESC"
        ).fetchall()


def story_exists(story_id):
    with connect() as conn:
        return conn.execute(
            "SELECT 1 FROM story_media WHERE instagram_story_id = ?", (story_id,)
        ).fetchone() is not None


def insert_story(story):
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO story_media
            (instagram_story_id, animal_id, media_type, local_path, source_url,
             permalink, ocr_text, match_reason, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                story["instagram_story_id"],
                story.get("animal_id"),
                story.get("media_type", "IMAGE"),
                story["local_path"],
                story.get("source_url", ""),
                story.get("permalink", ""),
                story.get("ocr_text", ""),
                story.get("match_reason", ""),
                story.get("confidence", 0),
                story["created_at"],
            ),
        )


def assign_story(story_id, animal_id):
    with connect() as conn:
        conn.execute(
            "UPDATE story_media SET animal_id = ?, match_reason = '관리자 수동 분류', confidence = 1 WHERE id = ?",
            (animal_id, story_id),
        )


def add_demo_story(story_id, animal_id, local_path, text, created_at):
    insert_story(
        {
            "instagram_story_id": story_id,
            "animal_id": animal_id,
            "media_type": "IMAGE",
            "local_path": local_path,
            "ocr_text": text,
            "match_reason": "데모 데이터",
            "confidence": 1,
            "created_at": created_at,
        }
    )
