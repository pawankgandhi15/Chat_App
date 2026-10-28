"""Durable accounts and direct conversations. Blocking work runs in bounded workers.

PostgreSQL is the deployment database; file-backed SQLite is a local/test option.
Only schema version 1 is supported. Run `python -m app.migrate` before serving.
"""
import hashlib
import hmac
import secrets
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import (Column, ForeignKey, Integer, MetaData, String, Table, Text,
                        UniqueConstraint, CheckConstraint, create_engine, event,
                        select, or_, update, delete, text)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from .protocol import timestamp

metadata = MetaData()
versions = Table("schema_version", metadata, Column("version", Integer, primary_key=True))
users = Table("accounts", metadata,
    Column("id", String(36), primary_key=True),
    Column("username", String(32), nullable=False, unique=True),
    Column("password_hash", String(200), nullable=False),
    Column("created_at", String(24), nullable=False))
sessions = Table("account_sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", ForeignKey("accounts.id"), nullable=False, index=True),
    Column("expires_at", Integer, nullable=False, index=True))
conversations = Table("conversations", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_a", ForeignKey("accounts.id"), nullable=False, index=True),
    Column("user_b", ForeignKey("accounts.id"), nullable=False, index=True),
    Column("last_seq", Integer, nullable=False, default=0),
    Column("updated_at", String(24), nullable=False),
    UniqueConstraint("user_a", "user_b"), CheckConstraint("user_a < user_b"))
messages = Table("saved_messages", metadata,
    Column("id", String(36), primary_key=True),
    Column("conversation_id", ForeignKey("conversations.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("sender_id", ForeignKey("accounts.id"), nullable=False),
    Column("client_id", String(36), nullable=False),
    Column("text", Text, nullable=False),
    Column("sent_at", String(24), nullable=False),
    UniqueConstraint("conversation_id", "seq"),
    UniqueConstraint("sender_id", "client_id"))
limits = Table("account_rate_limits", metadata,
    Column("key", String(64), primary_key=True),
    Column("window", Integer, primary_key=True),
    Column("count", Integer, nullable=False))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64 * 1024 * 1024)
    return "scrypt32768r8p3$" + salt + "$" + key.hex()


class Storage:
    def __init__(self, url, session_days=7):
        self.session_days = session_days
        self.sqlite = url.startswith("sqlite:")
        self.engine = create_engine(url, pool_pre_ping=True, pool_size=4, max_overflow=0,
            pool_timeout=3, hide_parameters=True,
            connect_args={"check_same_thread": False, "timeout": 5} if self.sqlite else
                         {"connect_timeout": 5, "options": "-c statement_timeout=5000 -c lock_timeout=3000"})
        if self.sqlite:
            @event.listens_for(self.engine, "connect")
            def sqlite_config(db, _):
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("PRAGMA journal_mode=WAL")
        self.insert = sqlite_insert if self.sqlite else pg_insert
        self.dummy_hash = password_hash("dummy-password-never-used")

    def migrate(self):
        with self.engine.begin() as db:
            if not self.sqlite:
                db.execute(text("SELECT pg_advisory_xact_lock(72410628)"))
            # Serializes first-time initialization across PostgreSQL replicas.
            metadata.create_all(db)
            existing = db.execute(select(versions.c.version)).scalars().all()
            if existing and existing != [1]:
                raise RuntimeError("Unsupported database schema version")
            db.execute(self.insert(versions).values(version=1).on_conflict_do_nothing())

    def check(self):
        with self.engine.connect() as db:
            if db.execute(select(versions.c.version)).scalars().all() != [1]:
                raise RuntimeError("Run the database migration before starting the app")
        return True

    def throttle(self, key, maximum, seconds):
        now = int(time.time())
        window = now // seconds * seconds
        with self.engine.begin() as db:
            db.execute(delete(limits).where(limits.c.window < now - 3600))
            stmt = self.insert(limits).values(key=digest(key), window=window, count=1)
            count = db.execute(stmt.on_conflict_do_update(
                index_elements=[limits.c.key, limits.c.window],
                set_={"count": limits.c.count + 1}).returning(limits.c.count)).scalar_one()
        if count > maximum:
            raise HTTPException(429, "Too many requests. Try again later.", headers={"Retry-After": str(seconds)})

    def _session(self, db, user_id):
        now = int(time.time())
        db.execute(delete(sessions).where(sessions.c.expires_at <= now))
        # Keep a bounded number of active sessions per account.
        old = db.execute(select(sessions.c.token_hash).where(sessions.c.user_id == user_id)
                         .order_by(sessions.c.expires_at.desc()).offset(9)).scalars().all()
        if old:
            db.execute(delete(sessions).where(sessions.c.token_hash.in_(old)))
        token = secrets.token_urlsafe(32)
        db.execute(sessions.insert().values(token_hash=digest(token), user_id=user_id,
                   expires_at=now + self.session_days * 86400))
        return token

    def register(self, username, password):
        user = {"id": str(uuid4()), "username": username.lower()}
        hashed = password_hash(password)
        try:
            with self.engine.begin() as db:
                db.execute(users.insert().values(**user, password_hash=hashed, created_at=timestamp()))
                token = self._session(db, user["id"])
        except IntegrityError:
            raise HTTPException(409, "That username is unavailable.") from None
        return user, token

    def login(self, username, password):
        with self.engine.begin() as db:
            user = db.execute(select(users).where(users.c.username == username.lower()).with_for_update()).mappings().first()
            stored = user["password_hash"] if user else self.dummy_hash
            valid = hmac.compare_digest(stored, password_hash(password, stored.split("$")[1]))
            if not valid or not user:
                raise HTTPException(401, "Incorrect username or password.")
            token = self._session(db, user["id"])
            return {"id": user["id"], "username": user["username"]}, token

    def _user(self, db, token):
        if not token or len(token) > 128:
            raise HTTPException(401, "Sign in to continue.")
        user = db.execute(select(users.c.id, users.c.username).join(sessions, sessions.c.user_id == users.c.id)
            .where(sessions.c.token_hash == digest(token), sessions.c.expires_at > int(time.time()))).mappings().first()
        if not user:
            raise HTTPException(401, "Your session has expired. Sign in again.")
        return dict(user)

    def me(self, token):
        with self.engine.connect() as db:
            return self._user(db, token)

    def logout(self, token):
        with self.engine.begin() as db:
            db.execute(delete(sessions).where(sessions.c.token_hash == digest(token or "")))

    def search(self, token, query):
        with self.engine.connect() as db:
            user = self._user(db, token)
            # Escape LIKE wildcards: underscores are valid username characters.
            query = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            return [dict(row) for row in db.execute(select(users.c.id, users.c.username)
                .where(users.c.id != user["id"], users.c.username.like(query + "%", escape="\\"))
                .order_by(users.c.username).limit(20)).mappings()]

    def open_conversation(self, token, target):
        with self.engine.begin() as db:
            user = self._user(db, token)
            if target == user["id"]:
                raise HTTPException(400, "Choose another account.")
            if not db.execute(select(users.c.id).where(users.c.id == target)).first():
                raise HTTPException(404, "Account not found.")
            a, b = sorted([user["id"], target])
            db.execute(self.insert(conversations).values(id=str(uuid4()), user_a=a, user_b=b,
                last_seq=0, updated_at=timestamp()).on_conflict_do_nothing(index_elements=["user_a", "user_b"]))
            return dict(db.execute(select(conversations).where(conversations.c.user_a == a,
                conversations.c.user_b == b)).mappings().one())

    def list_conversations(self, token, after=None):
        with self.engine.connect() as db:
            user = self._user(db, token)
            statement = select(conversations).where(or_(conversations.c.user_a == user["id"], conversations.c.user_b == user["id"]))
            if after:
                statement = statement.where(conversations.c.id > after)
            rows = db.execute(statement.order_by(conversations.c.id).limit(51)).mappings().all()
            result = []
            peer_ids = {r["user_b"] if r["user_a"] == user["id"] else r["user_a"] for r in rows[:50]}
            peers = {r.id: r.username for r in db.execute(select(users.c.id, users.c.username).where(users.c.id.in_(peer_ids)))}
            for row in rows[:50]:
                peer_id = row["user_b"] if row["user_a"] == user["id"] else row["user_a"]
                result.append({"id": row["id"], "peer": {"id": peer_id, "username": peers[peer_id]},
                               "last_seq": row["last_seq"], "updated_at": row["updated_at"]})
            return {"items": result, "next_cursor": rows[49]["id"] if len(rows) > 50 else None}

    def _conversation(self, db, user_id, conversation_id):
        row = db.execute(select(conversations).where(conversations.c.id == conversation_id,
            or_(conversations.c.user_a == user_id, conversations.c.user_b == user_id))).mappings().first()
        if not row:
            raise HTTPException(404, "Conversation not found.")
        return row

    def history(self, token, conversation_id, before=None):
        with self.engine.connect() as db:
            user = self._user(db, token)
            self._conversation(db, user["id"], conversation_id)
            stmt = select(messages).where(messages.c.conversation_id == conversation_id)
            if before is not None:
                stmt = stmt.where(messages.c.seq < before)
            rows = db.execute(stmt.order_by(messages.c.seq.desc()).limit(51)).mappings().all()
            return {"items": [dict(row) for row in reversed(rows[:50])],
                    "next_before": rows[49]["seq"] if len(rows) > 50 else None}

    def send(self, token, conversation_id, client_id, body):
        with self.engine.begin() as db:
            user = self._user(db, token)
            conversation = self._conversation(db, user["id"], conversation_id)
            # Serialize writers for this conversation, including duplicate requests.
            seq = db.execute(update(conversations).where(conversations.c.id == conversation_id)
                .values(last_seq=conversations.c.last_seq + 1).returning(conversations.c.last_seq)).scalar_one()
            old = db.execute(select(messages).where(messages.c.sender_id == user["id"], messages.c.client_id == client_id)).mappings().first()
            if old:
                db.execute(update(conversations).where(conversations.c.id == conversation_id).values(last_seq=seq - 1))
                if old["conversation_id"] != conversation_id or old["text"] != body:
                    raise HTTPException(409, "This request ID was already used for another message.")
                return dict(old), [conversation["user_a"], conversation["user_b"]]
            row = {"id": str(uuid4()), "conversation_id": conversation_id, "seq": seq,
                   "sender_id": user["id"], "client_id": client_id, "text": body, "sent_at": timestamp()}
            try:
                db.execute(messages.insert().values(**row))
            except IntegrityError:
                # Cross-conversation reuse racing another transaction is also rejected.
                raise HTTPException(409, "This request ID was already used.") from None
            db.execute(update(conversations).where(conversations.c.id == conversation_id).values(updated_at=row["sent_at"]))
            return row, [conversation["user_a"], conversation["user_b"]]
