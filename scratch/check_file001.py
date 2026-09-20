import sys
sys.path.insert(0, 'C:/YT-SHORTS')
from core.database import get_connection
conn = get_connection()
# We'll not set row_factory to keep it as tuple for simplicity
conn.row_factory = None
cursor = conn.cursor()

# Get video with file_number = 1
cursor.execute('SELECT * FROM videos WHERE file_number = 1')
row = cursor.fetchone()
if row:
    # Convert to dict for easier access
    columns = [col[0] for col in cursor.description]
    video_dict = dict(zip(columns, row))
    print('VIDEO ROW:', video_dict)
    video_id = video_dict['id']
    title = video_dict['title']
    youtube_id = video_dict['youtube_video_id']
    print('Title:', title)
    print('YouTube ID:', youtube_id)
    
    # Analytics count
    cursor.execute('SELECT COUNT(*) AS cnt FROM analytics WHERE video_id = ?', (video_id,))
    analytics_row = cursor.fetchone()
    analytics_count = analytics_row[0] if analytics_row else 0
    print('Analytics rows:', analytics_count)
    
    # Provenance count
    cursor.execute('SELECT COUNT(*) AS cnt FROM provenance_assets WHERE video_id = ?', (video_id,))
    provenance_row = cursor.fetchone()
    provenance_count = provenance_row[0] if provenance_row else 0
    print('Provenance rows:', provenance_count)
else:
    print('No video with file_number=1 found')

conn.close()
