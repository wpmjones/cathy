import creds
import psycopg2

from loguru import logger


def get_db():
    conn = psycopg2.connect(host=creds.pg_host,
                            dbname=creds.pg_name,
                            user=creds.pg_user,
                            password=creds.pg_pass)
    conn.set_session(autocommit=True)
    return conn


class Recipients:
    def __init__(self, id_, name, phone, store, position):
        self.id = id_
        self.name = name
        self.phone = phone
        self.store = store
        self.position = position

    @staticmethod
    def create(first, last, phone, store_id, position_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO cfa_recipients "
                               "(first_name, last_name, phone, store_id, position_id) "
                               "VALUES (%s, %s, %s, %s, %s) "
                               "RETURNING id", [first, last, phone, store_id, position_id])
                new_id = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"Recipient {first} {last} successfully added to database.")
        return new_id

    @staticmethod
    def get(id_):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT first_name, last_name, recipients.phone, store_name, positions.name "
                               "FROM cfa_recipients recipients "
                               "INNER JOIN cfa_stores stores ON stores.store_id = recipients.store_id "
                               "INNER JOIN cfa_positions positions ON positions.position_id = recipients.position_id "
                               "WHERE recipient_id = %s",
                               [id_])
                recipient = cursor.fetchone()
                name = f"{recipient[0]} {recipient[1]}"
                phone = recipient[2]
                store = recipient[3]
                position = recipient[4]
                recipient = Recipients(
                    id_=id_,
                    name=name,
                    phone=phone,
                    store=store,
                    position=position
                )
        cursor.close()
        conn.close()
        return recipient

    @staticmethod
    def update(id_, first, last, phone, store_id, position_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE cfa_recipients "
                               "SET first_name = %s, phone = %s, store_id = %s, position_id = %s "
                               "WHERE id = %s",
                               [first, last, phone, store_id, position_id, id_])
        cursor.close()
        conn.close()
        logger.info(f"Recipient {first} {last} updated.")

    @staticmethod
    def remove(id_):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM cfa_recipients WHERE recipient_id = %s",
                               [id_])
        cursor.close()
        conn.close()
        logger.info(f"Recipient {id_} removed from database.")


class Messages:
    @staticmethod
    def add_message(sid, recipient_id, store_id, message):
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = ("INSERT INTO cfa_messages "
                       "(sid, recipient_id, store_id, message) "
                       "VALUES (%s, %s, %s, %s)")
                cursor.execute(sql, [sid, recipient_id, store_id, message])
        cursor.close()
        conn.close()
