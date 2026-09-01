"""Verify that all ClipForge tables exist in the database."""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("DATABASE_URL_SYNC", "").replace("postgresql+psycopg2://", "postgresql://")
conn = psycopg2.connect(url)
cur = conn.cursor()

# List all public tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
print("Tables in public schema:")
for t in tables:
    print(f"  - {t}")

expected = {"users", "campaign_briefs", "projects", "clips", "jobs"}
found = expected.intersection(set(tables))
missing = expected - found

print(f"\nExpected: {len(expected)} | Found: {len(found)} | Missing: {len(missing)}")
if missing:
    print(f"MISSING TABLES: {missing}")
else:
    print("All ClipForge tables present.")

# Check columns on projects table as a spot check
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'projects' AND table_schema = 'public'
    ORDER BY ordinal_position
""")
print("\nProjects table columns:")
for col in cur.fetchall():
    print(f"  {col[0]:25s} {col[1]:20s} nullable={col[2]}")

# Check indexes
cur.execute("""
    SELECT indexname FROM pg_indexes
    WHERE schemaname = 'public' AND indexname LIKE 'idx_%'
    ORDER BY indexname
""")
print("\nCustom indexes:")
for idx in cur.fetchall():
    print(f"  - {idx[0]}")

cur.close()
conn.close()
