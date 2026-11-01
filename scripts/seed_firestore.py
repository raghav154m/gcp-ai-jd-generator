"""Seed Firestore with company culture data and job role templates."""
import os

from google.cloud import firestore

db = firestore.Client(project=os.environ["PROJECT_ID"])

db.collection("company_culture").document("default").set({
    "company_name": "TechInnovate Solutions",
    "mission": "Empowering businesses through innovative technology solutions",
    "values": ["Innovation", "Collaboration", "Integrity", "Excellence"],
    "culture_description": "Fast-paced, collaborative environment focused on continuous learning",
    "benefits": ["Competitive salary", "Health insurance", "Remote work options",
                 "Professional development budget"],
    "work_environment": "Hybrid office model with flexible hours",
})

templates = {
    "software_engineer": {
        "title": "Software Engineer", "department": "Engineering", "level": "mid",
        "required_skills": ["Python", "JavaScript", "React", "Node.js"],
        "nice_to_have": ["Google Cloud", "Docker", "GraphQL"],
        "education": "Bachelor's degree in Computer Science or equivalent experience",
        "experience_years": "2-4 years",
        "responsibilities": ["Develop and maintain web applications",
                             "Collaborate with cross-functional teams",
                             "Write clean, maintainable, tested code",
                             "Participate in code reviews"],
        "compliance_notes": "Equal opportunity employer statement required",
    },
    "ml_engineer": {
        "title": "Machine Learning Engineer", "department": "AI/ML", "level": "entry",
        "required_skills": ["Python", "PyTorch or TensorFlow", "SQL", "Statistics"],
        "nice_to_have": ["Vertex AI", "MLOps", "Docker", "LLM fine-tuning"],
        "education": "Bachelor's or Master's in CS, Physics, Mathematics or related field",
        "experience_years": "0-2 years",
        "responsibilities": ["Train, evaluate and deploy ML models",
                             "Build data pipelines for model training",
                             "Monitor models in production",
                             "Communicate results to stakeholders"],
        "compliance_notes": "Equal opportunity employer statement required",
    },
    "marketing_manager": {
        "title": "Marketing Manager", "department": "Marketing", "level": "senior",
        "required_skills": ["Digital Marketing", "Campaign Management", "Analytics",
                            "Content Strategy"],
        "nice_to_have": ["Marketing Automation", "SQL"],
        "education": "Bachelor's degree in Marketing, Business, or related field",
        "experience_years": "5-7 years",
        "responsibilities": ["Develop marketing strategies and campaigns",
                             "Own marketing budget and ROI",
                             "Lead the marketing team",
                             "Analyze market and competitor trends"],
        "compliance_notes": "Equal opportunity employer statement required",
    },
}
for role_id, data in templates.items():
    db.collection("job_templates").document(role_id).set(data)

print(f"Seeded company culture + {len(templates)} job templates")
