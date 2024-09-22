import uuid

def generate_uid(query):
    return query + '_' + str(uuid.uuid4())