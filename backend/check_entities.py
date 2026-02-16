"""Check entity_mentions and identity_nodes data for debugging parties in summary."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

from app.services.supabase.client import get_supabase_client

def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    print("=" * 60)
    print("ENTITY DATA CHECK")
    print("=" * 60)

    # 1. Check identity_nodes table
    print("\n1. IDENTITY_NODES TABLE")
    print("-" * 40)
    nodes = client.table("identity_nodes").select("*", count="exact").limit(20).execute()
    print(f"   Total identity_nodes: {nodes.count}")

    if nodes.data:
        print("\n   Sample entities with roles:")
        for node in nodes.data[:10]:
            name = node.get("canonical_name", "Unknown")[:40]
            entity_type = node.get("entity_type", "?")
            metadata = node.get("metadata", {}) or {}
            roles = metadata.get("roles", [])
            matter_id = node.get("matter_id", "")[:8]
            print(f"   - [{entity_type:12}] {name:40} roles={roles} (matter={matter_id}...)")
    else:
        print("   *** NO IDENTITY_NODES FOUND ***")

    # 2. Check entity_mentions table
    print("\n2. ENTITY_MENTIONS TABLE")
    print("-" * 40)
    mentions = client.table("entity_mentions").select("*", count="exact").limit(10).execute()
    print(f"   Total entity_mentions: {mentions.count}")

    if mentions.data:
        print("\n   Sample mentions:")
        for m in mentions.data[:5]:
            text = (m.get("mention_text") or "")[:30]
            doc_id = (m.get("document_id") or "")[:8]
            page = m.get("page_number")
            print(f"   - \"{text}...\" (doc={doc_id}..., page={page})")
    else:
        print("   *** NO ENTITY_MENTIONS FOUND ***")

    # 3. Check entities with party roles specifically
    print("\n3. ENTITIES WITH PARTY ROLES (petitioner/respondent)")
    print("-" * 40)

    # Query all nodes and filter for party roles
    all_nodes = client.table("identity_nodes").select("canonical_name, entity_type, metadata, matter_id").execute()
    party_nodes = []
    for node in (all_nodes.data or []):
        metadata = node.get("metadata", {}) or {}
        roles = metadata.get("roles", [])
        for role in roles:
            role_lower = role.lower() if isinstance(role, str) else ""
            if any(p in role_lower for p in ["petitioner", "respondent", "appellant", "defendant"]):
                party_nodes.append({
                    "name": node.get("canonical_name"),
                    "type": node.get("entity_type"),
                    "roles": roles,
                    "matter_id": node.get("matter_id")
                })
                break

    print(f"   Found {len(party_nodes)} entities with party roles")
    for p in party_nodes[:10]:
        name = (p["name"] or "Unknown")[:40]
        print(f"   - {name:40} roles={p['roles']}")

    # 4. Check matters with documents
    print("\n4. MATTERS WITH DOCUMENTS")
    print("-" * 40)
    matters = client.table("matters").select("id, title").limit(10).execute()
    for matter in (matters.data or []):
        matter_id = matter["id"]
        matter_name = (matter.get("title") or "Unnamed")[:30]

        # Count documents
        docs = client.table("documents").select("id", count="exact").eq("matter_id", matter_id).is_("deleted_at", "null").execute()
        doc_count = docs.count or 0

        # Count entities
        entities = client.table("identity_nodes").select("id", count="exact").eq("matter_id", matter_id).execute()
        entity_count = entities.count or 0

        # Count mentions
        if docs.data:
            doc_ids = [d["id"] for d in docs.data]
            mentions = client.table("entity_mentions").select("id", count="exact").in_("document_id", doc_ids[:50]).execute()
            mention_count = mentions.count or 0
        else:
            mention_count = 0

        print(f"   {matter_name:30} docs={doc_count:3} entities={entity_count:3} mentions={mention_count:3}")

    # 5. Test the IMPROVED summary parties query
    print("\n5. TEST IMPROVED PARTIES QUERY")
    print("-" * 40)

    if matters.data:
        test_matter_id = matters.data[0]["id"]
        print(f"   Testing with matter: {test_matter_id[:12]}...")

        # Get active document IDs
        docs_result = client.table("documents").select("id, filename").eq("matter_id", test_matter_id).is_("deleted_at", "null").execute()
        active_docs = {d["id"]: d["filename"] for d in docs_result.data or []}
        active_doc_ids = list(active_docs.keys())
        print(f"   Active documents: {len(active_doc_ids)}")

        # Step 1: Get PERSON/ORG entities with party roles
        entities_result = client.table("identity_nodes").select(
            "id, canonical_name, entity_type, metadata"
        ).eq("matter_id", test_matter_id).in_(
            "entity_type", ["PERSON", "ORG"]
        ).order("mention_count", desc=True).limit(100).execute()

        print(f"   Total PERSON/ORG entities: {len(entities_result.data or [])}")

        # Filter for party roles - improved placeholder detection
        import re
        def is_placeholder(name):
            if not name:
                return True
            name_lower = name.lower().strip()

            # Exact matches
            exact = ["respondent", "petitioner", "appellant", "defendant", "applicant", "complainant", "accused", "custodian"]
            if name_lower in exact:
                return True

            # Numbered patterns like "Respondent 2", "Respondent No.1"
            numbered_pattern = re.compile(
                r"^(respondent|petitioner|appellant|defendant|applicant|complainant)\s*(no\.?|nos\.?|number)?\s*\d*$",
                re.IGNORECASE,
            )
            if numbered_pattern.match(name_lower):
                return True

            # Startswith patterns
            for p in ["respondent no", "petitioner no", "appellant no", "defendant no"]:
                if name_lower.startswith(p):
                    return True
            return False

        party_entities = []
        for entity in entities_result.data or []:
            metadata = entity.get("metadata", {}) or {}
            roles = metadata.get("roles", [])
            name = entity.get("canonical_name", "")

            if is_placeholder(name):
                continue

            role = None
            for r in roles:
                r_lower = r.lower() if isinstance(r, str) else ""
                if any(x in r_lower for x in ["petitioner", "appellant", "complainant", "applicant"]):
                    role = "PETITIONER"
                    break
                elif any(x in r_lower for x in ["respondent", "defendant", "accused"]):
                    role = "RESPONDENT"
                    break

            if role:
                party_entities.append({
                    "entity_id": entity["id"],
                    "name": name,
                    "role": role,
                    "all_roles": roles,
                })

        print(f"   Entities with party roles (excluding placeholders): {len(party_entities)}")

        for p in party_entities[:10]:
            print(f"   - [{p['role']:10}] {p['name'][:35]:35} roles={p['all_roles']}")

    print("\n" + "=" * 60)
    print("CHECK COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
