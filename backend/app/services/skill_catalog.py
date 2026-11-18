"""Deterministic skill matcher. Canonical name -> aliases.

Ambiguous words (Go, R, C, Excel, Spark) are deliberately only matched via
unambiguous forms (Golang, Microsoft Excel, Apache Spark).
"""
import re

SKILLS: dict[str, list[str]] = {
    # languages
    "Python": [], "Java": [], "JavaScript": [], "TypeScript": [], "C++": [], "C#": [],
    "Golang": ["go lang"], "Rust": [], "Kotlin": [], "Swift": [], "PHP": [], "Ruby": [],
    "Scala": [], "MATLAB": [], "Bash": [],
    # web / backend
    "HTML": [], "CSS": [], "React": ["reactjs", "react.js"], "Next.js": ["nextjs"],
    "Node.js": ["nodejs"], "Express.js": ["expressjs"], "Angular": [], "Vue.js": ["vuejs"],
    "Tailwind CSS": ["tailwind"], "FastAPI": [], "Flask": [], "Django": [],
    "Spring Boot": [], "REST APIs": ["rest api", "restful"], "GraphQL": [],
    "Microservices": [], "SQLAlchemy": [], "Celery": [], "JWT": [], "Streamlit": [],
    # data
    "SQL": [], "PostgreSQL": ["postgres"], "MySQL": [], "SQLite": [], "MongoDB": [],
    "Redis": [], "pgvector": [], "Elasticsearch": [], "Pandas": [], "NumPy": [],
    "Matplotlib": [], "Seaborn": [], "Power BI": [], "Tableau": [],
    "Microsoft Excel": ["ms excel", "advanced excel"], "Apache Spark": ["pyspark"],
    "Kafka": [], "Airflow": [],
    # ML / AI
    "Machine Learning": [], "Deep Learning": [], "NLP": ["natural language processing"],
    "Computer Vision": [], "Scikit-learn": ["sklearn", "scikit learn"], "TensorFlow": [],
    "PyTorch": [], "Keras": [], "Hugging Face": ["huggingface"], "LangChain": [],
    "LangGraph": [], "LlamaIndex": [],
    "RAG": ["retrieval augmented generation", "retrieval-augmented generation"],
    "LLMs": ["llm", "large language models"], "Prompt Engineering": [],
    "Generative AI": ["genai", "gen ai"], "OpenAI": [], "Gemini": [],
    "Embeddings": ["embedding"], "FAISS": [], "Pinecone": [], "ChromaDB": ["chroma"],
    "OpenCV": [], "XGBoost": [], "MLOps": [],
    "Recommendation Systems": ["recommender system", "recommender systems", "recommendation system"],
    # devops / tools
    "Docker": [], "Kubernetes": ["k8s"], "Git": [], "GitHub": [], "GitHub Actions": [],
    "CI/CD": [], "AWS": [], "Azure": [], "GCP": ["google cloud"], "Linux": [],
    "Nginx": [], "Terraform": [], "Pytest": [], "Postman": [], "Jira": [], "Agile": [],
    # CS fundamentals
    "Data Structures": ["dsa", "data structures and algorithms"], "Algorithms": [],
    "OOP": ["object oriented programming", "object-oriented programming"],
    "System Design": [],
}


def _pattern(term: str) -> re.Pattern:
    # Not preceded/followed by a word char, +, # (so "Java" never matches "JavaScript",
    # and "SQL" never matches "PostgreSQL").
    return re.compile(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#])", re.IGNORECASE)


_COMPILED = [
    (canonical, [_pattern(t) for t in [canonical, *aliases]])
    for canonical, aliases in SKILLS.items()
]


def extract_skills(text: str) -> list[str]:
    return [
        canonical
        for canonical, patterns in _COMPILED
        if any(p.search(text) for p in patterns)
    ]