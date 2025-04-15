import os
import json
import re
import pandas as pd

def categorize_validation_messages(folder_path):
    results = []

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception as e:
                    results.append({
                        "file": filename,
                        "failures": "Unreadable JSON",
                        "category": "Other / Uncategorized"
                    })
                    continue

                messages = data.get("validation_messages", [])
                if not messages:
                    results.append({
                        "file": filename,
                        "failures": "No validation_messages",
                        "category": "Other / Uncategorized"
                    })
                    continue

                message_text = "\n".join(messages)

                has_rate_fail = bool(re.search(r"Rate validation failed", message_text, re.IGNORECASE))
                has_lineitem_fail = bool(re.search(r"Missing.*line items", message_text, re.IGNORECASE))
                has_intent_fail = bool(re.search(r"intent mismatch", message_text, re.IGNORECASE))
                has_orderid_fail = bool(re.search(r"No Order_ID found", message_text, re.IGNORECASE))

                if has_orderid_fail:
                    category = "Order_ID Missing / Processing Error"
                elif has_lineitem_fail and has_rate_fail:
                    category = "LINE_ITEMS + RATE"
                elif has_rate_fail and not has_lineitem_fail:
                    category = "RATE only"
                elif has_lineitem_fail and has_intent_fail:
                    category = "LINE_ITEMS + INTENT"
                else:
                    category = "Other / Uncategorized"

                results.append({
                    "file": filename,
                    "failures": message_text.strip().replace("\n", " "),
                    "category": category
                })

    # Save to CSV
    df = pd.DataFrame(results)
    output_path = os.path.join(folder_path, "validation_summary.csv")
    df.to_csv(output_path, index=False)
    print(f"Summary saved to {output_path}")

    return df

# Example usage:
# df = categorize_validation_messages(r"C:\path\to\your\json\folder")
