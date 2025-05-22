import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from collections import Counter
import spacy

# Lazy load Spacy model globally (once per cold start)
nlp = None

def get_spacy_model():
    global nlp
    if nlp is None:
        nlp = spacy.load("en_core_web_sm")
    return nlp

skill_patterns = re.compile(r"\b(java|python|kotlin|flutter|react|angular|node|swift|ruby|php|c\+\+|c#|go|docker|kubernetes|aws|azure|gcp|restful|graphql|ai|ml|dl|cv|nlp|cloud|devops|agile|ci/cd|sql|nosql|mongodb|firebase|redux|git|jira|confluence|trello|testing|tdd|bdd|scrum|microservices|big data|data science|machine learning|deep learning|nlp|cloud computing|containerization|orchestration|api|mvc|mvvm|mvp|.net|spring|django|express|flask|ios|android|dart|objective-c|cybersecurity|penetration testing|firewalls|siem|threat intelligence|data analysis|pandas|numpy|matplotlib|seaborn|scikit-learn|tensorflow|keras|pytorch)\b", re.IGNORECASE)

def clean_text(text):
    text = re.sub(r"\n|<.*?>|\t|\r", " ", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()

def extract_requirements_spacy(text):
    text = clean_text(text)
    if pd.isna(text):
        return ""
    nlp = get_spacy_model()
    doc = nlp(text)
    requirements = []
    for sent in doc.sents:
        if any(keyword in sent.text.lower() for keyword in ["requirement", "qualification", "must have", "need to", "should have", "skills", "experience", "looking for"]):
            requirements.append(sent.text)
    return ' '.join(requirements) if requirements else None

def extract_common_requirements(df):
    all_requirements = ' '.join(df['Requirements'].dropna().apply(clean_text))
    skills = skill_patterns.findall(all_requirements)
    skill_counts = Counter([skill.lower() for skill in skills])
    sorted_skills = [skill for skill, _ in skill_counts.most_common()]
    return sorted_skills

def get_skills(title, location):
    start = 0
    list_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={title}&location={location}&start={start}"
    response = requests.get(list_url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch jobs list: {response.status_code}")
    list_soup = BeautifulSoup(response.text, "html.parser")
    page_jobs = list_soup.find_all("li")
    
    id_list = []
    for job in page_jobs:
        base_card_div = job.find("div", {"class": "base-card"})
        if base_card_div and base_card_div.get("data-entity-urn"):
            job_id = base_card_div.get("data-entity-urn").split(":")[3]
            id_list.append(job_id)
    
    job_list = []
    for job_id in id_list:
        job_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        job_response = requests.get(job_url)
        if job_response.status_code != 200:
            continue
        job_soup = BeautifulSoup(job_response.text, "html.parser")
        
        job_post = {}
        try:
            job_post["job_title"] = job_soup.find("h2", {"class": "top-card-layout__title"}).text.strip()
        except:
            job_post["job_title"] = None

        try:
            job_post["company_name"] = job_soup.find("a", {"class": "topcard__org-name-link"}).text.strip()
        except:
            job_post["company_name"] = None

        try:
            job_post["Summary"] = job_soup.find("div", {"class": "description__text"}).text.strip()
        except:
            job_post["Summary"] = None

        job_list.append(job_post)

    jobs_df = pd.DataFrame(job_list)
    jobs_df['Requirements'] = jobs_df['Summary'].apply(extract_requirements_spacy)
    common_requirements = extract_common_requirements(jobs_df)
    return common_requirements

# Vercel entry point
def handler(request):
    try:
        params = request.args
        job_name = params.get("job_name", "")
        location = params.get("location", "")

        if not job_name or not location:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing job_name or location query parameters"})
            }

        skills = get_skills(job_name, location)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "job": job_name,
                "location": location,
                "skills": skills
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
