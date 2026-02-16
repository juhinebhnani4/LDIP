"""
Update golden dataset items with richer expected_answer values for RAGAS evaluation.

This script updates 4 golden dataset items for matter_id 91a4a4db-bc3d-40df-8dcc-49179ac49108
with more detailed expected answers that include specific facts, names, and document references
that should appear in retrieved chunks for proper RAGAS context_recall evaluation.
"""

from app.services.supabase.client import get_supabase_client


def main():
    """Update golden dataset items with richer expected answers."""
    supabase = get_supabase_client()
    matter_id = "91a4a4db-bc3d-40df-8dcc-49179ac49108"

    # Define the updated expected answers with rich, specific facts
    updates = [
        {
            "question": "What is the case number of this matter?",
            "expected_answer": (
                "The case number is Miscellaneous Application No. 10 of 2023 (MA NO 10 OF 2023). "
                "This application was filed before the appropriate authority handling matters related "
                "to the late Shri Harshad S. Mehta's estate, involving the Custodian as Respondent No. 1 "
                "and multiple other respondents including Nirav D Jobalia as Respondent No. 5."
            )
        },
        {
            "question": "Who is the applicant in this matter?",
            "expected_answer": (
                "The applicant in MA NO 10 OF 2023 is Smt. Jyoti H. Mehta, who is the sole legal heir "
                "of late Shri Harshad S. Mehta. She is represented by Advocate Ashwin S. Mehta in these "
                "proceedings. Smt. Jyoti H. Mehta has filed an Affidavit in Rejoinder and also addressed "
                "a letter dated November 28, 2023 to the Custodian regarding this matter."
            )
        },
        {
            "question": "Who is Nirav D Jobalia in this case?",
            "expected_answer": (
                "Nirav D Jobalia is Respondent No. 5 in MA NO 10 OF 2023. He is also referred to as "
                "'Respo no 5 Nirav Jbalia' in some document names. In his response to the application, "
                "Respondent No. 5 has claimed that the application filed by Smt. Jyoti H. Mehta is belated, "
                "coming after 30 years, and has filed affidavits in the proceedings."
            )
        },
        {
            "question": "What role does the Custodian play in this matter?",
            "expected_answer": (
                "The Custodian is Respondent No. 1 in MA NO 10 OF 2023 and plays a central role in this matter "
                "related to the estate of late Shri Harshad S. Mehta. The Custodian has filed an affidavit in reply "
                "to the applicant's submissions. Smt. Jyoti H. Mehta, the applicant, has directly addressed "
                "correspondence to the Custodian, including a letter dated November 28, 2023, regarding the issues "
                "raised in this miscellaneous application."
            )
        }
    ]

    print(f"Fetching golden dataset items for matter_id: {matter_id}\n")

    # Fetch all items for this matter
    response = supabase.table("golden_dataset") \
        .select("id, question, expected_answer") \
        .eq("matter_id", matter_id) \
        .execute()

    if not response.data:
        print(f"No items found for matter_id: {matter_id}")
        return

    print(f"Found {len(response.data)} items\n")

    # Create a mapping of questions to IDs
    question_to_id = {item["question"]: item["id"] for item in response.data}

    # Update each item
    updated_count = 0
    for update in updates:
        question = update["question"]
        new_answer = update["expected_answer"]

        if question not in question_to_id:
            print(f"[WARN] Question not found: {question}")
            continue

        item_id = question_to_id[question]
        old_item = next(item for item in response.data if item["id"] == item_id)
        old_answer = old_item["expected_answer"]

        print(f"Updating item ID: {item_id}")
        print(f"Question: {question}")
        print(f"Old answer ({len(old_answer)} chars): {old_answer}")
        print(f"New answer ({len(new_answer)} chars): {new_answer}")

        # Update the item
        update_response = supabase.table("golden_dataset") \
            .update({"expected_answer": new_answer}) \
            .eq("id", item_id) \
            .execute()

        if update_response.data:
            print("[OK] Updated successfully\n")
            updated_count += 1
        else:
            print("[FAIL] Update failed\n")

    print(f"\nSummary: Updated {updated_count}/{len(updates)} items")

    # Verify updates
    print("\nVerifying updates...")
    verify_response = supabase.table("golden_dataset") \
        .select("question, expected_answer") \
        .eq("matter_id", matter_id) \
        .execute()

    print("\nFinal state of golden dataset items:")
    for item in verify_response.data:
        print(f"\nQ: {item['question']}")
        print(f"A: {item['expected_answer']}")


if __name__ == "__main__":
    main()
