import re

SKILLS_DB = {
    "python", "django", "flask", "fastapi", "react", "angular", "vue", 
    "javascript", "typescript", "node.js", "java", "c++", "c#", "ruby", 
    "sql", "postgresql", "mysql", "mongodb", "aws", "azure", "gcp", 
    "docker", "kubernetes", "git", "linux", "machine learning", "nlp", "html", "css"
}

def extract_skills(text: str) -> list:
    text_lower = text.lower()
    extracted_skills = set()
    
    for skill in SKILLS_DB:
        escaped_skill = re.escape(skill)
        
        # (?<!\w) ensures the skill isn't preceded by a letter/number (stops "Java" from matching inside "JavaScript")
        # (?![\w+#]) ensures the skill isn't followed by a letter, number, +, or #
        pattern = r'(?<!\w)' + escaped_skill + r'(?![\w+#])'
        
        if re.search(pattern, text_lower):
            if skill in ['c++', 'c#', 'aws', 'gcp', 'sql', 'css', 'html', 'nlp']:
                extracted_skills.add(skill.upper())
            else:
                extracted_skills.add(skill.title())
            
    return list(extracted_skills)

def extract_years_of_experience(text):
    pattern = r'(\d{1,2})\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|work)?'
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    if matches:
        return max([int(m) for m in matches])
    return 0


def extract_contact_info(text: str) -> dict:
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    
    emails = re.findall(email_pattern, text)
    phones = re.findall(phone_pattern, text)
    
    return {
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None
    }

def build_resume_json_schema(cleaned_text):

    if not cleaned_text:
        return {}

    return {
        "contact_info": extract_contact_info(cleaned_text),
        "metrics": {
            "years_of_experience": extract_years_of_experience(cleaned_text),
        },
        "extracted_skills": extract_skills(cleaned_text),
    }