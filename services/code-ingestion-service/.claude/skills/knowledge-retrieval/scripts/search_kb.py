#!/usr/bin/env python3
"""
Search the local PostgreSQL knowledge base via the Spring Boot API.
Parses JSON responses and formats results for readability.
"""

import sys
import urllib.request
import urllib.parse
import json

def search_knowledge_base(query, language=None):
    """Query the Spring Boot knowledge base and print formatted results."""
    base_url = "http://localhost:8081/api/v1/chunks/search"
    params = {'q': query, 'limit': 10}
    if language:
        params['language'] = language

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            items = data.get('items', [])

            if not items:
                print(f"No results found in the knowledge base for: '{query}'")
                return

            print(f"Found {len(items)} results (out of {data.get('total', 0)} total):\n")
            for item in items:
                print(f"=== {item['repositoryName']} | {item['path']} | Score: {item['score']:.2f} ===")
                print(f"{item['content']}\n")

    except urllib.error.URLError as e:
        print(f"Error: Could not connect to the Spring Boot knowledge base at http://localhost:8081")
        print(f"Make sure the service is running: docker-compose up -d && mvn spring-boot:run")
        print(f"Details: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON response from the knowledge base: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error querying the Spring Boot knowledge base: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_kb.py <query> [language]")
        print("Examples:")
        print("  python search_kb.py 'ChunkRepository native SQL'")
        print("  python search_kb.py 'full-text search' java")
        sys.exit(1)

    query = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else None
    search_knowledge_base(query, language)
