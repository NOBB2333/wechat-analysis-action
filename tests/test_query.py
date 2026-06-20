import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from query import WeChatDB, md5


class QueryMessageRenderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        os.makedirs(os.path.join(self.base, "message"))
        os.makedirs(os.path.join(self.base, "contact"))

        contact = sqlite3.connect(os.path.join(self.base, "contact", "contact.db"))
        contact.execute("CREATE TABLE contact (username TEXT, nick_name TEXT, remark TEXT)")
        contact.executemany(
            "INSERT INTO contact VALUES (?, ?, ?)",
            [
                ("wxid_alice", "AliceNick", "Alice"),
                ("wxid_bob", "BobNick", "Bob"),
            ],
        )
        contact.commit()
        contact.close()

        self.chat = "12345@chatroom"
        self.table = f"Msg_{md5(self.chat)}"
        self.msg_db = os.path.join(self.base, "message", "message_1.db")
        msg = sqlite3.connect(self.msg_db)
        msg.execute("CREATE TABLE Name2Id (user_name TEXT)")
        msg.execute("INSERT INTO Name2Id(rowid, user_name) VALUES (?, ?)", (8, "wxid_alice"))
        msg.execute("INSERT INTO Name2Id(rowid, user_name) VALUES (?, ?)", (9, "wxid_bob"))
        msg.execute(
            f'CREATE TABLE "{self.table}" ('
            "local_id INTEGER, local_type INTEGER, create_time INTEGER, "
            "real_sender_id INTEGER, message_content BLOB)"
        )
        msg.commit()
        msg.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _insert_message(self, local_id, local_type, sender_id, content):
        conn = sqlite3.connect(self.msg_db)
        conn.execute(
            f'INSERT INTO "{self.table}" VALUES (?, ?, ?, ?, ?)',
            (local_id, local_type, 1_700_000_000 + local_id, sender_id, content),
        )
        conn.commit()
        conn.close()

    def test_image_sender_uses_name2id_when_content_has_no_sender_prefix(self):
        self._insert_message(1, 3, 8, sqlite3.Binary(b"\xff\xfe\x00"))

        db = WeChatDB(self.base)
        try:
            messages = db.query_messages(self.chat)
            normalized = db.normalize_messages(messages)
        finally:
            db.close()

        self.assertEqual(normalized[0]["sender"], "Alice")
        self.assertEqual(normalized[0]["sender_id"], "wxid_alice")
        self.assertEqual(normalized[0]["text"], "[图片]")

    def test_empty_image_content_keeps_placeholder_and_sender(self):
        self._insert_message(1, 3, 8, None)

        db = WeChatDB(self.base)
        try:
            messages = db.query_messages(self.chat)
            normalized = db.normalize_messages(messages)
        finally:
            db.close()

        self.assertEqual(normalized[0]["sender"], "Alice")
        self.assertEqual(normalized[0]["text"], "[图片]")

    def test_quote_reply_renders_referenced_image_summary(self):
        quote = (
            "wxid_bob:\n"
            '<msg><appmsg><title>这张图看一下</title><type>57</type>'
            '<refermsg><type>3</type><fromusr>wxid_alice</fromusr>'
            '<displayname>Alice</displayname>'
            '<content>&lt;msg&gt;&lt;img cdnurl="leak"/&gt;&lt;/msg&gt;</content>'
            "</refermsg></appmsg></msg>"
        )
        self._insert_message(2, 49, 9, quote)

        db = WeChatDB(self.base)
        try:
            messages = db.query_messages(self.chat)
            normalized = db.normalize_messages(messages, include_system=True)
        finally:
            db.close()

        self.assertEqual(normalized[0]["sender"], "Bob")
        self.assertIn("这张图看一下", normalized[0]["text"])
        self.assertIn("回复 Alice: [图片]", normalized[0]["text"])


if __name__ == "__main__":
    unittest.main()
