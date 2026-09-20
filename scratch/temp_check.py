import sqlite3
backup_db = "C:/YT-SHORTS-BACKUP/20260919_220327/nexus.db"
conn = sqlite3.connect(backup_db)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get video with file_number = 1
cursor.execute("SELECT * FROM videos WHERE file_number = 1")
row = cursor.fetchone()
if row:
    print("VIDEO ROW:", dict(row))
    video_id = row["id"]
    title = row["title"]
    youtube_id = row["youtube_video_id"]
    print("Title:", title)
    print("YouTube ID:", youtube_id)
    
    # Analytics count
    cursor.execute("SELECT COUNT(*) FROM analytics WHERE video_id = ?", (video_id,))
    analytics_count = cursor.fetchone()[0]
    print("Analytics rows:", analytics_count)
    
    # Provenance count
    cursor.execute("SELECT COUNT(*) FROM provenance_assets WHERE video_id = ?", (video_id,))
    provenance_count = cursor.fetchone()[0]
    print("Provenance rows:", provenance_count)
else:
    print("No video with file_number=1 found")

conn.close()
