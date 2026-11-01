import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
import main  # noqa: E402

CULTURE = {
    "company_name": "Acme", "mission": "Build things", "values": ["Integrity"],
    "culture_description": "Collaborative", "benefits": ["Health"],
    "work_environment": "Remote",
}
TEMPLATE = {
    "title": "ML Engineer", "department": "AI", "level": "entry",
    "required_skills": ["Python"], "nice_to_have": ["GCP"],
    "education": "BSc", "experience_years": "0-2",
    "responsibilities": ["Train models"],
}

app = Flask(__name__)


def call(fn, body, method="POST"):
    with app.test_request_context(method=method, json=body):
        from flask import request
        resp = fn(request)
        if isinstance(resp[0], str):
            return resp[0], resp[1]
        return resp[0].get_json(), resp[1]


def test_jd_prompt_contains_context():
    p = main.build_jd_prompt(CULTURE, TEMPLATE, "Must know Vertex AI")
    for s in ["ML Engineer", "Acme", "Python", "Must know Vertex AI", "Equal Opportunity"]:
        assert s in p


def test_parse_compliance_handles_fences():
    text = '```json\n{"score": 4, "issues": ["age limit"], "recommendations": ["remove"]}\n```'
    assert main.parse_compliance_response(text) == {
        "score": 4, "issues": ["age limit"], "recommendations": ["remove"]}


@pytest.mark.parametrize("bad", ["no json here", '{"score": 42}'])
def test_parse_compliance_rejects_bad(bad):
    with pytest.raises(ValueError):
        main.parse_compliance_response(bad)


def test_generate_requires_role_id():
    data, status = call(main.generate_job_description_http, {})
    assert status == 400 and "role_id" in data["error"]


def test_options_preflight():
    _, status = call(main.generate_job_description_http, None, method="OPTIONS")
    assert status == 204


def _doc(data):
    d = MagicMock()
    d.exists = data is not None
    d.to_dict.return_value = data
    return d


def test_generate_happy_path():
    db = MagicMock()
    docs = {"company_culture": _doc(CULTURE), "job_templates": _doc(TEMPLATE)}
    db.collection.side_effect = lambda name: MagicMock(
        document=lambda _id: MagicMock(get=lambda: docs.get(name)),
        add=MagicMock(return_value=(None, MagicMock(id="job123"))),
    )
    genai = MagicMock()
    genai.models.generate_content.return_value = MagicMock(text="# ML Engineer at Acme")
    with patch.object(main, "get_db", return_value=db), \
         patch.object(main, "get_genai", return_value=genai), \
         patch.dict(sys.modules, {"google.cloud.firestore": MagicMock()}):
        data, status = call(main.generate_job_description_http, {"role_id": "ml_engineer"})
    assert status == 200
    assert data["job_id"] == "job123" and data["description"].startswith("# ML Engineer")


def test_generate_unknown_role_404():
    db = MagicMock()
    docs = {"company_culture": _doc(CULTURE), "job_templates": _doc(None)}
    db.collection.side_effect = lambda name: MagicMock(
        document=lambda _id: MagicMock(get=lambda: docs.get(name)))
    with patch.object(main, "get_db", return_value=db), \
         patch.dict(sys.modules, {"google.cloud.firestore": MagicMock()}):
        data, status = call(main.generate_job_description_http, {"role_id": "nope"})
    assert status == 404


def test_validate_compliance_returns_structured_review():
    review = {"score": 3, "issues": ["age requirement"], "recommendations": ["remove it"]}
    with patch.object(main, "review_compliance", return_value=review):
        data, status = call(main.validate_compliance,
                            {"job_description": "Must be under 35"})
    assert status == 200 and data["score"] == 3
