import sys
sys.path.insert(0, 'C:/YT-SHORTS')
from core.database import get_connection
conn = get_connection()
conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
cursor = conn.cursor()

print('=== Checking for videos with file_number 2,3,4,5 ===')
for fn in [2,3,4,5]:
    cursor.execute('SELECT * FROM videos WHERE file_number = ?', (fn,))
    rows = cursor.fetchall()
    if rows:
        print(f'File number {fn}: {len(rows)} rows')
        for row in rows:
            print(row)
    else:
        print(f'File number {fn}: no rows')

print('')
print('=== Checking for topics linked to videos with file_number 2,3,4,5 ===')
cursor.execute('''
    SELECT t.* FROM topics t
    JOIN videos v ON t.id = v.topic_id
    WHERE v.file_number IN (2,3,4,5)
''')
rows = cursor.fetchall()
if rows:
    print(f'Topics linked to file numbers 2-5: {len(rows)} rows')
    for row in rows:
        print(row)
else:
    print('No topics linked to file numbers 2-5')

print('')
print('=== Checking content_memory for file_number 2,3,4,5 ===')
for fn in [2,3,4,5]:
    cursor.execute('SELECT * FROM content_memory WHERE file_number = ?', (fn,))
    rows = cursor.fetchall()
    if rows:
        print(f'Content memory for file number {fn}: {len(rows)} rows')
        for row in rows:
            print(row)
    else:
        print(f'No content memory for file number {fn}')

print('')
print('=== Checking for negative file_number in videos ===')
cursor.execute('SELECT * FROM videos WHERE file_number < 0')
rows = cursor.fetchall()
if rows:
    print(f'Negative file_number rows: {len(rows)}')
    for row in rows:
        print(row)
else:
    print('No negative file_number rows')

print('')
print('=== Checking for topics with status archived_test ===')
cursor.execute('SELECT * FROM topics WHERE status = \"archived_test\"')
rows = cursor.fetchall()
if rows:
    print(f'Topics with status archived_test: {len(rows)}')
    for row in rows:
        print(row)
else:
    print('No topics with status archived_test')

print('')
print('=== Checking for dangling video_path (NULL or empty) ===')
cursor.execute('SELECT * FROM videos WHERE video_path IS NULL OR video_path = \"\"')
rows = cursor.fetchall()
if rows:
    print(f'Dangling video_path rows: {len(rows)}')
    for row in rows:
        print(row)
else:
    print('No dangling video_path rows')

print('')
print('=== Checking dynamic_weights table ===')
cursor.execute('SELECT * FROM dynamic_weights')
rows = cursor.fetchall()
if rows:
    print(f'Dynamic weights rows: {len(rows)}')
    for row in rows:
        print(row)
else:
    print('No dynamic weights rows')

print('')
print('=== Checking for test-like topics (title containing test, tunguska, check, etc.) ===')
cursor.execute('''
    SELECT * FROM topics 
    WHERE title LIKE \"%test%\" 
       OR title LIKE \"%tunguska%\"
       OR title LIKE \"%check%\"
       OR title LIKE \"%verify%\"
       OR title LIKE \"%dryrun%\"
       OR title LIKE \"%validation%\"
       OR title LIKE \"%db_output%\"
       OR title LIKE \"%output%\"
''')
rows = cursor.fetchall()
if rows:
    print(f'Test-like topics: {len(rows)}')
    for row in rows:
        print(row)
else:
    print('No test-like topics found')

conn.close()
