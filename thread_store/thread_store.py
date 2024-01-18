import shelve

def check_if_thread_exists(lookup_id):
    lookup_id_str = str(lookup_id)  # Convert lookup_id to string
    with shelve.open("threads_db") as threads_shelf:
        return threads_shelf.get(lookup_id_str, None)

def store_thread(lookup_id, thread_id):
    lookup_id_str = str(lookup_id)  # Convert lookup_id to string
    with shelve.open("threads_db", writeback=True) as threads_shelf:
        threads_shelf[lookup_id_str] = thread_id
