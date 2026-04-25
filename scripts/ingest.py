#!/usr/bin/env python3
"""
ingest.py — Called by ingestor agent.
Usage: printf '%s' '<json_array>' | python3 scripts/ingest.py
Reads JSON array from stdin, inserts into Supabase.
"""

import sys
import json
import os
from urllib.parse import urlparse
from datetime import date
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL")

# Ensure sslmode is set
if "?" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL + "?sslmode=require"

IOC_TYPE_MAP = {
    "upi_id": "upi_id",
    "phone": "phone_number",
    "phone_number": "phone_number",
    "url": "url",
    "telegram_id": "telegram_id",
    "email": "email",
    "app_name": "app_name",
}

SOURCE_TYPE_MAP = {
    "reddit.com": "social_media",
    "twitter.com": "social_media",
    "x.com": "social_media",
    "consumercomplaints.in": "complaint_portal",
    "consumerhelpline.gov.in": "government",
    "pgportal.gov.in": "government",
    "timesofindia.com": "news",
    "hindustantimes.com": "news",
    "ndtv.com": "news",
    "thehindu.com": "news",
}


def get_or_create_connection():
    """Get a fresh database connection with retry logic."""
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)


def get_source_type(source_url):
    from urllib.parse import urlparse
    domain = urlparse(source_url).netloc.lower()
    return SOURCE_TYPE_MAP.get(domain, "research")


def get_source_name_from_url(source_url):
    """Extract a reasonable name from source URL."""
    from urllib.parse import urlparse
    parsed = urlparse(source_url)
    domain = parsed.netloc.lower()
    
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    
    return domain


def upsert_source(cur, source_url):
    if not source_url:
        return None
    source_type = get_source_type(source_url)
    source_name = get_source_name_from_url(source_url)
    
    # First try to get existing
    cur.execute("SELECT source_id FROM sources WHERE source_url = %s", (source_url,))
    row = cur.fetchone()
    if row:
        return row[0]
    
    # If not exists, insert new
    cur.execute("""
        INSERT INTO sources (source_name, source_url, source_type)
        VALUES (%s, %s, %s)
        RETURNING source_id
    """, (source_name, source_url, source_type))
    return cur.fetchone()[0]


def upsert_red_flag(cur, name, description):
    if not name:
        return None
    
    # First try to get existing by ID (name is the ID)
    cur.execute("SELECT red_flag_id FROM red_flags WHERE red_flag_id = %s", (name,))
    row = cur.fetchone()
    if row:
        # Increment scenario count
        cur.execute("""
            UPDATE red_flags SET scenario_count = scenario_count + 1
            WHERE red_flag_id = %s
        """, (name,))
        return row[0]
    
    # If not exists, insert new
    # Use name as red_flag_id
    cur.execute("""
        INSERT INTO red_flags (red_flag_id, red_flag_name, description, scenario_count)
        VALUES (%s, %s, %s, 1)
        RETURNING red_flag_id
    """, (name, name, description or name))
    return cur.fetchone()[0]


def upsert_mechanism(cur, name, description):
    if not name:
        return None
    
    # First try to get existing
    cur.execute("SELECT mechanism_id FROM mechanisms WHERE mechanism_id = %s", (name,))
    row = cur.fetchone()
    if row:
        # Increment scenario count
        cur.execute("""
            UPDATE mechanisms SET scenario_count = scenario_count + 1
            WHERE mechanism_id = %s
        """, (name,))
        return row[0]
    
    # If not exists, insert new
    # Use name as mechanism_id
    cur.execute("""
        INSERT INTO mechanisms (mechanism_id, mechanism_name, description, scenario_count)
        VALUES (%s, %s, %s, 1)
        RETURNING mechanism_id
    """, (name, name, description or name))
    return cur.fetchone()[0]


def upsert_scam_type(cur, type_id, type_name):
    if not type_id:
        return None
    
    # Try to insert, ignore if exists
    cur.execute("""
        INSERT INTO scam_types (type_id, type_name)
        VALUES (%s, %s)
        ON CONFLICT (type_id) DO NOTHING
    """, (type_id, type_name or type_id))
    return type_id


def upsert_ioc(cur, ioc_type, ioc_value):
    ioc_type_db = IOC_TYPE_MAP.get(ioc_type)
    if not ioc_type_db or not ioc_value:
        return None
    
    # Try to update first
    cur.execute("""
        UPDATE iocs SET report_count = report_count + 1, last_seen = NOW()
        WHERE ioc_type = %s::ioc_type_enum AND ioc_value = %s
        RETURNING ioc_id
    """, (ioc_type_db, ioc_value))
    row = cur.fetchone()
    if row:
        return row[0]
    
    # If not exists, insert new
    cur.execute("""
        INSERT INTO iocs (ioc_type, ioc_value, is_scam, report_count, first_seen, last_seen)
        VALUES (%s::ioc_type_enum, %s, true, 1, NOW(), NOW())
        RETURNING ioc_id
    """, (ioc_type_db, ioc_value))
    return cur.fetchone()[0]


def insert_record(cur, record):
    raw_text = record.get("raw_text")
    if not raw_text:
        return None, "raw_text is null"

    # Determine scenario_type from scam_type field
    scam_type = record.get("scam_type")
    type_id = scam_type.get("type_id") if isinstance(scam_type, dict) else None
    scenario_type_arr = [type_id] if type_id else []

    cur.execute("""
        INSERT INTO scenarios (raw_text, summary, scenario_type, loss_amount, is_scam, is_synthetic, importance_score)
        VALUES (%s, %s, %s::varchar[], %s, %s, false, 0.5)
        RETURNING scenario_id
    """, (
        raw_text,
        record.get("summary"),
        scenario_type_arr,
        record.get("loss_amount"),
        record.get("is_scam"),
    ))
    scenario_id = cur.fetchone()[0]

    # Insert IOCs
    iocs = record.get("iocs", [])
    if isinstance(iocs, list):
        for ioc in iocs:
            ioc_id = upsert_ioc(cur, ioc.get("type"), ioc.get("value"))
            if ioc_id:
                # Check if link exists
                cur.execute("""
                    SELECT 1 FROM scenario_iocs WHERE scenario_id = %s AND ioc_id = %s
                """, (scenario_id, ioc_id))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO scenario_iocs (scenario_id, ioc_id)
                        VALUES (%s, %s)
                    """, (scenario_id, ioc_id))

    # Insert source
    source_url = record.get("source_url")
    if source_url:
        source_id = upsert_source(cur, source_url)
        if source_id:
            date_reported = record.get("date_reported")
            # Check if link exists
            cur.execute("""
                SELECT 1 FROM scenario_sources WHERE scenario_id = %s AND source_id = %s
            """, (scenario_id, source_id))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO scenario_sources (scenario_id, source_id, date_reported)
                    VALUES (%s, %s, %s)
                """, (scenario_id, source_id, date_reported))

    # Insert mechanisms
    mechanisms = record.get("mechanisms", [])
    if isinstance(mechanisms, list):
        for mech in mechanisms:
            mech_id = upsert_mechanism(cur, mech.get("name"), mech.get("description"))
            if mech_id:
                # Check if link exists
                cur.execute("""
                    SELECT 1 FROM scenario_mechanisms WHERE scenario_id = %s AND mechanism_id = %s
                """, (scenario_id, mech_id))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO scenario_mechanisms (scenario_id, mechanism_id)
                        VALUES (%s, %s)
                    """, (scenario_id, mech_id))

    # Insert red flags
    red_flags = record.get("red_flags", [])
    if isinstance(red_flags, list):
        for flag in red_flags:
            flag_id = upsert_red_flag(cur, flag.get("name"), flag.get("description"))
            if flag_id:
                # Check if link exists
                cur.execute("""
                    SELECT 1 FROM scenario_red_flags WHERE scenario_id = %s AND red_flag_id = %s
                """, (scenario_id, flag_id))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO scenario_red_flags (scenario_id, red_flag_id)
                        VALUES (%s, %s)
                    """, (scenario_id, flag_id))

    # Upsert scam type
    if scam_type and isinstance(scam_type, dict):
        type_id = scam_type.get("type_id")
        type_name = scam_type.get("type_name")
        upsert_scam_type(cur, type_id, type_name)

    return str(scenario_id), None


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("ERROR: no input on stdin", file=sys.stderr)
        sys.exit(1)

    try:
        records = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not records:
        print("0 records to insert")
        return

    inserted = []
    errors = []

    for i, record in enumerate(records):
        if record.get("status") != "approved" or record.get("is_scam") is not True:
            continue
        
        conn = None
        try:
            conn = get_or_create_connection()
            with conn.cursor() as cur:
                scenario_id, err = insert_record(cur, record)
            conn.commit()
            if err:
                errors.append(f"Record {i}: {err}")
            else:
                inserted.append(scenario_id)
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            errors.append(f"Record {i}: {str(e)}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    print(f"Inserted: {len(inserted)} records")
    if inserted:
        print(f"scenario_ids: {', '.join(inserted)}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
