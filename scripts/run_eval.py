import sys
import os
import json
import re
from urllib.parse import urlparse

# Ensure the parent directory is in the path for proper module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Reconfigure stdout to use UTF-8 if supported
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from dotenv import load_dotenv
load_dotenv()

from agents.intake_agent import run_agent_1
from agents.policy_agent import run_agent_2
from agents.action_agent import run_agent_3

# Synthetic test cases representing diverse scenarios
TEST_CASES = [
    {
        "id": 1,
        "name": "Low-Income Family (Texas)",
        "input_message": "I live in Austin, Texas. I have two children, ages 4 and 7. My monthly income is about $1,500. We need help getting groceries and medical checkups.",
        "expected": {
            "location_keyword": "texas",
            "monthly_income": 1500.0,
            "family_size": 3,
            "expected_benefits": ["SNAP", "Medicaid"],
            "urgency_flag": False
        }
    },
    {
        "id": 2,
        "name": "Elderly Individual (Florida)",
        "input_message": "I am 68 years old, living alone in Orlando, Florida. My monthly income is $900 from Social Security and I cannot afford food or my medical bills.",
        "expected": {
            "location_keyword": "florida",
            "monthly_income": 900.0,
            "family_size": 1,
            "expected_benefits": ["SNAP", "Medicaid"],
            "urgency_flag": False
        }
    },
    {
        "id": 3,
        "name": "High-Income Family (California)",
        "input_message": "We live in San Francisco, CA. Family size is 4. Income is $8,500 monthly. Just looking to see if we qualify for SNAP.",
        "expected": {
            "location_keyword": "california",
            "monthly_income": 8500.0,
            "family_size": 4,
            "expected_benefits": [],
            "urgency_flag": False
        }
    },
    {
        "id": 4,
        "name": "Single Parent with Infant (New York)",
        "input_message": "I am a single mother living in Brooklyn, New York with my 6-month-old baby. I earn $1,800 a month and need help with food, formula, and health insurance.",
        "expected": {
            "location_keyword": "new york",
            "monthly_income": 1800.0,
            "family_size": 2,
            "expected_benefits": ["SNAP", "Medicaid", "WIC"],
            "urgency_flag": False
        }
    },
    {
        "id": 5,
        "name": "Crisis / Zero-Income (Ohio)",
        "input_message": "I got evicted today in Cleveland, Ohio. I have zero income and no money left. I am living in my car. Urgent help needed for shelter and food.",
        "expected": {
            "location_keyword": "ohio",
            "monthly_income": 0.0,
            "family_size": 1,
            "expected_benefits": ["SNAP"],
            "urgency_flag": True
        }
    }
]

# Standard allowed taxonomy of benefits to check for program hallucinations.
# Includes state-branded aliases so legitimate programs are not flagged.
ALLOWED_BENEFITS_TAXONOMY = {
    # Federal names
    "snap", "medicaid", "tanf", "wic", "chip", "liheap", "ssi",
    "general assistance", "emergency housing", "housing assistance", "food assistance",
    # State-branded equivalents
    "calfresh", "calworks", "medi-cal",           # California
    "child health plus", "ch+", "ccap", "ccdf",  # NY / childcare
    "peachcare", "georgia families",              # Georgia
    "florida medicaid", "sunshine health",        # Florida
    "ohio medicaid", "ohio works",                # Ohio
    "eic", "eitc", "earned income",              # Tax credits (common companion)
    "heap", "utility assistance",                 # LIHEAP aliases
    "essential plan", "ny essential plan",        # NY low-cost health insurance
    "nys eia", "nys eic", "new york state medicaid",  # NY variants
    "access nyc", "ny medicaid",                  # NYC portals
    "upk", "universal pre-k",                    # NY pre-K (education)
}


def normalize_benefit_name(raw_name: str) -> str:
    """
    Map state-branded program names to their federal equivalents so that
    'TEXAS MEDICAID', 'NEW YORK MEDICAID', 'MEDI-CAL' all match 'MEDICAID',
    and 'CALFRESH' matches 'SNAP'.  This prevents false F1 penalties for
    programs that are real but named differently by each state.
    """
    name = raw_name.lower().strip()
    if any(k in name for k in ["snap", "calfresh", "food stamp", "food assistance"]):
        return "SNAP"
    if any(k in name for k in ["medicaid", "medi-cal", "medical assistance"]):
        return "MEDICAID"
    if any(k in name for k in ["chip", "child health plus", "peachcare", "ch+"]):
        return "CHIP"
    if any(k in name for k in ["wic", "women, infant", "women infant"]):
        return "WIC"
    if any(k in name for k in ["tanf", "calworks", "cash assistance", "ohio works", "temporary assistance"]):
        return "TANF"
    if any(k in name for k in ["liheap", "heap", "utility assistance", "energy assistance"]):
        return "LIHEAP"
    if any(k in name for k in ["ssi", "supplemental security"]):
        return "SSI"
    if any(k in name for k in ["housing", "shelter", "emergency housing"]):
        return "HOUSING ASSISTANCE"
    if any(k in name for k in ["childcare", "child care", "ccdf", "ccap", "pre-k", "upk"]):
        return "CHILDCARE ASSISTANCE"
    if any(k in name for k in ["essential plan", "ny essential"]):
        return "MEDICAID"  # NY Essential Plan is the state's low-cost health coverage
    if any(k in name for k in ["eitc", "eic", "earned income credit"]):
        return "EITC"
    # Return uppercased original for unknown programs
    return raw_name.strip().upper()

def evaluate_pipeline():
    print("=" * 60)
    print("      CIVICEASE AI -- AUTOMATED EVALUATION FRAMEWORK")
    print("=" * 60)
    
    total_extraction_score = 0.0
    total_precision = 0.0
    total_recall = 0.0
    total_hallucinations = 0
    total_cot_completions = 0
    total_test_cases = len(TEST_CASES)
    
    results = []
    
    for tc in TEST_CASES:
        print(f"\n[Test Case {tc['id']}] Running: {tc['name']}...")
        
        # 1. Run Intake Agent (Agent 1)
        profile = run_agent_1(tc["input_message"])
        if not isinstance(profile, dict):
            print(f"  [ERROR] Failed: Agent 1 returned invalid type {type(profile)}")
            continue
            
        # Evaluate extraction accuracy
        expected = tc["expected"]
        
        # Location evaluation
        extracted_loc = str(profile.get("location") or "").lower()
        loc_match = 1.0 if expected["location_keyword"] in extracted_loc or any(t in extracted_loc for t in expected["location_keyword"].split()) else 0.0
        
        # Income evaluation
        try:
            raw_income = profile.get("monthly_income")
            extracted_income = 0.0 if raw_income == "None" or raw_income is None else float(raw_income)
        except (ValueError, TypeError):
            extracted_income = -1.0
        income_match = 1.0 if abs(extracted_income - expected["monthly_income"]) < 1.0 else 0.0
        
        # Family size evaluation
        extracted_size = profile.get("family_size")
        size_match = 1.0 if extracted_size == expected["family_size"] else 0.0
        
        # Urgency flag
        extracted_urgency = bool(profile.get("urgency_flag"))
        urgency_match = 1.0 if extracted_urgency == expected["urgency_flag"] else 0.0
        
        extraction_score = ((loc_match + income_match + size_match + urgency_match) / 4.0) * 100.0
        total_extraction_score += extraction_score
        
        print(f"  Intake Extraction Accuracy: {extraction_score:.1f}%")
        print(f"    - Location Match: {'[OK]' if loc_match else '[FAIL]'} (Extracted: '{profile.get('location')}')")
        print(f"    - Income Match:   {'[OK]' if income_match else '[FAIL]'} (Extracted: '{profile.get('monthly_income')}', Expected: {expected['monthly_income']})")
        print(f"    - Family Match:   {'[OK]' if size_match else '[FAIL]'} (Extracted: {extracted_size}, Expected: {expected['family_size']})")
        print(f"    - Urgency Match:  {'[OK]' if urgency_match else '[FAIL]'} (Extracted: {extracted_urgency}, Expected: {expected['urgency_flag']})")
        
        # Check for clarification gate
        if profile.get("clarification_needed"):
            print("  [WARN] Clarification requested. Skipping Agent 2/3 for this pipeline stage.")
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "extraction_score": extraction_score,
                "status": "clarification_needed"
            })
            continue

        # 2. Run Policy Agent (Agent 2)
        policy_matches = run_agent_2(profile)
        matches_list = policy_matches.get("matches", [])
        
        # Evaluate Precision and Recall of benefit matching.
        # Normalize state-branded names to federal equivalents before comparison
        # so 'TEXAS MEDICAID' correctly matches expected 'MEDICAID'.
        matched_benefit_names = {
            normalize_benefit_name(m.get("benefit_name", ""))
            for m in matches_list
        }
        expected_benefit_names = {b.strip().upper() for b in expected["expected_benefits"]}

        # Precision: of what we returned, how much was correct?
        if matched_benefit_names:
            correct_matches = matched_benefit_names.intersection(expected_benefit_names)
            precision = len(correct_matches) / len(matched_benefit_names)
        else:
            precision = 1.0 if not expected_benefit_names else 0.0

        # Recall: of what was expected, how much did we find?
        if expected_benefit_names:
            correct_matches = matched_benefit_names.intersection(expected_benefit_names)
            recall = len(correct_matches) / len(expected_benefit_names)
        else:
            # Expected=[] and matched=[]: perfect (precision already handles this)
            # Expected=[] but matched something: precision=0, recall treated as 1.0
            # to avoid inflating F1 — use 0.0 when we over-returned.
            recall = 0.0 if matched_benefit_names else 1.0

        f1_score = (2 * precision * recall / (precision + recall)) * 100.0 if (precision + recall) > 0 else 0.0
        total_precision += precision
        total_recall += recall

        print(f"  Policy Matching F1-Score:  {f1_score:.1f}% (Precision: {precision*100:.1f}%, Recall: {recall*100:.1f}%)")
        print(f"    - Matched Benefits (normalized): {sorted(matched_benefit_names)}")
        print(f"    - Expected:                     {sorted(expected_benefit_names)}")
        
        # ---------------------------------------------------------------
        # Evaluate Chain-of-Thought (CoT) completeness — Structured Validator
        # Checks all 4 ReasoningChain steps individually.
        # step3_compare must also contain a numeric value (math verification).
        # ---------------------------------------------------------------
        COT_MIN_CHARS = 20   # minimum meaningful length per step
        HAS_NUMBER    = re.compile(r"\d")  # at least one digit proves math was done

        cot_verified   = True
        cot_fail_reason = ""

        if not matches_list:
            cot_verified    = False
            cot_fail_reason = "no benefit matches returned"
        else:
            for m in matches_list:
                chain = m.get("reasoning_chain") or {}

                s1 = str(chain.get("step1_extract_criteria") or "").strip()
                s2 = str(chain.get("step2_extract_user_data")  or "").strip()
                s3 = str(chain.get("step3_compare")            or "").strip()
                s4 = str(chain.get("step4_conclusion")         or "").strip()

                missing_steps = []
                if len(s1) < COT_MIN_CHARS: missing_steps.append("step1_extract_criteria")
                if len(s2) < COT_MIN_CHARS: missing_steps.append("step2_extract_user_data")
                if len(s3) < COT_MIN_CHARS: missing_steps.append("step3_compare")
                if len(s4) < COT_MIN_CHARS: missing_steps.append("step4_conclusion")

                if missing_steps:
                    cot_verified    = False
                    cot_fail_reason = f"Steps too short or missing: {missing_steps}"
                    break

                if not HAS_NUMBER.search(s3):
                    cot_verified    = False
                    cot_fail_reason = "step3_compare contains no numeric value (no math detected)"
                    break

        if cot_verified:
            total_cot_completions += 1
            print("    - CoT reasoning verification: [OK] All 4 steps verified with numeric comparison")
        elif matches_list:
            print(f"    - CoT reasoning verification: [FAIL] {cot_fail_reason}")
        else:
            print("    - CoT reasoning verification: [N/A] (No benefit matches)")

        # 3. Run Action Planner Agent (Agent 3) & Evaluate Guardrails
        action_plan = run_agent_3(profile, policy_matches)
        
        # Check for hallucinations
        # Hallucination 1: Did Agent 3 build actions for unapproved/unmatched programs?
        allowed_names = {m.get("benefit_name", "").strip().lower() for m in matches_list}
        action_blocks = action_plan.get("benefit_action_blocks", [])
        plan_benefit_names = {b.get("benefit_name", "").strip().lower() for b in action_blocks}
        
        alignment_hallucinations = len(plan_benefit_names - allowed_names)
        total_hallucinations += alignment_hallucinations
        
        # Hallucination 2: Standard Taxonomy Check
        taxonomy_hallucinations = 0
        for name in plan_benefit_names:
            if not any(term in name for term in ALLOWED_BENEFITS_TAXONOMY):
                taxonomy_hallucinations += 1
        total_hallucinations += taxonomy_hallucinations
        
        # Hallucination 3: Link/URL sanity checks
        url_violations = 0
        for block in action_blocks:
            for item in block.get("checklist", []):
                url = item.get("resource_url")
                if url:
                    parsed = urlparse(url)
                    hostname = parsed.hostname or ""
                    if not hostname.lower().endswith((".gov", ".org", ".edu")):
                        url_violations += 1
        total_hallucinations += url_violations
        
        print(f"  Safety Guardrails Verification:")
        print(f"    - Unapproved Program Blocks:  {f'[OK] 0' if alignment_hallucinations == 0 else f'[FAIL] {alignment_hallucinations}'}")
        print(f"    - Out-of-Taxonomy Benefits:   {f'[OK] 0' if taxonomy_hallucinations == 0 else f'[FAIL] {taxonomy_hallucinations}'}")
        print(f"    - Non-whitelisted Links:      {f'[OK] 0' if url_violations == 0 else f'[FAIL] {url_violations}'}")
        
        results.append({
            "id": tc["id"],
            "name": tc["name"],
            "extraction_score": extraction_score,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "cot_verified": cot_verified,
            "hallucinations": alignment_hallucinations + taxonomy_hallucinations + url_violations
        })

    # Output Summary Report
    avg_extraction = total_extraction_score / total_test_cases
    avg_precision = (total_precision / total_test_cases) * 100.0
    avg_recall = (total_recall / total_test_cases) * 100.0
    avg_f1 = (2 * avg_precision * avg_recall / (avg_precision + avg_recall)) if (avg_precision + avg_recall) > 0 else 0.0
    cot_rate = (total_cot_completions / total_test_cases) * 100.0
    
    print("\n" + "=" * 60)
    print("                 METRICS EVALUATION REPORT")
    print("=" * 60)
    print(f"Average Intake Extraction Accuracy:  {avg_extraction:.1f}%")
    print(f"Average Policy Retrieval Precision:  {avg_precision:.1f}%")
    print(f"Average Policy Retrieval Recall:     {avg_recall:.1f}%")
    print(f"Average System F1-Score:             {avg_f1:.1f}%")
    print(f"Chain-of-Thought (CoT) Completeness: {cot_rate:.1f}%")
    print(f"Total Hallucinations Detected:        {total_hallucinations} (Lower is better)")
    print("=" * 60)
    
    # Save results as a local report
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/eval_report.json"))
    with open(report_path, "w") as f:
        json.dump({
            "avg_extraction_accuracy": avg_extraction,
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_f1": avg_f1,
            "cot_completeness": cot_rate,
            "total_hallucinations": total_hallucinations,
            "individual_results": results
        }, f, indent=2)
    print(f"Full report saved to: data/eval_report.json")

if __name__ == "__main__":
    evaluate_pipeline()
