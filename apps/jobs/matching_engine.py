from .models import Job


def calculate_skills_score(candidate_skills, job_skills):
    if not job_skills:
        return 100

    candidate_skills_lower = {skill.lower() for skill in candidate_skills}
    job_skills_lower = {skill.lower() for skill in job_skills}

    print(f"When calculating -> candidate_skills_lower : {candidate_skills_lower}")
    print(f"When calculating -> job_skills_lower : {job_skills_lower}")

    matched_skills = job_skills_lower.intersection(candidate_skills_lower)
    return (len(matched_skills) / len(job_skills)) * 100

def calculate_experience_score(candidate_years, job_years):
    if not job_years:
        return 100

    if candidate_years >= job_years:
        return 100

    return (candidate_years/job_years) * 100


def generate_ats_suitability_score(candidate_profile, job):
    resume_data = candidate_profile.structured_resume_data or {}
    candidate_skills = resume_data.get('extracted_skills', [])
    metrics = resume_data.get('metrics', {})
    candidate_experience = metrics.get('years_of_experience', 0)
    print(f"candidate_skills : {candidate_skills}, candidate_experience : {candidate_experience}")

    # job_skills = job.skills if hasattr(job, 'skills') else []
    job_skills = job_skills = [
        skill.strip()
        for skill in job.skills.split(",")
        if skill.strip()
        ] if hasattr(job, 'skills') and job.skills else []
    job_experience = job.experience if hasattr(job, 'experience') else 0
    print(f"job_skills : {job_skills}, job_experience: {job_experience}")
    print("cadidate_skill_type",type(candidate_skills))
    print("job_skill_type",type(job_skills))

    skills_score = calculate_skills_score(candidate_skills, job_skills)
    experience_score = calculate_experience_score(candidate_experience, job_experience)
    print(f"skills_score : {skills_score}, experience_score : {experience_score}")

    weighted_score = (skills_score * 0.70) + (experience_score * 0.30)
    print(f"weighted_score : {weighted_score}")
    return int(round(weighted_score))