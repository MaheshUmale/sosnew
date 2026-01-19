import threading
from data_sourcing.database_manager import DatabaseManager
import time

db_manager = DatabaseManager('sos_master_data.db')

def task(name):
    print(f"Thread {name} starting...")
    try:
        with db_manager as db:
            res = db.conn.execute("SELECT 1").fetchone()
            print(f"Thread {name} result: {res}")
            time.sleep(0.5)
    except Exception as e:
        print(f"Thread {name} ERROR: {e}")

threads = []
for i in range(5):
    t = threading.Thread(target=task, args=(f"T{i}",))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("All threads finished.")
