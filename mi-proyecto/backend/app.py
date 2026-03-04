import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "db.json"

MAX_EMAIL_LENGTH = 120
MAX_PASSWORD_LENGTH = 128
MIN_PASSWORD_LENGTH = 6
MAX_NOTE_TITLE_LENGTH = 120
MAX_NOTE_CONTENT_LENGTH = 5000

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ALLOWED_ORIGINS = {
   "http://localhost:8080",
   "http://127.0.0.1:8080",
}


def utc_now_iso() -> str:
   return datetime.now(timezone.utc).isoformat()


def empty_db():
   return {
      "users": [],
      "notes": [],
      "nextUserId": 1,
      "nextNoteId": 1,
   }


def load_db():
   DATA_DIR.mkdir(parents=True, exist_ok=True)

   if not DB_PATH.exists():
      data = empty_db()
      save_db(data)
      return data

   try:
      with DB_PATH.open("r", encoding="utf-8") as file:
         data = json.load(file)
   except (json.JSONDecodeError, OSError):
      data = empty_db()
      save_db(data)
      return data

   data.setdefault("users", [])
   data.setdefault("notes", [])
   data.setdefault("nextUserId", 1)
   data.setdefault("nextNoteId", 1)
   return data


def save_db(data):
   with DB_PATH.open("w", encoding="utf-8") as file:
      json.dump(data, file, ensure_ascii=False, indent=2)


def error_response(message: str, status: int):
   return jsonify({"error": message}), status


def get_current_user_id():
   user_id = session.get("user_id")
   return user_id if isinstance(user_id, int) else None


def require_auth():
   user_id = get_current_user_id()
   if user_id is None:
      return None, error_response("Debes iniciar sesión", 401)
   return user_id, None


def find_user_by_email(data, email):
   for user in data["users"]:
      if user["email"].lower() == email.lower():
         return user
   return None


def public_user(user):
   return {
      "id": user["id"],
      "email": user["email"],
      "created_at": user["created_at"],
   }


def public_note(note):
   return {
      "id": note["id"],
      "title": note["title"],
      "content": note["content"],
      "created_at": note["created_at"],
      "updated_at": note["updated_at"],
   }


@app.before_request
def handle_preflight():
   if request.method == "OPTIONS":
      return ("", 204)


@app.after_request
def add_cors_headers(response):
   origin = request.headers.get("Origin")
   if origin in ALLOWED_ORIGINS:
      response.headers["Access-Control-Allow-Origin"] = origin
      response.headers["Access-Control-Allow-Credentials"] = "true"
      response.headers["Access-Control-Allow-Headers"] = "Content-Type"
      response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
      response.headers["Vary"] = "Origin"
   return response


@app.get("/")
def health():
   return jsonify(
      {
         "message": "API Flask de Notas Privadas activa",
         "routes": {
               "register": "POST /api/auth/register",
               "login": "POST /api/auth/login",
               "logout": "POST /api/auth/logout",
               "me": "GET /api/auth/me",
               "notes": "CRUD /api/notes",
         },
      }
   )


@app.post("/api/auth/register")
def register():
   payload = request.get_json(silent=True) or {}
   email = str(payload.get("email", "")).strip().lower()
   password = str(payload.get("password", ""))
   confirm_password = str(payload.get("confirm_password", ""))

   if not email or "@" not in email or len(email) > MAX_EMAIL_LENGTH:
      return error_response("Email inválido", 400)

   if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
      return error_response("La contraseña debe tener entre 6 y 128 caracteres", 400)

   if password != confirm_password:
      return error_response("Las contraseñas no coinciden", 400)

   data = load_db()
   if find_user_by_email(data, email):
      return error_response("Ese email ya está registrado", 409)

   user = {
      "id": data["nextUserId"],
      "email": email,
      "password": generate_password_hash(password),
      "created_at": utc_now_iso(),
   }

   data["users"].append(user)
   data["nextUserId"] += 1
   save_db(data)

   session["user_id"] = user["id"]
   return jsonify({"message": "Usuario registrado", "user": public_user(user)}), 201


@app.post("/api/auth/login")
def login():
   payload = request.get_json(silent=True) or {}
   email = str(payload.get("email", "")).strip().lower()
   password = str(payload.get("password", ""))

   if not email or not password:
      return error_response("Email y contraseña son obligatorios", 400)

   data = load_db()
   user = find_user_by_email(data, email)

   if not user or not check_password_hash(user["password"], password):
      return error_response("Credenciales inválidas", 401)

   session["user_id"] = user["id"]
   return jsonify({"message": "Sesión iniciada", "user": public_user(user)})


@app.post("/api/auth/logout")
def logout():
   session.clear()
   return jsonify({"message": "Sesión cerrada"})


@app.get("/api/auth/me")
def me():
   user_id, auth_error = require_auth()
   if auth_error:
      return auth_error

   data = load_db()
   user = next((candidate for candidate in data["users"] if candidate["id"] == user_id), None)
   if not user:
      session.clear()
      return error_response("Sesión inválida", 401)

   return jsonify({"user": public_user(user)})


@app.get("/api/notes")
def list_notes():
   user_id, auth_error = require_auth()
   if auth_error:
      return auth_error

   data = load_db()
   notes = [
      public_note(note)
      for note in data["notes"]
      if note["user_id"] == user_id
   ]
   notes.sort(key=lambda note: note["created_at"], reverse=True)
   return jsonify(notes)


@app.get("/api/notes/<int:note_id>")
def get_note(note_id: int):
   user_id, auth_error = require_auth()
   if auth_error:
      return auth_error

   data = load_db()
   note = next((item for item in data["notes"] if item["id"] == note_id), None)
   if not note:
      return error_response("Nota no encontrada", 404)

   if note["user_id"] != user_id:
      return error_response("No tienes permiso para ver esta nota", 403)

   return jsonify(public_note(note))


@app.post("/api/notes")
def create_note():
   user_id, auth_error = require_auth()
   if auth_error:
      return auth_error

   payload = request.get_json(silent=True) or {}
   title = str(payload.get("title", "")).strip()
   content = str(payload.get("content", "")).strip()

   if not title or len(title) > MAX_NOTE_TITLE_LENGTH:
      return error_response("Título inválido", 400)

   if not content or len(content) > MAX_NOTE_CONTENT_LENGTH:
      return error_response("Contenido inválido", 400)

   data = load_db()
   timestamp = utc_now_iso()
   note = {
      "id": data["nextNoteId"],
      "user_id": user_id,
      "title": title,
      "content": content,
      "created_at": timestamp,
      "updated_at": timestamp,
   }

   data["notes"].append(note)
   data["nextNoteId"] += 1
   save_db(data)

   return jsonify({"message": "Nota creada", "note": public_note(note)}), 201


@app.put("/api/notes/<int:note_id>")
def update_note(note_id: int):
   user_id, auth_error = require_auth()
   if auth_error:
      return auth_error

   payload = request.get_json(silent=True) or {}
   title = str(payload.get("title", "")).strip()
   content = str(payload.get("content", "")).strip()

   if not title or len(title) > MAX_NOTE_TITLE_LENGTH:
      return error_response("Título inválido", 400)

   if not content or len(content) > MAX_NOTE_CONTENT_LENGTH:
      return error_response("Contenido inválido", 400)

   data = load_db()
   note = next((item for item in data["notes"] if item["id"] == note_id), None)

   if not note:
      return error_response("Nota no encontrada", 404)

   if note["user_id"] != user_id:
      return error_response("No tienes permiso para editar esta nota", 403)

   note["title"] = title
   note["content"] = content
   note["updated_at"] = utc_now_iso()
   save_db(data)

   return jsonify({"message": "Nota actualizada", "note": public_note(note)})


@app.delete("/api/notes/<int:note_id>")
def delete_note(note_id: int):
   user_id, auth_error = require_auth()
   if auth_error:
      return auth_error

   data = load_db()
   note_index = next((i for i, item in enumerate(data["notes"]) if item["id"] == note_id), -1)

   if note_index == -1:
      return error_response("Nota no encontrada", 404)

   note = data["notes"][note_index]
   if note["user_id"] != user_id:
      return error_response("No tienes permiso para eliminar esta nota", 403)

   data["notes"].pop(note_index)
   save_db(data)

   return jsonify({"message": "Nota eliminada"})


@app.errorhandler(404)
def not_found(_error):
   return error_response("Ruta no encontrada", 404)


@app.errorhandler(405)
def method_not_allowed(_error):
   return error_response("Método no permitido", 405)


@app.errorhandler(500)
def internal_error(_error):
   return error_response("Error interno del servidor", 500)


if __name__ == "__main__":
   app.run(host="0.0.0.0", port=3000, debug=False)
