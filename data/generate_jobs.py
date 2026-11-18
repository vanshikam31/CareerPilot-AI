"""Generates data/sample_jobs.csv: SYNTHETIC jobs with fictional companies.
Seeded RNG, so the output is identical on every run."""
import csv
import random
from pathlib import Path

random.seed(42)

# (category, title, skills, description). Skill names match the Phase 2 skill catalog.
TEMPLATES = [
    ("AI/ML", "AI Engineer", ["Python", "LLMs", "RAG", "LangChain", "FastAPI", "Embeddings", "Prompt Engineering"],
     "Design and ship LLM-powered features such as retrieval-augmented chatbots, AI agents and semantic search."),
    ("AI/ML", "Machine Learning Engineer", ["Python", "Machine Learning", "Scikit-learn", "PyTorch", "MLOps", "Docker", "SQL"],
     "Train, evaluate and deploy machine learning models and maintain the pipelines that serve them in production."),
    ("AI/ML", "NLP Engineer", ["Python", "NLP", "Hugging Face", "PyTorch", "Embeddings", "Deep Learning"],
     "Build text classification, entity extraction and language understanding systems using transformer models."),
    ("AI/ML", "Computer Vision Engineer", ["Python", "Computer Vision", "OpenCV", "PyTorch", "Deep Learning", "Docker"],
     "Develop image and video analysis models for detection, segmentation and quality inspection."),
    ("AI/ML", "Data Scientist", ["Python", "Pandas", "SQL", "Scikit-learn", "Machine Learning", "Matplotlib"],
     "Analyse business data, build predictive models and present insights to product and leadership teams."),
    ("AI/ML", "Recommendation Systems Engineer", ["Python", "Recommendation Systems", "Embeddings", "SQL", "Machine Learning", "Redis"],
     "Build ranking and personalization models that power search results and recommendation feeds."),
    ("Backend", "Backend Engineer (Python)", ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs", "SQLAlchemy"],
     "Design REST APIs, database schemas and background workers for a high-traffic SaaS platform."),
    ("Backend", "Java Backend Developer", ["Java", "Spring Boot", "MySQL", "Microservices", "REST APIs", "Docker"],
     "Develop and maintain Java microservices and optimise database queries for enterprise clients."),
    ("Backend", "Node.js Developer", ["Node.js", "JavaScript", "MongoDB", "Express.js", "REST APIs", "Git"],
     "Build scalable server-side applications and APIs using Node.js and MongoDB."),
    ("Backend", "Software Engineer", ["Python", "Java", "Data Structures", "Algorithms", "SQL", "Git"],
     "Write clean, tested code, solve algorithmic problems and contribute to core product features across the stack."),
    ("Data", "Data Analyst", ["SQL", "Microsoft Excel", "Power BI", "Tableau", "Python", "Pandas"],
     "Create dashboards and reports, clean datasets and answer business questions with SQL and BI tools."),
    ("Data", "Data Engineer", ["Python", "SQL", "Apache Spark", "Airflow", "Kafka", "PostgreSQL", "AWS"],
     "Build and monitor batch and streaming data pipelines that feed analytics and machine learning."),
    ("Frontend", "Frontend Developer", ["React", "JavaScript", "TypeScript", "HTML", "CSS", "Tailwind CSS"],
     "Build responsive, accessible user interfaces and reusable component libraries with React."),
    ("Frontend", "Full Stack Developer", ["React", "Node.js", "JavaScript", "PostgreSQL", "REST APIs", "Docker"],
     "Own features end to end, from React user interfaces to APIs and database design."),
    ("DevOps", "DevOps Engineer", ["Docker", "Kubernetes", "CI/CD", "Linux", "AWS", "Terraform", "GitHub Actions"],
     "Automate build and deployment pipelines, manage cloud infrastructure and improve reliability."),
    ("DevOps", "Cloud Engineer", ["AWS", "Azure", "Linux", "Terraform", "Python", "Docker"],
     "Design secure, cost-efficient cloud infrastructure and automate provisioning."),
]

LEVELS = {
    "fresher": ("Associate ", "Freshers and final-year students are welcome (0-1 years of experience). You will learn from senior engineers."),
    "junior": ("Junior ", "1-3 years of experience expected. You will own small features with guidance."),
    "mid": ("", "3-6 years of experience expected. You will own features end to end and review code."),
    "senior": ("Senior ", "6+ years of experience expected. You will lead design decisions and mentor the team."),
}

COMPANIES = [
    "Nimbus Labs", "Orbit Technologies", "Zenith Analytics", "BrightPath Software", "Quantum Leaf",
    "PixelForge", "Cobalt Systems", "Lumen AI", "Vertex Cloud", "Maple Soft", "Atlas Data",
    "Skyline Digital", "Ember Works", "Nova Stack", "Pinecrest Tech", "Helix Robotics",
    "Summit Logic", "Tidal Analytics", "Kite Commerce", "Aurora Fintech", "Bluepeak Solutions",
    "Zephyr Networks", "Granite Labs", "Spark Harbor",
]
CITIES = ["Gurgaon", "Noida", "Delhi", "Bengaluru", "Hyderabad", "Pune", "Mumbai", "Jaipur", "Chennai"]
CITY_WEIGHTS = [3, 2, 2, 3, 2, 2, 1, 1, 1]
JOBS_PER_COMBO = 2

rows, seen = [], set()
for category, base_title, skills, role_desc in TEMPLATES:
    for level, (prefix, level_text) in LEVELS.items():
        made = 0
        while made < JOBS_PER_COMBO:
            company = random.choice(COMPANIES)
            work_mode = random.choice(["onsite", "hybrid", "remote"])
            location = "Remote" if work_mode == "remote" else random.choices(CITIES, CITY_WEIGHTS)[0]
            title = f"{prefix}{base_title}"
            key = (title, company, location)
            if key in seen:
                continue
            seen.add(key)
            keep = set(random.sample(skills, random.randint(max(4, len(skills) - 2), len(skills))))
            chosen = [s for s in skills if s in keep]
            where = "remote" if work_mode == "remote" else location
            description = (
                f"{company} is hiring a {title} for its {where} team. {role_desc} "
                f"Day-to-day you will work with {', '.join(chosen[:4])} and related tools. {level_text}"
            )
            rows.append({
                "title": title, "company": company, "location": location, "work_mode": work_mode,
                "experience_level": level, "category": category,
                "skills": "|".join(chosen), "description": description,
            })
            made += 1

out = Path(__file__).parent / "sample_jobs.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print(f"Wrote {len(rows)} jobs to {out}")