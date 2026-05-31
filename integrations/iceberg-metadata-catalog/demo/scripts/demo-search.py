#!/usr/bin/env python3
"""
demo-search.py — Vector Similarity Search Demo

Queries OpenSearch Serverless with a natural language query,
converts to embedding, and performs kNN search.

Usage:
    python demo-search.py --query "find invoice documents" --region ap-northeast-1
"""

import argparse
import json
import sys

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


def main():
    parser = argparse.ArgumentParser(description="Vector Search Demo")
    parser.add_argument("--query", required=True, help="Natural language search query")
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--collection-endpoint", default=None,
                        help="OpenSearch endpoint (auto-detected if not provided)")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    # Auto-detect OpenSearch endpoint
    endpoint = args.collection_endpoint
    if not endpoint:
        aoss = boto3.client("opensearchserverless", region_name=args.region)
        collections = aoss.list_collections()["collectionSummaries"]
        vector_collections = [c for c in collections if "metadata" in c.get("name", "")]
        if vector_collections:
            detail = aoss.batch_get_collection(ids=[vector_collections[0]["id"]])
            endpoint = detail["collectionDetails"][0].get("collectionEndpoint")

    if not endpoint:
        print("  ⚠️  No OpenSearch collection found. Skipping vector search.")
        print("  To enable: deploy OpenSearch Serverless NextGen collection")
        return

    # Setup auth
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(credentials.access_key, credentials.secret_key, args.region, "aoss",
                    session_token=credentials.token)

    host = endpoint.replace("https://", "")
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth, use_ssl=True, verify_certs=True,
        connection_class=RequestsHttpConnection, timeout=60,
    )

    # Generate query embedding
    bedrock = boto3.client("bedrock-runtime", region_name=args.region)
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json", accept="application/json",
        body=json.dumps({"inputText": args.query, "dimensions": 1024, "normalize": True}),
    )
    query_embedding = json.loads(response["body"].read())["embedding"]

    print(f"  Query: \"{args.query}\"")
    print(f"  Embedding: {len(query_embedding)} dimensions")
    print()

    # kNN search
    index_name = "fsxn-metadata-embeddings"
    try:
        results = client.search(index=index_name, body={
            "size": args.top_k,
            "query": {"knn": {"embedding_vector": {"vector": query_embedding, "k": args.top_k}}},
        })

        hits = results["hits"]["hits"]
        print(f"  Results: {len(hits)} similar files found")
        print()
        for i, hit in enumerate(hits, 1):
            src = hit["_source"]
            print(f"  {i}. {src.get('file_name', 'unknown')} (score: {hit['_score']:.4f})")
            print(f"     Classification: {src.get('classification', 'N/A')}")
            print(f"     Summary: {(src.get('summary', '') or '')[:80]}")
            print()

        if not hits:
            print("  No results. Index may be empty or collection is scaling from zero.")
            print("  Tip: Run demo-enrich.py first to populate embeddings.")

    except Exception as e:
        print(f"  ⚠️  Search failed: {e}")
        print("  Collection may be scaling from zero (10-30s cold start). Retry in 30 seconds.")


if __name__ == "__main__":
    main()
