"""
Test the GraphQATool end-to-end with 5 representative questions.

Usage: python -m scripts.test_graph_qa
"""

import asyncio
import os
from dotenv import load_dotenv

from app.infrastructure.neo4j_client import Neo4jClient
from app.services.graph_service import GraphService

QUESTIONS = [
    "What chemicals can I use to control Green Mirids?",
    "Which beneficial insects prey on Helicoverpa?",
    "What causes Fusarium wilt and how do I manage it?",
    "Which insecticides have the lowest impact on beneficial insects for aphid control?",
    "What harvest aid chemicals are available and what are they used for?",
]

async def main():
    load_dotenv()

    neo4j_client = Neo4jClient(
        uri=os.environ["NEO4J_URI"],
        username=os.environ["NEO4J_USERNAME"],
        password=os.environ["NEO4J_PASSWORD"],
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
    )
    await neo4j_client.connect()

    service = GraphService(
        neo4j_client=neo4j_client,
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    )

    print("=" * 68)
    print("  CRDC GraphQATool — End-to-End Test")
    print("=" * 68)

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n[Q{i}] {question}")
        print("-" * 68)

        try:
            result = await service.query(question)
            print(f"Cypher : {result['cypher'][:120]}{'...' if len(result['cypher']) > 120 else ''}")
            print(f"Records: {result['record_count']}")
            print(f"Answer : {result['answer']}")
        except Exception as e:
            print(f"ERROR  : {e}")

        await asyncio.sleep(1)

    await neo4j_client.close()
    print("\n" + "=" * 68)
    print("  Test complete.")

if __name__ == "__main__":
    asyncio.run(main())
