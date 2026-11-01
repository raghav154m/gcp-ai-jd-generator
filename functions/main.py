"""Cloud Functions (gen2) for AI job-description generation and compliance review.

Two HTTP entry points share this source:
  - generate_job_description_http : Firestore context + Gemini -> stored job description
  - validate_compliance           : Gemini review of a job description, returns structured JSON
"""
import json
import os
import re

import functions_framework
from flask import jsonify

PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
REGION = os.environ.get("FUNCTION_REGION", "us-central1")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "3600",
}

_db = None
_genai = None


def get_db():
    """Lazily create the Firestore client (keeps cold starts and unit tests cheap)."""
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client(project=PROJECT_ID)
    return _db


def get_genai():
    """Lazily create the Gen AI client, routed through Vertex AI."""
    global _genai
    if _genai is None:
        from google import genai
        _genai = genai.Client(vertexai=True, project=PROJECT_ID, location=os.environ.get("GEMINI_LOCATION", "global"))
    return _genai


# ---------- pure logic (unit-tested) ----------

def build_jd_prompt(culture: dict, template: dict, custom_requirements: str | None) -> str:
    return f"""Create a professional, inclusive job description for the role of
{template['title']} at {culture['company_name']}.

Company
- Mission: {culture['mission']}
- Values: {', '.join(culture['values'])}
- Culture: {culture['culture_description']}
- Work environment: {culture['work_environment']}
- Benefits: {'; '.join(culture['benefits'])}

Role
- Department: {template['department']}
- Level: {template['level']}
- Experience: {template['experience_years']}
- Education: {template['education']}
- Required skills: {', '.join(template['required_skills'])}
- Nice to have: {', '.join(template['nice_to_have'])}
- Responsibilities: {'; '.join(template['responsibilities'])}
- Compliance notes: {template.get('compliance_notes', 'None')}

Additional requirements: {custom_requirements or 'None'}

Structure the output in Markdown with these sections: About Us, Role Summary,
Responsibilities, Required Qualifications, Preferred Skills, Benefits,
Equal Opportunity Statement, How to Apply. Avoid gendered, age-related or
otherwise exclusionary language."""


def build_compliance_prompt(job_description: str) -> str:
    return f"""You are an HR compliance reviewer. Review the job description below for:
1. Discriminatory language or requirements
2. Bias related to age, gender, or other protected characteristics
3. A missing equal opportunity statement
4. Unreasonable or unlawful requirements
5. Inaccessible or non-inclusive language

Respond with ONLY a JSON object of the form:
{{"score": <integer 1-10, 10 = fully compliant>,
  "issues": [<string>, ...],
  "recommendations": [<string>, ...]}}

Job description:
\"\"\"{job_description}\"\"\""""


def parse_compliance_response(text: str) -> dict:
    """Extract the JSON object from a model reply, tolerating code fences or prose."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object in model response")
    data = json.loads(match.group(0))
    score = int(data.get("score", 0))
    if not 1 <= score <= 10:
        raise ValueError(f"Score out of range: {score}")
    return {
        "score": score,
        "issues": list(data.get("issues", [])),
        "recommendations": list(data.get("recommendations", [])),
    }


# ---------- service logic ----------

def generate_job_description(role_id: str, custom_requirements: str | None = None) -> dict:
    from google.cloud import firestore

    db = get_db()
    culture_doc = db.collection("company_culture").document("default").get()
    if not culture_doc.exists:
        return {"error": "Company culture data not found", "status": 404}

    template_doc = db.collection("job_templates").document(role_id).get()
    if not template_doc.exists:
        return {"error": f"Job template '{role_id}' not found", "status": 404}

    culture, template = culture_doc.to_dict(), template_doc.to_dict()
    prompt = build_jd_prompt(culture, template, custom_requirements)
    response = get_genai().models.generate_content(model=MODEL, contents=prompt)

    _, job_ref = db.collection("generated_jobs").add({
        "role_id": role_id,
        "title": template["title"],
        "company_name": culture["company_name"],
        "custom_requirements": custom_requirements,
        "generated_description": response.text,
        "model": MODEL,
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    return {"success": True, "job_id": job_ref.id, "role": template["title"],
            "description": response.text}


def review_compliance(job_description: str) -> dict:
    from google.genai import types

    response = get_genai().models.generate_content(
        model=MODEL,
        contents=build_compliance_prompt(job_description),
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           temperature=0.2),
    )
    return parse_compliance_response(response.text)


# ---------- HTTP entry points ----------

@functions_framework.http
def generate_job_description_http(request):
    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)
    body = request.get_json(silent=True) or {}
    role_id = body.get("role_id")
    if not role_id:
        return jsonify({"error": "Missing role_id parameter"}), 400, CORS_HEADERS
    try:
        result = generate_job_description(role_id, body.get("custom_requirements"))
    except Exception as e:  # surface upstream errors as 500
        return jsonify({"error": str(e)}), 500, CORS_HEADERS
    status = result.pop("status", 200 if "error" not in result else 400)
    return jsonify(result), status, CORS_HEADERS


@functions_framework.http
def validate_compliance(request):
    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)
    body = request.get_json(silent=True) or {}
    jd = body.get("job_description")
    if not jd:
        return jsonify({"error": "Missing job_description"}), 400, CORS_HEADERS
    try:
        review = review_compliance(jd)
    except Exception as e:
        return jsonify({"error": str(e)}), 500, CORS_HEADERS
    return jsonify({"success": True, **review}), 200, CORS_HEADERS
