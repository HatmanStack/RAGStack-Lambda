"""Sample metadata for testing.

This module provides sample metadata dictionaries for various document types
used in testing metadata extraction, filtering, and search functionality.
"""

# Sample key library entries
SAMPLE_KEY_LIBRARY_ENTRIES = [
    {
        "key_name": "topic",
        "data_type": "string",
        "sample_values": ["genealogy", "immigration", "military_service", "census"],
        "occurrence_count": 150,
        "first_seen": "2024-01-15T10:00:00+00:00",
        "last_seen": "2024-03-20T15:30:00+00:00",
        "status": "active",
    },
    {
        "key_name": "document_type",
        "data_type": "string",
        "sample_values": ["certificate", "letter", "census_record", "ship_manifest"],
        "occurrence_count": 145,
        "first_seen": "2024-01-15T10:00:00+00:00",
        "last_seen": "2024-03-20T15:30:00+00:00",
        "status": "active",
    },
    {
        "key_name": "date_range",
        "data_type": "string",
        "sample_values": ["1900-1920", "1850-1900", "1920-1950", "19th_century"],
        "occurrence_count": 120,
        "first_seen": "2024-01-16T09:00:00+00:00",
        "last_seen": "2024-03-19T14:00:00+00:00",
        "status": "active",
    },
    {
        "key_name": "location",
        "data_type": "string",
        "sample_values": ["New York", "Ellis Island", "Ireland", "Boston"],
        "occurrence_count": 95,
        "first_seen": "2024-01-17T11:00:00+00:00",
        "last_seen": "2024-03-18T16:00:00+00:00",
        "status": "active",
    },
    {
        "key_name": "source_category",
        "data_type": "string",
        "sample_values": ["government_record", "personal_document", "church_record"],
        "occurrence_count": 80,
        "first_seen": "2024-01-18T08:00:00+00:00",
        "last_seen": "2024-03-17T12:00:00+00:00",
        "status": "active",
    },
    {
        "key_name": "old_deprecated_key",
        "data_type": "string",
        "sample_values": ["value1"],
        "occurrence_count": 5,
        "first_seen": "2024-01-10T08:00:00+00:00",
        "last_seen": "2024-01-12T12:00:00+00:00",
        "status": "deprecated",
    },
]

# Sample extracted metadata for different document types

IMMIGRATION_RECORD_METADATA = {
    "topic": "immigration",
    "document_type": "ship_manifest",
    "date_range": "1905-1910",
    "location": "Ellis Island",
    "source_category": "government_record",
    "language": "english",
    "port_of_origin": "Liverpool",
}

# Sample document texts for extraction testing

SAMPLE_IMMIGRATION_TEXT = """
Immigration Record - Ellis Island

Name: John Patrick O'Brien
Date of Arrival: March 15, 1905
Ship: SS Carpathia
Port of Origin: Liverpool, England
Destination: New York City

This document certifies that the above named person arrived at
Ellis Island immigration station on the date specified. The passenger
was traveling in steerage class and declared Ireland as country of origin.

Occupation: Laborer
Age: 28
Marital Status: Single
Literacy: Can read and write

Final Destination: Boston, Massachusetts
Relatives in USA: Brother - Michael O'Brien, 123 Main Street, Boston
"""

SAMPLE_CENSUS_TEXT = """
United States Census, 1900
Brooklyn, Kings County, New York

Household Head: James Wilson
Relationship to Head | Name | Age | Birthplace | Occupation
Head | James Wilson | 45 | New York | Carpenter
Wife | Mary Wilson | 42 | Ireland | None
Son | Thomas Wilson | 18 | New York | Clerk
Daughter | Ellen Wilson | 15 | New York | At School
Son | Patrick Wilson | 12 | New York | At School

Dwelling Number: 234
Family Number: 89
Street: Atlantic Avenue
"""

SAMPLE_GENEALOGY_TEXT = """
Family History Research Notes

Subject: O'Brien Family of County Cork, Ireland

The O'Brien family emigrated from County Cork, Ireland to Boston,
Massachusetts in the mid-19th century. Records indicate that Patrick
O'Brien (b. 1825) and his wife Margaret (née Sullivan, b. 1830) arrived
in Boston Harbor in 1852 during the height of the Irish Famine migration.

Their children included:
- John O'Brien (b. 1853, Boston)
- Mary O'Brien (b. 1855, Boston)
- Thomas O'Brien (b. 1858, Boston)

Patrick worked as a dock laborer while Margaret took in laundry.
The family lived in the North End neighborhood until 1875 when they
moved to South Boston.
"""

SAMPLE_IMAGE_CAPTION = """
Family wedding photograph, circa 1925.

Shows the bride (identified as Margaret O'Brien) with her wedding party
outside St. Patrick's Church in South Boston. The groom (Thomas Sullivan)
stands to her right. Approximately 15 people visible in the photograph.

Original photograph from the O'Brien family collection.
Scanned from 5x7 inch black and white print.
"""
