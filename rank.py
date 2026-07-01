#!/usr/bin/env python3
"""
Redrob Intelligent Candidate Ranking System
============================================
India Runs 2026 · Track 1: The Data & AI Challenge
Author: Aaryan Karthik (Boyapati)

Ranks 100,000 candidates against a specific JD (Senior AI/ML Engineer at Redrob)
using multi-dimensional scoring with honeypot detection.

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Constraints: ≤5 min, ≤16 GB RAM, CPU only, no network, no external APIs.
"""

import argparse
import csv
import gzip
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Any

# ============================================================================
# CONFIGURATION — All scoring weights and thresholds
# ============================================================================

WEIGHTS = {
    "role_fit":     0.30,
    "skill_match":  0.25,
    "career":       0.15,
    "behavioral":   0.20,
    "logistics":    0.10,
}

# Reference date for recency calculations
REFERENCE_DATE = date(2026, 6, 1)

# ============================================================================
# JOB DESCRIPTION REQUIREMENTS (extracted from job_description.docx)
# ============================================================================

# Core required skills — what the JD says you "absolutely need"
MUST_HAVE_SKILLS = {
    # Embeddings-based retrieval
    "sentence-transformers", "openai embeddings", "bge", "e5",
    "embeddings", "word embeddings", "sentence embeddings",
    "embedding", "word2vec", "fasttext", "glove",
    # Vector databases / hybrid search
    "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
    "elasticsearch", "faiss", "vector database", "vector db",
    "hybrid search", "vector search", "similarity search",
    "annoy", "hnsw", "scann",
    # Python
    "python",
    # Ranking/evaluation
    "ndcg", "mrr", "map", "ranking", "learning to rank",
    "information retrieval", "search", "recommendation",
    "evaluation", "a/b testing", "ab testing",
    # NLP/IR core
    "nlp", "natural language processing", "ir",
    "text classification", "text mining", "text processing",
    "retrieval", "search systems", "search engine",
    # ML/AI production
    "machine learning", "ml", "deep learning", "dl",
    "neural networks", "transformers", "huggingface",
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn",
    "model deployment", "mlops", "ml engineering",
}

# Nice-to-have skills
NICE_TO_HAVE_SKILLS = {
    "lora", "qlora", "peft", "fine-tuning", "fine-tuning llms",
    "finetuning", "llm fine-tuning",
    "xgboost", "lightgbm", "catboost", "gradient boosting",
    "distributed systems", "large-scale", "inference optimization",
    "hr-tech", "recruiting", "marketplace",
    "open-source", "open source", "github",
    "rag", "retrieval augmented generation",
    "langchain", "llamaindex", "llama",
    "prompt engineering", "prompt design",
    "bert", "gpt", "llm", "large language model",
    "bentoml", "mlflow", "weights & biases", "wandb",
    "docker", "kubernetes", "k8s",
    "aws", "gcp", "azure", "cloud",
    "spark", "airflow", "kafka", "data pipeline",
    "sql", "postgresql", "mongodb", "redis",
    "api", "rest", "graphql", "microservices",
    "system design", "architecture",
}

# Skills that are RED FLAGS for this JD (mentioned in JD "do NOT want")
IRRELEVANT_PRIMARY_SKILLS = {
    "computer vision", "image classification", "object detection",
    "speech recognition", "speech", "tts", "text to speech",
    "robotics", "autonomous", "self-driving",
    "photoshop", "illustrator", "figma", "sketch", "canva",
    "marketing", "seo", "content writing", "copywriting",
    "accounting", "finance", "tax", "audit",
    "mechanical engineering", "civil engineering", "chemical engineering",
    "solidworks", "autocad", "creo", "ansys",
    "six sigma", "lean", "supply chain",
    "hr", "human resources", "recruitment", "talent acquisition",
    "sales", "business development", "lead generation",
    "angular", "react", "vue", "frontend", "tailwind", "css",
    "ui/ux", "ux design", "ui design", "graphic design",
    "powerpoint", "excel", "word",
    "project management", "scrum", "agile", "jira",
}

# Titles that indicate strong fit
STRONG_FIT_TITLES = {
    "ml engineer", "machine learning engineer", "ai engineer",
    "senior ml engineer", "senior machine learning engineer",
    "senior ai engineer", "lead ml engineer", "staff ml engineer",
    "data scientist", "senior data scientist", "lead data scientist",
    "nlp engineer", "search engineer", "ranking engineer",
    "applied scientist", "research engineer", "ml scientist",
    "backend engineer",  # can be fit if they have ML skills
    "software engineer",  # can be fit if they have ML skills
    "senior software engineer", "senior backend engineer",
    "full stack engineer", "senior full stack engineer",
    "data engineer", "senior data engineer",
    "platform engineer",
}

# Titles that are explicitly NOT a fit
POOR_FIT_TITLES = {
    "marketing manager", "hr manager", "operations manager",
    "sales executive", "accountant", "customer support",
    "graphic designer", "content writer", "mechanical engineer",
    "civil engineer", "business analyst", "project manager",
    "product manager",  # close but JD wants an IC engineer
}

# Services/consulting companies (JD explicitly says "do NOT want" pure-services)
SERVICES_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mindtree", "mphasis",
    "l&t infotech", "persistent systems", "cyient", "ltimindtree",
    "hexaware", "niit", "zensar",
}

# Fictional/placeholder companies in the dataset
FICTIONAL_COMPANIES = {
    "acme corp", "dunder mifflin", "globex inc", "initech",
    "stark industries", "wayne enterprises", "umbrella corp",
    "oscorp", "cyberdyne", "weyland-yutani",
}

# Target locations (JD says Pune/Noida-preferred, India-based)
PREFERRED_LOCATIONS = {
    "pune", "noida", "delhi", "new delhi", "delhi ncr",
    "gurgaon", "gurugram", "hyderabad", "mumbai",
}

INDIA_LOCATIONS = {
    "india", "bangalore", "bengaluru", "chennai", "kolkata",
    "jaipur", "ahmedabad", "lucknow", "chandigarh", "bhopal",
    "kochi", "thiruvananthapuram", "patna", "indore",
    "coimbatore", "visakhapatnam", "nagpur", "surat",
    "gurgaon", "gurugram", "pune", "noida", "delhi",
    "new delhi", "delhi ncr", "hyderabad", "mumbai",
    "haryana", "karnataka", "maharashtra", "tamil nadu",
    "telangana", "uttar pradesh", "rajasthan", "kerala",
    "west bengal", "madhya pradesh", "gujarat",
}

# Education tiers
EDUCATION_RELEVANCE = {
    "computer science": 1.0,
    "information technology": 0.9,
    "artificial intelligence": 1.0,
    "machine learning": 1.0,
    "data science": 0.95,
    "software engineering": 0.9,
    "electrical engineering": 0.6,
    "electronics": 0.6,
    "mathematics": 0.7,
    "statistics": 0.75,
    "physics": 0.5,
    "mechanical engineering": 0.2,
    "civil engineering": 0.1,
    "chemical engineering": 0.1,
}

TIER_SCORES = {
    "tier_1": 1.0,
    "tier_2": 0.75,
    "tier_3": 0.5,
    "tier_4": 0.25,
    "unknown": 0.35,
}

# ============================================================================
# HONEYPOT DETECTION
# ============================================================================

def detect_honeypot(candidate: dict) -> bool:
    """
    Detect honeypot candidates with subtly impossible profiles.
    
    Honeypot signals:
    1. Expert in 10+ skills with 0 duration months
    2. Years of experience at a company exceeds what's plausible
    3. Massive skill endorsements with beginner proficiency
    4. Impossible skill assessment scores (high scores on unrelated skills)
    5. Profile signals that are internally contradictory
    """
    flags = 0
    
    skills = candidate.get("skills", [])
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    signals = candidate.get("redrob_signals", {})
    
    # Check 1: Skills with expert/advanced proficiency but 0 or very low duration
    expert_zero_duration = sum(
        1 for s in skills
        if s.get("proficiency") in ("expert", "advanced")
        and s.get("duration_months", 0) <= 2
    )
    if expert_zero_duration >= 3:
        flags += 2
    
    # Check 2: Too many advanced/expert skills relative to experience
    yoe = profile.get("years_of_experience", 0)
    advanced_count = sum(
        1 for s in skills 
        if s.get("proficiency") in ("expert", "advanced")
    )
    if yoe < 3 and advanced_count >= 6:
        flags += 2
    
    # Check 3: High endorsements on skills with beginner proficiency
    sus_endorsements = sum(
        1 for s in skills
        if s.get("proficiency") == "beginner"
        and s.get("endorsements", 0) > 30
    )
    if sus_endorsements >= 2:
        flags += 1
    
    # Check 4: Career duration doesn't add up
    total_career_months = sum(c.get("duration_months", 0) for c in career)
    expected_months = yoe * 12
    if total_career_months > 0 and expected_months > 0:
        ratio = total_career_months / expected_months
        if ratio > 2.0 or ratio < 0.3:
            flags += 1
    
    # Check 5: Company experience impossibly long
    for job in career:
        duration = job.get("duration_months", 0)
        company = job.get("company", "").lower()
        # If they claim 100+ months at a fictional company, suspicious
        if duration > 120 and company in FICTIONAL_COMPANIES:
            flags += 1
    
    # Check 6: Skill assessment scores very high on skills they have beginner proficiency
    assessments = signals.get("skill_assessment_scores", {})
    for skill_name, score in assessments.items():
        matching = [s for s in skills if s["name"].lower() == skill_name.lower()]
        if matching and matching[0].get("proficiency") == "beginner" and score > 85:
            flags += 1
    
    # Check 7: Wildly inconsistent profile - headline/title doesn't match career at all
    title = profile.get("current_title", "").lower()
    headline = profile.get("headline", "").lower()
    
    # Check for completely mismatched skill profiles
    # E.g., "Marketing Manager" with expert-level ML skills and 0 duration
    if title in POOR_FIT_TITLES or any(t in title for t in ["manager", "support", "accountant", "designer"]):
        ml_expert_skills = sum(
            1 for s in skills
            if s.get("proficiency") in ("expert", "advanced")
            and s["name"].lower() in MUST_HAVE_SKILLS
            and s.get("duration_months", 0) <= 6
        )
        if ml_expert_skills >= 3:
            flags += 2
    
    # Check 8: Profile completeness vs actual content mismatch
    completeness = signals.get("profile_completeness_score", 50)
    if completeness > 90 and len(skills) <= 2 and len(career) <= 1:
        flags += 1
    
    # Check 9: Impossibly high GitHub score with no technical background
    github = signals.get("github_activity_score", -1)
    has_tech_career = any(
        job.get("industry", "").lower() in ("software", "it services", "technology", "tech")
        or any(kw in job.get("description", "").lower() for kw in ["code", "software", "engineer", "develop", "python", "api"])
        for job in career
    )
    if github > 80 and not has_tech_career and yoe > 5:
        flags += 1
    
    return flags >= 3


# ============================================================================
# SKILL MATCHING ENGINE
# ============================================================================

def normalize_skill(skill_name: str) -> str:
    """Normalize a skill name for matching."""
    return skill_name.lower().strip().replace("-", " ").replace("_", " ")


def compute_skill_match_score(candidate: dict) -> tuple[float, dict]:
    """
    Compute skill match score against JD requirements.
    
    Returns (score, details_dict)
    
    Strategy:
    - Direct matches to must-have skills: high value
    - Nice-to-have matches: moderate value
    - Account for skill proficiency and duration
    - Penalize keyword-stuffing (many skills, all beginner, short duration)
    - Check for irrelevant primary skills
    """
    skills = candidate.get("skills", [])
    if not skills:
        return 0.0, {"must_have_matches": [], "nice_to_have_matches": []}
    
    must_have_matches = []
    nice_to_have_matches = []
    irrelevant_count = 0
    keyword_stuff_signals = 0
    
    proficiency_weights = {
        "expert": 1.0,
        "advanced": 0.8,
        "intermediate": 0.55,
        "beginner": 0.25,
    }
    
    for skill in skills:
        name = normalize_skill(skill.get("name", ""))
        prof = skill.get("proficiency", "beginner")
        duration = skill.get("duration_months", 0)
        endorsements = skill.get("endorsements", 0)
        
        prof_weight = proficiency_weights.get(prof, 0.25)
        
        # Duration weight: more months = more credibility, cap at 48 months
        duration_weight = min(duration / 48.0, 1.0) if duration > 0 else 0.1
        
        # Endorsement boost (mild)
        endorsement_boost = min(endorsements / 50.0, 0.3)
        
        skill_value = prof_weight * 0.6 + duration_weight * 0.3 + endorsement_boost * 0.1
        
        # Check if this skill matches must-have
        if name in MUST_HAVE_SKILLS or any(mh in name for mh in MUST_HAVE_SKILLS):
            must_have_matches.append((name, skill_value))
        
        # Check nice-to-have
        elif name in NICE_TO_HAVE_SKILLS or any(nh in name for nh in NICE_TO_HAVE_SKILLS):
            nice_to_have_matches.append((name, skill_value))
        
        # Check irrelevant
        if name in IRRELEVANT_PRIMARY_SKILLS or any(ir in name for ir in IRRELEVANT_PRIMARY_SKILLS):
            irrelevant_count += 1
        
        # Keyword stuffing detection: beginner + very low duration + many skills
        if prof == "beginner" and duration <= 3:
            keyword_stuff_signals += 1
    
    # Score computation
    # Must-have: sum of values, capped, then normalized
    must_have_score = min(sum(v for _, v in must_have_matches), 4.0) / 4.0
    
    # Nice-to-have: bonus on top
    nice_to_have_score = min(sum(v for _, v in nice_to_have_matches), 3.0) / 3.0
    
    # Combined skill score
    raw_score = must_have_score * 0.7 + nice_to_have_score * 0.3
    
    # Keyword stuffing penalty
    if len(skills) > 0:
        stuff_ratio = keyword_stuff_signals / len(skills)
        if stuff_ratio > 0.6:
            raw_score *= 0.5  # Heavy penalty for keyword stuffers
        elif stuff_ratio > 0.4:
            raw_score *= 0.7
    
    # Irrelevant skills don't directly penalize but reduce if they're the majority
    if len(skills) > 0 and irrelevant_count / len(skills) > 0.5:
        raw_score *= 0.7
    
    return min(raw_score, 1.0), {
        "must_have_matches": must_have_matches,
        "nice_to_have_matches": nice_to_have_matches,
        "irrelevant_count": irrelevant_count,
    }


# ============================================================================
# ROLE FIT SCORING
# ============================================================================

def compute_role_fit_score(candidate: dict) -> tuple[float, dict]:
    """
    Assess how well the candidate's role/career fits the JD.
    
    Key signals:
    - Current title alignment
    - Career history: product vs services companies
    - ML/AI production experience in descriptions
    - Summary/headline relevance
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    
    title = profile.get("current_title", "").lower().strip()
    headline = profile.get("headline", "").lower()
    summary = profile.get("summary", "").lower()
    yoe = profile.get("years_of_experience", 0)
    company = profile.get("current_company", "").lower().strip()
    industry = profile.get("current_industry", "").lower()
    
    details = {}
    
    # --- Title fit ---
    title_score = 0.0
    if title in STRONG_FIT_TITLES:
        title_score = 1.0
    elif any(t in title for t in ["ml", "machine learning", "ai", "data scien", "nlp", "search", "ranking"]):
        title_score = 0.9
    elif any(t in title for t in ["software engineer", "backend", "full stack", "developer", "data engineer"]):
        title_score = 0.5  # Possible fit if they have ML skills
    elif title in POOR_FIT_TITLES or any(t in title for t in ["manager", "support", "accountant", "designer", "writer", "sales", "hr"]):
        title_score = 0.05  # Very poor fit
    else:
        title_score = 0.3  # Unknown title
    
    details["title_score"] = title_score
    details["title"] = title
    
    # --- Experience range fit ---
    # JD says 5-9 years preferred, but flexible
    exp_score = 0.0
    if 5 <= yoe <= 9:
        exp_score = 1.0
    elif 4 <= yoe < 5 or 9 < yoe <= 12:
        exp_score = 0.7
    elif 3 <= yoe < 4 or 12 < yoe <= 15:
        exp_score = 0.4
    elif yoe > 15:
        exp_score = 0.2  # Too senior, may not write code
    elif yoe < 3:
        exp_score = 0.15  # Too junior
    
    details["exp_score"] = exp_score
    
    # --- Summary/headline relevance ---
    # Check for keywords that indicate ML/AI/ranking/search production experience
    ml_production_keywords = [
        "embedding", "vector", "retrieval", "ranking", "search",
        "recommendation", "nlp", "natural language", "information retrieval",
        "machine learning", "deep learning", "model", "deploy",
        "production", "shipped", "built", "scaled", "inference",
        "pipeline", "feature engineering", "training",
        "pytorch", "tensorflow", "transformers", "huggingface",
        "rag", "retrieval augmented",
    ]
    
    # Count keyword hits in summary
    summary_hits = sum(1 for kw in ml_production_keywords if kw in summary)
    headline_hits = sum(1 for kw in ml_production_keywords if kw in headline)
    
    summary_score = min((summary_hits * 0.15 + headline_hits * 0.2), 1.0)
    details["summary_relevance"] = summary_score
    
    # --- Career in product vs services ---
    product_experience_months = 0
    services_experience_months = 0
    ml_career_months = 0
    
    for job in career:
        comp = job.get("company", "").lower().strip()
        dur = job.get("duration_months", 0)
        desc = job.get("description", "").lower()
        job_title = job.get("title", "").lower()
        
        # Check if services company
        if comp in SERVICES_COMPANIES or any(sc in comp for sc in SERVICES_COMPANIES):
            services_experience_months += dur
        else:
            product_experience_months += dur
        
        # Check if ML-related role
        ml_keywords_in_desc = sum(1 for kw in ml_production_keywords if kw in desc)
        ml_keywords_in_title = sum(1 for kw in ["ml", "machine learning", "ai", "data", "nlp", "search"] if kw in job_title)
        
        if ml_keywords_in_desc >= 2 or ml_keywords_in_title >= 1:
            ml_career_months += dur
    
    total_months = product_experience_months + services_experience_months
    
    # Product vs services ratio
    if total_months > 0:
        product_ratio = product_experience_months / total_months
    else:
        product_ratio = 0.5
    
    # JD explicitly says pure-services is a red flag
    if services_experience_months > 0 and product_experience_months == 0:
        career_type_score = 0.1  # Pure services — JD says "do NOT want"
    elif product_ratio > 0.5:
        career_type_score = 0.8 + (product_ratio - 0.5) * 0.4  # Strong product background
    else:
        career_type_score = 0.3 + product_ratio * 0.5
    
    details["career_type_score"] = career_type_score
    details["product_months"] = product_experience_months
    details["services_months"] = services_experience_months
    
    # ML career depth
    if total_months > 0:
        ml_career_ratio = ml_career_months / total_months
    else:
        ml_career_ratio = 0
    
    ml_depth_score = min(ml_career_ratio * 1.5, 1.0)
    details["ml_depth_score"] = ml_depth_score
    
    # --- Combine ---
    role_fit = (
        title_score * 0.30 +
        exp_score * 0.20 +
        summary_score * 0.15 +
        career_type_score * 0.20 +
        ml_depth_score * 0.15
    )
    
    return min(role_fit, 1.0), details


# ============================================================================
# CAREER QUALITY SCORING
# ============================================================================

def compute_career_score(candidate: dict) -> tuple[float, dict]:
    """
    Assess career quality and trajectory.
    
    Signals:
    - Number of roles and progression
    - Company diversity (not just one company)
    - Role titles showing growth
    - Industry relevance
    - Education quality and field relevance
    """
    career = candidate.get("career_history", [])
    education = candidate.get("education", [])
    certifications = candidate.get("certifications", [])
    
    details = {}
    
    # --- Career progression ---
    num_roles = len(career)
    if num_roles == 0:
        return 0.1, {"note": "no career history"}
    
    # Moderate job hopping check
    # JD explicitly warns against "switching companies every 1.5 years"
    avg_tenure_months = sum(j.get("duration_months", 0) for j in career) / num_roles if num_roles > 0 else 0
    
    if avg_tenure_months >= 30:
        tenure_score = 1.0  # Stable
    elif avg_tenure_months >= 20:
        tenure_score = 0.7
    elif avg_tenure_months >= 12:
        tenure_score = 0.4  # Somewhat hopper-ish
    else:
        tenure_score = 0.15  # Job hopper
    
    details["avg_tenure_months"] = avg_tenure_months
    details["tenure_score"] = tenure_score
    
    # --- Education ---
    edu_score = 0.3  # default
    if education:
        best_edu = 0
        for edu in education:
            field = edu.get("field_of_study", "").lower()
            tier = edu.get("tier", "unknown")
            degree = edu.get("degree", "").lower()
            
            field_relevance = 0.3
            for field_name, score in EDUCATION_RELEVANCE.items():
                if field_name in field:
                    field_relevance = max(field_relevance, score)
            
            tier_score = TIER_SCORES.get(tier, 0.35)
            
            degree_weight = 1.0
            if "ph.d" in degree or "phd" in degree:
                degree_weight = 1.1
            elif "m.tech" in degree or "m.e." in degree or "m.sc" in degree or "ms" in degree:
                degree_weight = 1.0
            elif "b.tech" in degree or "b.e." in degree or "b.sc" in degree:
                degree_weight = 0.9
            
            combined = (field_relevance * 0.5 + tier_score * 0.4) * degree_weight
            best_edu = max(best_edu, combined)
        
        edu_score = min(best_edu, 1.0)
    
    details["edu_score"] = edu_score
    
    # --- Certifications ---
    relevant_certs = 0
    for cert in certifications:
        cert_name = cert.get("name", "").lower()
        if any(kw in cert_name for kw in ["aws", "gcp", "azure", "ml", "ai", "data", "python", "tensorflow", "deep learning"]):
            relevant_certs += 1
    
    cert_score = min(relevant_certs * 0.3, 0.6)
    details["cert_score"] = cert_score
    
    # --- Combine ---
    career_quality = (
        tenure_score * 0.40 +
        edu_score * 0.40 +
        cert_score * 0.20
    )
    
    return min(career_quality, 1.0), details


# ============================================================================
# BEHAVIORAL SIGNAL SCORING
# ============================================================================

def compute_behavioral_score(candidate: dict) -> tuple[float, dict]:
    """
    Score based on Redrob behavioral signals.
    
    Key principle from JD: "A perfect-on-paper candidate who hasn't logged in for
    6 months and has a 5% recruiter response rate is, for hiring purposes, not 
    actually available."
    """
    signals = candidate.get("redrob_signals", {})
    details = {}
    
    # --- Recruiter response rate (very important) ---
    response_rate = signals.get("recruiter_response_rate", 0)
    if response_rate >= 0.7:
        response_score = 1.0
    elif response_rate >= 0.5:
        response_score = 0.8
    elif response_rate >= 0.3:
        response_score = 0.5
    elif response_rate >= 0.15:
        response_score = 0.3
    else:
        response_score = 0.1  # Very unresponsive
    
    details["response_score"] = response_score
    
    # --- Response time ---
    avg_response_hours = signals.get("avg_response_time_hours", 100)
    if avg_response_hours <= 12:
        time_score = 1.0
    elif avg_response_hours <= 24:
        time_score = 0.85
    elif avg_response_hours <= 48:
        time_score = 0.7
    elif avg_response_hours <= 96:
        time_score = 0.5
    else:
        time_score = 0.2  # Very slow to respond
    
    details["time_score"] = time_score
    
    # --- Recency / activity ---
    last_active_str = signals.get("last_active_date", "2025-01-01")
    try:
        last_active = datetime.strptime(last_active_str, "%Y-%m-%d").date()
        days_inactive = (REFERENCE_DATE - last_active).days
    except (ValueError, TypeError):
        days_inactive = 365
    
    if days_inactive <= 30:
        recency_score = 1.0
    elif days_inactive <= 60:
        recency_score = 0.85
    elif days_inactive <= 90:
        recency_score = 0.7
    elif days_inactive <= 180:
        recency_score = 0.4
    else:
        recency_score = 0.15  # Hasn't logged in for 6+ months
    
    details["recency_score"] = recency_score
    details["days_inactive"] = days_inactive
    
    # --- Open to work ---
    open_to_work = signals.get("open_to_work_flag", False)
    otw_score = 1.0 if open_to_work else 0.5
    details["otw_score"] = otw_score
    
    # --- Profile completeness ---
    completeness = signals.get("profile_completeness_score", 50)
    completeness_score = completeness / 100.0
    details["completeness_score"] = completeness_score
    
    # --- GitHub activity ---
    github = signals.get("github_activity_score", -1)
    if github < 0:
        github_score = 0.3  # No GitHub — neutral-ish
    elif github >= 60:
        github_score = 1.0
    elif github >= 30:
        github_score = 0.7
    elif github >= 10:
        github_score = 0.5
    else:
        github_score = 0.35
    
    details["github_score"] = github_score
    
    # --- Interview completion rate ---
    interview_rate = signals.get("interview_completion_rate", 0.5)
    interview_score = interview_rate  # Direct: 0.0-1.0
    details["interview_score"] = interview_score
    
    # --- Verification signals ---
    verified = 0
    if signals.get("verified_email", False):
        verified += 1
    if signals.get("verified_phone", False):
        verified += 1
    if signals.get("linkedin_connected", False):
        verified += 1
    verification_score = verified / 3.0
    details["verification_score"] = verification_score
    
    # --- Recruiter interest (saved + profile views) ---
    saved = signals.get("saved_by_recruiters_30d", 0)
    views = signals.get("profile_views_received_30d", 0)
    interest_score = min((saved * 0.05 + views * 0.02), 1.0)
    details["interest_score"] = interest_score
    
    # --- Combine ---
    behavioral = (
        response_score * 0.25 +
        time_score * 0.10 +
        recency_score * 0.20 +
        otw_score * 0.08 +
        completeness_score * 0.07 +
        github_score * 0.10 +
        interview_score * 0.08 +
        verification_score * 0.05 +
        interest_score * 0.07
    )
    
    return min(behavioral, 1.0), details


# ============================================================================
# LOGISTICS SCORING
# ============================================================================

def compute_logistics_score(candidate: dict) -> tuple[float, dict]:
    """
    Score based on location, notice period, salary, and work mode.
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    location = profile.get("location", "").lower()
    country = profile.get("country", "").lower()
    
    details = {}
    
    # --- Location ---
    if any(loc in location for loc in PREFERRED_LOCATIONS):
        location_score = 1.0
    elif country == "india" or any(loc in location for loc in INDIA_LOCATIONS):
        location_score = 0.7
    elif signals.get("willing_to_relocate", False):
        location_score = 0.4
    else:
        location_score = 0.15  # Outside India, not willing to relocate
    
    details["location_score"] = location_score
    
    # --- Notice period ---
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        notice_score = 1.0  # JD says "love sub-30-day"
    elif notice <= 60:
        notice_score = 0.7  # Can buy out up to 30
    elif notice <= 90:
        notice_score = 0.4  # JD says "bar gets higher"
    else:
        notice_score = 0.2  # 90+ days, very high bar
    
    details["notice_score"] = notice_score
    
    # --- Work mode ---
    work_mode = signals.get("preferred_work_mode", "onsite")
    if work_mode in ("hybrid", "flexible"):
        work_mode_score = 1.0  # JD is mostly hybrid (Tue/Thu office)
    elif work_mode == "onsite":
        work_mode_score = 0.8
    elif work_mode == "remote":
        work_mode_score = 0.6
    else:
        work_mode_score = 0.5
    
    details["work_mode_score"] = work_mode_score
    
    # --- Salary alignment ---
    salary = signals.get("expected_salary_range_inr_lpa", {})
    sal_min = salary.get("min", 0)
    sal_max = salary.get("max", 0)
    # The JD doesn't specify salary, but for a senior AI role at a startup,
    # expect 25-50 LPA range. Way above or way below is a mismatch signal
    if sal_min > 0:
        if 15 <= sal_max <= 60:
            salary_score = 0.8
        elif sal_max < 15:
            salary_score = 0.6  # Might be a mismatch or they're underselling
        elif sal_max > 60:
            salary_score = 0.4  # Might be too expensive
        else:
            salary_score = 0.5
    else:
        salary_score = 0.5  # No salary data
    
    details["salary_score"] = salary_score
    
    # --- Combine ---
    logistics = (
        location_score * 0.40 +
        notice_score * 0.25 +
        work_mode_score * 0.15 +
        salary_score * 0.20
    )
    
    return min(logistics, 1.0), details


# ============================================================================
# REASONING GENERATOR
# ============================================================================

def generate_reasoning(
    candidate: dict,
    rank: int,
    final_score: float,
    role_fit_details: dict,
    skill_details: dict,
    career_details: dict,
    behavioral_details: dict,
    logistics_details: dict,
    is_honeypot: bool
) -> str:
    """
    Generate a 1-2 sentence reasoning for each candidate.
    Must reference specific facts from their profile.
    """
    if is_honeypot:
        return "Profile flagged as inconsistent: skill proficiency levels and durations are internally contradictory; likely not a genuine candidate."
    
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = candidate.get("skills", [])
    
    title = profile.get("current_title", "Unknown")
    company = profile.get("current_company", "Unknown")
    yoe = profile.get("years_of_experience", 0)
    location = profile.get("location", "Unknown")
    
    # Gather strengths
    strengths = []
    concerns = []
    
    # Title
    if role_fit_details.get("title_score", 0) >= 0.8:
        strengths.append(f"{title} at {company}")
    elif role_fit_details.get("title_score", 0) <= 0.2:
        concerns.append(f"current role ({title}) not aligned with AI/ML engineering")
    
    # Experience
    if 5 <= yoe <= 9:
        strengths.append(f"{yoe:.1f} yrs in target experience band")
    elif yoe > 12:
        concerns.append(f"potentially over-senior at {yoe:.1f} yrs")
    elif yoe < 3:
        concerns.append(f"only {yoe:.1f} yrs experience")
    
    # Skills
    must_have = skill_details.get("must_have_matches", [])
    if len(must_have) >= 3:
        top_skills = [s[0] for s in sorted(must_have, key=lambda x: -x[1])[:3]]
        strengths.append(f"{len(must_have)} must-have skills incl. {', '.join(top_skills)}")
    elif len(must_have) == 0:
        concerns.append("no must-have JD skills matched")
    
    # Career type
    product_months = role_fit_details.get("product_months", 0)
    services_months = role_fit_details.get("services_months", 0)
    if services_months > 0 and product_months == 0:
        concerns.append("entire career in services/consulting companies")
    elif product_months > services_months:
        strengths.append("strong product-company background")
    
    # Behavioral
    response_rate = signals.get("recruiter_response_rate", 0)
    days_inactive = behavioral_details.get("days_inactive", 365)
    
    if response_rate >= 0.5:
        strengths.append(f"{response_rate:.0%} recruiter response rate")
    elif response_rate < 0.15:
        concerns.append(f"very low recruiter response rate ({response_rate:.0%})")
    
    if days_inactive > 180:
        concerns.append(f"inactive for {days_inactive} days")
    
    # Location
    if logistics_details.get("location_score", 0) >= 0.7:
        strengths.append(f"based in {location}")
    elif logistics_details.get("location_score", 0) <= 0.2:
        concerns.append(f"located in {location}, not willing to relocate")
    
    # GitHub
    github = signals.get("github_activity_score", -1)
    if github >= 50:
        strengths.append(f"strong GitHub activity ({github:.0f}/100)")
    
    # Notice period
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        strengths.append("sub-30-day notice period")
    elif notice > 90:
        concerns.append(f"{notice}-day notice period")
    
    # Build reasoning
    parts = []
    if strengths:
        parts.append("; ".join(strengths[:3]))
    if concerns:
        concern_text = "; ".join(concerns[:2])
        if strengths:
            parts.append(f"concerns: {concern_text}")
        else:
            parts.append(concern_text)
    
    reasoning = ". ".join(parts)
    if not reasoning:
        reasoning = f"{title} at {company} with {yoe:.1f} yrs experience; score {final_score:.3f}."
    
    # Truncate if too long
    if len(reasoning) > 300:
        reasoning = reasoning[:297] + "..."
    
    return reasoning


# ============================================================================
# MAIN RANKING PIPELINE
# ============================================================================

def load_candidates(path: str) -> list[dict]:
    """Load candidates from JSONL (plain or gzipped)."""
    candidates = []
    file_path = Path(path)
    
    if file_path.suffix == ".gz":
        opener = gzip.open(file_path, "rt", encoding="utf-8")
    else:
        opener = open(file_path, "r", encoding="utf-8")
    
    with opener as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))
    
    return candidates


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """
    Main ranking function.
    
    For each candidate:
    1. Detect honeypots (auto-score = 0)
    2. Compute 5 dimension scores
    3. Weighted aggregate
    4. Sort descending
    5. Take top 100
    6. Generate reasoning
    """
    print(f"  Ranking {len(candidates)} candidates...")
    
    scored = []
    honeypot_count = 0
    
    for i, candidate in enumerate(candidates):
        if (i + 1) % 10000 == 0:
            print(f"    Processed {i + 1}/{len(candidates)}...")
        
        cid = candidate.get("candidate_id", "UNKNOWN")
        
        # Honeypot detection
        is_honeypot = detect_honeypot(candidate)
        if is_honeypot:
            honeypot_count += 1
            scored.append({
                "candidate_id": cid,
                "score": 0.0,
                "is_honeypot": True,
                "candidate": candidate,
                "details": {},
            })
            continue
        
        # Compute dimension scores
        role_fit_score, role_fit_details = compute_role_fit_score(candidate)
        skill_score, skill_details = compute_skill_match_score(candidate)
        career_score, career_details = compute_career_score(candidate)
        behavioral_score, behavioral_details = compute_behavioral_score(candidate)
        logistics_score, logistics_details = compute_logistics_score(candidate)
        
        # Weighted aggregate
        final_score = (
            role_fit_score * WEIGHTS["role_fit"] +
            skill_score * WEIGHTS["skill_match"] +
            career_score * WEIGHTS["career"] +
            behavioral_score * WEIGHTS["behavioral"] +
            logistics_score * WEIGHTS["logistics"]
        )
        
        scored.append({
            "candidate_id": cid,
            "score": final_score,
            "is_honeypot": False,
            "candidate": candidate,
            "role_fit_score": role_fit_score,
            "skill_score": skill_score,
            "career_score": career_score,
            "behavioral_score": behavioral_score,
            "logistics_score": logistics_score,
            "role_fit_details": role_fit_details,
            "skill_details": skill_details,
            "career_details": career_details,
            "behavioral_details": behavioral_details,
            "logistics_details": logistics_details,
        })
    
    print(f"  Detected {honeypot_count} honeypot candidates.")
    
    # Sort by score descending, break ties by candidate_id ascending
    scored.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    
    # Take top 100
    top_100 = scored[:100]
    
    # Verify no honeypots in top 100
    honeypots_in_top = sum(1 for s in top_100 if s["is_honeypot"])
    print(f"  Honeypots in top 100: {honeypots_in_top}")
    
    # If any honeypots leaked in (shouldn't happen since score=0), remove them
    if honeypots_in_top > 0:
        non_honeypot = [s for s in scored if not s["is_honeypot"]]
        top_100 = non_honeypot[:100]
    
    # Generate reasoning for top 100
    results = []
    for rank, entry in enumerate(top_100, 1):
        reasoning = generate_reasoning(
            entry["candidate"],
            rank,
            entry["score"],
            entry.get("role_fit_details", {}),
            entry.get("skill_details", {}),
            entry.get("career_details", {}),
            entry.get("behavioral_details", {}),
            entry.get("logistics_details", {}),
            entry["is_honeypot"],
        )
        
        results.append({
            "candidate_id": entry["candidate_id"],
            "rank": rank,
            "score": round(entry["score"], 6),
            "reasoning": reasoning,
        })
    
    return results


def write_submission(results: list[dict], output_path: str):
    """Write results to CSV in the required format."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for row in results:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Redrob Intelligent Candidate Ranking System"
    )
    parser.add_argument(
        "--candidates", "-c",
        required=True,
        help="Path to candidates.jsonl or candidates.jsonl.gz"
    )
    parser.add_argument(
        "--out", "-o",
        default="submission.csv",
        help="Output CSV path (default: submission.csv)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed scoring for top candidates"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Redrob Intelligent Candidate Ranking System")
    print("India Runs 2026 · Track 1 · By Aaryan Karthik")
    print("=" * 60)
    
    start_time = time.time()
    
    # Load candidates
    print(f"\n[1/3] Loading candidates from {args.candidates}...")
    candidates = load_candidates(args.candidates)
    load_time = time.time() - start_time
    print(f"  Loaded {len(candidates)} candidates in {load_time:.1f}s")
    
    # Rank
    print(f"\n[2/3] Running ranking pipeline...")
    rank_start = time.time()
    results = rank_candidates(candidates)
    rank_time = time.time() - rank_start
    print(f"  Ranking completed in {rank_time:.1f}s")
    
    # Write output
    print(f"\n[3/3] Writing submission to {args.out}...")
    write_submission(results, args.out)
    
    total_time = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Done! Total time: {total_time:.1f}s")
    print(f"Output: {args.out}")
    print(f"Top 5 candidates:")
    for r in results[:5]:
        print(f"  #{r['rank']} {r['candidate_id']} (score: {r['score']:.4f})")
        print(f"     {r['reasoning'][:100]}...")
    print(f"{'=' * 60}")
    
    if args.verbose:
        print("\n\nDETAILED TOP 10:")
        for r in results[:10]:
            print(f"\n--- Rank {r['rank']}: {r['candidate_id']} (score: {r['score']:.4f}) ---")
            print(f"    {r['reasoning']}")


if __name__ == "__main__":
    main()
