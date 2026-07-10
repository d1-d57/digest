#!/usr/bin/env python3
"""
Load final_batch_2_scores.json into materials.db
Update g1_breadth, g2_bridge, g3_clarity, g4_signif, g5_extract, score_total,
areas_multi, interdisc, read_note, content_read, scored_from='meta'
"""

import json
import sqlite3
from pathlib import Path

def main():
    db_path = Path('/Users/ivanyakovlev/Documents/GitHub/matemdigest-map/materials.db')
    scores_path = Path('/Users/ivanyakovlev/Documents/GitHub/matemdigest-map/final_batch_2_scores.json')

    # Read scores
    with open(scores_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    scores = data.get('batch_2', [])
    print(f"Read {len(scores)} scores from {scores_path.name}")

    # Connect to DB
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Update each score
    updated = 0
    skipped = 0

    for score in scores:
        article_id = score['id']
        
        # Check if article exists
        check = cur.execute("SELECT id FROM materials WHERE id = ?", (article_id,)).fetchone()
        if not check:
            print(f"  ⚠ ID {article_id} not in DB, skipping")
            skipped += 1
            continue

        # Update
        cur.execute("""
            UPDATE materials 
            SET g1_breadth = ?,
                g2_bridge = ?,
                g3_clarity = ?,
                g4_signif = ?,
                g5_extract = ?,
                score_total = ?,
                areas_multi = ?,
                interdisc = ?,
                read_note = ?,
                content_read = ?,
                scored_from = 'meta'
            WHERE id = ?
        """, (
            score.get('g1'),
            score.get('g2'),
            score.get('g3'),
            score.get('g4'),
            score.get('g5'),
            score.get('score_total'),
            score.get('areas_multi'),
            score.get('interdisc'),
            score.get('read_note'),
            score.get('content_read'),
            article_id
        ))
        updated += 1

    con.commit()
    con.close()

    print(f"✓ Updated {updated} scores")
    if skipped:
        print(f"⚠ Skipped {skipped} IDs (not in DB)")

    # Verify
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    with_scores = cur.execute("SELECT COUNT(*) FROM materials WHERE scored_from = 'meta'").fetchone()[0]
    con.close()

    print(f"✓ Total with scored_from='meta': {with_scores}")


if __name__ == '__main__':
    main()
